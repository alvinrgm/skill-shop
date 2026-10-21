// Handler-level tests: register the real vendor / Meta-write / google_api tools on a
// fake MCP server, mock fetch, and prove each handler checks the ACL against the
// target it ACTUALLY requests (and refuses before any request otherwise).
// Run: npm test
import { registerVendors } from "../.wrangler/test/vendors.mjs";
import { registerMetaWrites } from "../.wrangler/test/vendors-write.mjs";
import { registerGsuite } from "../.wrangler/test/gsuite.mjs";
import { registerGsuiteParity } from "../.wrangler/test/gsuite-parity.mjs";
import { addMetaRoutes } from "../.wrangler/test/meta-oauth.mjs";
import { Hono } from "hono";
import assert from "node:assert/strict";

let passed = 0;
const t = async (name, fn) => {
	try {
		await fn();
		passed++;
	} catch (e) {
		console.error(`FAIL: ${name}`);
		throw e;
	}
};

// ---------- harness ----------
let calls = [];
globalThis.fetch = async (input, init = {}) => {
	const url = String(input instanceof Request ? input.url : input);
	calls.push({ url, method: init.method ?? "GET" });
	if (url.startsWith("https://oauth2.googleapis.com/token")) return Response.json({ access_token: "gads-access", expires_in: 3600 });
	return Response.json({ data: [], results: [] });
};
const origLog = console.log;
console.log = () => {}; // silence audit lines during the run

const kv = new Map();
const KV = { get: async (k) => kv.get(k) ?? null, put: async (k, v) => kv.set(k, v), delete: async (k) => kv.delete(k), list: async () => ({ keys: [] }) };
const env = {
	OAUTH_KV: KV,
	ALLOWED_EMAILS: "a@x.com,n@x.com,k@x.com,gone@x.com,admin@x.com",
	ALLOWED_DOMAINS: "",
	ADMIN_EMAIL: "admin@x.com",
	CLIENTS: JSON.stringify({
		acme: { meta: "act_111", gads: "111-222-3333", shopify: "acme-store" },
		other: { meta: "act_222", gads: "9998887777", shopify: "acmestore" },
	}),
	ACL: JSON.stringify({ "a@x.com": ["acme"], "n@x.com": ["1112223333"], "k@x.com": ["klaviyo"], "gone@x.com": ["acme"] }),
	META_ACCESS_TOKEN: "server-meta-token",
	META_APP_ID: "app",
	META_APP_SECRET: "secret",
	GOOGLE_ADS_DEVELOPER_TOKEN: "dev",
	GOOGLE_ADS_CLIENT_ID: "cid",
	GOOGLE_ADS_CLIENT_SECRET: "csec",
	GOOGLE_ADS_REFRESH_TOKEN: "rt",
	SHOPIFY_TOKENS: JSON.stringify({ "acme-store": "shpat_test", acmestore: "shpat_other" }),
	KLAVIYO_API_KEY: "pk_test",
	WORKER_BASE: "https://worker.example",
};

let who = "a@x.com";
const tools = {};
const server = { tool: (name, _desc, _schema, handler) => (tools[name] = handler) };
registerVendors(server, env, () => who);
registerMetaWrites(server, env, () => who);
registerGsuite(server, async () => "google-token", () => who, env);

const run = async (name, args, as = "a@x.com") => {
	who = as;
	calls = [];
	const r = await tools[name](args);
	return JSON.parse(r.content[0].text);
};
const fetched = (host) => calls.filter((c) => c.url.includes(host));
const graph = () => fetched("graph.facebook.com/");
const refused = (out) => out.refused === true || typeof out.error === "string";

