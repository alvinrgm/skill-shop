// Unit tests for the sign-in allowlist, ACL, input hardening and approval gate (src/gate.ts).
// Run: npm test   (bundles the sources with the esbuild that ships with wrangler)
import * as g from "../.wrangler/test/gate.mjs";
import assert from "node:assert/strict";

const {
	aclAllows,
	aclAllowsKlaviyo,
	aclList,
	aclMode,
	aclSummary,
	canonicalId,
	consumeApproval,
	gadsCustomerId,
	googleApiTarget,
	graphqlIsWrite,
	hostedDomainHint,
	isAdmin,
	metaGraphTarget,
	parsedSegment,
	resolveClient,
	safeSegments,
	shopifyStore,
	signInAllowed,
	unsafeReason,
	visibleClients,
} = g;

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

const kv = new Map();
const KV = { get: async (k) => kv.get(k) ?? null, put: async (k, v) => kv.set(k, v), delete: async (k) => kv.delete(k) };
const CLIENTS = JSON.stringify({
	acme: { meta: "act_111", gads: "111-222-3333", shopify: "acme-store" },
	other: { meta: "act_222", gads: "9998887777", shopify: "acmestore" },
});
const env = {
	OAUTH_KV: KV,
	ALLOWED_EMAILS: "a@x.com, B@Y.com, admin@x.com",
	ALLOWED_DOMAINS: "",
	ADMIN_EMAIL: "",
	CLIENTS,
	ACL: JSON.stringify({
		"a@x.com": ["acme"],
		"k@x.com": ["klaviyo"],
		"n@x.com": ["1112223333"],
		"s@x.com": ["acme-store"],
		"m@x.com": ["act_111"],
		"Mixed@X.com": ["act_222"],
		"*": ["act_999"],
	}),
};
const uuid = () => crypto.randomUUID();

// ---------- sign-in allowlist ----------
await t("allowlist: listed email (case-insensitive)", () => assert.equal(signInAllowed(env, "b@y.com", true).ok, true));
await t("allowlist: unlisted email", () => assert.equal(signInAllowed(env, "c@y.com", true).ok, false));
await t("allowlist: unverified email", () => assert.equal(signInAllowed(env, "a@x.com", false).ok, false));
await t("allowlist: empty fails closed", () => assert.equal(signInAllowed({ ...env, ALLOWED_EMAILS: "", ALLOWED_DOMAINS: "" }, "a@x.com", true).ok, false));
await t("allowlist: domain", () => assert.equal(signInAllowed({ ...env, ALLOWED_EMAILS: "", ALLOWED_DOMAINS: "corp.com" }, "z@corp.com", true).ok, true));
await t("hd hint", () => assert.equal(hostedDomainHint({ ALLOWED_DOMAINS: "corp.com", ALLOWED_EMAILS: "" }), "corp.com"));
await t("no admin when ADMIN_EMAIL empty", () => assert.equal(isAdmin(env, "a@x.com"), false));

// ---------- per-vendor canonical ids ----------
await t("canonical meta: act_ + digits only", () => {
	assert.equal(canonicalId("meta", "act_111"), "act_111");
	for (const bad of ["111", "ACT_111", "act_1-11", "act_111.", "act_111:x", "act_111,act_222", "ａct_222", "act_"]) assert.equal(canonicalId("meta", bad), null, bad);
});
await t("canonical gads: only dashes stripped, 10 digits", () => {
	assert.equal(canonicalId("gads", "111-222-3333"), "1112223333");
	assert.equal(canonicalId("gads", "1112223333"), "1112223333");
	for (const bad of ["act_1112223333", "１１１２２２３３３３", "1112223333 ", "1112223333​", "0x1112223333", "111222333"]) assert.equal(canonicalId("gads", bad), null, bad);
});
await t("canonical shopify: exact, dashes significant", () => {
	assert.equal(canonicalId("shopify", "Acme-Store"), "acme-store");
	assert.notEqual(canonicalId("shopify", "acmestore"), canonicalId("shopify", "acme-store"));
	for (const bad of ["acme_store", "acme.store", "acme-store@evil.com", "acme-store:443", "-x"]) assert.equal(canonicalId("shopify", bad), null, bad);
});
await t("canonical sheet: exact (case and dashes significant)", () => {
	assert.equal(canonicalId("sheet", "1AbC-sheet_id"), "1AbC-sheet_id");
	assert.notEqual(canonicalId("sheet", "1AbC"), canonicalId("sheet", "1abc"));
});

