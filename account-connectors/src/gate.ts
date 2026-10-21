// Approval gate + audit + access control + account registry.
//
// GATE: every write tool that can change a vendor account (Meta writes) or lose
// someone's work (sheet_clear_range, sheet_delete_tab) MUST call consumeApproval()
// before mutating anything. A slip is a per-action, single-use, expiring record
// of one human "yes" for one specific change, minted by approve_change.
//
// AUDIT: structured console.log lines -> Cloudflare Workers observability logs.
// One line per consequential tool call: who, tool, resource, when.
//
// ACCESS: who may sign in at all (ALLOWED_EMAILS / ALLOWED_DOMAINS), who is the
// admin (ADMIN_EMAIL, optional), and which vendor accounts each signed-in user may
// reach through the server-held keys (ACL).
//
// REGISTRY: the CLIENTS var (JSON) maps a short slug -> per-vendor ids, so tools
// accept "acme" instead of raw account ids. Raw ids always work too.

import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { jtext } from "./lib";
export { GOOGLE_ID_RE, googleIdProblem, googleUrlProblem } from "./lib";

export function audit(user: string, tool: string, resource: string) {
	console.log(JSON.stringify({ audit: true, user, tool, resource, ts: new Date().toISOString() }));
}

function csv(v: string | undefined): string[] {
	return (v ?? "")
		.split(",")
		.map((s) => s.trim().toLowerCase())
		.filter(Boolean);
}

// The admin is optional. With ADMIN_EMAIL unset, nobody is admin: google_api is
// unavailable and every approval slip only authorizes its own minter.
export function isAdmin(env: Env, email: string) {
	const admin = (env.ADMIN_EMAIL ?? "").trim().toLowerCase();
	return admin !== "" && email.toLowerCase() === admin;
}

// Who may complete sign-in. The server holds vendor keys, so an empty allowlist
// means NOBODY gets in (fail closed), never "everybody".
export function signInAllowed(env: Env, email: string, verified: boolean): { ok: true } | { ok: false; reason: string } {
	if (!verified) return { ok: false, reason: "your Google email address is not verified" };
	const emails = csv(env.ALLOWED_EMAILS);
	const domains = csv(env.ALLOWED_DOMAINS);
	if (!emails.length && !domains.length)
		return {
			ok: false,
			reason: "this server has no allowlist yet. The operator must set ALLOWED_EMAILS or ALLOWED_DOMAINS (wrangler secret put) before anyone can sign in.",
		};
	const e = email.toLowerCase();
	const domain = e.split("@")[1] ?? "";
	if (emails.includes(e) || domains.includes(domain)) return { ok: true };
	return { ok: false, reason: `${email} is not on this server's allowlist` };
}

// Single Google Workspace domain in the allowlist -> pass it to Google as the
// `hd` hint so the account chooser only offers that domain. A hint only; the
// real check is signInAllowed() in /callback.
export function hostedDomainHint(env: Env): string | undefined {
	const domains = csv(env.ALLOWED_DOMAINS);
	return domains.length === 1 && !csv(env.ALLOWED_EMAILS).length ? domains[0] : undefined;
}

// Per-vendor canonical ids. Each vendor is compared ONLY in its own form, so ids
// never match across vendors (a Google Ads id is not a Meta account or a store):
//   meta    "act_<digits>" exactly ("act_" required; a bare Graph node id is NOT an account)
//   gads    10 digits; dashes are the only thing stripped ("111-222-3333" == "1112223333")
//   shopify the myshopify subdomain, lowercased, compared exactly (dashes significant)
//   klaviyo the literal "klaviyo"
//   sheet   a spreadsheet/doc id, compared exactly (case and dashes significant)
export type Vendor = "meta" | "gads" | "shopify" | "klaviyo";
export type SlipKind = "meta" | "sheet";

export function canonicalId(kind: Vendor | SlipKind, id: unknown): string | null {
	const s = typeof id === "string" ? id : ""; // no trimming: stray whitespace is refused, not cleaned
	if (!s || unsafeReason(s)) return null;
	switch (kind) {
		case "meta":
			return /^act_\d{1,20}$/.test(s) ? s : null;
		case "gads": {
			const d = s.replace(/-/g, "");
			return /^\d{10}$/.test(d) && /^[\d-]+$/.test(s) ? d : null;
		}
		case "shopify": {
			const st = s.toLowerCase();
			return /^[a-z0-9][a-z0-9-]{0,62}$/.test(st) ? st : null;
		}
		case "klaviyo":
			return s.toLowerCase() === "klaviyo" ? "klaviyo" : null;
		case "sheet":
			return /^[A-Za-z0-9_-]{1,200}$/.test(s) ? s : null;
	}
	return null;
}