// ---------- meta_get ----------
await t("meta_get: own account fetched, at exactly that account", async () => {
	await run("meta_get", { path: "act_111/insights", params: {}, api_version: "v24.0" });
	assert.equal(graph().length, 1);
	assert.equal(new URL(graph()[0].url).pathname, "/v24.0/act_111/insights");
});
await t("meta_get: slug resolves and is fetched as its account", async () => {
	await run("meta_get", { path: "acme/campaigns", params: {}, api_version: "v24.0" });
	assert.equal(new URL(graph()[0].url).pathname, "/v24.0/act_111/campaigns");
});
for (const path of ["act_111/../act_222/insights", "act_111/%2e%2e/act_222", "act_111/%2E%2E/act_222/insights", "act_111\\..\\act_222", "act_111?x=/../act_222"]) {
	await t(`meta_get: traversal refused with no request: ${path}`, async () => {
		const out = await run("meta_get", { path, params: {}, api_version: "v24.0" });
		assert.ok(refused(out));
		assert.equal(calls.length, 0);
	});
}
await t("meta_get: other account refused with no request", async () => {
	const out = await run("meta_get", { path: "act_222/insights", params: {}, api_version: "v24.0" });
	assert.equal(out.refused, true);
	assert.equal(calls.length, 0);
});
await t("meta_get: gads grant does not reach Meta act_<same digits>", async () => {
	const out = await run("meta_get", { path: "act_1112223333/insights", params: {}, api_version: "v24.0" }, "n@x.com");
	assert.equal(out.refused, true);
	assert.equal(calls.length, 0);
});
await t("meta_get: bare Graph node not allowed by an account grant", async () => {
	const out = await run("meta_get", { path: "111", params: {}, api_version: "v24.0" });
	assert.equal(out.refused, true);
	assert.equal(calls.length, 0);
});
await t("meta_get: server token never echoed", async () => {
	globalThis.fetch = async (u) => (calls.push({ url: String(u) }), Response.json({ paging: { next: `${u}&access_token=server-meta-token` } }));
	const out = await run("meta_get", { path: "act_111/ads", params: {}, api_version: "v24.0" });
	assert.ok(!JSON.stringify(out).includes("server-meta-token"));
});
// restore default fetch mock
globalThis.fetch = async (input, init = {}) => {
	const url = String(input);
	calls.push({ url, method: init.method ?? "GET" });
	if (url.startsWith("https://oauth2.googleapis.com/token")) return Response.json({ access_token: "gads-access", expires_in: 3600 });
	return Response.json({ data: [], results: [] });
};

// ---------- gads_search ----------
for (const cid of ["111-222-3333", "1112223333", "acme"]) {
	await t(`gads_search: ${cid} fetches customers/1112223333`, async () => {
		await run("gads_search", { customer_id: cid, gaql: "SELECT campaign.id FROM campaign", api_version: "v24", max_rows: 10 });
		const g = fetched("googleads.googleapis.com");
		assert.equal(g.length, 1);
		assert.equal(new URL(g[0].url).pathname, "/v24/customers/1112223333/googleAds:search");
	});
}
for (const cid of ["9998887777", "1112223333/../9998887777", "1112223333%2f..%2f9998887777", "111222333"]) {
	await t(`gads_search: refused with no Ads request: ${cid}`, async () => {
		const out = await run("gads_search", { customer_id: cid, gaql: "SELECT campaign.id FROM campaign", api_version: "v24", max_rows: 10 });
		assert.ok(refused(out));
		assert.equal(fetched("googleads.googleapis.com").length, 0);
	});
}
await t("gads_search: api_version traversal refused", async () => {
	const out = await run("gads_search", { customer_id: "1112223333", gaql: "x", api_version: "v24/customers/9998887777/googleAds:search?", max_rows: 10 });
	assert.equal(out.refused, true);
	assert.equal(fetched("googleads.googleapis.com").length, 0);
});