// ---------- ACL basics ----------
await t("acl: slug entry grants its meta id", () => assert.equal(aclAllows(env, "a@x.com", "meta", "act_111"), true));
await t("acl: slug entry grants its gads id (undashed)", () => assert.equal(aclAllows(env, "a@x.com", "gads", "1112223333"), true));
await t("acl: slug entry grants its gads id (dashed)", () => assert.equal(aclAllows(env, "a@x.com", "gads", "111-222-3333"), true));
await t("acl: slug entry grants its store", () => assert.equal(aclAllows(env, "a@x.com", "shopify", "acme-store"), true));
await t("acl: no prefix match", () => assert.equal(aclAllows(env, "a@x.com", "meta", "act_1111"), false));
await t("acl: other client's account refused", () => assert.equal(aclAllows(env, "a@x.com", "meta", "act_222"), false));
await t("acl: '*' key default", () => assert.equal(aclAllows(env, "z@z.com", "meta", "act_999"), true));
await t("acl: '*' key default, no substring", () => assert.equal(aclAllows(env, "z@z.com", "meta", "act_99"), false));
await t("acl: malformed fails closed", () => assert.equal(aclAllows({ ...env, ACL: "{bad" }, "a@x.com", "meta", "act_111"), false));
await t("acl: non-list value fails closed", () => assert.equal(aclMode({ ...env, ACL: '{"a@x.com":"act_111"}' }), "invalid"));
await t("acl: malformed mode", () => assert.equal(aclMode({ ...env, ACL: "{bad" }), "invalid"));
await t("acl: unsafe resource id never matches, even for '*'", () => {
	const all = { ...env, ACL: JSON.stringify({ "*": ["*"] }) };
	assert.equal(aclAllows(all, "a@x.com", "meta", "act_111/../act_222"), false);
	assert.equal(aclAllows(all, "a@x.com", "meta", "act_111%2f..%2fact_222"), false);
	assert.equal(aclAllows(all, "a@x.com", "shopify", "evil.com/x?"), false);
	assert.equal(aclAllows(all, "a@x.com", "meta", "120000000000"), true); // '*' covers bare Graph nodes
});

// ---------- finding 1: no dash/case normalisation outside Google Ads ----------
await t("acl: store 'acme-store' does NOT allow 'acmestore'", () => {
	assert.equal(aclAllows(env, "a@x.com", "shopify", "acmestore"), false);
	assert.equal(aclAllows(env, "s@x.com", "shopify", "acmestore"), false);
	assert.equal(aclAllows(env, "a@x.com", "shopify", "a-c-m-e-s-t-o-r-e"), false);
	assert.equal(aclAllows(env, "s@x.com", "shopify", "acme-store"), true);
});
await t("acl: act_1-11 is not act_111", () => assert.equal(aclAllows(env, "m@x.com", "meta", "act_1-11"), false));

