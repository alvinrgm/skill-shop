#!/usr/bin/env node
// Mint a Google Ads API refresh token with YOUR OWN OAuth client.
//
// Usage (from the package root):
//   node scripts/mint-google-ads-refresh-token.mjs            # prints the token
//   node scripts/mint-google-ads-refresh-token.mjs --write-env  # writes it to .env instead
//
// Needs in .env (or the environment):
//   GOOGLE_ADS_CLIENT_ID, GOOGLE_ADS_CLIENT_SECRET
//   from a "Desktop app" OAuth client in YOUR Google Cloud project (SETUP.md,
//   section "Google Ads"). Desktop clients accept any http://127.0.0.1:<port>
//   redirect, so nothing has to be registered.
//
// What it does: starts a one-shot local web server on 127.0.0.1, prints a Google
// consent URL, you sign in with the Google account that can see your Google Ads
// accounts, Google redirects back to the local server, and the script exchanges
// the code for a refresh token. Node 20+ built-ins only, nothing to install.

import http from "node:http";
import crypto from "node:crypto";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const ENV_PATH = process.env.ACCOUNT_CONNECTORS_ENV || path.join(ROOT, ".env");
const PORT = Number(process.env.MINT_PORT || 8765);
const SCOPE = "https://www.googleapis.com/auth/adwords";

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

function upsertEnv(file, key, value) {
	let text = fs.existsSync(file) ? fs.readFileSync(file, "utf8") : "";
	const re = new RegExp(`^${key}=.*$`, "m");
	text = re.test(text) ? text.replace(re, `${key}=${value}`) : `${text.replace(/\n?$/, "\n")}${key}=${value}\n`;
	fs.writeFileSync(file, text, { mode: 0o600 });
}

const env = { ...loadEnv(ENV_PATH), ...process.env };
const clientId = env.GOOGLE_ADS_CLIENT_ID;
const clientSecret = env.GOOGLE_ADS_CLIENT_SECRET;
if (!clientId || !clientSecret) {
	console.error(
		"GOOGLE_ADS_CLIENT_ID and GOOGLE_ADS_CLIENT_SECRET must be set in .env first.\n" +
			"Create them in YOUR Google Cloud project: APIs & Services > Credentials > Create credentials >\n" +
			"OAuth client ID > Application type: Desktop app. See SETUP.md, section 'Google Ads'.",
	);
	process.exit(2);
}

const writeEnv = process.argv.includes("--write-env");
const redirectUri = `http://127.0.0.1:${PORT}/callback`;
const state = crypto.randomBytes(16).toString("hex");
const verifier = crypto.randomBytes(32).toString("base64url");
const challenge = crypto.createHash("sha256").update(verifier).digest("base64url");

const auth = new URL("https://accounts.google.com/o/oauth2/v2/auth");
auth.searchParams.set("client_id", clientId);
auth.searchParams.set("redirect_uri", redirectUri);
auth.searchParams.set("response_type", "code");
auth.searchParams.set("scope", SCOPE);
auth.searchParams.set("access_type", "offline");
auth.searchParams.set("prompt", "consent"); // always return a refresh token
auth.searchParams.set("state", state);
auth.searchParams.set("code_challenge", challenge);
auth.searchParams.set("code_challenge_method", "S256");

const server = http.createServer(async (req, res) => {
	const url = new URL(req.url, redirectUri);
	if (url.pathname !== "/callback") {
		res.writeHead(404).end();
		return;
	}
	const finish = (code, msg) => {
		res.writeHead(code, { "Content-Type": "text/plain; charset=utf-8" }).end(msg);
		server.close();
	};
	if (url.searchParams.get("error")) {
		console.error(`Google returned an error: ${url.searchParams.get("error")}`);
		finish(400, "Google returned an error. Check the terminal.");
		process.exitCode = 1;
		return;
	}
	if (url.searchParams.get("state") !== state) {
		finish(400, "State mismatch. Re-run the script.");
		process.exitCode = 1;
		return;
	}
	const tokenRes = await fetch("https://oauth2.googleapis.com/token", {
		method: "POST",
		headers: { "Content-Type": "application/x-www-form-urlencoded" },
		body: new URLSearchParams({
			code: url.searchParams.get("code") ?? "",
			client_id: clientId,
			client_secret: clientSecret,
			redirect_uri: redirectUri,
			grant_type: "authorization_code",
			code_verifier: verifier,
		}),
	});
	const body = await tokenRes.json().catch(() => ({}));
	if (!tokenRes.ok || !body.refresh_token) {
		console.error(`Token exchange failed (${tokenRes.status}): ${JSON.stringify(body)}`);
		finish(500, "Token exchange failed. Check the terminal.");
		process.exitCode = 1;
		return;
	}
	if (writeEnv) {
		upsertEnv(ENV_PATH, "GOOGLE_ADS_REFRESH_TOKEN", body.refresh_token);
		console.log(`\nGOOGLE_ADS_REFRESH_TOKEN written to ${ENV_PATH}.`);
	} else {
		console.log(`\nGOOGLE_ADS_REFRESH_TOKEN=${body.refresh_token}`);
	}
	console.log(
		"Next: bash scripts/push-secrets.sh   (or: npx wrangler secret put GOOGLE_ADS_REFRESH_TOKEN)\n" +
			"Note: if your OAuth consent screen is External and still in 'Testing', Google expires this\n" +
			"refresh token after 7 days. See SETUP.md, section 'Google Ads', for the fix.",
	);
	finish(200, "Done. You can close this tab and go back to the terminal.");
});

server.listen(PORT, "127.0.0.1", () => {
	console.log("Open this URL in your browser and sign in with the Google account that can see your Google Ads accounts:\n");
	console.log(auth.href);
	console.log(`\nWaiting for Google to redirect to ${redirectUri} ...`);
});