type Registry = Record<string, { gads?: string | null; meta?: string | null; shopify?: string | null }>;

export function registry(env: Env): Registry {
	try {
		const raw = (env as { CLIENTS?: string }).CLIENTS;
		const r = raw ? JSON.parse(raw) : {};
		return r && typeof r === "object" && !Array.isArray(r) ? r : {};
	} catch {
		return {};
	}
}

// Own-property lookup only, so "__proto__" / "constructor" never resolve.
export function registryEntry(env: Env, slug: string): Registry[string] | undefined {
	const reg = registry(env);
	const k = String(slug ?? "").toLowerCase();
	// a slug spelled like an account id ("act_222", "1112223333") is ignored, so an
	// id always means itself and never silently aliases another account
	if (/^act_\d+$/.test(k) || /^[\d-]+$/.test(k)) return undefined;
	const hit = Object.prototype.hasOwnProperty.call(reg, k) ? reg[k] : undefined;
	return hit && typeof hit === "object" ? hit : undefined;
}

// Resolve a client slug to the vendor-specific id; pass raw ids through untouched.
export function resolveClient(env: Env, idOrSlug: string, kind: "gads" | "meta" | "shopify"): string {
	const v = registryEntry(env, idOrSlug)?.[kind];
	return typeof v === "string" && v ? v : idOrSlug;
}

// ---------- Input hardening for ids and paths that end up in vendor URLs ----------
// The ACL is checked against an id or a path's first segment, but fetch() and URL
// parsing normalise `..`, `%2e%2e`, backslashes and `?`/`#` AFTER the check, so
// `act_111/../act_222/insights` would pass an ACL for act_111 and then read
// act_222. Everything below rejects such input outright (never "cleans" it), and
// the vendor tools additionally re-check the ACL against the pathname of the URL
// actually fetched (parsedSegment).

