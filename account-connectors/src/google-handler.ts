import type { AuthRequest, OAuthHelpers } from "@cloudflare/workers-oauth-provider";
import { Hono } from "hono";
import { fetchUpstreamAuthToken, getUpstreamAuthorizeUrl, type Props } from "./utils";
import { hostedDomainHint, signInAllowed } from "./gate";
import {
	addApprovedClient,
	bindStateToSession,
	createOAuthState,
	generateCSRFProtection,
	isClientApproved,
	OAuthError,
	renderApprovalDialog,
	validateCSRFToken,
	validateOAuthState,
} from "./workers-oauth-utils";

const app = new Hono<{ Bindings: Env & { OAUTH_PROVIDER: OAuthHelpers } }>();

app.get("/authorize", async (c) => {
	// parseAuthRequest throws on an unknown client_id or a redirect_uri the client
	// did not register: that is a bad request (400), not a server error.
	let oauthReqInfo: AuthRequest;
	try {
		oauthReqInfo = await c.env.OAUTH_PROVIDER.parseAuthRequest(c.req.raw);
	} catch (e: any) {
		return c.text(`Invalid authorization request: ${String(e?.description ?? e?.message ?? "unknown client or redirect_uri").slice(0, 200)}`, 400);
	}
	const { clientId } = oauthReqInfo;
	if (!clientId) {
		return c.text("Invalid request", 400);
	}
	const client = await c.env.OAUTH_PROVIDER.lookupClient(clientId);
	if (!client) return c.text("Invalid authorization request: unknown client_id", 400);

	// Check if client is already approved
	if (await isClientApproved(c.req.raw, clientId, c.env.COOKIE_ENCRYPTION_KEY)) {
		// Skip approval dialog but still create secure state and bind to session
		const { stateToken } = await createOAuthState(oauthReqInfo, c.env.OAUTH_KV);
		const { setCookie: sessionBindingCookie } = await bindStateToSession(stateToken);
		return redirectToGoogle(c.req.raw, c.env, stateToken, {
			"Set-Cookie": sessionBindingCookie,
		});
	}

	// Generate CSRF protection for the approval form
	const { token: csrfToken, setCookie } = generateCSRFProtection();

	return renderApprovalDialog(c.req.raw, {
		client,
		csrfToken,
		server: {
			description: "Account connectors: Google Drive, Docs, Sheets, Slides, Gmail (drafts only), Calendar acting as YOUR Google account, plus read-only ad account and store data.",
			name: "Account connectors",
		},
		setCookie,
		state: { oauthReqInfo },
	});
});

app.post("/authorize", async (c) => {
	try {
		// Read form data once
		const formData = await c.req.raw.formData();

		// Validate CSRF token
		validateCSRFToken(formData, c.req.raw);

		// Extract state from form data
		const encodedState = formData.get("state");
		if (!encodedState || typeof encodedState !== "string") {
			return c.text("Missing state in form data", 400);
		}

		let state: { oauthReqInfo?: AuthRequest };
		try {
			state = JSON.parse(atob(encodedState));
		} catch (_e) {
			return c.text("Invalid state data", 400);
		}

		if (!state.oauthReqInfo || !state.oauthReqInfo.clientId) {
			return c.text("Invalid request", 400);
		}

		// Add client to approved list
		const approvedClientCookie = await addApprovedClient(
			c.req.raw,
			state.oauthReqInfo.clientId,
			c.env.COOKIE_ENCRYPTION_KEY,
		);

		// Create OAuth state and bind it to this user's session
		const { stateToken } = await createOAuthState(state.oauthReqInfo, c.env.OAUTH_KV);
		const { setCookie: sessionBindingCookie } = await bindStateToSession(stateToken);

		// Set both cookies: approved client list + session binding
		const headers = new Headers();
		headers.append("Set-Cookie", approvedClientCookie);
		headers.append("Set-Cookie", sessionBindingCookie);

		return redirectToGoogle(c.req.raw, c.env, stateToken, headers);
	} catch (error: any) {
		console.error("POST /authorize error:", error);
		if (error instanceof OAuthError) {
			return error.toResponse();
		}
		// Unexpected non-OAuth error
		return c.text(`Internal server error: ${error.message}`, 500);
	}
});

async function redirectToGoogle(
	request: Request,
	env: Env,
	stateToken: string,
	init: HeadersInit = {},
) {
	// Keep a Headers object end to end: a plain object would collapse repeated Set-Cookie values.
	const headers = new Headers(init);
	headers.set(
		"location",
		getUpstreamAuthorizeUrl({
			clientId: env.GOOGLE_CLIENT_ID,
			hostedDomain: hostedDomainHint(env),
			redirectUri: new URL("/callback", request.url).href,
			scope: "email profile https://www.googleapis.com/auth/drive https://www.googleapis.com/auth/documents https://www.googleapis.com/auth/spreadsheets https://www.googleapis.com/auth/presentations https://www.googleapis.com/auth/gmail.modify https://www.googleapis.com/auth/calendar",
			state: stateToken,
			upstreamUrl: "https://accounts.google.com/o/oauth2/v2/auth",
		}),
	);
	return new Response(null, { headers, status: 302 });
}

