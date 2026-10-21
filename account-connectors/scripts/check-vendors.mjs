#!/usr/bin/env node
// Probe each configured vendor key in .env with the SAME call the server makes,
// before you push the keys to Cloudflare. Prints one line per vendor:
//   OK   <vendor>  what was proven
//   FAIL <vendor>  what went wrong and the likely fix
//   --   <vendor>  not configured (optional)
// Exit code: 1 if any configured vendor FAILS, else 0.
//
// Usage: node scripts/check-vendors.mjs
// Optional .env helpers (never pushed to Cloudflare, only used here):
//   CHECK_META_AD_ACCOUNT=act_<id>       probe a real ad account read
//   CHECK_GOOGLE_ADS_CUSTOMER_ID=<digits> probe a real GAQL search
//   CHECK_SHOPIFY_STORE=<subdomain>       which SHOPIFY_TOKENS entry to probe

import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const ENV_PATH = process.env.ACCOUNT_CONNECTORS_ENV || path.join(ROOT, ".env");

function loadEnv(file) {
	const out = {};
	if (!fs.existsSync(file)) return out;
	for (const line of fs.readFileSync(file, "utf8").split(/\r?\n/)) {
		const m = /^\s*([A-Z0-9_]+)\s*=\s*(.*)\s*$/.exec(line);
		if (!m) continue;
		let v = m[2];
		if ((v.startsWith('"') && v.endsWith('"')) || (v.startsWith("'") && v.endsWith("'"))) v = v.slice(1, -1);
		out[m[1]] = v;
	}
	return out;
}
const env = { ...loadEnv(ENV_PATH), ...process.env };
const META_V = "v24.0";
let failed = 0;
const ok = (n, m) => console.log(`OK   ${n.padEnd(16)} ${m}`);
const skip = (n, m) => console.log(`--   ${n.padEnd(16)} ${m}`);
const bad = (n, m) => {
	failed++;
	console.log(`FAIL ${n.padEnd(16)} ${m}`);
};
async function json(res) {
	return res.json().catch(() => null);
}

// ---- Meta reads: same Graph GET as meta_get, with the System User token ----
async function meta() {
	const t = env.META_ACCESS_TOKEN;
	if (!t) return skip("Meta (read)", "META_ACCESS_TOKEN not set (optional)");
	const dbg = await json(await fetch(`https://graph.facebook.com/${META_V}/me?fields=id,name&access_token=${encodeURIComponent(t)}`));
	if (!dbg || dbg.error) return bad("Meta (read)", `token rejected: ${dbg?.error?.message ?? "no response"}. Regenerate it from the System User panel.`);
	const acct = env.CHECK_META_AD_ACCOUNT;
	const p = acct ? `${acct.startsWith("act_") ? acct : `act_${acct}`}/campaigns?fields=id,name&limit=1` : "me/adaccounts?fields=id,name&limit=5";
	const r = await json(await fetch(`https://graph.facebook.com/${META_V}/${p}&access_token=${encodeURIComponent(t)}`));
	if (!r || r.error) {
		const code = r?.error?.code;
		const hint = code === 200 ? "the ad account is not assigned to the System User (Assign assets > Ad accounts)" : code === 10 ? "the token is missing the ads_read permission" : "see SETUP.md, Meta troubleshooting";
		return bad("Meta (read)", `${r?.error?.message ?? "no response"} -> ${hint}`);
	}
	ok("Meta (read)", acct ? `read campaigns on ${acct}` : `token sees ${r.data?.length ?? 0} ad account(s): ${(r.data ?? []).map((a) => a.id).join(", ") || "none, assign one in Business settings"}`);
}

// ---- Meta writes: app id + secret pair is valid (app access token) ----
async function metaApp() {
	const id = env.META_APP_ID;
	const sec = env.META_APP_SECRET;
	if (!id && !sec) return skip("Meta (writes)", "META_APP_ID / META_APP_SECRET not set (optional)");
	if (!id || !sec) return bad("Meta (writes)", "set BOTH META_APP_ID and META_APP_SECRET");
	const r = await json(await fetch(`https://graph.facebook.com/${META_V}/oauth/access_token?client_id=${id}&client_secret=${encodeURIComponent(sec)}&grant_type=client_credentials`));
	if (!r?.access_token) return bad("Meta (writes)", `app id/secret pair rejected: ${r?.error?.message ?? "no response"}`);
	ok("Meta (writes)", "app id + secret pair is valid (users still connect with meta_connect)");
}