export function unsafeReason(s: unknown): string | null {
	if (typeof s !== "string" || s.length === 0) return "empty";
	if (s.includes("..")) return "contains '..'";
	if (s.includes("%")) return "contains percent-encoding (e.g. %2e, %2f); pass plain ids";
	if (/[?#]/.test(s)) return "contains '?' or '#' (put query parameters in `params`)";
	if (s.includes("\\")) return "contains a backslash";
	if (/[^\x21-\x7e]/.test(s)) return "contains whitespace, control or non-ASCII characters";
	return null;
}

const SEGMENT_RE = /^[A-Za-z0-9_.:,-]+$/;

// Validate a relative API path ("act_123/insights", "campaigns/abc"). Returns the
// segments or a reason. No empty, "." or ".." segments, no encoding tricks.
export function safeSegments(path: string): { ok: true; segs: string[] } | { ok: false; reason: string } {
	const why = unsafeReason(path);
	if (why) return { ok: false, reason: `path ${why}` };
	const segs = path.split("/");
	for (const seg of segs) {
		if (seg === "" || seg === ".") return { ok: false, reason: "path has an empty or '.' segment (no leading, trailing or double slashes)" };
		if (!SEGMENT_RE.test(seg)) return { ok: false, reason: `path segment '${seg}' has characters outside [A-Za-z0-9_.:,-]` };
	}
	return { ok: true, segs };
}

// The segment at `index` of the pathname the URL ACTUALLY resolves to (after
// the WHATWG parser normalises it), so the ACL runs on what fetch() will request.
export function parsedSegment(url: string, index: number): string | null {
	try {
		return new URL(url).pathname.split("/")[index + 1] ?? null;
	} catch {
		return null;
	}
}

export function safeApiVersion(v: string, kind: "meta" | "gads" | "shopify" | "klaviyo"): boolean {
	const re = { meta: /^v\d{1,3}\.\d{1,2}$/, gads: /^v\d{1,3}$/, shopify: /^(\d{4}-\d{2}|unstable)$/, klaviyo: /^\d{4}-\d{2}-\d{2}(\.pre)?$/ }[kind];
	return re.test(v);
}

// Meta Graph path: validate, resolve a CLIENTS slug in the first segment, return
// the full URL plus the account segment the parsed URL really targets.
export function metaGraphTarget(
	env: Env,
	path: string,
	apiVersion: string,
): { ok: true; first: string; path: string; url: string } | { ok: false; reason: string } {
	if (!safeApiVersion(apiVersion, "meta")) return { ok: false, reason: `api_version '${apiVersion}' must look like v24.0` };
	const r = safeSegments(path);
	if (!r.ok) return r;
	const segs = [...r.segs];
	segs[0] = resolveClient(env, segs[0], "meta");
	const again = safeSegments(segs.join("/"));
	if (!again.ok) return { ok: false, reason: `resolved ${again.reason}` };
	const joined = again.segs.join("/");
	const url = `https://graph.facebook.com/${apiVersion}/${joined}`;
	const first = parsedSegment(url, 1);
	if (!first || first !== again.segs[0] || new URL(url).pathname !== `/${apiVersion}/${joined}`)
		return { ok: false, reason: "path does not resolve to the account it names" };
	return { ok: true, first, path: joined, url };
}

// Google Ads customer id: CLIENTS slug or id, dashes allowed, must be 10 digits.
export function gadsCustomerId(env: Env, idOrSlug: string): { ok: true; id: string } | { ok: false; reason: string } {
	const why = unsafeReason(idOrSlug);
	if (why) return { ok: false, reason: `customer_id ${why}` };
	const id = canonicalId("gads", resolveClient(env, idOrSlug, "gads"));
	if (!id) return { ok: false, reason: `customer_id must be 10 digits (dashes optional) or a CLIENTS slug; got '${idOrSlug}'` };
	return { ok: true, id };
}

// Shopify store: CLIENTS slug or myshopify subdomain (".myshopify.com" suffix tolerated).
export function shopifyStore(env: Env, storeOrSlug: string): { ok: true; store: string } | { ok: false; reason: string } {
	const why = unsafeReason(storeOrSlug);
	if (why) return { ok: false, reason: `store ${why}` };
	const store = canonicalId("shopify", String(resolveClient(env, storeOrSlug, "shopify") ?? "").toLowerCase().replace(/\.myshopify\.com$/, ""));
	if (!store) return { ok: false, reason: `store must be a myshopify subdomain (letters, digits, dashes); got '${storeOrSlug}'` };
	return { ok: true, store };
}

// Shopify: is this GraphQL document anything but a read? Strips string literals,
// block strings and comments first, then refuses any `mutation` / `subscription`
// keyword anywhere (a document may hold several operations and fragments, so
// "starts with mutation" is not enough). The real wall is still the app token's
// read-only scopes; this check just refuses early and clearly.
// Returns the document with comments and string literals removed, or null if a
// string or block string is unterminated (refused: it could hide a keyword).
export function graphqlStripped(query: string): string | null {
	const q = String(query ?? "");
	let out = "";
	for (let i = 0; i < q.length; ) {
		const c = q[i];
		if (c === "#") {
			while (i < q.length && q[i] !== "\n" && q[i] !== "\r") i++;
			out += " ";
		} else if (q.startsWith('"""', i)) {
			// block string: \""" is an escaped triple quote, NOT the end
			let j = i + 3;
			for (;;) {
				if (j >= q.length) return null;
				if (q.startsWith('\\"""', j)) j += 4;
				else if (q.startsWith('"""', j)) break;
				else j++;
			}
			i = j + 3;
			out += " ";
		} else if (c === '"') {
			i++;
			while (i < q.length && q[i] !== '"') {
				if (q[i] === "\n" || q[i] === "\r") return null;
				i += q[i] === "\\" ? 2 : 1;
			}
			if (i >= q.length) return null;
			i++;
			out += " ";
		} else {
			out += c;
			i++;
		}
	}
	return out;
}

export function graphqlIsWrite(query: string): boolean {
	const s = graphqlStripped(query);
	return s === null || /\b(mutation|subscription)\b/i.test(s);
}

// google_api (admin-only): each api may reach only its own path prefixes, so the
// "drive" host (www.googleapis.com) cannot be used for /gmail or /calendar.
const GOOGLE_API: Record<string, { host: string; bases: string[] }> = {
	docs: { host: "docs.googleapis.com", bases: ["/v1/documents"] },
	sheets: { host: "sheets.googleapis.com", bases: ["/v4/spreadsheets"] },
	slides: { host: "slides.googleapis.com", bases: ["/v1/presentations"] },
	drive: { host: "www.googleapis.com", bases: ["/drive/v3", "/upload/drive/v3"] },
};

const underBase = (p: string, bases: string[]) => bases.some((b) => p === b || p.startsWith(`${b}/`));

export function googleApiTarget(api: string, path: string): { ok: true; url: string } | { ok: false; reason: string } {
	const spec = Object.prototype.hasOwnProperty.call(GOOGLE_API, api) ? GOOGLE_API[api] : undefined;
	if (!spec) return { ok: false, reason: `unknown api '${api}'` };
	const raw = String(path ?? "");
	const qi = raw.indexOf("?");
	const p = qi === -1 ? raw : raw.slice(0, qi);
	const q = qi === -1 ? "" : raw.slice(qi + 1);
	if (p.includes("..") || p.includes("\\") || p.includes("#") || /[^\x21-\x7e]/.test(p))
		return { ok: false, reason: "path may not contain '..', backslashes, '#', whitespace or non-ASCII" };
	if (/%(2e|2f|5c|25|3f|23)/i.test(p)) return { ok: false, reason: "path may not percent-encode '.', '/', '\\', '%', '?' or '#'" };
	if (q.includes("#") || /[^\x21-\x7e]/.test(q)) return { ok: false, reason: "query may not contain '#', whitespace or non-ASCII" };
	if (!underBase(p, spec.bases)) return { ok: false, reason: `${api} paths must start with ${spec.bases.join(" or ")}` };
	const url = `https://${spec.host}${p}${q ? `?${q}` : ""}`;
	let u: URL;
	try {
		u = new URL(url);
	} catch {
		return { ok: false, reason: "not a valid URL" };
	}
	if (u.hostname !== spec.host || !underBase(u.pathname, spec.bases))
		return { ok: false, reason: "path does not stay under the api's prefix after URL parsing" };
	return { ok: true, url };
}

// ---------- ACL ----------
// Per-user authorization over the server-held vendor keys. ACL (JSON var) maps a
// caller email -> allowed resource ids (Meta act_ ids, Google Ads customer ids,
// Shopify store subdomains, client slugs from CLIENTS, or "klaviyo"). "*" as an
// id means everything; the "*" email key is the default for users not listed.
// Matching is EXACT after normalization (no prefix/substring matches).
//
// DEFAULT (ACL unset, blank or {}): ADMIN-ONLY. Only ADMIN_EMAIL may use the
// vendor tools; everyone else is refused. With no ADMIN_EMAIL either, nobody is.
export type AclMode = "configured" | "admin-only" | "invalid";

function aclRaw(env: Env): string {
	return String((env as { ACL?: string }).ACL ?? "").trim();
}

// Parsed ACL with lowercased email keys (own properties only), or null if invalid.
function aclParsed(env: Env): Record<string, string[]> | null {
	try {
		const acl = JSON.parse(aclRaw(env));
		if (!acl || typeof acl !== "object" || Array.isArray(acl)) return null;
		const out: Record<string, string[]> = Object.create(null);
		for (const [k, v] of Object.entries(acl)) {
			if (!Array.isArray(v)) return null;
			out[k.trim().toLowerCase()] = v.map((x) => String(x));
		}
		return out;
	} catch {
		return null;
	}
}

export function aclMode(env: Env): AclMode {
	if (!aclRaw(env)) return "admin-only";
	const acl = aclParsed(env);
	if (!acl) return "invalid";
	return Object.keys(acl).length ? "configured" : "admin-only";
}

// The caller's ACL entry list ([] = nothing).
export function aclList(env: Env, email: string): string[] {
	const mode = aclMode(env);
	if (mode === "invalid") return []; // a malformed ACL fails closed
	if (mode === "admin-only") return isAdmin(env, email) ? ["*"] : [];
	const acl = aclParsed(env)!;
	const e = String(email ?? "").trim().toLowerCase();
	return acl[e] ?? acl["*"] ?? [];
}

// Each raw ACL entry belongs to exactly ONE vendor, so nothing matches across
// vendors: "act_<digits>" is Meta, a 10-digit id (dashes optional) is Google Ads,
// "klaviyo" is Klaviyo, any other subdomain-shaped entry is a Shopify store. An
// explicit "shopify:<store>" / "gads:<id>" / "meta:act_<id>" prefix also works
// (e.g. for a store whose subdomain is all digits). A CLIENTS slug grants only its
// id for the vendor being called.
export function classifyEntry(entry: string): { kind: Vendor; id: string } | null {
	const m = /^(meta|gads|shopify|klaviyo):(.*)$/i.exec(entry);
	if (m) {
		const kind = m[1].toLowerCase() as Vendor;
		const id = canonicalId(kind, m[2]);
		return id ? { kind, id } : null;
	}
	for (const kind of ["meta", "gads", "klaviyo", "shopify"] as const) {
		const id = canonicalId(kind, entry);
		if (id) return { kind, id };
	}
	return null;
}

function entryIds(env: Env, entry: string, kind: Vendor): string[] {
	const slug = kind === "klaviyo" ? undefined : registryEntry(env, entry);
	if (slug) {
		const c = canonicalId(kind, slug[kind as "meta" | "gads" | "shopify"]);
		return c ? [c] : [];
	}
	const c = classifyEntry(entry);
	return c && c.kind === kind ? [c.id] : [];
}

export function aclAllows(env: Env, email: string, kind: Vendor, resourceId: string): boolean {
	const want = canonicalId(kind, resourceId);
	const list = aclList(env, email);
	// "*" = everything the server keys can see. For Meta that includes bare Graph
	// node ids (an ad, a creative), but still only well-formed ones.
	if (list.includes("*")) return want !== null || (kind === "meta" && !unsafeReason(resourceId) && /^[A-Za-z0-9_]{1,64}$/.test(resourceId));
	if (!want) return false;
	return list.some((entry) => entryIds(env, entry, kind).includes(want));
}

// Klaviyo has one server key and no account id: gate it on the literal ACL entry
// "klaviyo" (or "*").
export function aclAllowsKlaviyo(env: Env, email: string): boolean {
	return aclAllows(env, email, "klaviyo", "klaviyo");
}

// The registry filtered to what this caller may reach: a slug is listed only
// with the per-vendor ids the ACL allows them, and dropped if none are allowed.
export function visibleClients(env: Env, email: string): Registry {
	const out: Registry = {};
	for (const [slug, ids] of Object.entries(registry(env))) {
		const keep: Registry[string] = {};
		for (const k of ["gads", "meta", "shopify"] as const) {
			const v = ids?.[k];
			if (typeof v === "string" && canonicalId(k, v) && aclAllows(env, email, k, v)) keep[k] = v;
		}
		if (Object.keys(keep).length) out[slug] = keep;
	}
	return out;
}

export function aclSummary(env: Env, email: string): string {
	const mode = aclMode(env);
	if (mode === "invalid") return "ACL var is not valid JSON (an object of email -> list): every vendor tool is refused for everyone (fails closed)";
	if (mode === "admin-only")
		return (env.ADMIN_EMAIL ?? "").trim()
			? `ACL is not set: admin-only. Only ADMIN_EMAIL may use vendor tools; you are ${isAdmin(env, email) ? "the admin (allowed)" : "not the admin (refused)"}. Set the ACL var to grant others (SETUP.md, ACL).`
			: "ACL is not set and ADMIN_EMAIL is empty: nobody may use vendor tools. Set ADMIN_EMAIL or the ACL var (SETUP.md, ACL).";
	const list = aclList(env, email);
	return list.includes("*") ? "ACL configured: you may reach every account" : `ACL configured: you may reach ${list.length ? list.join(", ") : "no accounts"}`;
}

export function aclRefusal(email: string, resource: string) {
	return jtext({
		refused: true,
		reason: `${email} is not authorized for ${resource} (server ACL)`,
		ask: "the server operator can grant access by editing the ACL var and redeploying",
	});
}

// Single-use approval consumption, the check every gated write runs.
// The slip must have been minted by the SAME person now executing (their own
// per-action confirmation), except slips minted by the ADMIN, which are valid
// for anyone (delegation path) unless the admin bound them to one person with
// for_email. The slip's resource must equal the target, compared in the target's
// own form: a Meta slip names act_<id> exactly (or a CLIENTS slug, meaning its
// Meta id); a sheet slip names the spreadsheet id exactly.
//
// Single use is BEST-EFFORT: Workers KV has no compare-and-delete, so the slip is
// read, checked and deleted, and two redemptions racing in the same instant could
// both pass. The blast radius stays one already-approved change on one account by
// one person, and slips expire quickly (default 1 hour, max 24).
export function slipTarget(env: Env, kind: SlipKind, resource: string): string | null {
	if (kind === "sheet") return canonicalId("sheet", resource);
	const r = String(resource ?? "").trim();
	const viaSlug = registryEntry(env, r)?.meta;
	const v = typeof viaSlug === "string" && viaSlug ? viaSlug : r;
	return canonicalId("meta", v); // act_<digits> exactly: bare digits could be any vendor's id
}

export async function consumeApproval(
	env: Env,
	approvalId: string,
	kind: SlipKind,
	resource: string,
	callerEmail: string,
): Promise<{ ok: true; description: string } | { ok: false; reason: string }> {
	if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(String(approvalId ?? "")))
		return { ok: false, reason: "approval_id must be the full id returned by approve_change" };
	const key = `approval:${approvalId}`;
	const raw = await env.OAUTH_KV.get(key);
	if (!raw) return { ok: false, reason: "no such approval (wrong id, already used, or expired)" };
	const a = JSON.parse(raw);
	const want = slipTarget(env, kind, resource);
	const have = slipTarget(env, kind, String(a.resource ?? ""));
	if (!want || !have || want !== have)
		return { ok: false, reason: `approval is for '${a.resource}', not '${resource}'` };
	const caller = String(callerEmail ?? "").toLowerCase();
	if (a.for && String(a.for).toLowerCase() !== caller)
		return { ok: false, reason: `approval was minted for ${a.for}; only they can redeem it` };
	if (String(a.by).toLowerCase() !== caller && !isAdmin(env, a.by))
		return { ok: false, reason: `approval was minted by ${a.by}; only they (or an admin slip) can authorize this write` };
	await env.OAUTH_KV.delete(key); // single-use (best-effort, see above): burn before acting
	return { ok: true, description: a.description };
}

export function registerGate(server: McpServer, env: Env, whoami: () => string) {
	server.tool(
		"approve_change",
		"Record a single-use approval slip for ONE specific change: the per-action human confirmation gate. PROTOCOL (mandatory): before calling this, RESTATE the exact change to your human (account, entity, what changes, to what value) and get their explicit yes IN CHAT. This tool records that confirmation; it does not replace it. `resource` must be exactly the target: the ad account (act_<id>) for Meta writes, or the spreadsheet id for sheet_clear_range / sheet_delete_tab. The slip only authorizes writes by the same signed-in person who minted it. The admin may set `for_email` to mint a slip for one other person; an admin slip without for_email works for anyone. Returns the approval_id the gated tool must present; single-use, expires after ttl_hours (default 1).",
		{
			description: z.string().min(1),
			resource: z.string().min(1),
			ttl_hours: z.number().min(1).max(24).default(1),
			for_email: z.string().optional().describe("admin only: the one person who may redeem this slip"),
		},
		async ({ description, resource, ttl_hours, for_email }) => {
			const who = whoami();
			const forEmail = (for_email ?? "").trim().toLowerCase();
			if (forEmail && !isAdmin(env, who))
				return jtext({ refused: true, reason: "for_email is admin-only; your slips always authorize only you" });
			const id = crypto.randomUUID(); // full 122-bit id: not guessable
			await env.OAUTH_KV.put(
				`approval:${id}`,
				JSON.stringify({ description, resource, by: who, ...(forEmail ? { for: forEmail } : {}), at: new Date().toISOString() }),
				{ expirationTtl: ttl_hours * 3600 },
			);
			audit(who, "approve_change", `${resource} :: ${description.slice(0, 120)}`);
			return jtext({ approval_id: id, resource, ...(forEmail ? { for_email: forEmail } : {}), expires_in_hours: ttl_hours, single_use: true });
		},
	);

	server.tool(
		"list_approvals",
		"List currently outstanding (unused, unexpired) approval slips: your own; the admin sees everyone's.",
		{},
		async () => {
			const who = whoami();
			const list = await env.OAUTH_KV.list({ prefix: "approval:" });
			const out: any[] = [];
			for (const k of list.keys) {
				const raw = await env.OAUTH_KV.get(k.name);
				if (!raw) continue;
				const a = JSON.parse(raw);
				if (isAdmin(env, who) || a.by === who || a.for === who.toLowerCase()) out.push({ approval_id: k.name.slice(9), ...a });
			}
			return jtext({ outstanding: out });
		},
	);

	server.tool(
		"clients",
		"List the account registry entries YOU may reach: slug -> per-vendor account ids (from the CLIENTS var, filtered by the server ACL). Tools accept these slugs anywhere they accept a raw id.",
		{},
		async () => jtext({ clients: visibleClients(env, whoami()), access: aclSummary(env, whoami()) }),
	);
}
