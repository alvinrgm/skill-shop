// Vendor READ tools — server-held service credentials (no per-user sign-in).
// Everything in THIS file is read-only by construction: GET/search only.
// Account writes live in vendors-write.ts (Meta only) behind a different
// contract: per-user Meta OAuth + ACL + single-use approval slip.

import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { jtext, scrubTokens } from "./lib";
import { aclAllows, aclAllowsKlaviyo, aclRefusal, audit, gadsCustomerId, graphqlIsWrite, metaGraphTarget, parsedSegment, safeApiVersion, safeSegments, shopifyStore } from "./gate";
import { workerBase } from "./meta-oauth";

// Some MCP clients deliver object params as JSON strings (degraded schemas).
// Accept both: parse strings into records before use.
function coerceRecord(v: any): Record<string, any> {
	if (typeof v === "string") { try { return JSON.parse(v); } catch { return {}; } }
	return v ?? {};
}


// module-scope cache for the Google Ads access token (per isolate)
let gadsToken: { token: string; expiresAt: number } | null = null;

async function getGadsToken(env: Env): Promise<string> {
	if (gadsToken && gadsToken.expiresAt > Date.now()) return gadsToken.token;
	const res = await fetch("https://oauth2.googleapis.com/token", {
		method: "POST",
		headers: { "Content-Type": "application/x-www-form-urlencoded" },
		body: new URLSearchParams({
			client_id: env.GOOGLE_ADS_CLIENT_ID,
			client_secret: env.GOOGLE_ADS_CLIENT_SECRET,
			refresh_token: env.GOOGLE_ADS_REFRESH_TOKEN,
			grant_type: "refresh_token",
		}).toString(),
	});
	const body: any = await res.json();
	if (!res.ok || !body.access_token) throw new Error(`gads token refresh failed (${res.status})`);
	gadsToken = { token: body.access_token, expiresAt: Date.now() + (body.expires_in - 60) * 1000 };
	return gadsToken.token;
}