/**
 * OAuth Callback Endpoint
 *
 * This route handles the callback from Google after user authentication.
 * It exchanges the temporary code for an access token, then stores some
 * user metadata & the auth token as part of the 'props' on the token passed
 * down to the client. It ends by redirecting the client back to _its_ callback URL
 *
 * SECURITY: This endpoint validates that the state parameter from Google
 * matches both:
 * 1. A valid state token in KV (proves it was created by our server)
 * 2. The __Host-CONSENTED_STATE cookie (proves THIS browser consented to it)
 *
 * This prevents CSRF attacks where an attacker's state token is injected
 * into a victim's OAuth flow.
 */
app.get("/callback", async (c) => {
	// Validate OAuth state with session binding
	// This checks both KV storage AND the session cookie
	let oauthReqInfo: AuthRequest;
	let clearSessionCookie: string;

	try {
		const result = await validateOAuthState(c.req.raw, c.env.OAUTH_KV);
		oauthReqInfo = result.oauthReqInfo;
		clearSessionCookie = result.clearCookie;
	} catch (error: any) {
		if (error instanceof OAuthError) {
			return error.toResponse();
		}
		// Unexpected non-OAuth error
		return c.text("Internal server error", 500);
	}

	if (!oauthReqInfo.clientId) {
		return c.text("Invalid OAuth request data", 400);
	}

	// Exchange the code for an access token
	const code = c.req.query("code");
	if (!code) {
		return c.text("Missing code", 400);
	}

	const [tokens, googleErrResponse] = await fetchUpstreamAuthToken({
		clientId: c.env.GOOGLE_CLIENT_ID,
		clientSecret: c.env.GOOGLE_CLIENT_SECRET,
		code,
		grantType: "authorization_code",
		redirectUri: new URL("/callback", c.req.url).href,
		upstreamUrl: "https://accounts.google.com/o/oauth2/token",
	});
	if (googleErrResponse) {
		return googleErrResponse;
	}
	const { accessToken, refreshToken } = tokens!;

	// Fetch the user info from Google
	const userResponse = await fetch("https://www.googleapis.com/oauth2/v2/userinfo", {
		headers: {
			Authorization: `Bearer ${accessToken}`,
		},
	});
	if (!userResponse.ok) {
		return c.text(`Failed to fetch user info: ${await userResponse.text()}`, 500);
	}

	const { id, name, email, verified_email } = (await userResponse.json()) as {
		id: string;
		name: string;
		email: string;
		verified_email?: boolean;
	};

	// Server-side allowlist. The consent-screen mode limits who Google lets
	// through; this is the check this server itself enforces, because it holds
	// vendor keys on behalf of whoever signs in.
	const allowed = signInAllowed(c.env, email, verified_email !== false);
	if (!allowed.ok) {
		console.log(JSON.stringify({ audit: true, user: email, tool: "sign_in_refused", resource: allowed.reason, ts: new Date().toISOString() }));
		return c.text(`Sign-in refused: ${allowed.reason}`, 403);
	}

	// Return back to the MCP client a new token
	const { redirectTo } = await c.env.OAUTH_PROVIDER.completeAuthorization({
		metadata: {
			label: name,
		},
		props: {
			accessToken,
			refreshToken,
			email,
			name,
		} as Props,
		request: oauthReqInfo,
		scope: oauthReqInfo.scope,
		userId: id,
	});

	// Clear the session binding cookie (one-time use) by creating response with headers
	const headers = new Headers({ Location: redirectTo });
	if (clearSessionCookie) {
		headers.set("Set-Cookie", clearSessionCookie);
	}

	return new Response(null, {
		status: 302,
		headers,
	});
});


// Human-friendly landing pages: the MCP endpoint is not a webpage, so explain
// it to anyone who opens the URL in a browser (prevents the "HTTP 401" confusion).
const PAGE_STYLE = "font-family:system-ui;max-width:560px;margin:80px auto;padding:0 16px;line-height:1.6;color:#222";
app.get("/", (c) => {
	const mcpUrl = `${new URL(c.req.url).origin}/mcp`;
	return c.html(`<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Account connectors</title>
<body style="${PAGE_STYLE}">
<h2>Account connectors</h2>
<p>This is a private tool server for Claude. It is an API endpoint, not a website; opening it in a browser shows an error, and that's normal.</p>
<p><b>To connect:</b></p>
<ol>
<li><b>claude.ai</b>: Settings &rarr; Connectors &rarr; Add custom connector &rarr; URL <code>${mcpUrl}</code>, then sign in with your Google account when asked.</li>
<li><b>Claude Code</b>: <code>claude mcp add --transport http account-connectors ${mcpUrl}</code>, then run <code>/mcp</code> and sign in.</li>
</ol>
<p>Only Google accounts on this server's allowlist can sign in. Then ask Claude to &ldquo;ping account connectors&rdquo;.</p>
</body>`);
});
app.get("/mcp", (c) =>
	c.html(
		`<!doctype html><meta charset="utf-8"><title>Account connectors</title><body style="${PAGE_STYLE}"><h2>MCP endpoint</h2><p>You opened the MCP endpoint in a browser; it only speaks to Claude. See <a href="/">setup instructions</a>.</p></body>`,
	),
);

import { addShopifyRoutes } from "./shopify-install";
addShopifyRoutes(app as any);

import { addMetaRoutes } from "./meta-oauth";
addMetaRoutes(app as any);

export { app as GoogleHandler };
