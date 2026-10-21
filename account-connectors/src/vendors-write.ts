// Meta WRITE tools: the gated mutate layer.
//
// Every write requires ALL FOUR, in order:
//   1. a per-user Meta OAuth token (meta_connect): the write executes AS the
//      caller and Meta's activity log attributes it to their real identity;
//      Meta's own asset permissions are the outer wall (no access = no write)
//   2. the server ACL (same aclAllows as reads)
//   3. a live single-use approval slip (approve_change) whose resource matches
//      the target ad account, consumed before acting
//   4. the audit log line (who, tool, resource, approval description)
//
// The tool surface is deliberately generic (upload + mutate + delete) rather than
// one tool per entity type: the Graph API is uniform, and the gate, not the tool
// list, is the safety layer. adimages accepts base64 `bytes`, so no public image
// hosting is ever needed. The server's System User token (meta_get) never signs
// a write.

import type { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { z } from "zod";
import { jtext, scrubTokens } from "./lib";
import { aclAllows, audit, consumeApproval, metaGraphTarget, resolveClient, signInAllowed, unsafeReason } from "./gate";
import { getMetaUserToken, metaConnectHint, META_API_VERSION, workerBase } from "./meta-oauth";

// Some MCP clients deliver object params as JSON strings (degraded schemas).
// Accept both: parse strings into records before use.
function coerceRecord(v: any): Record<string, any> {
	if (typeof v === "string") { try { return JSON.parse(v); } catch { return {}; } }
	return v ?? {};
}


// Resolve the owning ad account of any Graph object so the ACL + approval slip
// always gate on act_<id>, even when the tool call targets a bare entity id.
async function owningAccount(token: string, pathFirstSeg: string): Promise<string | null> {
	if (unsafeReason(pathFirstSeg) || !/^[A-Za-z0-9_]+$/.test(pathFirstSeg)) return null;
	if (/^act_\d+$/.test(pathFirstSeg)) return pathFirstSeg;
	const res = await fetch(
		`https://graph.facebook.com/${META_API_VERSION}/${pathFirstSeg}?fields=account_id&access_token=${token}`,
	);
	const body: any = await res.json().catch(() => null);
	return body?.account_id && /^\d+$/.test(String(body.account_id)) ? `act_${body.account_id}` : null;
}

function formEncode(params: Record<string, unknown>): URLSearchParams {
	const out = new URLSearchParams();
	for (const [k, v] of Object.entries(params)) {
		if (v === undefined || v === null) continue;
		out.set(k, typeof v === "string" ? v : JSON.stringify(v));
	}
	return out;
}

// Meta deprecated location_types ("people living in / travelling to / recently
// in", error #1870194). Ad sets created before the change still CARRY the dead
// field; any API copy inherits it and publish fails. Scrub it from every
// outbound targeting payload — the server-side version of the UI's
// edit-locations-and-republish dance.
function scrubTargeting(params: Record<string, any>): { params: Record<string, any>; scrubbed: string[] } {
	const scrubbed: string[] = [];
	const p = { ...params };
	if (p.targeting) {
		let t = p.targeting;
		const wasString = typeof t === "string";
		try {
			if (wasString) t = JSON.parse(t);
		} catch {
			return { params: p, scrubbed };
		}
		if (t && typeof t === "object") {
			// Meta deprecated location_types (living in / recently in / travelling)
			// — submitting them fails publish with #1870194. Old ad sets carry
			// them; strip on every write so clones just work.
			if (t.geo_locations?.location_types) {
				delete t.geo_locations.location_types;
				scrubbed.push("geo_locations.location_types");
			}
			if (t.excluded_geo_locations?.location_types) {
				delete t.excluded_geo_locations.location_types;
				scrubbed.push("excluded_geo_locations.location_types");
			}
			// Deprecated placement (v23+): "video_feeds" — old ad sets carry it;
			// submitting fails with subcode 2490562. Same treatment.
			if (Array.isArray(t.facebook_positions) && t.facebook_positions.includes("video_feeds")) {
				t.facebook_positions = t.facebook_positions.filter((x: string) => x !== "video_feeds");
				scrubbed.push("facebook_positions.video_feeds");
			}
			p.targeting = wasString ? JSON.stringify(t) : t;
		}
	}
	return { params: p, scrubbed };
}

export function registerMetaWrites(server: McpServer, env: Env, whoami: () => string) {
	if (!env.META_APP_ID) return; // per-user OAuth not configured -> no write surface at all

	const guard = async (
		pathFirstSeg: string,
		approval_id: string,
	): Promise<{ token: string; acct: string; approved: string } | { error: object }> => {
		const email = whoami();
		// Re-check the sign-in allowlist on EVERY write, so removing someone from
		// ALLOWED_EMAILS / ALLOWED_DOMAINS stops their writes even mid-session.
		const access = signInAllowed(env, email ?? "", true);
		if (!access.ok) return { error: { refused: true, status: "access_revoked", reason: access.reason } };
		const t = await getMetaUserToken(env, email);
		if (!t) return { error: metaConnectHint("") };
		const acct = await owningAccount(t.token, resolveClient(env, pathFirstSeg, "meta"));
		if (!acct) return { error: { error: `cannot resolve the owning ad account of '${pathFirstSeg}'` } };
		if (!aclAllows(env, email, "meta", acct))
			return { error: { refused: true, reason: `${email} is not authorized for ${acct} (server ACL)` } };
		const ap = await consumeApproval(env, approval_id, "meta", acct, email);
		if (!ap.ok)
			return {
				error: {
					refused: true,
					reason: `approval gate: ${ap.reason}`,
					fix: "restate the exact change to YOUR human, get their explicit yes in chat, then mint a slip with approve_change and retry with its approval_id",
				},
			};
		return { token: t.token, acct, approved: ap.description };
	};

	// An upload target must be an ad account: CLIENTS slug, act_<id>, or bare digits.
	const normAccount = (account: string): string => {
		const a = String(resolveClient(env, String(account ?? "").trim(), "meta") ?? "");
		return /^\d+$/.test(a) ? `act_${a}` : a;
	};

	// Direct disk -> worker -> Meta upload. The MCP tool mints a
	// single-use ticket URL; ONE curl pushes the file from the operator's disk to
	// POST /meta/upload/<ticket> (meta-oauth.ts route), which relays the bytes to
	// Graph adimages as multipart and returns the hash. Image bytes never transit
	// the model context (base64-in-params costs ~1 token/char — a 1080px image is
	// ~200k tokens; the ticket + hash are ~50). The approval slip is consumed HERE,
	// at mint time; the ticket carries its authorization (bearer: 122-bit UUID,
	// single-use, short TTL, bound to one act_ id + one signed-in user).
	server.tool(
		"meta_upload_begin",
		"Start a direct IMAGE or VIDEO upload into an ad account's library WITHOUT base64-ing the bytes through chat: returns a single-use upload URL; push the file with `curl -F \"filename=@/path/to/file\" <upload_url>` (Bash). Requires meta_connect + a single-use approval slip for the account (consumed now). Ticket expires in ttl_minutes; one upload only. IMAGE (kind='image', default) -> Graph adimages, returns the image hash immediately (use for the creative's image_hash). VIDEO (kind='video') -> Graph advideos, returns a video_id; video ingestion is ASYNC — poll meta_video_status until 'ready' before building the creative. Preferred over meta_upload_image for any real-size file; the only path for video.",
		{
			account: z.string().describe("act_<id>, bare numeric id, or a CLIENTS slug"),
			approval_id: z.string(),
			kind: z.enum(["image", "video"]).default("image").describe("image -> adimages (hash); video -> advideos (video_id, async)"),
			ttl_minutes: z.number().int().min(2).max(60).default(15),
		},
		async ({ account, approval_id, kind, ttl_minutes }) => {
			const g = await guard(normAccount(account), approval_id);
			if ("error" in g) return jtext(g.error);
			const ticket = crypto.randomUUID();
			await env.OAUTH_KV.put(
				`upload_ticket:${ticket}`,
				JSON.stringify({ email: whoami(), acct: g.acct, approved: g.approved, kind, at: new Date().toISOString() }),
				{ expirationTtl: ttl_minutes * 60 },
			);
			audit(whoami(), "meta_upload_begin", `${g.acct} :: ${kind} :: approved: ${g.approved.slice(0, 100)}`);
			const base = workerBase(env);
			if (!base) return jtext({ error: "WORKER_BASE is not set on the server (wrangler secret put WORKER_BASE); upload URLs need it" });
			const isVideo = kind === "video";
			return jtext({
				upload_url: `${base}/meta/upload/${ticket}`,
				account: g.acct,
				kind,
				expires_in_minutes: ttl_minutes,
				single_use: true,
				how: `curl -sS -F "filename=@/path/to/${isVideo ? "ad.mp4" : "ad.png"}" "${base}/meta/upload/${ticket}"`,
				returns: isVideo
					? "Meta's advideos JSON — read `id` for the video_id, then poll meta_video_status until status='ready' before building the creative (video_data.video_id)"
					: "Meta's adimages JSON — read images.filename.hash for the creative's image_hash",
			});
		},
	);

	// Video ingestion is async: advideos returns a video_id immediately, but the
	// video is not usable in a creative until Meta finishes processing (seconds to
	// minutes). Poll this before building the creative.
	server.tool(
		"meta_video_status",
		"Check whether an uploaded video has finished Meta-side processing. Returns status_code: 'ready' (usable in a creative now), 'processing' (poll again in ~10s), or 'error'. Pass the video_id from a meta_upload_begin (kind='video') upload. Read-only, no approval needed — uses the caller's Meta token.",
		{ video_id: z.string() },
		async ({ video_id }) => {
			const email = whoami();
			if (!/^\d+$/.test(video_id)) return jtext({ refused: true, reason: "video_id must be digits" });
			const t = await getMetaUserToken(env, email);
			if (!t) return jtext(metaConnectHint(""));
			const res = await fetch(
				`https://graph.facebook.com/${META_API_VERSION}/${video_id}?fields=status&access_token=${t.token}`,
			);
			const body: any = await res.json().catch(() => null);
			if (!res.ok) return jtext(scrubTokens({ error: res.status, detail: body }));
			const code = body?.status?.video_status ?? "unknown";
			return jtext({
				video_id,
				status_code: code === "ready" ? "ready" : code === "error" ? "error" : "processing",
				meta_status: body?.status,
				next: code === "ready" ? "build the creative with video_data.video_id" : "poll again in ~10s",
			});
		},
	);

	server.tool(
		"meta_upload_image",
		"Upload a SMALL image from base64 into an ad account's image library; returns the image hash used by creatives. Base64 through chat costs ~1 token per character — for any real-size image use meta_upload_begin (direct file upload) instead. Requires meta_connect + a single-use approval slip for the account. Meta dedupes by content (same bytes -> same hash).",
		{
			account: z.string().describe("act_<id>, bare numeric id, or a CLIENTS slug"),
			image_base64: z.string().describe("the PNG/JPG bytes, base64-encoded"),
			approval_id: z.string(),
		},
		async ({ account, image_base64, approval_id }) => {
			const g = await guard(normAccount(account), approval_id);
			if ("error" in g) return jtext(g.error);
			audit(whoami(), "meta_upload_image", `${g.acct} :: approved: ${g.approved.slice(0, 100)}`);
			const res = await fetch(`https://graph.facebook.com/${META_API_VERSION}/${g.acct}/adimages`, {
				method: "POST",
				body: formEncode({ bytes: image_base64, access_token: g.token }),
			});
			const body: any = await res.json().catch(() => null);
			return jtext(scrubTokens(res.ok ? body : { error: res.status, detail: body }));
		},
	);

	server.tool(
		"meta_mutate",
		"Gated POST against the Meta Graph API, acting AS the connected user — create creatives (act_X/adcreatives), create ads (act_X/ads), update entities (POST <id> with {status:'PAUSED'} etc.). `path` without version prefix; object/array param values are JSON-encoded automatically. Requires meta_connect + a single-use approval slip matching the owning ad account. New ads should default {status:'PAUSED'}.",
		{
			path: z.string().describe("e.g. 'act_<id>/adcreatives', 'act_<id>/ads', or a bare entity id to update"),
			params: z.union([z.record(z.string(), z.any()), z.string()]),
			approval_id: z.string(),
		},
		async ({ path, params, approval_id }) => {
			params = coerceRecord(params);
			const tg = metaGraphTarget(env, path, META_API_VERSION);
			if (!tg.ok) return jtext({ refused: true, reason: tg.reason });
			// guard() gates on the first segment of the URL actually requested
			const g = await guard(tg.first, approval_id);
			if ("error" in g) return jtext(g.error);
			audit(whoami(), "meta_mutate", `${tg.path} :: approved: ${g.approved.slice(0, 100)}`);
			const sc = scrubTargeting(params);
			const res = await fetch(tg.url, {
				method: "POST",
				body: formEncode({ ...sc.params, access_token: g.token }),
			});
			const body: any = await res.json().catch(() => null);
			const extra = sc.scrubbed.length ? { scrubbed_deprecated_fields: sc.scrubbed } : {};
			return jtext(scrubTokens(res.ok ? { ...body, ...extra } : { error: res.status, detail: body, ...extra }));
		},
	);

	server.tool(
		"meta_delete",
		"Gated DELETE of one Meta Graph object (a creative, an image by hash via act_X/adimages?hash=, etc.), acting AS the connected user. Requires meta_connect + a single-use approval slip matching the owning ad account.",
		{
			object_id: z.string().describe("entity id, or 'act_<id>/adimages' with params.hash for image deletion"),
			params: z.union([z.record(z.string(), z.any()), z.string()]).optional(),
			approval_id: z.string(),
		},
		async ({ object_id, params, approval_id }) => {
			params = coerceRecord(params);
			const tg = metaGraphTarget(env, object_id, META_API_VERSION);
			if (!tg.ok) return jtext({ refused: true, reason: tg.reason });
			const g = await guard(tg.first, approval_id);
			if ("error" in g) return jtext(g.error);
			audit(whoami(), "meta_delete", `${tg.path} :: approved: ${g.approved.slice(0, 100)}`);
			const qs = formEncode({ ...(params ?? {}), access_token: g.token });
			const res = await fetch(`${tg.url}?${qs}`, {
				method: "DELETE",
			});
			const body: any = await res.json().catch(() => null);
			return jtext(scrubTokens(res.ok ? body : { error: res.status, detail: body }));
		},
	);
}