// ---------- finding 5: no cross-vendor matches ----------
await t("acl: gads grant does not reach Meta act_<same digits>", () => assert.equal(aclAllows(env, "n@x.com", "meta", "act_1112223333"), false));
await t("acl: gads grant does not reach a store named like it", () => assert.equal(aclAllows(env, "n@x.com", "shopify", "1112223333"), false));
await t("acl: gads grant reaches gads", () => assert.equal(aclAllows(env, "n@x.com", "gads", "111-222-3333"), true));
await t("acl: act_111 does not allow bare Graph node 111", () => assert.equal(aclAllows(env, "m@x.com", "meta", "111"), false));
await t("acl: bare digits entry does not grant Meta", () => assert.equal(aclAllows({ ...env, ACL: '{"q@x.com":["111"]}' }, "q@x.com", "meta", "act_111"), false));
await t("acl: explicit 'shopify:' prefix for an all-digit store", () => {
	const e = { ...env, ACL: '{"q@x.com":["shopify:1112223333"]}' };
	assert.equal(aclAllows(e, "q@x.com", "shopify", "1112223333"), true);
	assert.equal(aclAllows(e, "q@x.com", "gads", "1112223333"), false);
});
await t("acl: meta grant does not reach gads", () => assert.equal(aclAllows(env, "m@x.com", "gads", "0000000111"), false));
await t("acl: store entry does not grant klaviyo, klaviyo entry does not grant stores", () => {
	const e = { ...env, ACL: '{"q@x.com":["klaviyo"],"r@x.com":["some-store"]}' };
	assert.equal(aclAllows(e, "q@x.com", "shopify", "klaviyo"), false);
	assert.equal(aclAllowsKlaviyo(e, "r@x.com"), false);
});

// ---------- finding 6: ACL email keys are case-insensitive ----------
await t("acl: key Mixed@X.com matches caller mixed@x.com", () => assert.equal(aclAllows(env, "mixed@x.com", "meta", "act_222"), true));
await t("acl: key matches caller MIXED@x.COM", () => assert.equal(aclAllows(env, "MIXED@x.COM", "meta", "act_222"), true));
await t("acl: prototype names are not keys or slugs", () => {
	const e = { ...env, ACL: '{"*":[]}' };
	for (const k of ["__proto__", "constructor", "toString"]) assert.deepEqual(aclList(e, k), []);
	assert.equal(aclAllows({ ...env, ACL: '{"a@x.com":["constructor"]}' }, "a@x.com", "meta", "act_111"), false);
	assert.equal(resolveClient(env, "__proto__", "meta"), "__proto__");
	assert.equal(resolveClient(env, "constructor", "meta"), "constructor");
});

await t("CLIENTS slugs spelled like ids never alias another account", () => {
	const e = { ...env, CLIENTS: JSON.stringify({ act_222: { meta: "act_111" }, "1112223333": { gads: "9998887777" } }) };
	assert.equal(resolveClient(e, "act_222", "meta"), "act_222");
	assert.equal(resolveClient(e, "1112223333", "gads"), "1112223333");
	assert.equal(metaGraphTarget(e, "act_222/insights", "v24.0").first, "act_222");
});

// ---------- ACL default: admin-only ----------
for (const [label, ACL] of [["unset", undefined], ["blank", ""], ["whitespace", "  "], ["empty object", "{}"]]) {
	const noAcl = { ...env, ACL, ADMIN_EMAIL: "Admin@x.com" };
	await t(`acl ${label}: mode admin-only`, () => assert.equal(aclMode(noAcl), "admin-only"));
	await t(`acl ${label}: admin allowed`, () => assert.equal(aclAllows(noAcl, "admin@x.com", "meta", "act_222"), true));
	await t(`acl ${label}: non-admin refused`, () => assert.equal(aclAllows(noAcl, "a@x.com", "meta", "act_111"), false));
	await t(`acl ${label}: non-admin refused klaviyo`, () => assert.equal(aclAllowsKlaviyo(noAcl, "a@x.com"), false));
	await t(`acl ${label}: admin klaviyo`, () => assert.equal(aclAllowsKlaviyo(noAcl, "admin@x.com"), true));
	await t(`acl ${label}: no admin -> nobody`, () => assert.equal(aclAllows({ ...noAcl, ADMIN_EMAIL: "" }, "admin@x.com", "meta", "act_111"), false));
	await t(`acl ${label}: ping text says admin-only`, () => {
		assert.match(aclSummary(noAcl, "a@x.com"), /admin-only/);
		assert.match(aclSummary(noAcl, "a@x.com"), /refused/);
		assert.match(aclSummary(noAcl, "admin@x.com"), /allowed/);
		assert.match(aclSummary({ ...noAcl, ADMIN_EMAIL: "" }, "a@x.com"), /nobody/);
	});
}
await t("acl: configured mode", () => assert.equal(aclMode(env), "configured"));
await t("acl: explicit allow-all still works", () => assert.equal(aclAllows({ ...env, ACL: '{"*":["*"]}' }, "q@q.com", "meta", "act_5"), true));