// ---------- shopify_query ----------
await t("shopify_query: own store fetched on its own host", async () => {
	await run("shopify_query", { store: "acme-store", query: "{ shop { name } }", variables: {}, api_version: "2025-07" });
	assert.equal(calls.length, 1);
	assert.equal(new URL(calls[0].url).hostname, "acme-store.myshopify.com");
});
for (const store of ["acmestore", "other", "evil.com/x?", "acme-store.myshopify.com.evil"]) {
	await t(`shopify_query: refused with no request: ${store}`, async () => {
		const out = await run("shopify_query", { store, query: "{ shop { name } }", variables: {}, api_version: "2025-07" });
		assert.ok(refused(out));
		assert.equal(calls.length, 0);
	});
}
for (const query of ["fragment F on Shop { name } mutation M { shopUpdate { x } }", "query Q { shop { name } } mutation M { x }"]) {
	await t(`shopify_query: mutation bypass refused: ${query}`, async () => {
		const out = await run("shopify_query", { store: "acme-store", query, variables: {}, api_version: "2025-07" });
		assert.equal(out.refused, true);
		assert.equal(calls.length, 0);
	});
}

// ---------- klaviyo_get ----------
await t("klaviyo_get: 'klaviyo' entry allowed, under /api/", async () => {
	await run("klaviyo_get", { path: "campaigns", params: {}, revision: "2025-07-15" }, "k@x.com");
	assert.equal(new URL(calls[0].url).pathname, "/api/campaigns");
});
await t("klaviyo_get: account-only user refused", async () => {
	const out = await run("klaviyo_get", { path: "campaigns", params: {}, revision: "2025-07-15" }, "a@x.com");
	assert.equal(out.refused, true);
	assert.equal(calls.length, 0);
});
await t("klaviyo_get: traversal refused", async () => {
	const out = await run("klaviyo_get", { path: "../accounts", params: {}, revision: "2025-07-15" }, "k@x.com");
	assert.equal(out.refused, true);
	assert.equal(calls.length, 0);
});

// ---------- Meta writes ----------
kv.set("meta_user_token:a@x.com", JSON.stringify({ token: "user-meta-token", fb_name: "A", fb_id: "1" }));
kv.set("meta_user_token:n@x.com", JSON.stringify({ token: "user-meta-token-n", fb_name: "N", fb_id: "2" }));
kv.set("meta_user_token:gone@x.com", JSON.stringify({ token: "user-meta-token-g", fb_name: "G", fb_id: "3" }));
const slip = (resource, by = "a@x.com") => {
	const id = crypto.randomUUID();
	kv.set(`approval:${id}`, JSON.stringify({ resource, by, description: "test change" }));
	return id;
};
await t("meta_mutate: approved write posts to exactly that account", async () => {
	const id = slip("act_111");
	await run("meta_mutate", { path: "act_111/ads", params: { status: "PAUSED" }, approval_id: id });
	const posts = graph().filter((c) => c.method === "POST");
	assert.equal(posts.length, 1);
	assert.equal(new URL(posts[0].url).pathname, "/v24.0/act_111/ads");
	assert.equal(kv.has(`approval:${id}`), false); // slip consumed
});
for (const path of ["act_111/../act_222/ads", "act_111/%2e%2e/act_222/ads", "act_111\\..\\act_222"]) {
	await t(`meta_mutate: traversal refused, slip NOT consumed: ${path}`, async () => {
		const id = slip("act_111");
		const out = await run("meta_mutate", { path, params: { status: "PAUSED" }, approval_id: id });
		assert.equal(out.refused, true);
		assert.equal(calls.length, 0);
		assert.equal(kv.has(`approval:${id}`), true);
	});
}
await t("meta_mutate: other account refused by ACL before the slip", async () => {
	const id = slip("act_222");
	const out = await run("meta_mutate", { path: "act_222/ads", params: {}, approval_id: id });
	assert.equal(out.refused, true);
	assert.equal(graph().filter((c) => c.method === "POST").length, 0);
	assert.equal(kv.has(`approval:${id}`), true);
});
await t("meta_mutate: slip for act_1-11 does not authorize act_111", async () => {
	const id = slip("act_1-11");
	const out = await run("meta_mutate", { path: "act_111/ads", params: {}, approval_id: id });
	assert.equal(out.refused, true);
	assert.equal(graph().filter((c) => c.method === "POST").length, 0);
});
await t("meta_mutate: gads grant cannot write Meta act_<same digits>", async () => {
	const id = slip("act_1112223333", "n@x.com");
	const out = await run("meta_mutate", { path: "act_1112223333/ads", params: {}, approval_id: id }, "n@x.com");
	assert.equal(out.refused, true);
	assert.equal(graph().filter((c) => c.method === "POST").length, 0);
});
await t("meta_mutate: removed from allowlist mid-session -> refused", async () => {
	const id = slip("act_111", "gone@x.com");
	const env2 = { ...env, ALLOWED_EMAILS: "a@x.com" };
	const t2 = {};
	registerMetaWrites({ tool: (n, _d, _s, h) => (t2[n] = h) }, env2, () => "gone@x.com");
	calls = [];
	const out = JSON.parse((await t2.meta_mutate({ path: "act_111/ads", params: {}, approval_id: id })).content[0].text);
	assert.equal(out.status, "access_revoked");
	assert.equal(calls.length, 0);
});
await t("meta_mutate: user token never echoed", async () => {
	globalThis.fetch = async (u, init = {}) => (calls.push({ url: String(u), method: init.method ?? "GET" }), Response.json({ id: "1", next: "https://graph.facebook.com/x?access_token=user-meta-token" }));
	const id = slip("act_111");
	const out = await run("meta_mutate", { path: "act_111/ads", params: {}, approval_id: id });
	assert.ok(!JSON.stringify(out).includes("user-meta-token"));
});
await t("meta_delete: traversal refused", async () => {
	const id = slip("act_111");
	const out = await run("meta_delete", { object_id: "act_111/../act_222", params: {}, approval_id: id });
	assert.equal(out.refused, true);
	assert.equal(calls.length, 0);
});

