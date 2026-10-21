// Shopify OAuth install flow (for an app created in the Shopify Dev Dashboard).
// GET /shopify/install?store=<subdomain>  -> redirects to the store's approval screen
// GET /shopify/callback                   -> verifies state + HMAC, exchanges the code,
//                                            stores the offline Admin token in KV.
// The token never leaves the server. Shopify's own admin approval screen is the
// human gate: only store staff can approve the install. Read scopes only.

import type { Hono } from "hono";

export const SHOPIFY_READ_SCOPES =
	"read_analytics,read_customers,read_discounts,read_price_rules,read_fulfillments,read_inventory,read_orders,read_all_orders,read_products";

const STORE_RE = /^[a-z0-9][a-z0-9-]{1,60}$/;

async function hmacHex(secret: string, message: string): Promise<string> {
	const key = await crypto.subtle.importKey(
		"raw",
		new TextEncoder().encode(secret),
		{ name: "HMAC", hash: "SHA-256" },
		false,
		["sign"],
	);
	const sig = await crypto.subtle.sign("HMAC", key, new TextEncoder().encode(message));
	return [...new Uint8Array(sig)].map((b) => b.toString(16).padStart(2, "0")).join("");
}

export function addShopifyRoutes(app: Hono<{ Bindings: Env & { OAUTH_PROVIDER: any } }>) {
	app.get("/shopify/install", async (c) => {
		const store = (c.req.query("store") ?? "").toLowerCase();
		if (!STORE_RE.test(store)) return c.text("pass ?store=<myshopify subdomain>", 400);
		if (!c.env.SHOPIFY_CLIENT_ID) return c.text("SHOPIFY_CLIENT_ID not configured", 500);
		const state = crypto.randomUUID();
		await c.env.OAUTH_KV.put(`shopify_state:${state}`, store, { expirationTtl: 600 });
		const u = new URL(`https://${store}.myshopify.com/admin/oauth/authorize`);
		u.searchParams.set("client_id", c.env.SHOPIFY_CLIENT_ID);
		u.searchParams.set("scope", SHOPIFY_READ_SCOPES);
		u.searchParams.set("redirect_uri", new URL("/shopify/callback", c.req.url).href);
		u.searchParams.set("state", state);
		return c.redirect(u.href);
	});

	app.get("/shopify/callback", async (c) => {
		const q = c.req.query();
		const { code, hmac, state, shop } = q as Record<string, string>;
		if (!code || !hmac || !state || !shop) return c.text("missing params", 400);
		// state: single-use, minted by /shopify/install
		const expectedStore = await c.env.OAUTH_KV.get(`shopify_state:${state}`);
		if (!expectedStore) return c.text("bad or expired state", 403);
		await c.env.OAUTH_KV.delete(`shopify_state:${state}`);
		if (shop !== `${expectedStore}.myshopify.com`) return c.text("shop mismatch", 403);
		// HMAC per Shopify docs: sorted query params minus hmac, joined k=v&
		const msg = Object.keys(q)
			.filter((k) => k !== "hmac")
			.sort()
			.map((k) => `${k}=${q[k]}`)
			.join("&");
		const digest = await hmacHex(c.env.SHOPIFY_CLIENT_SECRET, msg);
		if (digest !== hmac) return c.text("hmac verification failed", 403);
		// exchange code for the offline Admin API token
		const res = await fetch(`https://${shop}/admin/oauth/access_token`, {
			method: "POST",
			headers: { "Content-Type": "application/json" },
			body: JSON.stringify({
				client_id: c.env.SHOPIFY_CLIENT_ID,
				client_secret: c.env.SHOPIFY_CLIENT_SECRET,
				code,
			}),
		});
		const body: any = await res.json().catch(() => null);
		if (!res.ok || !body?.access_token)
			return c.text(`token exchange failed (${res.status})`, 502);
		await c.env.OAUTH_KV.put(`shopify_token:${expectedStore}`, body.access_token);
		console.log(
			JSON.stringify({ audit: true, user: "install-flow", tool: "shopify_install", resource: expectedStore, scope: body.scope, ts: new Date().toISOString() }),
		);
		return c.html(
			`<h2>Account connectors installed on ${expectedStore}</h2><p>Read-only Admin token stored server-side. Granted scopes: <code>${String(body.scope ?? "?").replace(/[<>&"']/g, "")}</code>. You can close this tab.</p>`,
		);
	});
}