// ---- Google Ads: refresh -> access token, then the same googleAds:search call ----
async function gads() {
	const need = ["GOOGLE_ADS_CLIENT_ID", "GOOGLE_ADS_CLIENT_SECRET", "GOOGLE_ADS_REFRESH_TOKEN", "GOOGLE_ADS_DEVELOPER_TOKEN"];
	const missing = need.filter((k) => !env[k]);
	if (missing.length === need.length) return skip("Google Ads", "not configured (optional)");
	if (missing.length) return bad("Google Ads", `missing: ${missing.join(", ")}`);
	const tr = await fetch("https://oauth2.googleapis.com/token", {
		method: "POST",
		headers: { "Content-Type": "application/x-www-form-urlencoded" },
		body: new URLSearchParams({
			client_id: env.GOOGLE_ADS_CLIENT_ID,
			client_secret: env.GOOGLE_ADS_CLIENT_SECRET,
			refresh_token: env.GOOGLE_ADS_REFRESH_TOKEN,
			grant_type: "refresh_token",
		}),
	});
	const tb = await json(tr);
	if (!tb?.access_token) return bad("Google Ads", `refresh token rejected (${tb?.error ?? tr.status}). Re-run: node scripts/mint-google-ads-refresh-token.mjs`);
	const headers = { Authorization: `Bearer ${tb.access_token}`, "developer-token": env.GOOGLE_ADS_DEVELOPER_TOKEN, "Content-Type": "application/json" };
	if (env.GOOGLE_ADS_LOGIN_CUSTOMER_ID) headers["login-customer-id"] = env.GOOGLE_ADS_LOGIN_CUSTOMER_ID.replace(/-/g, "");
	const cid = (env.CHECK_GOOGLE_ADS_CUSTOMER_ID ?? "").replace(/-/g, "");
	if (!cid) {
		const r = await fetch("https://googleads.googleapis.com/v24/customers:listAccessibleCustomers", { headers });
		const b = await json(r);
		if (!r.ok) return bad("Google Ads", `listAccessibleCustomers failed (${r.status}): ${JSON.stringify(b?.error?.details ?? b?.error ?? b).slice(0, 300)}`);
		return ok("Google Ads", `token + dev token work; accessible: ${(b.resourceNames ?? []).join(", ") || "none"}. Set CHECK_GOOGLE_ADS_CUSTOMER_ID to probe a real search.`);
	}
	const r = await fetch(`https://googleads.googleapis.com/v24/customers/${cid}/googleAds:search`, {
		method: "POST",
		headers,
		body: JSON.stringify({ query: "SELECT customer.id, customer.descriptive_name FROM customer LIMIT 1" }),
	});
	const b = await json(r);
	if (!r.ok) {
		const s = JSON.stringify(b ?? {});
		const hint = s.includes("DEVELOPER_TOKEN_NOT_APPROVED") ? "your developer token only has test access: apply for Basic access in the API Center" : s.includes("USER_PERMISSION_DENIED") ? "set GOOGLE_ADS_LOGIN_CUSTOMER_ID to your manager account id" : "see SETUP.md, Google Ads";
		return bad("Google Ads", `search failed (${r.status}) -> ${hint}`);
	}
	ok("Google Ads", `GAQL search worked on ${cid}`);
}

// ---- Shopify: pre-made tokens map (the OAuth install path is checked after deploy) ----
async function shopify() {
	if (!env.SHOPIFY_TOKENS && !env.SHOPIFY_CLIENT_ID) return skip("Shopify", "not configured (optional)");
	if (env.SHOPIFY_CLIENT_ID && !env.SHOPIFY_CLIENT_SECRET) return bad("Shopify", "SHOPIFY_CLIENT_ID is set but SHOPIFY_CLIENT_SECRET is not");
	if (!env.SHOPIFY_TOKENS) return ok("Shopify", "app credentials set; install it after deploy via <WORKER_BASE>/shopify/install?store=<subdomain>");
	let map;
	try {
		map = JSON.parse(env.SHOPIFY_TOKENS);
	} catch {
		return bad("Shopify", 'SHOPIFY_TOKENS is not valid JSON. Format: {"your-store": "shpat_..."}');
	}
	const store = env.CHECK_SHOPIFY_STORE || Object.keys(map)[0];
	if (!store || !map[store]) return bad("Shopify", "SHOPIFY_TOKENS has no entry to probe");
	const r = await fetch(`https://${store}.myshopify.com/admin/api/2025-07/graphql.json`, {
		method: "POST",
		headers: { "X-Shopify-Access-Token": map[store], "Content-Type": "application/json" },
		body: JSON.stringify({ query: "{ shop { name } }" }),
	});
	const b = await json(r);
	if (!r.ok || b?.errors) return bad("Shopify", `query on ${store} failed (${r.status})`);
	ok("Shopify", `read shop name on ${store}`);
}

// ---- Klaviyo: same GET as klaviyo_get ----
async function klaviyo() {
	if (!env.KLAVIYO_API_KEY) return skip("Klaviyo", "KLAVIYO_API_KEY not set (optional)");
	const r = await fetch("https://a.klaviyo.com/api/accounts", {
		headers: { Authorization: `Klaviyo-API-Key ${env.KLAVIYO_API_KEY}`, revision: "2025-07-15", accept: "application/vnd.api+json" },
	});
	if (!r.ok) return bad("Klaviyo", `GET accounts failed (${r.status}). Check the key has read access to Accounts.`);
	ok("Klaviyo", "private key can read the account");
}

console.log(`Vendor key check (reading ${ENV_PATH})\n`);
for (const f of [meta, metaApp, gads, shopify, klaviyo]) {
	try {
		await f();
	} catch (e) {
		bad(f.name, `network error: ${e.message}`);
	}
}
console.log(failed ? `\n${failed} configured vendor(s) failed. Fix them before pushing secrets.` : "\nAll configured vendors passed.");
process.exit(failed ? 1 : 0);