// ---------- google_api (admin-only) ----------
globalThis.fetch = async (u, init = {}) => (calls.push({ url: String(u), method: init.method ?? "GET" }), new Response("{}", { status: 200 }));
await t("google_api: non-admin refused", async () => {
	const out = await run("google_api", { api: "drive", path: "/drive/v3/files", method: "GET" }, "a@x.com");
	assert.equal(out.refused, true);
	assert.equal(calls.length, 0);
});
for (const path of ["/gmail/v1/users/me/messages", "/calendar/v3/calendars/primary/events", "/drive/v3/../../gmail/v1/users/me/messages", "/drive/v3/%2e%2e/%2e%2e/gmail/v1/users/me/messages"]) {
	await t(`google_api: drive host cannot reach ${path}`, async () => {
		const out = await run("google_api", { api: "drive", path, method: "GET" }, "admin@x.com");
		assert.equal(out.refused, true);
		assert.equal(calls.length, 0);
	});
}
await t("google_api: drive files allowed for the admin", async () => {
	await run("google_api", { api: "drive", path: "/drive/v3/files?fields=files(id)", method: "GET" }, "admin@x.com");
	assert.equal(calls.length, 1);
	assert.equal(new URL(calls[0].url).pathname, "/drive/v3/files");
});

// ---------- every Google tool: id params validated before any request ----------
const gTools = {};
const gSchemas = {};
const gServer = { tool: (name, _d, schema, handler) => ((gTools[name] = handler), (gSchemas[name] = Object.keys(schema ?? {}))) };
registerGsuite(gServer, async () => "google-token", () => who, env);
registerGsuiteParity(gServer, async () => "google-token", () => who, env);
const idKeys = (name) => gSchemas[name].filter((k) => /(^|_)ids?$/.test(k));
await t("google tools: every id-looking param is named *_id / *_ids (so the guard sees it)", () => {
	for (const [name, keys] of Object.entries(gSchemas))
		for (const k of keys) if (/(^|_)id(s)?(_|$)/.test(k)) assert.match(k, /(^|_)ids?$/, `${name}.${k}`);
});
await t("google tools: the id guard covers a real set of tools", () => {
	const withIds = Object.keys(gSchemas).filter((n) => idKeys(n).length);
	assert.ok(withIds.length >= 25, `only ${withIds.length} tools have id params`);
});
const BAD_IDS = ["VICTIM#", "x?alt=media", "../../../gmail/v1/users/me/drafts/send#", "..", "a/b", "%2e%2e", "a%2Fb", "a b", "a\\b"];
for (const name of Object.keys(gSchemas)) {
	for (const key of idKeys(name)) {
		await t(`${name}.${key}: bad ids refused with no request`, async () => {
			for (const bad of BAD_IDS) {
				const args = {};
				for (const k of idKeys(name)) args[k] = "good_id-1";
				args[key] = bad;
				who = "admin@x.com";
				calls = [];
				const out = JSON.parse((await gTools[name](args)).content[0].text);
				assert.equal(out.refused, true, `${name}.${key}=${bad}`);
				assert.equal(calls.length, 0, `${name}.${key}=${bad} made a request`);
			}
		});
	}
}
await t("doc_delete_comment: 'VICTIM#' never becomes DELETE /drive/v3/files/VICTIM", async () => {
	calls = [];
	const out = JSON.parse((await gTools.doc_delete_comment({ file_id: "VICTIMFILE#", comment_id: "c1" })).content[0].text);
	assert.equal(out.refused, true);
	assert.equal(calls.filter((c) => c.method === "DELETE").length, 0);
});
await t("doc_delete_comment: a good call deletes exactly that comment", async () => {
	globalThis.fetch = async (u, init = {}) => (calls.push({ url: String(u), method: init.method ?? "GET" }), new Response(null, { status: 204 }));
	calls = [];
	await gTools.doc_delete_comment({ file_id: "file_1", comment_id: "c1" });
	assert.equal(calls.length, 1);
	assert.equal(new URL(calls[0].url).pathname, "/drive/v3/files/file_1/comments/c1");
});

