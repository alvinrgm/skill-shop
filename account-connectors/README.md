# Account connectors

A remote MCP server you run yourself. It connects your **Google Workspace**, your
**ad accounts** (Meta, Google Ads) and your **store and email** (Shopify, Klaviyo) to
Claude, in claude.ai and in Claude Code, through one connector.

- **You host it**, on your own Cloudflare account (the free Workers plan is enough).
- **People sign in with Google.** They never hold a raw vendor key. Keys live only as
  Cloudflare secrets on your Worker.
- **Google tools act as the person signed in**, so their own Drive, Docs and Calendar
  permissions apply.
- **Vendor tools are read-only by construction.** The only write path is Meta. Each Meta
  change needs a single-use approval slip, minted after the person confirms that exact
  change in chat, and it executes as that person through their own Facebook Login.
- **Safety rules are enforced in code**: no Gmail send tool, no calendar invites unless
  asked, no permanent Drive delete, no overwriting non-empty sheet cells by default,
  destructive sheet changes gated, a sign-in allowlist that fails closed, and an audit
  log line for every consequential call.

```bash
git clone https://github.com/alvinrgm/skill-shop
cd skill-shop/account-connectors
npm install
npm run check                               # typecheck + unit tests + dry-run build
cp .env.example .env                        # your local staging copy of the secrets
# optional: npm run dev, then bash scripts/smoke-test.sh http://localhost:8788 (SETUP.md)
npx wrangler login
npx wrangler kv namespace create OAUTH_KV   # answer No to "add it on your behalf"; paste the id into wrangler.jsonc
npx wrangler deploy                         # prints your URL: put it in .env as WORKER_BASE
# in .env: your own Google OAuth client (redirect <WORKER_BASE>/callback), the allowlist,
# ADMIN_EMAIL, and any vendors (SETUP.md steps 4 to 6)
bash scripts/push-secrets.sh                # wrangler secret put, for every non-empty key
bash scripts/smoke-test.sh                  # checks the live deployment
```

Full walkthrough, including your own Google OAuth client and each vendor:
**[SETUP.md](SETUP.md)**. Or open the folder in Claude Code and paste the one-paste
install block from the top of SETUP.md. `SKILL.md` teaches Claude to walk you through
it and how to use every tool.

## What you get

| Area | Tools |
|---|---|
| Drive | search, file info, copy, move, rename, share, trash |
| Docs | create, read, structure (paragraph indexes), rich update (headings, styled runs, bullets, tables, callouts) to append, prepend or insert, find/replace, images, linked contents, comments |
| Sheets | create, read, find row, append rows, write cells (overwrite-guarded), format, freeze, add/rename tab; clear range and delete tab behind the approval gate |
| Slides | build a deck from an outline, list slide/element ids, replace text, raw batch update |
| Gmail | search, read, create drafts (including in-thread replies). No send. |
| Calendar | list events, create events (no invites unless asked) |
| Meta | `meta_get` (read-only Graph GET); gated writes: create/update creatives and ads, image/video upload, delete |
| Google Ads | `gads_search` (read-only GAQL) |
| Shopify | `shopify_query` (read-only Admin GraphQL) |
| Klaviyo | `klaviyo_get` (read-only GET) |
| Gate | `approve_change`, `list_approvals`, `clients` |

A vendor's tools appear only when its keys are set, so you can start with Google
Workspace alone and add vendors later. Vendor tools are **admin-only by default**: the
shipped `ACL` is `{}`, so only `ADMIN_EMAIL` can use them until you grant others in the
`ACL` var (SETUP.md, "per-person account access"). `ping` shows the active mode.

## How it fits together

```
claude.ai / Claude Code
   │  MCP over HTTPS, OAuth 2.1 (dynamic client registration)
   ▼
Your Cloudflare Worker  (/mcp)
   ├─ sign-in: Google OAuth with YOUR client → allowlist check → session
   ├─ Google Workspace tools ──► Google APIs, with the signed-in person's own token
   ├─ read-only vendor tools ──► Meta / Google Ads / Shopify / Klaviyo, server-held keys + ACL
   └─ gated Meta writes ──────► approval slip (single-use) + the person's own Meta token
KV: OAuth sessions, approval slips, per-person Meta tokens, Shopify store tokens
```

## Limits, honestly

- **Three vendors are read-only by design.** Google Ads, Shopify and Klaviyo have no write
  tools. Meta is the only write surface.
- **Gmail-account users on an External consent screen in Testing sign in again about
  weekly** (Google's 7-day refresh-token limit for test apps). Google Workspace (Internal)
  doesn't have this limit. SETUP.md explains the trade-off of switching the app to production.
- **You need admin rights in each vendor**: Business Manager admin for the Meta System
  User, a Google Ads manager account with an approved developer token (Basic access for
  production accounts), store admin for Shopify.
- **The server's instructions are guidance for Claude, not a hook.** The hard guarantees
  are the ones in code: the approval gate, read-only vendor tools, no send tool, the allowlist.
- **Changes made outside this server** (Ads Manager, other connectors) don't go through its
  gate or its audit log.
- **`npm audit` shows warnings.** They come from exact versions pinned by the `agents`
  package (the MCP runtime) and from local dev tooling. Don't run `npm audit fix --force`;
  it upgrades past those pins. Moving to newer pins is a planned follow-up.
- This is a template you operate. You're responsible for your Cloudflare account, your
  OAuth client, your keys, and each vendor's terms.

## Files

| Path | What |
|---|---|
| `src/` | The Worker: OAuth gate, Google tools, vendor tools, approval gate |
| `wrangler.jsonc` | Worker config (name, KV, Durable Object, optional `ACL` / `CLIENTS`) |
| `.env.example` | Every secret, with where to get it |
| `scripts/push-secrets.sh` | `.env` → `wrangler secret put` for each key |
| `scripts/check-vendors.mjs` | Tests each vendor key with the same call the server makes |
| `scripts/mint-google-ads-refresh-token.mjs` | Mints the Google Ads refresh token with your own OAuth client |
| `scripts/smoke-test.sh` | Deployment check (live or `npm run dev`): landing page, 401 gate, OAuth metadata, bad-client 400 |
| `test/gate.test.mjs` | Unit tests for the allowlist, ACL (incl. path-traversal hardening), GraphQL/Google id/URL guards and approval gate (`npm test`) |
| `test/handlers.test.mjs` | Handler tests with a mocked `fetch`: every vendor, Meta-write and Google tool refuses bad ids/paths before any request, and the ACL runs on the URL actually requested (`npm test`) |
| `doctor.sh` / `doctor.ps1` | Setup health check (Mac/Linux and Windows) |
| `dependencies.yml` | The setup manifest |
| `verify_portable.py` | Re-audits the package structure: `python3 verify_portable.py .` |

## License

**CC BY 4.0**, see [LICENSE.txt](LICENSE.txt). Attribution required. Issues and
improvements are welcome: https://github.com/alvinrgm/skill-shop/issues

---
Built by Rise Growth Marketing: https://www.risegm.com/skills?utm_source=github&utm_medium=skill&utm_content=account-connectors
