// Meta per-user OAuth: writes act AS THE CALLER, not the server's System User.
//
// Flow: the signed-in user runs the `meta_connect` tool -> gets a Facebook Login
// URL carrying a single-use state nonce bound to their email -> approves in the
// browser -> GET /meta/callback exchanges the code, upgrades it to a long-lived
// (~60 day) user token, and stores it in KV keyed to the email. Write tools then
// use THAT token, so Meta's own activity log attributes every change to the human
// who made it (and Meta's own asset permissions cap what they can touch: a user
// with no access to an ad account cannot write to it no matter what this server
// allows).
//
// Needs secrets: META_APP_ID + META_APP_SECRET (a Meta Business app with Facebook
// Login for Business; its settings must list <WORKER_BASE>/meta/callback as a
// valid OAuth redirect URI, and while the app is in development mode every user
// who connects must hold a role on the app) and WORKER_BASE.

import type { Hono } from "hono";
import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { jtext, scrubTokens } from "./lib";
import { aclAllows, audit, signInAllowed } from "./gate";

export const META_API_VERSION = "v24.0";
export const META_WRITE_SCOPES =
	"ads_management,ads_read,business_management,pages_show_list,pages_manage_ads,pages_read_engagement";

// Public base URL of this deployment, e.g. https://account-connectors.<you>.workers.dev
// (no trailing slash). Needed wherever a tool hands out a URL back to this server.
export function workerBase(env: Env): string {
	return (env.WORKER_BASE ?? "").trim().replace(/\/+$/, "");
}