// ---------- meta_connect: login-CSRF confirm step ----------
await t("meta callback shows both identities and stores nothing until confirmed", async () => {
	globalThis.fetch = async (u) => {
		const url = String(u);
		if (url.includes("/oauth/access_token")) return Response.json({ access_token: "fresh-user-token" });
		if (url.includes("/me?")) return Response.json({ id: "42", name: "Someone Else" });
		return Response.json({});
	};
	const app = new Hono();
	addMetaRoutes(app);
	kv.set("meta_state:st1", "sender@x.com");
	kv.delete("meta_user_token:sender@x.com");
	const page = await (await app.request("/meta/callback?code=c&state=st1", {}, env)).text();
	assert.match(page, /Someone Else/);
	assert.match(page, /sender@x\.com/);
	assert.match(page, /Only confirm if both are you/);
	assert.equal(kv.has("meta_user_token:sender@x.com"), false);
	const nonce = /name="nonce" value="([0-9a-f-]{36})"/.exec(page)[1];
	const bad = await app.request("/meta/confirm", { method: "POST", body: new URLSearchParams({ nonce: crypto.randomUUID() }) }, env);
	assert.equal(bad.status, 403);
	const ok = await app.request("/meta/confirm", { method: "POST", body: new URLSearchParams({ nonce }) }, env);
	assert.equal(ok.status, 200);
	assert.equal(JSON.parse(kv.get("meta_user_token:sender@x.com")).fb_name, "Someone Else");
	const again = await app.request("/meta/confirm", { method: "POST", body: new URLSearchParams({ nonce }) }, env);
	assert.equal(again.status, 403); // single use
});

console.log = origLog;
console.log(`handler tests passed (${passed} test cases)`);