// ---------- klaviyo gate ----------
await t("klaviyo: entry 'klaviyo' allowed", () => assert.equal(aclAllowsKlaviyo(env, "k@x.com"), true));
await t("klaviyo: account-only user refused", () => assert.equal(aclAllowsKlaviyo(env, "a@x.com"), false));
await t("klaviyo: '*' allowed", () => assert.equal(aclAllowsKlaviyo({ ...env, ACL: '{"*":["*"]}' }, "q@q.com"), true));

// ---------- clients filtered by ACL ----------
await t("clients: user sees only their client", () => {
	assert.deepEqual(visibleClients(env, "a@x.com"), { acme: { meta: "act_111", gads: "111-222-3333", shopify: "acme-store" } });
});
await t("clients: default user sees nothing", () => assert.deepEqual(visibleClients(env, "z@z.com"), {}));
await t("clients: partial grant shows only granted ids, per vendor", () => {
	const e = { ...env, ACL: JSON.stringify({ "p@x.com": ["act_222"] }) };
	assert.deepEqual(visibleClients(e, "p@x.com"), { other: { meta: "act_222" } });
	assert.deepEqual(visibleClients(env, "s@x.com"), { acme: { shopify: "acme-store" } }); // not 'acmestore'
});
await t("clients: admin-only default hides registry from non-admin", () => {
	const e = { ...env, ACL: "", ADMIN_EMAIL: "admin@x.com" };
	assert.deepEqual(visibleClients(e, "a@x.com"), {});
	assert.equal(Object.keys(visibleClients(e, "admin@x.com")).length, 2);
});

