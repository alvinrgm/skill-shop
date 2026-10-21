// Shared helpers: Google fetch w/ per-user token refresh, JSON tool output,
// and the contentBlocks -> Google Docs batchUpdate engine (a rich block schema:
// headings, runs, bullets, tables, callouts, dividers).

export type Props = {
	name: string;
	email: string;
	accessToken: string;
	refreshToken?: string;
};

// Some MCP clients (claude.ai connector proxy, some Claude Code builds) deliver
// array/object params as JSON STRINGS. zod then rejects with "expected array,
// received string" and the tool is unusable from that client. `jsonish` widens a
// schema to also accept a string; `coerce` parses it back. Apply to EVERY
// array/object tool param.
export function coerce<T>(v: T | string): T {
	if (typeof v === "string") {
		const t = v.trim();
		if (t.startsWith("[") || t.startsWith("{")) {
			try { return JSON.parse(t) as T; } catch { /* fall through */ }
		}
	}
	return v as T;
}

export function jtext(data: unknown) {
	return { content: [{ type: "text" as const, text: JSON.stringify(data) }] };
}

// Strip access tokens from any URLs embedded in an API response (Graph paging
// URLs echo the request's access_token back — never hand server-held or user
// tokens to MCP callers).
export function scrubTokens<T>(data: T): T {
	if (data == null) return data;
	return JSON.parse(JSON.stringify(data).replace(/access_token=[^&"\\]+/g, "access_token=REDACTED"));
}

// ---------- Google id + URL guards (every Google tool) ----------
// Every *_id / *_ids parameter of a Google tool must be a plain Google id. Drive,
// Docs, Sheets, Slides, Gmail message/thread and Drive comment ids all use only
// [A-Za-z0-9_-], so anything else ('#', '?', '/', '../', '%2e', whitespace) is an
// injection attempt: "VICTIM#" would otherwise turn ".../files/VICTIM#/comments/c"
// into DELETE /drive/v3/files/VICTIM.
export const GOOGLE_ID_RE = /^[A-Za-z0-9_-]{1,200}$/;

export function googleIdProblem(args: unknown): string | null {
	if (!args || typeof args !== "object") return null;
	for (const [k, v] of Object.entries(args as Record<string, unknown>)) {
		if (!/(^|_)ids?$/.test(k)) continue;
		for (const x of Array.isArray(v) ? v : [v]) {
			if (x === undefined || x === null || x === "") continue;
			if (typeof x !== "string" || !GOOGLE_ID_RE.test(x))
				return `${k} must be a Google id (letters, digits, '-' and '_' only); got ${JSON.stringify(String(x)).slice(0, 80)}`;
		}
	}
	return null;
}

// Wrap a server so every tool registered through it refuses bad ids up front.
export function guardGoogleIds<S extends object>(server: S): S {
	return new Proxy(server, {
		get(target, prop, recv) {
			const v = Reflect.get(target, prop, recv);
			if (prop !== "tool" || typeof v !== "function") return v;
			return (...a: any[]) => {
				const cb = a[a.length - 1];
				if (typeof cb === "function")
					a[a.length - 1] = async (args: any, extra: any) => {
						const p = googleIdProblem(args);
						return p ? jtext({ refused: true, reason: p }) : cb(args, extra);
					};
				return v.apply(target, a);
			};
		},
	});
}

// Second wall, on the URL actually requested: a known Google host, the path the
// parser produces must equal the path written (no '..', '.', '%2e' or backslash
// normalisation, no '#'), it must sit under that host's allowed prefixes, and
// nothing may ever reach a Gmail send endpoint.
const GOOGLE_PREFIXES: Record<string, string[]> = {
	"www.googleapis.com": ["/drive/v3", "/upload/drive/v3", "/gmail/v1/users/me/messages", "/gmail/v1/users/me/drafts", "/gmail/v1/users/me/threads", "/calendar/v3"],
	"docs.googleapis.com": ["/v1/documents"],
	"sheets.googleapis.com": ["/v4/spreadsheets"],
	"slides.googleapis.com": ["/v1/presentations"],
};

export function googleUrlProblem(url: string): string | null {
	let u: URL;
	try {
		u = new URL(url);
	} catch {
		return "not a valid URL";
	}
	const prefixes = Object.prototype.hasOwnProperty.call(GOOGLE_PREFIXES, u.hostname) ? GOOGLE_PREFIXES[u.hostname] : undefined;
	if (u.protocol !== "https:" || !prefixes) return `host ${u.hostname} is not an allowed Google API host`;
	if (url.includes("#")) return "URL contains '#'";
	const written = url.split("?")[0];
	if (written !== `${u.origin}${u.pathname}`) return "URL path is not in canonical form (dot segments, encoded dots or backslashes)";
	if (!prefixes.some((p) => u.pathname === p || u.pathname.startsWith(`${p}/`) || u.pathname.startsWith(`${p}:`)))
		return `path ${u.pathname} is outside the allowed Google API prefixes`;
	if (/\/send$|:send$|\/send\//.test(u.pathname)) return "Gmail send endpoints are never reachable";
	return null;
}

export async function googleFetch(url: string, init: RequestInit = {}): Promise<Response> {
	const p = googleUrlProblem(url);
	if (p) return Response.json({ refused: true, reason: p }, { status: 400 });
	return fetch(url, init);
}

export async function gfetch(
	token: string,
	url: string,
	init: RequestInit = {},
): Promise<{ ok: boolean; status: number; body: any }> {
	const res = await googleFetch(url, {
		...init,
		headers: {
			Authorization: `Bearer ${token}`,
			"Content-Type": "application/json",
			...(init.headers ?? {}),
		},
	});
	let body: any = null;
	try {
		body = await res.json();
	} catch {
		body = await res.text().catch(() => null);
	}
	return { ok: res.ok, status: res.status, body };
}

// Mint a fresh Google access token from a refresh token (form-encoded).
export async function refreshGoogleToken(
	env: Env,
	refreshToken: string,
): Promise<{ token: string; expiresAt: number } | { error: string }> {
	const res = await fetch("https://oauth2.googleapis.com/token", {
		method: "POST",
		headers: { "Content-Type": "application/x-www-form-urlencoded" },
		body: new URLSearchParams({
			client_id: env.GOOGLE_CLIENT_ID,
			client_secret: env.GOOGLE_CLIENT_SECRET,
			refresh_token: refreshToken,
			grant_type: "refresh_token",
		}).toString(),
	});
	const body: any = await res.json().catch(() => ({}));
	if (!res.ok || !body.access_token) return { error: `refresh failed (${res.status})` };
	return { token: body.access_token, expiresAt: Date.now() + (body.expires_in - 60) * 1000 };
}

// ---------- contentBlocks -> Docs batchUpdate engine ----------

export type Run = {
	text: string;
	bold?: boolean;
	italic?: boolean;
	strikethrough?: boolean;
	color?: string;
	bg?: string;
	link?: string;
	size?: number;
};
export type Cell = string | { text?: string; runs?: Run[]; bold?: boolean; color?: string; bg?: string };
export type Block =
	| { type: "heading1" | "heading2" | "heading3"; text?: string; runs?: Run[] }
	| { type: "paragraph"; text?: string; runs?: Run[]; align?: "LEFT" | "CENTER" | "RIGHT" }
	| { type: "bullet" | "numbered"; text?: string; runs?: Run[]; nesting?: number }
	| { type: "divider" }
	| { type: "table"; rows: Cell[][]; headerRow?: boolean; headerBg?: string; headerFg?: string }
	| { type: "callout"; text?: string; runs?: Run[]; bg?: string };

export function hexToRgb(hex: string) {
	const h = hex.replace("#", "");
	return {
		red: parseInt(h.slice(0, 2), 16) / 255,
		green: parseInt(h.slice(2, 4), 16) / 255,
		blue: parseInt(h.slice(4, 6), 16) / 255,
	};
}

function runsOf(b: { text?: string; runs?: Run[] }): Run[] {
	if (b.runs?.length) return b.runs;
	return [{ text: b.text ?? "" }];
}

function textStyleFor(r: Run): { style: any; fields: string[] } {
	const style: any = {};
	const fields: string[] = [];
	if (r.bold !== undefined) (style.bold = r.bold), fields.push("bold");
	if (r.italic !== undefined) (style.italic = r.italic), fields.push("italic");
	if (r.strikethrough !== undefined) (style.strikethrough = r.strikethrough), fields.push("strikethrough");
	if (r.color) (style.foregroundColor = { color: { rgbColor: hexToRgb(r.color) } }), fields.push("foregroundColor");
	if (r.bg) (style.backgroundColor = { color: { rgbColor: hexToRgb(r.bg) } }), fields.push("backgroundColor");
	if (r.link) (style.link = { url: r.link }), fields.push("link");
	if (r.size) (style.fontSize = { magnitude: r.size, unit: "PT" }), fields.push("fontSize");
	return { style, fields };
}

async function docEndIndex(token: string, docId: string): Promise<number> {
	const r = await gfetch(token, `https://docs.googleapis.com/v1/documents/${docId}?fields=body(content(endIndex))`);
	if (!r.ok) throw new Error(`docs.get failed ${r.status}`);
	const content = r.body.body.content as { endIndex?: number }[];
	return content[content.length - 1].endIndex ?? 1;
}

async function docBatch(token: string, docId: string, requests: any[]) {
	if (!requests.length) return;
	const r = await gfetch(token, `https://docs.googleapis.com/v1/documents/${docId}:batchUpdate`, {
		method: "POST",
		body: JSON.stringify({ requests }),
	});
	if (!r.ok) throw new Error(`batchUpdate failed ${r.status}: ${JSON.stringify(r.body).slice(0, 400)}`);
}

// Append text-flavored blocks (headings/paragraphs/bullets/divider) in ONE
// batchUpdate with locally tracked indices; tables/callouts go through the
// slower structural path (insert, re-read, fill cells reverse-order, style).
//
// `at` switches the engine from APPEND to INSERT-AT-INDEX for prepend /
// insert_blocks_at. Left undefined, the engine appends (endOfSegmentLocation + "last table" lookup). Returns the cursor just
// past the last rendered block, so callers can chain.
export async function appendBlocksToDoc(token: string, docId: string, blocks: Block[], at?: number): Promise<number> {
	let i = 0;
	// The cursor is threaded between groups ONLY when inserting. In append mode
	// every group must keep getting `undefined`, or the second group onward would
	// silently flip to insert-at-index.
	const inserting = at !== undefined;
	let cursor = at;
	while (i < blocks.length) {
		const b = blocks[i];
		if (b.type === "table" || b.type === "callout") {
			const end = await appendTable(token, docId, b, inserting ? cursor : undefined);
			if (inserting) cursor = end;
			i++;
			continue;
		}
		// batch consecutive text blocks
		const batch: Block[] = [];
		while (i < blocks.length && blocks[i].type !== "table" && blocks[i].type !== "callout") {
			batch.push(blocks[i]);
			i++;
		}
		const end = await appendTextBlocks(token, docId, batch, inserting ? cursor : undefined);
		if (inserting) cursor = end;
	}
	return cursor ?? (await docEndIndex(token, docId)) - 1;
}

async function appendTextBlocks(token: string, docId: string, blocks: Block[], at?: number): Promise<number> {
	let idx = at ?? (await docEndIndex(token, docId)) - 1;
	const inserts: any[] = [];
	const styles: any[] = [];
	for (const b of blocks) {
		if (b.type === "divider") {
			inserts.push({ insertText: { location: { index: idx }, text: "\n" } });
			styles.push({
				updateParagraphStyle: {
					range: { startIndex: idx, endIndex: idx + 1 },
					paragraphStyle: {
						borderBottom: {
							color: { color: { rgbColor: hexToRgb("#CCCCCC") } },
							width: { magnitude: 1, unit: "PT" },
							padding: { magnitude: 4, unit: "PT" },
							dashStyle: "SOLID",
						},
					},
					fields: "borderBottom",
				},
			});
			idx += 1;
			continue;
		}
		const runs = runsOf(b as any);
		const paraStart = idx;
		for (const r of runs) {
			if (!r.text) continue;
			inserts.push({ insertText: { location: { index: idx }, text: r.text } });
			const { style, fields } = textStyleFor(r);
			if (fields.length)
				styles.push({
					updateTextStyle: { range: { startIndex: idx, endIndex: idx + r.text.length }, textStyle: style, fields: fields.join(",") },
				});
			idx += r.text.length;
		}
		inserts.push({ insertText: { location: { index: idx }, text: "\n" } });
		idx += 1;
		const paraRange = { startIndex: paraStart, endIndex: idx };
		if (b.type.startsWith("heading")) {
			styles.push({
				updateParagraphStyle: {
					range: paraRange,
					paragraphStyle: { namedStyleType: `HEADING_${b.type.slice(-1)}` },
					fields: "namedStyleType",
				},
			});
		}
		if (b.type === "paragraph" && (b as any).align && (b as any).align !== "LEFT") {
			styles.push({
				updateParagraphStyle: {
					range: paraRange,
					paragraphStyle: { alignment: (b as any).align === "CENTER" ? "CENTER" : "END" },
					fields: "alignment",
				},
			});
		}
		if (b.type === "bullet" || b.type === "numbered") {
			styles.push({
				createParagraphBullets: {
					range: paraRange,
					bulletPreset: b.type === "bullet" ? "BULLET_DISC_CIRCLE_SQUARE" : "NUMBERED_DECIMAL_ALPHA_ROMAN",
				},
			});
		}
	}
	await docBatch(token, docId, [...inserts, ...styles]);
	return idx;
}

async function appendTable(token: string, docId: string, b: Block, at?: number): Promise<number> {
	const isCallout = b.type === "callout";
	const rows: Cell[][] = isCallout ? [[{ runs: runsOf(b as any) }]] : (b as any).rows;
	const nRows = rows.length;
	const nCols = Math.max(...rows.map((r) => r.length));
	await docBatch(token, docId, [
		{
			insertTable:
				at === undefined
					? { rows: nRows, columns: nCols, endOfSegmentLocation: { segmentId: "" } }
					: { rows: nRows, columns: nCols, location: { index: at } },
		},
	]);
	// re-read to find the table we just wrote. Appending: it is the LAST table.
	// Inserting at `at`: everything that used to sit at >= at shifted right, so ours
	// is the FIRST table whose startIndex >= at.
	const r = await gfetch(
		token,
		`https://docs.googleapis.com/v1/documents/${docId}?fields=body(content(startIndex,endIndex,table))`,
	);
	if (!r.ok) throw new Error(`docs.get failed ${r.status}`);
	const els = (r.body.body.content as any[]).filter((e) => e.table);
	const tbl = at === undefined ? els[els.length - 1] : els.filter((e) => e.startIndex >= at)[0];
	if (!tbl) throw new Error("could not locate the table just inserted");
	const tableStart = tbl.startIndex;
	// collect per-cell insertion points; fill in REVERSE so indices stay valid
	const cellOps: { at: number; runs: Run[] }[] = [];
	tbl.table.tableRows.forEach((row: any, ri: number) => {
		row.tableCells.forEach((cell: any, ci: number) => {
			const raw = rows[ri]?.[ci];
			if (raw === undefined) return;
			const runs: Run[] =
				typeof raw === "string"
					? [{ text: raw }]
					: raw.runs?.length
						? raw.runs
						: [{ text: raw.text ?? "", bold: raw.bold, color: raw.color }];
			cellOps.push({ at: cell.content[0].startIndex, runs });
		});
	});
	cellOps.sort((a, z) => z.at - a.at);
	const reqs: any[] = [];
	for (const op of cellOps) {
		let at = op.at;
		// styles first in the final array? no: per-cell, insert then style, all
		// within this reverse walk so earlier indices are untouched.
		const local: any[] = [];
		for (const run of op.runs) {
			if (!run.text) continue;
			local.push({ insertText: { location: { index: at }, text: run.text } });
			const { style, fields } = textStyleFor(run);
			if (fields.length)
				local.push({
					updateTextStyle: { range: { startIndex: at, endIndex: at + run.text.length }, textStyle: style, fields: fields.join(",") },
				});
			at += run.text.length;
		}
		reqs.push(...local);
	}
	await docBatch(token, docId, reqs);
	// header / callout shading via tableStartLocation (index-math-free)
	const shade: any[] = [];
	const headerRow = !isCallout && (b as any).headerRow;
	const bg = isCallout ? ((b as any).bg ?? "#FBF3E2") : ((b as any).headerBg ?? "#D94127");
	if (isCallout || headerRow) {
		shade.push({
			updateTableCellStyle: {
				tableRange: {
					tableCellLocation: { tableStartLocation: { index: tableStart }, rowIndex: 0, columnIndex: 0 },
					rowSpan: 1,
					columnSpan: isCallout ? 1 : nCols,
				},
				tableCellStyle: { backgroundColor: { color: { rgbColor: hexToRgb(bg) } } },
				fields: "backgroundColor",
			},
		});
	}
	if (headerRow) {
		// bold + color the header row text (re-read for fresh ranges — same
		// last-table / first-table-at-or-after rule as the lookup above)
		const r2 = await gfetch(
			token,
			`https://docs.googleapis.com/v1/documents/${docId}?fields=body(content(startIndex,endIndex,table))`,
		);
		const els2 = (r2.body.body.content as any[]).filter((e: any) => e.table);
		const tbl2 = at === undefined ? els2[els2.length - 1] : els2.filter((e: any) => e.startIndex >= at)[0];
		const fg = (b as any).headerFg ?? "#FFFFFF";
		for (const cell of tbl2.table.tableRows[0].tableCells) {
			const cs = cell.content[0].startIndex;
			const ce = cell.content[cell.content.length - 1].endIndex - 1;
			if (ce > cs)
				shade.push({
					updateTextStyle: {
						range: { startIndex: cs, endIndex: ce },
						textStyle: { bold: true, foregroundColor: { color: { rgbColor: hexToRgb(fg) } } },
						fields: "bold,foregroundColor",
					},
				});
		}
	}
	await docBatch(token, docId, shade);
	// cursor just past the table: its pre-fill endIndex plus every character we
	// inserted into its cells (shading changes no indices).
	const inserted = cellOps.reduce((n, op) => n + op.runs.reduce((m, r) => m + (r.text?.length ?? 0), 0), 0);
	return (tbl.endIndex as number) + inserted;
}

// Index just after the document's first heading (or TITLE) paragraph — the
// insertion point for update_doc's `after_first_heading`. Returns 1 (the first
// legal body index) when the doc has no heading at all.
export async function docFirstHeadingEnd(token: string, docId: string): Promise<number> {
	const r = await gfetch(
		token,
		`https://docs.googleapis.com/v1/documents/${docId}?fields=body(content(endIndex,paragraph(paragraphStyle(namedStyleType))))`,
	);
	if (!r.ok) throw new Error(`docs.get failed ${r.status}`);
	const content = (r.body.body?.content ?? []) as any[];
	// max legal insertion index: one before the body's own end marker
	const bodyEnd = (content[content.length - 1]?.endIndex ?? 2) - 1;
	for (const el of content) {
		const named = el.paragraph?.paragraphStyle?.namedStyleType as string | undefined;
		if (named && (named.startsWith("HEADING_") || named === "TITLE" || named === "SUBTITLE"))
			// start of the paragraph AFTER the heading: new content lands as its own
			// paragraph and inherits normal text, not the heading's style
			return Math.min(el.endIndex as number, bodyEnd);
	}
	return 1;
}