function escapeHtml(s: string): string {
	return s.replace(/[&<>"']/g, (ch) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[ch]!);
}

export type MetaUserToken = { token: string; fb_name?: string; fb_id?: string; obtained: string };

export async function getMetaUserToken(env: Env, email: string): Promise<MetaUserToken | null> {
	const raw = await env.OAUTH_KV.get(`meta_user_token:${email}`);
	return raw ? (JSON.parse(raw) as MetaUserToken) : null;
}

export function metaConnectHint(base: string) {
	return {
		error: "no Meta connection for this user",
		fix: "run the meta_connect tool, open the returned URL in a browser, and approve — then retry",
	};
}

export function registerMetaConnect(server: McpServer, env: Env, whoami: () => string) {
	server.tool(
		"meta_connect",
		"Start the per-user Meta (Facebook) sign-in that write tools require. Returns a URL to open in a browser; after approving, this user's Meta identity is stored server-side and every meta write executes AS THEM (Meta's activity log shows their name). Re-run any time to refresh or switch identity. Tokens last ~60 days.",
		{},
		async () => {
			const email = whoami();
			if (!env.META_APP_ID) return jtext({ error: "META_APP_ID not configured on the server" });
			if (!workerBase(env)) return jtext({ error: "WORKER_BASE not configured on the server (wrangler secret put WORKER_BASE)" });
			const state = crypto.randomUUID();
			await env.OAUTH_KV.put(`meta_state:${state}`, email, { expirationTtl: 600 });
			const u = new URL(`https://www.facebook.com/${META_API_VERSION}/dialog/oauth`);
			u.searchParams.set("client_id", env.META_APP_ID);
			u.searchParams.set("redirect_uri", `${workerBase(env)}/meta/callback`);
			u.searchParams.set("state", state);
			u.searchParams.set("scope", META_WRITE_SCOPES);
			audit(email, "meta_connect", "start");
			return jtext({ open_this_url: u.href, binds_to: email, expires_in_minutes: 10, note: "open it yourself, never forward it: after Facebook sign-in the page asks you to confirm both identities" });
		},
	);

	server.tool(
		"meta_whoami",
		"Shows which Meta identity (if any) is connected for the signed-in user — the identity meta writes will act as.",
		{},
		async () => {
			const email = whoami();
			const t = await getMetaUserToken(env, email);
			if (!t) return jtext({ connected: false, ...metaConnectHint(workerBase(env)) });
			return jtext({ connected: true, as: { name: t.fb_name, id: t.fb_id }, since: t.obtained, signed_in_as: email });
		},
	);
}

export function addMetaRoutes(app: Hono<{ Bindings: Env & { OAUTH_PROVIDER: any } }>) {
	// Upload relay: receives ONE multipart file from the operator's
	// machine under a single-use ticket minted by meta_upload_begin (which already
	// consumed the approval slip), relays it to Graph adimages under the ticket
	// owner's per-user Meta token, and returns Meta's JSON (the image hash).
	// Bytes pass through worker memory only — nothing is stored.
	app.post("/meta/upload/:ticket", async (c) => {
		const ticket = c.req.param("ticket");
		if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(ticket)) return c.json({ error: "bad upload ticket" }, 403);
		const raw = await c.env.OAUTH_KV.get(`upload_ticket:${ticket}`);
		if (!raw) return c.json({ error: "bad, used, or expired upload ticket — re-run meta_upload_begin" }, 403);
		// single-use, best-effort: KV has no atomic compare-and-delete, so two uploads racing
		// in the same instant could both pass; tickets are bound to one user + account and
		// expire in minutes (meta_upload_begin ttl_minutes, max 60).
		await c.env.OAUTH_KV.delete(`upload_ticket:${ticket}`);

		const t = JSON.parse(raw) as { email: string; acct: string; approved: string; kind?: "image" | "video" };
		const kind = t.kind === "video" ? "video" : "image";
		// Re-check at upload time: the ticket's owner must still be on the sign-in
		// allowlist and still be granted this account by the ACL.
		const access = signInAllowed(c.env, t.email ?? "", true);
		if (!access.ok) return c.json({ refused: true, status: "access_revoked", reason: access.reason }, 403);
		if (!/^act_\d+$/.test(t.acct) || !aclAllows(c.env, t.email, "meta", t.acct))
			return c.json({ refused: true, reason: `${t.email} is not authorized for ${t.acct} (server ACL)` }, 403);
		const userTok = await getMetaUserToken(c.env, t.email);
		if (!userTok) return c.json({ error: "Meta connection expired for this user — re-run meta_connect" }, 403);

		let fd: FormData;
		try {
			fd = await c.req.raw.formData();
		} catch {
			return c.json({ error: 'expected multipart form data: curl -F "filename=@/path/to/file" <url>' }, 400);
		}
		let file: File | null = null;
		for (const [, v] of fd.entries()) if (v instanceof File) { file = v; break; }
		if (!file) return c.json({ error: 'no file part found — use curl -F "filename=@/path/to/file"' }, 400);
		// adimages non-resumable cap ~30MB; advideos non-resumable cap ~1GB (chunked
		// start/transfer/finish only needed beyond that — not built yet).
		const cap = kind === "video" ? 1024 * 1024 * 1024 : 30 * 1024 * 1024;
		if (file.size > cap)
			return c.json({ error: `file is ${file.size} bytes; ${kind} cap here is ${cap} bytes (larger needs the chunked protocol — not yet built)` }, 413);

		const endpoint = kind === "video" ? "advideos" : "adimages";
		const out = new FormData();
		out.append(kind === "video" ? "source" : "filename", file, file.name || (kind === "video" ? "ad.mp4" : "ad.png"));
		out.append("access_token", userTok.token);
		const res = await fetch(`https://graph.facebook.com/${META_API_VERSION}/${t.acct}/${endpoint}`, {
			method: "POST",
			body: out,
		});
		const body: any = await res.json().catch(() => null);
		audit(t.email, "meta_upload_relay", `${t.acct} :: ${kind} :: ${file.name} (${file.size}b) :: approved: ${t.approved.slice(0, 100)}`);
		if (!res.ok) return c.json(scrubTokens({ error: res.status, detail: body }), 502);
		const extra = kind === "video" ? { note: "video is processing — poll meta_video_status with this id until status='ready' before building the creative" } : {};
		return c.json(scrubTokens({ ...body, ...extra }), 200);
	});

	app.get("/meta/callback", async (c) => {
		const { code, state, error, error_description } = c.req.query() as Record<string, string>;
		if (error) return c.text(`Meta sign-in failed: ${error}: ${error_description ?? ""}`, 400);
		if (!code || !state) return c.text("missing params", 400);
		const email = await c.env.OAUTH_KV.get(`meta_state:${state}`);
		if (!email) return c.text("bad or expired state — re-run meta_connect", 403);
		await c.env.OAUTH_KV.delete(`meta_state:${state}`);

		const base = workerBase(c.env) || new URL(c.req.url).origin;
		// 1. code -> short-lived user token
		const q1 = new URLSearchParams({
			client_id: c.env.META_APP_ID,
			client_secret: c.env.META_APP_SECRET,
			redirect_uri: `${base}/meta/callback`,
			code,
		});
		const r1 = await fetch(`https://graph.facebook.com/${META_API_VERSION}/oauth/access_token?${q1}`);
		const b1: any = await r1.json().catch(() => null);
		if (!r1.ok || !b1?.access_token) return c.text(`code exchange failed (${r1.status}): ${JSON.stringify(b1)}`, 502);

		// 2. short-lived -> long-lived (~60 days)
		const q2 = new URLSearchParams({
			grant_type: "fb_exchange_token",
			client_id: c.env.META_APP_ID,
			client_secret: c.env.META_APP_SECRET,
			fb_exchange_token: b1.access_token,
		});
		const r2 = await fetch(`https://graph.facebook.com/${META_API_VERSION}/oauth/access_token?${q2}`);
		const b2: any = await r2.json().catch(() => null);
		const token = (r2.ok && b2?.access_token) || b1.access_token; // degrade to short-lived

		// 3. who is this?
		const r3 = await fetch(`https://graph.facebook.com/${META_API_VERSION}/me?fields=id,name&access_token=${token}`);
		const me: any = await r3.json().catch(() => ({}));

		// Do NOT store yet. The state proves which server user STARTED this, not who
		// is finishing it in this browser: a meta_connect link forwarded to someone
		// else would otherwise bind THEIR Meta identity to the sender (login CSRF).
		// Show both identities and require an explicit confirm click.
		const rec: MetaUserToken = { token, fb_name: me?.name, fb_id: me?.id, obtained: new Date().toISOString() };
		const nonce = crypto.randomUUID();
		await c.env.OAUTH_KV.put(`meta_pending:${nonce}`, JSON.stringify({ email, rec }), { expirationTtl: 600 });
		return c.html(
			`<h2>Confirm Meta connection</h2>
<p>Facebook signed you in as <b>${escapeHtml(me?.name ?? "?")}</b> (id ${escapeHtml(String(me?.id ?? "?"))}).</p>
<p>This link was started by server user <b>${escapeHtml(email)}</b>. If you confirm, Meta writes made by <b>${escapeHtml(email)}</b> through this server will act (and be logged by Meta) as <b>${escapeHtml(me?.name ?? "?")}</b> for about 60 days.</p>
<p><b>Only confirm if both are you.</b> If someone sent you this link, close this tab.</p>
<form method="post" action="/meta/confirm"><input type="hidden" name="nonce" value="${nonce}"><button type="submit">Yes, connect ${escapeHtml(me?.name ?? "this identity")} to ${escapeHtml(email)}</button></form>`,
			200,
			{ "X-Frame-Options": "DENY", "Content-Security-Policy": "frame-ancestors 'none'", "Cache-Control": "no-store" },
		);
	});

	app.post("/meta/confirm", async (c) => {
		let nonce = "";
		try {
			nonce = String((await c.req.raw.formData()).get("nonce") ?? "");
		} catch {
			return c.text("missing confirmation", 400);
		}
		if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/.test(nonce)) return c.text("bad confirmation", 400);
		const raw = await c.env.OAUTH_KV.get(`meta_pending:${nonce}`);
		if (!raw) return c.text("confirmation expired or already used — re-run meta_connect", 403);
		await c.env.OAUTH_KV.delete(`meta_pending:${nonce}`);
		const { email, rec } = JSON.parse(raw) as { email: string; rec: MetaUserToken };
		await c.env.OAUTH_KV.put(`meta_user_token:${email}`, JSON.stringify(rec));
		console.log(
			JSON.stringify({ audit: true, user: email, tool: "meta_callback", resource: `fb:${rec.fb_name ?? "?"} (${rec.fb_id ?? "?"})`, ts: new Date().toISOString() }),
		);
		return c.html(
			`<h2>Meta connected</h2><p><b>${escapeHtml(rec.fb_name ?? "?")}</b> is now the Meta identity for <b>${escapeHtml(email)}</b> on this server. Writes will act (and be logged by Meta) as this person. Token lasts ~60 days — re-run meta_connect when it expires. You can close this tab.</p>`,
		);
	});
}