export function registerVendors(server: McpServer, env: Env, whoami: () => string) {
	// ---------- Meta (Marketing API, read-only) ----------
	if (env.META_ACCESS_TOKEN) {
		server.tool(
			"meta_get",
			"Read-only GET against the Meta Graph API using the server's Meta System User token. `path` is the Graph path without version prefix (e.g. 'act_<id>/insights' or 'act_<id>/campaigns'); `params` are query params (e.g. {fields:'spend,impressions', date_preset:'last_7d', level:'campaign'}). Mutations are impossible through this tool.",
			{ path: z.string(), params: z.union([z.record(z.string(), z.string()), z.string()]).optional(), api_version: z.string().default("v24.0") },
			async ({ path, params, api_version }) => {
				params = coerceRecord(params);
				const t = metaGraphTarget(env, path, api_version);
				if (!t.ok) return jtext({ refused: true, reason: t.reason });
				const acct = t.first; // the account segment of the URL actually fetched
				audit(whoami(), "meta_get", acct);
				if (!aclAllows(env, whoami(), "meta", acct)) return aclRefusal(whoami(), acct);
				const qs = new URLSearchParams({ ...(params ?? {}), access_token: env.META_ACCESS_TOKEN });
				const res = await fetch(`${t.url}?${qs}`);
				const body: any = await res.json().catch(() => null);
				return jtext(scrubTokens(res.ok ? body : { error: res.status, detail: body }));
			},
		);
	}

	// ---------- Google Ads (GAQL search, read-only) ----------
	if (env.GOOGLE_ADS_DEVELOPER_TOKEN) {
		server.tool(
			"gads_search",
			"Run a read-only GAQL query against a Google Ads account (googleAds:search). customer_id digits only, no dashes. Uses the server's stored Google Ads OAuth; no per-user sign-in. Writes are impossible through this tool.",
			{
				customer_id: z.string(),
				gaql: z.string(),
				login_customer_id: z.string().optional(),
				api_version: z.string().default("v24"),
				max_rows: z.number().int().max(10000).default(500),
			},
			async ({ customer_id, gaql, login_customer_id, api_version, max_rows }) => {
				if (!safeApiVersion(api_version, "gads")) return jtext({ refused: true, reason: `api_version '${api_version}' must look like v24` });
				const cid = gadsCustomerId(env, customer_id);
				if (!cid.ok) return jtext({ refused: true, reason: cid.reason });
				const url = `https://googleads.googleapis.com/${api_version}/customers/${cid.id}/googleAds:search`;
				const target = parsedSegment(url, 2); // ACL runs on the customer id of the URL actually fetched
				if (target !== cid.id) return jtext({ refused: true, reason: "customer_id does not resolve to a single account" });
				audit(whoami(), "gads_search", target);
				if (!aclAllows(env, whoami(), "gads", target)) return aclRefusal(whoami(), target);
				let token: string;
				try {
					token = await getGadsToken(env);
				} catch (e: any) {
					return jtext({ error: e.message });
				}
				const headers: Record<string, string> = {
					Authorization: `Bearer ${token}`,
					"developer-token": env.GOOGLE_ADS_DEVELOPER_TOKEN,
					"Content-Type": "application/json",
				};
				const lcid = (login_customer_id ?? env.GOOGLE_ADS_LOGIN_CUSTOMER_ID ?? "").replace(/-/g, "");
				if (lcid && !/^\d{10}$/.test(lcid)) return jtext({ refused: true, reason: "login_customer_id must be 10 digits (dashes optional)" });
				if (lcid) headers["login-customer-id"] = lcid;
				const res = await fetch(
					url,
					// pageSize was removed from googleAds:search in v17+ (fixed 10k pages) — never send it
					{ method: "POST", headers, body: JSON.stringify({ query: gaql }) },
				);
				const body: any = await res.json().catch(() => null);
				if (!res.ok) return jtext({ error: res.status, detail: body, hint: "if version error, retry with api_version v23/v22" });
				const rows = body.results ?? [];
				return jtext({
					results: rows.slice(0, max_rows),
					fieldMask: body.fieldMask,
					next: rows.length > max_rows || body.nextPageToken ? `truncated at ${Math.min(rows.length, max_rows)} rows — narrow with GAQL LIMIT/WHERE` : undefined,
				});
			},
		);
	}

	// ---------- Shopify (Admin GraphQL, per-store token) ----------
	if (env.SHOPIFY_TOKENS || env.SHOPIFY_CLIENT_ID) {
		server.tool(
			"shopify_query",
			"Run a read-only GraphQL QUERY against a Shopify store's Admin API. `store` is the myshopify subdomain (e.g. 'your-store' for your-store.myshopify.com) or a CLIENTS slug. Mutations are rejected.",
			{ store: z.string(), query: z.string(), variables: z.union([z.record(z.string(), z.any()), z.string()]).optional(), api_version: z.string().default("2025-07") },
			async ({ store, query, variables, api_version }) => {
				variables = coerceRecord(variables);
				if (!safeApiVersion(api_version, "shopify")) return jtext({ refused: true, reason: `api_version '${api_version}' must look like 2025-07` });
				const st = shopifyStore(env, store);
				if (!st.ok) return jtext({ refused: true, reason: st.reason });
				store = st.store;
				audit(whoami(), "shopify_query", store);
				if (!aclAllows(env, whoami(), "shopify", store)) return aclRefusal(whoami(), store);
				if (graphqlIsWrite(query)) return jtext({ refused: true, reason: "only read queries are allowed through this tool (no mutation/subscription anywhere in the document, no unterminated strings)" });
				let tok = await env.OAUTH_KV.get(`shopify_token:${store}`);
				if (!tok && env.SHOPIFY_TOKENS) {
					try {
						tok = (JSON.parse(env.SHOPIFY_TOKENS) as Record<string, string>)[store] ?? null;
					} catch {}
				}
				if (!tok)
					return jtext({
						error: `no token for store '${store}'`,
						hint: workerBase(env)
							? `install the app: open ${workerBase(env)}/shopify/install?store=${store} in a browser (a store admin approves it)`
							: "install the app: open <your server URL>/shopify/install?store=<store> in a browser (a store admin approves it)",
					});
				const shopUrl = `https://${store}.myshopify.com/admin/api/${api_version}/graphql.json`;
				if (new URL(shopUrl).hostname !== `${store}.myshopify.com`) return jtext({ refused: true, reason: "store does not resolve to a myshopify.com host" });
				const res = await fetch(shopUrl, {
					method: "POST",
					headers: { "X-Shopify-Access-Token": tok, "Content-Type": "application/json" },
					body: JSON.stringify({ query, variables }),
				});
				const body: any = await res.json().catch(() => null);
				return jtext(scrubTokens(res.ok ? body : { error: res.status, detail: body }));
			},
		);
	}

	// ---------- Klaviyo (read-only) ----------
	if (env.KLAVIYO_API_KEY) {
		server.tool(
			"klaviyo_get",
			"Read-only GET against the Klaviyo API (e.g. path 'campaigns', 'metrics', 'segments'; put filters in `params`, e.g. {filter: \"equals(messages.channel,'email')\"}). Uses the server's read-only private key; writes impossible through this tool. Needs the ACL entry \"klaviyo\" (or \"*\").",
			{ path: z.string(), params: z.union([z.record(z.string(), z.string()), z.string()]).optional(), revision: z.string().default("2025-07-15") },
			async ({ path, params, revision }) => {
				params = coerceRecord(params);
				if (!aclAllowsKlaviyo(env, whoami())) return aclRefusal(whoami(), "klaviyo");
				if (!safeApiVersion(revision, "klaviyo")) return jtext({ refused: true, reason: `revision '${revision}' must look like 2025-07-15` });
				const r = safeSegments(path);
				if (!r.ok) return jtext({ refused: true, reason: r.reason });
				const kpath = r.segs.join("/");
				const kurl = `https://a.klaviyo.com/api/${kpath}`;
				if (new URL(kurl).pathname !== `/api/${kpath}`) return jtext({ refused: true, reason: "path does not stay under /api/" });
				audit(whoami(), "klaviyo_get", kpath);
				const qs = params && Object.keys(params).length ? `?${new URLSearchParams(params)}` : "";
				const res = await fetch(`${kurl}${qs}`, {
					headers: { Authorization: `Klaviyo-API-Key ${env.KLAVIYO_API_KEY}`, revision, accept: "application/vnd.api+json" },
				});
				const body: any = await res.json().catch(() => null);
				return jtext(scrubTokens(res.ok ? body : { error: res.status, detail: body }));
			},
		);
	}
}