// ---------- path traversal / injection ----------
const traversal = [
	"act_111/../act_222",
	"act_111/../act_222/insights",
	"act_111/..",
	"act_111/insights/..",
	"acme/../other",
	"act_111/%2e%2e/act_222",
	"act_111/%2E%2E/act_222",
	"act_111/%2e%2E/act_222",
	"act_111/.%2e/act_222",
	"act_111/%2e./act_222",
	"act_111%2f..%2fact_222",
	"act_111%2F%2E%2E%2Fact_222",
	"act_111/%252e%252e/act_222",
	"act_111/insights%00",
	"act_111\\..\\act_222",
	"act_111\\insights",
	"act_111/insights?x=1",
	"act_111?/../../act_222",
	"act_111#/../act_222",
	"act_111//act_222",
	"/act_222",
	"act_111/./insights",
	"act_111/insights/",
	"act_111/ins ights",
	"act_111/\tinsights",
	"act_111/insights;x",
	"act_111/‥/act_222",
	"act_111/．．/act_222",
	"act_111/。。/act_222",
	"ａct_222",
	"",
];
for (const p of traversal) {
	await t(`meta path rejected: ${JSON.stringify(p)}`, () => {
		const r = metaGraphTarget(env, p, "v24.0");
		assert.equal(r.ok, false, `expected rejection for ${p}`);
	});
}
await t("meta path: odd-but-parseable first segments never pass a scoped ACL", () => {
	for (const p of ["ACT_111/insights", "act_111./insights", "act_111:x/insights", "act_111,act_222/insights", "111/insights"]) {
		const r = metaGraphTarget(env, p, "v24.0");
		if (r.ok) assert.equal(aclAllows(env, "a@x.com", "meta", r.first), false, p);
	}
});
await t("unsafeReason catches each class", () => {
	assert.match(unsafeReason("a/../b"), /\.\./);
	assert.match(unsafeReason("a/%2e%2e/b"), /percent/);
	assert.match(unsafeReason("a/%2E%2E/b"), /percent/);
	assert.match(unsafeReason("a?b"), /\?/);
	assert.match(unsafeReason("a#b"), /#/);
	assert.match(unsafeReason("a\\b"), /backslash/);
	assert.match(unsafeReason("a\nb"), /whitespace/);
	assert.match(unsafeReason("a​b"), /non-ASCII/);
	assert.equal(unsafeReason("act_111/insights"), null);
});
await t("meta path: legit path accepted and targets its own account", () => {
	const r = metaGraphTarget(env, "act_111/insights", "v24.0");
	assert.equal(r.ok, true);
	assert.equal(r.first, "act_111");
	assert.equal(r.url, "https://graph.facebook.com/v24.0/act_111/insights");
});
await t("meta path: slug resolves to its account", () => {
	const r = metaGraphTarget(env, "acme/campaigns", "v24.0");
	assert.equal(r.ok, true);
	assert.equal(r.first, "act_111");
	assert.equal(aclAllows(env, "a@x.com", "meta", r.first), true);
});
await t("meta path: slug resolving to a traversal value rejected", () => {
	const bad = { ...env, CLIENTS: JSON.stringify({ evil: { meta: "act_111/../act_222" } }) };
	assert.equal(metaGraphTarget(bad, "evil/insights", "v24.0").ok, false);
});
for (const v of ["v24.0/../act_222", "v24.0?", "v24.0/act_222", "x", "v24.0#", "%76"]) {
	await t(`meta api_version rejected: ${v}`, () => assert.equal(metaGraphTarget(env, "act_111/insights", v).ok, false));
}
await t("the bug the hardening prevents: URL parsing does normalise '..'", () => {
	assert.equal(new URL("https://graph.facebook.com/v24.0/act_111/../act_222").pathname, "/v24.0/act_222");
	assert.equal(new URL("https://graph.facebook.com/v24.0/act_111/%2e%2e/act_222").pathname, "/v24.0/act_222");
	assert.equal(parsedSegment("https://graph.facebook.com/v24.0/act_111/../act_222/insights", 1), "act_222");
});
await t("safeSegments: klaviyo-style paths", () => {
	assert.equal(safeSegments("campaigns").ok, true);
	assert.equal(safeSegments("profiles/01HABCDEF").ok, true);
	for (const bad of ["campaigns?filter=x", "../accounts", "%2e%2e/accounts", "campaigns/", "/accounts"]) assert.equal(safeSegments(bad).ok, false, bad);
});

// ---------- Google Ads customer ids ----------
await t("gads: undashed id", () => assert.deepEqual(gadsCustomerId(env, "1112223333"), { ok: true, id: "1112223333" }));
await t("gads: dashed id", () => assert.deepEqual(gadsCustomerId(env, "111-222-3333"), { ok: true, id: "1112223333" }));
await t("gads: slug (any case)", () => {
	assert.deepEqual(gadsCustomerId(env, "acme"), { ok: true, id: "1112223333" });
	assert.deepEqual(gadsCustomerId(env, "ACME"), { ok: true, id: "1112223333" });
});
await t("gads: dashed and undashed hit the same ACL entry", () => {
	for (const raw of ["111-222-3333", "1112223333"]) {
		const r = gadsCustomerId(env, raw);
		assert.equal(r.ok, true);
		assert.equal(aclAllows(env, "a@x.com", "gads", r.id), true);
		assert.equal(aclAllows(env, "n@x.com", "gads", r.id), true);
		assert.equal(aclAllows(env, "z@z.com", "gads", r.id), false);
	}
});
for (const bad of [
	"1112223333/../9998887777",
	"111222333",
	"11122233334",
	"111-222-333a",
	"1112223333%2f..%2f9998887777",
	"1112223333?x",
	"1112223333#",
	"1112223333\\",
	"1112223333 ",
	"1112223333​",
	"１１１２２２３３３３",
	"0x1112223333",
	"..",
	"",
	"customers/1112223333",
]) {
	await t(`gads: rejected ${JSON.stringify(bad)}`, () => assert.equal(gadsCustomerId(env, bad).ok, false));
}

// ---------- Shopify store ----------
await t("shopify: subdomain", () => assert.deepEqual(shopifyStore(env, "acme-store"), { ok: true, store: "acme-store" }));
await t("shopify: slug", () => assert.deepEqual(shopifyStore(env, "acme"), { ok: true, store: "acme-store" }));
await t("shopify: full host tolerated", () => assert.deepEqual(shopifyStore(env, "Acme-Store.myshopify.com"), { ok: true, store: "acme-store" }));
for (const bad of ["evil.com/x?", "acme-store/../x", "a.b", "acme%2estore", "attacker.example#", "-x", "", "acme-store.myshopify.com.evil", "acme-store.myshopify.com.myshopify.com", "acme_store", "acme-store@evil.com", "acme-store:443"]) {
	await t(`shopify: rejected ${JSON.stringify(bad)}`, () => assert.equal(shopifyStore(env, bad).ok, false));
}

// ---------- finding 3: GraphQL write detection ----------
for (const q of [
	"mutation { a }",
	"  # c\nmutation { a }",
	"fragment F on Shop { name } mutation M { shopUpdate { x } }",
	"query Q { shop { name } } mutation M { x }",
	"query Q { shop { name } }\n\n  mutation M { x }",
	'query Q { a(q: "x") } mutation M { x }',
	"subscription S { x }",
	"MUTATION { a }",
	'query Q { a(q: "unterminated) } mutation M { x }',
	'query Q { a(q: """unterminated) } mutation M { x }',
	// escaped triple quote inside a block string must not end it
	'fragment F on Product { metafield(namespace: """\\""" """, key: "k") { id } } mutation { productUpdate(product: {id: "gid://shopify/Product/1", title: "pwn"}) { product { ...F } } } #"""',
	'query { a(q: """x \\""" mutation y""") } mutation M { x }',
]) {
	await t(`graphql write refused: ${JSON.stringify(q)}`, () => assert.equal(graphqlIsWrite(q), true));
}
for (const q of [
	"{ shop { name } }",
	"query Q { orders(first: 5) { nodes { name } } }",
	'query { products(query: "title:mutation") { nodes { id } } }',
	"query { shop { name } } # no mutation here",
	'query { a(q: """a mutation in a block string""") }',
	'query { a(q: "escaped \\" mutation") }',
	'query { a(q: """has \\""" inside, still a string: mutation""") }',
	"query { mutationLog: shop { name } }",
]) {
	await t(`graphql read allowed: ${JSON.stringify(q)}`, () => assert.equal(graphqlIsWrite(q), false));
}

// ---------- finding 2: google_api prefixes ----------
for (const [api, path] of [
	["drive", "/gmail/v1/users/me/messages"],
	["drive", "/calendar/v3/calendars/primary/events"],
	["drive", "/drive/v3/../../gmail/v1/users/me/messages"],
	["drive", "/drive/v3/%2e%2e/%2e%2e/gmail/v1/users/me"],
	["drive", "/drive/v3/%2E%2E%2Fgmail"],
	["drive", "/drive/v3\\..\\gmail"],
	["drive", "/drive/v30/files"],
	["drive", "//evil.example/drive/v3/files"],
	["drive", "/drive/v3/files#frag"],
	["drive", "/drive/v3/files/ x"],
	["docs", "/v1/presentations/abc"],
	["sheets", "/v1/documents/abc"],
	["slides", "/v4/spreadsheets/abc"],
	["gmail", "/gmail/v1/users/me/messages"],
	["__proto__", "/x"],
]) {
	await t(`google_api refused: ${api} ${path}`, () => assert.equal(googleApiTarget(api, path).ok, false));
}
for (const [api, path, url] of [
	["drive", "/drive/v3/files/abc?fields=id,name", "https://www.googleapis.com/drive/v3/files/abc?fields=id,name"],
	["drive", "/upload/drive/v3/files?uploadType=media", "https://www.googleapis.com/upload/drive/v3/files?uploadType=media"],
	["docs", "/v1/documents/abc:batchUpdate", "https://docs.googleapis.com/v1/documents/abc:batchUpdate"],
	["sheets", "/v4/spreadsheets/abc/values/Sheet1!A1:B2", "https://sheets.googleapis.com/v4/spreadsheets/abc/values/Sheet1!A1:B2"],
	["slides", "/v1/presentations/abc", "https://slides.googleapis.com/v1/presentations/abc"],
]) {
	await t(`google_api allowed: ${api} ${path}`, () => assert.deepEqual(googleApiTarget(api, path), { ok: true, url }));
}

// ---------- Google ids and URLs (every Google tool) ----------
const { googleIdProblem, googleUrlProblem } = g;
for (const bad of ["VICTIM#", "a?b", "../x", "..", "a/b", "%2e%2e", "a%2Fb", "a b", "a\\b", "a\u200bb", "x".repeat(201), 5]) {
	await t(`googleIdProblem refuses ${JSON.stringify(bad)}`, () => {
		assert.ok(googleIdProblem({ file_id: bad }));
		assert.ok(googleIdProblem({ comment_id: "ok", message_id: bad }));
		assert.ok(googleIdProblem({ ids: ["ok", bad] }));
	});
}
await t("googleIdProblem accepts real-looking ids and ignores non-id params", () => {
	assert.equal(googleIdProblem({ file_id: "1AbC-dEf_123", message_id: "18c2f0a9b3d4e5f6", comment_id: "AAAAxyz", approval_id: crypto.randomUUID() }), null);
	assert.equal(googleIdProblem({ query: "name contains '../x#'", width_pt: 3, file_id: undefined }), null);
});
for (const url of [
	"https://www.googleapis.com/drive/v3/files/VICTIM#/comments/c",
	"https://www.googleapis.com/drive/v3/files/../../gmail/v1/users/me/drafts/send",
	"https://www.googleapis.com/drive/v3/files/%2e%2e/%2e%2e/gmail/v1/users/me",
	"https://www.googleapis.com/drive/v3/files/x\\..\\..\\gmail",
	"https://www.googleapis.com/gmail/v1/users/me/drafts/send",
	"https://www.googleapis.com/gmail/v1/users/me/messages/send",
	"https://www.googleapis.com/gmail/v1/users/me/settings/filters",
	"https://www.googleapis.com/oauth2/v2/userinfo",
	"https://docs.googleapis.com/v1/presentations/x",
	"https://evil.example/drive/v3/files",
	"http://www.googleapis.com/drive/v3/files",
]) {
	await t(`googleUrlProblem refuses ${url}`, () => assert.ok(googleUrlProblem(url)));
}
for (const url of [
	"https://www.googleapis.com/drive/v3/files/abc?fields=id,name&supportsAllDrives=true",
	"https://www.googleapis.com/drive/v3/files/abc/comments/c1",
	"https://www.googleapis.com/gmail/v1/users/me/drafts",
	"https://www.googleapis.com/gmail/v1/users/me/messages/18c2f0a9?format=full",
	"https://www.googleapis.com/calendar/v3/calendars/primary/events?sendUpdates=none",
	"https://docs.googleapis.com/v1/documents/abc:batchUpdate",
	"https://sheets.googleapis.com/v4/spreadsheets/abc/values/Sheet1!A1%3AB2",
	"https://slides.googleapis.com/v1/presentations/abc",
]) {
	await t(`googleUrlProblem allows ${url}`, () => assert.equal(googleUrlProblem(url), null));
}

// ---------- approval slips ----------
const slip = (o) => {
	const id = uuid();
	kv.set(`approval:${id}`, JSON.stringify({ description: "d", ...o }));
	return id;
};
await t("approval: wrong resource, wrong person, right person, single use", async () => {
	const s1 = slip({ resource: "act_111", by: "a@x.com" });
	assert.equal((await consumeApproval(env, s1, "meta", "act_1111", "a@x.com")).ok, false);
	assert.equal((await consumeApproval(env, s1, "meta", "act_111", "b@y.com")).ok, false);
	assert.equal((await consumeApproval(env, s1, "meta", "act_111", "a@x.com")).ok, true);
	assert.equal((await consumeApproval(env, s1, "meta", "act_111", "a@x.com")).ok, false);
});
await t("approval: slip for act_1-11 does not redeem for act_111", async () => {
	const id = slip({ resource: "act_1-11", by: "a@x.com" });
	assert.equal((await consumeApproval(env, id, "meta", "act_111", "a@x.com")).ok, false);
});
await t("approval: slug slip redeems only for that slug's Meta account", async () => {
	const id = slip({ resource: "acme", by: "a@x.com" });
	assert.equal((await consumeApproval(env, id, "meta", "act_222", "a@x.com")).ok, false);
	assert.equal((await consumeApproval(env, id, "sheet", "acmestore", "a@x.com")).ok, false);
	assert.equal((await consumeApproval(env, id, "meta", "act_111", "a@x.com")).ok, true);
});
await t("approval: a bare-digit or gads-id slip does not redeem for a Meta account", async () => {
	for (const resource of ["111-222-3333", "1112223333", "111"]) {
		const id = slip({ resource, by: "a@x.com" });
		assert.equal((await consumeApproval(env, id, "meta", "act_1112223333", "a@x.com")).ok, false, resource);
		assert.equal((await consumeApproval(env, id, "meta", "act_111", "a@x.com")).ok, false, resource);
	}
});
await t("approval: sheet id slip is exact", async () => {
	const id = slip({ resource: "1AbC-sheet_id", by: "a@x.com" });
	assert.equal((await consumeApproval(env, id, "sheet", "1abc-sheet_id", "a@x.com")).ok, false);
	assert.equal((await consumeApproval(env, id, "sheet", "1AbCsheet_id", "a@x.com")).ok, false);
	assert.equal((await consumeApproval(env, id, "sheet", "1AbC-sheet_id", "a@x.com")).ok, true);
});
await t("approval: short / guessed / uppercased ids refused", async () => {
	kv.set("approval:abcd1234", JSON.stringify({ resource: "act_111", by: "a@x.com", description: "d" }));
	assert.equal((await consumeApproval(env, "abcd1234", "meta", "act_111", "a@x.com")).ok, false);
	assert.equal((await consumeApproval(env, "../x", "meta", "act_111", "a@x.com")).ok, false);
	const id = slip({ resource: "act_111", by: "a@x.com" });
	assert.equal((await consumeApproval(env, id.toUpperCase(), "meta", "act_111", "a@x.com")).ok, false);
});
await t("approval: admin slip without for_email works for anyone", async () => {
	const e = { ...env, ADMIN_EMAIL: "admin@x.com" };
	const id = slip({ resource: "act_111", by: "admin@x.com" });
	assert.equal((await consumeApproval(e, id, "meta", "act_111", "b@y.com")).ok, true);
});
await t("approval: admin slip bound with for_email only works for that person", async () => {
	const e = { ...env, ADMIN_EMAIL: "admin@x.com" };
	const id = slip({ resource: "act_111", by: "admin@x.com", for: "a@x.com" });
	assert.equal((await consumeApproval(e, id, "meta", "act_111", "b@y.com")).ok, false);
	assert.equal((await consumeApproval(e, id, "meta", "act_111", "admin@x.com")).ok, false);
	assert.equal((await consumeApproval(e, id, "meta", "act_111", "A@x.com")).ok, true);
});
await t("approval: single use is best-effort under a racing KV (documented limit)", async () => {
	// Workers KV has no compare-and-delete. This records the behaviour so a
	// change to it is deliberate: sequential reuse is always refused.
	const id = slip({ resource: "act_111", by: "a@x.com" });
	assert.equal((await consumeApproval(env, id, "meta", "act_111", "a@x.com")).ok, true);
	assert.equal((await consumeApproval(env, id, "meta", "act_111", "a@x.com")).ok, false);
});

console.log(`gate tests passed (${passed} test cases)`);
