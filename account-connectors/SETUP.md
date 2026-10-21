# account-connectors: setup

Deploy your own copy of this remote MCP server on **your** Cloudflare account, with
**your** Google OAuth client and **your** vendor keys. When you're done, you and the
people you allow can sign in from claude.ai or Claude Code with Google and use:

- **Google Workspace**: Drive, Docs, Sheets, Slides, Gmail (drafts only), Calendar, acting as each signed-in person
- **Ad accounts and store, read-only**: Meta, Google Ads, Shopify, Klaviyo
- **Meta writes, gated**: each change needs a single-use approval slip, minted only after the person confirms it

Every key lives as a Cloudflare secret on your Worker. The people using the server
never see a vendor key. They only sign in with Google.

Plan on 30 to 45 minutes for the required part (steps 1 to 8). Each vendor in step 6
adds roughly 10 minutes, and you can add vendors later.

**Get the folder** (it lives in a public repository with other packages):

```bash
git clone https://github.com/alvinrgm/skill-shop
cd skill-shop/account-connectors
```

---

## One-paste install

Clone the repository as above, open a terminal in `skill-shop/account-connectors`,
start Claude Code, and paste this:

```
Set me up with account-connectors from this folder. Read SKILL.md, SETUP.md and
dependencies.yml, then run `bash doctor.sh --quick` (Windows: `powershell
-ExecutionPolicy Bypass -File doctor.ps1 -Quick`). Walk me through each missing item
one at a time, in SETUP.md order: run `npm install`, copy .env.example to .env, log
me in to Cloudflare, create the KV namespace, deploy and put the URL in .env as
WORKER_BASE, then guide me through my own Google OAuth client, the allowlist and any
vendors I want. When I paste a key, write it to .env and never echo it back. When
the required items pass, push the secrets with `bash scripts/push-secrets.sh`, run
`bash scripts/smoke-test.sh`, help me connect the server in Claude, and confirm the
`ping` tool answers. Write `.onboarded` when everything required is green.
```

Prefer to do it by hand? Follow the steps below.

---

## What you need

| What | Required? | Cost | Where |
|---|---|---|---|
| Node.js 20+ (includes npm and npx) | yes | free | https://nodejs.org/en/download |
| A Cloudflare account | yes | free Workers plan is enough | https://dash.cloudflare.com/sign-up |
| A Google Cloud project you own | yes | free | https://console.cloud.google.com/projectcreate |
| A Google account to sign in with: Google Workspace or plain Gmail | yes | none extra | |
| curl (for the smoke test) | no | free, usually preinstalled | https://curl.se/download.html |
| Admin on your Meta Business Manager | only for Meta | free | https://business.facebook.com/settings |
| A Google Ads manager account + developer token | only for Google Ads | free | https://ads.google.com/aw/apicenter |
| A Shopify store you administer | only for Shopify | free app | https://dev.shopify.com |
| A Klaviyo account | only for Klaviyo | free key | https://www.klaviyo.com/settings/account/api-keys |
| Claude: a claude.ai plan that allows custom connectors, or Claude Code | yes | | https://claude.ai/settings/connectors |

Everything below is created in **your own** accounts. You never need access to anyone
else's cloud project, app or Business Manager.

---

## Step 1. Install

```bash
cd skill-shop/account-connectors
npm install
npm run check        # typecheck + unit tests + dry-run build; must end with "--dry-run: exiting now."
cp .env.example .env # your local staging copy of the secrets (git-ignored)
```

`npm audit` reports warnings after `npm install`. They come from exact versions that the
`agents` package (the MCP runtime for Workers) pins for its dependencies, and from
local-only dev tooling. Leave them as they are: `npm audit fix --force` would upgrade past
those pins and can break the build. Moving to newer pinned versions is a planned follow-up.

Check where you stand anytime:

- Mac/Linux: `bash doctor.sh` (or `bash doctor.sh --quick` to skip network checks)
- Windows: `powershell -ExecutionPolicy Bypass -File doctor.ps1`

### Optional: try it locally first

You can run the server on your machine before touching Cloudflare:

```bash
# in .env, give the required keys fake values for this check, e.g. GOOGLE_CLIENT_ID=local-test, GOOGLE_CLIENT_SECRET=local-test,
# COOKIE_ENCRYPTION_KEY=<any 64 hex chars>, ALLOWED_EMAILS=you@example.com
npm run dev                                       # serves http://localhost:8788
bash scripts/smoke-test.sh http://localhost:8788  # in a second terminal
```

The smoke test should print only `OK` lines. Real Google sign-in against the local server
needs your real OAuth client (step 4) with `http://localhost:8788/callback` added as an
extra authorized redirect URI. `npm run dev` reads `.env`, so it binds every key there,
including the `CHECK_*` helpers; they are never pushed to Cloudflare.

## Step 2. Pick a name (optional)

The Worker is called `account-connectors`, so its URL will be
`https://account-connectors.<your-subdomain>.workers.dev`. To use another name, change
`"name"` in `wrangler.jsonc` now, before the first deploy.

## Step 3. Cloudflare: log in, create storage, first deploy

```bash
npx wrangler login                          # opens a browser; approve
npx wrangler kv namespace create OAUTH_KV   # prints an id
```

Wrangler 4 then offers to add the binding to your config for you ("Would you like Wrangler
to add it on your behalf?"). Answer **No**: `wrangler.jsonc` already has the `OAUTH_KV`
binding and only needs the id. (If you answered yes, open `wrangler.jsonc` and delete the
extra `OAUTH_KV` entry it added, so exactly one remains.)

Open `wrangler.jsonc` and replace `REPLACE_WITH_YOUR_KV_NAMESPACE_ID` with that id.
Then deploy once so you get your URL:

```bash
npx wrangler deploy
```

Wrangler prints `https://account-connectors.<your-subdomain>.workers.dev`. (On a brand-new
Cloudflare account it may first ask you to pick a workers.dev subdomain.) Put that URL in
`.env` as `WORKER_BASE` (no trailing slash). The server is live but nobody can sign in yet,
and that's expected.

## Step 4. Google: your own OAuth client (the sign-in)

This is the step people get stuck on, so it's spelled out. Do it in **your own** Google
Cloud project, signed in as the Google account that will own the server.

1. **Create a project**: https://console.cloud.google.com/projectcreate (any name).
2. **Enable the APIs** the tools call. In the console search bar, enable each of these:
   Google Drive API, Google Docs API, Google Sheets API, Google Slides API, Gmail API,
   Google Calendar API. Or, with the gcloud CLI:
   ```bash
   gcloud services enable drive.googleapis.com docs.googleapis.com sheets.googleapis.com \
     slides.googleapis.com gmail.googleapis.com calendar-json.googleapis.com --project <your-project-id>
   ```
3. **Set up the consent screen**: https://console.cloud.google.com/auth/overview
   (Google Auth Platform; older consoles call it "OAuth consent screen"). Fill in the app
   name and your support email. Then the **Audience** choice decides everything:

   | You sign in with | Choose | Then |
   |---|---|---|
   | **Google Workspace** (you@yourcompany.com) | **Internal** | Nothing else. Only people in your Workspace can sign in. No test users, no Google review. |
   | **Plain Gmail** (you@gmail.com) | **External**, leave it in **Testing** | Under **Audience > Test users**, **add yourself** (and anyone else who will sign in). Google refuses anyone not on that list. |

   With External in Testing, Google shows a "Google hasn't verified this app" screen on
   sign-in. Click **Continue**: it's your own app. Google also expires refresh tokens for
   Testing apps after 7 days, so Gmail users sign in again about once a week (Claude
   prompts for it). Switching the app to **In production** removes the 7-day limit. Without
   Google verification, an app in production is capped at 100 users and still shows the
   warning screen.
4. **Data access (scopes)**: under **Data Access > Add or remove scopes**, add:
   `.../auth/drive`, `.../auth/documents`, `.../auth/spreadsheets`,
   `.../auth/presentations`, `.../auth/gmail.modify`, `.../auth/calendar`, plus `email`
   and `profile`. (The server requests exactly these. Sending email is blocked in the
   server's code, not by the scope: there is no send tool.)
5. **Create the OAuth client**: https://console.cloud.google.com/apis/credentials >
   **Create credentials > OAuth client ID > Web application**.
   - Authorized redirect URI: `<WORKER_BASE>/callback`, for example
     `https://account-connectors.your-subdomain.workers.dev/callback`
   - Create, then copy the **Client ID** and **Client secret** into `.env` as
     `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`.

Leave `COOKIE_ENCRYPTION_KEY` blank: step 7 generates it.

## Step 5. Decide who may sign in

The server holds your vendor keys for whoever signs in, so it refuses everyone who is not
on its allowlist. That holds even if your consent screen would let them through.

```bash
# in .env, set one or both (comma-separated)
ALLOWED_EMAILS=you@example.com,teammate@example.com
ALLOWED_DOMAINS=yourcompany.com
```

Recommended: `ADMIN_EMAIL=you@example.com` makes one person the admin. The admin can use
the raw `google_api` passthrough (Docs/Sheets/Slides/Drive REST; each api is limited to
its own path prefix, so Gmail and Calendar are unreachable even on Drive's shared host),
and approval slips the admin mints work for any user unless the admin binds a
slip to one person with `for_email`.

**Vendor tools are admin-only by default.** The shipped `ACL` in `wrangler.jsonc` is `{}`,
which means only `ADMIN_EMAIL` may use the Meta, Google Ads, Shopify and Klaviyo tools;
every other signed-in person is refused (with no `ADMIN_EMAIL`, nobody can use them).
Google Workspace tools are not affected: they always act as the signed-in person. To let
others reach vendor accounts, set the ACL (see "Optional: per-person account access"
below). `ping` reports which mode is active under `vendor_access`.

To remove someone later, take them off the list and push the secret again. Every tool call
re-checks the allowlist, so their already-open session is refused at its next call with
an "access revoked" notice, and Meta writes and pending upload links stop working too. A
new session gets only a `ping` tool that explains why.

## Step 6. Vendors (each optional, add any time)

A vendor's tools show up in Claude only once its secrets are set. Skip any you don't use.
After filling a vendor's keys in `.env`, test them locally **before** pushing:

```bash
node scripts/check-vendors.mjs
```

It makes the same calls the server makes and tells you which thing is wrong.

### Meta (reads): a System User token

The token is read-only and never expires. `meta_get` uses it. You need admin on your Meta
Business Manager; if you aren't, ask whoever is to do steps 1 to 4 and hand you the token.

1. **Business app**: if you don't have one, go to https://developers.facebook.com/apps >
   Create app > type **Business**.
2. **System User**: https://business.facebook.com/settings/system-users > **Add**. Name it
   something like `claude-reader`, role Admin.
3. **Assign assets**: in that System User's panel, **Assign assets > Ad accounts**, pick
   each ad account, and switch on access. This is the most common silent failure: an
   unassigned account later returns `(#200) ... has NOT grant`.
4. **Generate New Token**: pick your app from step 1 and tick **ads_read**. (Reads need
   only ads_read. Writes do not use this token at all; see below.) Copy it right away, since
   Meta shows it only once. Lost it? Generate a new one.
5. Put it in `.env` as `META_ACCESS_TOKEN`. Optional for the local check:
   `CHECK_META_AD_ACCOUNT=act_<your id>` (from the `act=` number in your Ads Manager URL).

| Error | Fix |
|---|---|
| `(#200) ... has NOT grant` | The ad account isn't assigned to the System User. Redo step 3. |
| `(#10)` permission error | The token is missing `ads_read`. Redo step 4. |
| Token stops working after hours or days | You used a personal or Graph Explorer token. Generate it from the System User panel. |
| App and ad account belong to different businesses | Meta may require Advanced Access for the permission on your app (App Review > Permissions). If both belong to the same business, you don't need it. |

### Meta writes (optional): per-person Facebook Login

Write tools (`meta_mutate`, `meta_upload_begin`, `meta_upload_image`, `meta_delete`) act
**as the person** who connected, so Meta's activity log shows their name, and Meta's own
permissions cap what they can change.

1. In your Business app (https://developers.facebook.com/apps), add the **Facebook Login
   for Business** product.
2. Under its settings, add **Valid OAuth Redirect URI**: `<WORKER_BASE>/meta/callback`.
3. Copy **App ID** and **App secret** (App settings > Basic) into `.env` as `META_APP_ID`
   and `META_APP_SECRET`. `WORKER_BASE` must be set.
4. While the app is in development mode, everyone who will connect needs a role on the app
   (App roles > Add people, e.g. Developer or Tester). Each person then runs `meta_connect`
   from Claude, opens the link **themselves**, and approves `ads_management`, `ads_read`,
   `business_management` and the page permissions. The server then shows a confirm page
   naming both the Facebook identity and the server user; nothing is stored until they
   click confirm. (Never forward a `meta_connect` link: whoever finishes it would become
   the sender's Meta identity, which is why the page asks.) Their token lasts about 60
   days, and `meta_connect` refreshes it.

### Google Ads (reads)

`gads_search` runs read-only GAQL. It needs four values from your own accounts.

1. **Developer token**: in your Google Ads **manager** account, open
   https://ads.google.com/aw/apicenter, fill in the form, and copy the token into
   `GOOGLE_ADS_DEVELOPER_TOKEN`. A new token's access level may only reach test accounts.
   If real accounts fail with `DEVELOPER_TOKEN_NOT_APPROVED`, apply for **Basic access** on
   the same page.
2. **Enable the Google Ads API** in your Google Cloud project (the same one as step 4 is
   fine): `gcloud services enable googleads.googleapis.com --project <your-project-id>`, or search "Google Ads API"
   in the console and enable it.
3. **Desktop OAuth client**: https://console.cloud.google.com/apis/credentials > Create
   credentials > OAuth client ID > **Desktop app**. Put its id and secret in `.env` as
   `GOOGLE_ADS_CLIENT_ID` / `GOOGLE_ADS_CLIENT_SECRET`. You don't need to register a
   redirect URI.
4. **Mint the refresh token** with the shipped script. Sign in as a Google user who can see
   your Google Ads accounts:
   ```bash
   node scripts/mint-google-ads-refresh-token.mjs --write-env
   ```
   It prints a URL, you approve in the browser, and it writes `GOOGLE_ADS_REFRESH_TOKEN`
   to `.env`.
   **Heads-up:** if your consent screen is **External + Testing**, Google expires this
   token after 7 days. For a server token that's a problem. Either use a Workspace project
   (Internal) or switch the app to **In production** before minting. The unverified-app
   warning is fine for your own use.
5. If you reach accounts through a manager account, set `GOOGLE_ADS_LOGIN_CUSTOMER_ID` to
   the manager id (digits only).
6. Optional for the local check: `CHECK_GOOGLE_ADS_CUSTOMER_ID=<an account id>`.

### Shopify (reads)

`shopify_query` runs read-only Admin GraphQL. The server refuses any document containing
`mutation` or `subscription` (outside strings and comments), but the real wall is the
token's scopes: give the app (or any token in `SHOPIFY_TOKENS`) read scopes only. There are two ways in; use either one.

**A. Install an app through the server** (works for any store you administer):

1. Create an app in the Shopify Dev Dashboard: https://dev.shopify.com > Apps > Create app.
2. In the app's configuration, set:
   - App URL: `<WORKER_BASE>`
   - Allowed redirection URL: `<WORKER_BASE>/shopify/callback`
   - Access scopes: `read_analytics, read_customers, read_discounts, read_price_rules,
     read_fulfillments, read_inventory, read_orders, read_all_orders, read_products`
     (`read_all_orders` may need Shopify's approval; drop it if you only need the last
     60 days of orders).
   Release that version and choose distribution to your store.
3. Copy the app's **Client ID** and **Client secret** into `.env` as `SHOPIFY_CLIENT_ID`
   / `SHOPIFY_CLIENT_SECRET`, and push secrets (step 7).
4. A store admin opens `<WORKER_BASE>/shopify/install?store=<subdomain>` (the part before
   `.myshopify.com`) and approves. The token goes straight into the server's storage; you
   never handle it.

**B. Tokens you already have.** Put them in `.env` as JSON:
`SHOPIFY_TOKENS={"your-store": "shpat_..."}`

### Klaviyo (reads)

1. https://www.klaviyo.com/settings/account/api-keys > **Create Private API Key**.
2. Choose **Read-only** access (or Custom with read scopes only; include Accounts so the
   local check can prove it).
3. Put it in `.env` as `KLAVIYO_API_KEY`.
4. `klaviyo_get` follows the ACL like the other vendors, with the literal entry
   `"klaviyo"` (Klaviyo keys are not tied to an account id): add `"klaviyo"` to a person's ACL list, or
   use `"*"`. Under the default `{}` ACL only the admin can use it.

## Step 7. Push the secrets to Cloudflare

```bash
node scripts/check-vendors.mjs   # optional: proves each configured vendor key works
bash scripts/push-secrets.sh     # runs `npx wrangler secret put` for every non-empty key
```

`push-secrets.sh` generates `COOKIE_ENCRYPTION_KEY` if it's blank and never prints a value.
To set one secret by hand: `npx wrangler secret put KLAVIYO_API_KEY` (paste when asked).
Secrets apply right away; you don't need to redeploy.

Then confirm the deployment from outside:

```bash
bash scripts/smoke-test.sh       # landing page 200, anonymous /mcp refused with 401, OAuth metadata served, bad client 400
bash doctor.sh                   # everything required should now be OK
```

## Step 8. Connect Claude and test

**claude.ai**: Settings > Connectors > **Add custom connector**
(https://claude.ai/settings/connectors). Name: `Account connectors`. URL:
`<WORKER_BASE>/mcp`. Save, click **Connect**, approve the server's consent page, and sign
in with an allowlisted Google account. On Team/Enterprise plans an owner may need to add
the connector for the organization.

**Claude Code**:

```bash
claude mcp add --transport http account-connectors <WORKER_BASE>/mcp
```

Then run `/mcp` inside Claude Code, pick `account-connectors`, and sign in.

**Test**: ask Claude to "call the account-connectors ping tool". You should get your
email back as `signed_in_as`, a `vendors` map showing which vendors are configured, and
`vendor_access` saying whether the ACL is admin-only (the default) or configured.
Then try "list my 5 most recent Google Docs" (`drive_search`).

---

## Optional: per-person account access and short names

Both live in `vars` in `wrangler.jsonc`. Run `npx wrangler deploy` after editing.

- **`ACL`**: which ad accounts and stores each signed-in person can reach through the
  server's keys. The shipped default `{}` (or an unset/blank ACL) is **admin-only**: only
  `ADMIN_EMAIL` may use vendor tools. Example that grants others:
  `{"owner@example.com": ["*"], "*": ["act_YOUR_AD_ACCOUNT_ID", "1234567890", "acme", "klaviyo"]}`.
  Each entry belongs to exactly one vendor and only matches that vendor: `act_<digits>`
  is a Meta ad account (the `act_` is required), a 10-digit id is a Google Ads customer
  (dashes optional, the only normalisation anywhere), `"klaviyo"` is the Klaviyo tool,
  anything else subdomain-shaped is a Shopify store (compared exactly, so `acme-store` is
  not `acmestore`). Prefix `shopify:` for an all-digit store name. A `CLIENTS` slug grants
  that client's id for each vendor; `"*"` grants everything. Email keys are
  case-insensitive. Matching is exact. A user not listed falls back to the `"*"` key; with no `"*"` key they
  get nothing. `{"*": ["*"]}` lets every signed-in person reach every account your keys
  can see; use it only if that is what you want. Ids and paths containing `..`, `%`,
  `?`, `#`, backslashes or whitespace are refused before the ACL runs, and the ACL is
  checked against the account in the URL actually requested. The `clients` tool shows
  each person only the entries the ACL lets them reach.
  **Limit:** the ACL is a guard rail, not a hard wall. Meta Graph field expansion (for
  example `fields=business{owned_ad_accounts{...}}`) can still return data about other
  ad accounts the server's Meta token is assigned to. The real boundary is the token:
  give the System User access only to the ad accounts this server should ever touch.
- **`CLIENTS`**: short names, so you can say "acme" instead of ids (a slug spelled like an
  id, such as `act_123` or `1234567890`, is ignored: an id always means itself). Example:
  `{"acme": {"gads": "1234567890", "meta": "act_YOUR_AD_ACCOUNT_ID", "shopify": "acme-store"}}`

Want the ACL kept out of the file? Delete it from `vars`, then
`npx wrangler secret put ACL`.

Every Google tool also refuses any `*_id` parameter that is not a plain Google id
(letters, digits, `-`, `_`), and checks the final request URL stays under the expected
Google API path; Gmail send endpoints are never reachable.

## Updating, rotating, removing

- **Code update**: replace the files, `npm install`, `npm run check`, `npx wrangler deploy`.
- **Rotate a key**: change it in `.env`, then `bash scripts/push-secrets.sh <NAME>`.
- **Remove a person**: edit `ALLOWED_EMAILS`, run `bash scripts/push-secrets.sh ALLOWED_EMAILS`.
- **See who did what**: Cloudflare dashboard > Workers > account-connectors > Logs. Every
  consequential call writes an `audit` line (user, tool, resource, time).
- **Remove everything**: `npx wrangler delete`, then delete the KV namespace and revoke
  the OAuth client / tokens in each vendor.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Sign-in refused: ... not on this server's allowlist` | Add the email to `ALLOWED_EMAILS` (or its domain to `ALLOWED_DOMAINS`) and push that secret. |
| Google: `Error 403: access_denied` on sign-in | External app in Testing: add the person under Audience > Test users. Internal app: they must be in your Workspace. |
| Google: `redirect_uri_mismatch` | The OAuth client's redirect URI must be exactly `<WORKER_BASE>/callback`. |
| A Google tool returns 403 `... API has not been used in project` | Enable that API in your project (step 4.2). |
| Gmail users must sign in again every week | External + Testing. See step 4.3 (In production removes it). |
| `ping` shows `meta_read: false` (or another vendor false) | That vendor's secret isn't on the Worker. Run `npx wrangler secret list`, then `bash scripts/push-secrets.sh`. |
| `meta_connect` says `WORKER_BASE not configured` | Set `WORKER_BASE` and push it. |
| Meta callback: "URL blocked" | Add `<WORKER_BASE>/meta/callback` to Facebook Login for Business > Valid OAuth Redirect URIs. |
| Shopify: `no token for store` | Open `<WORKER_BASE>/shopify/install?store=<subdomain>` as a store admin, or add it to `SHOPIFY_TOKENS`. |
| `npm run check` fails after editing `wrangler.jsonc` | Move `.env` aside first (`mv .env .env.bak`), run `npx wrangler types` to regenerate `worker-configuration.d.ts`, then `mv .env.bak .env`. With `.env` present, wrangler copies its keys (including `CHECK_*`) into the generated types. |
| Wrangler warns "types might be out of date" | Expected right after you edit `wrangler.jsonc` vars (for example the ACL). Regenerate as in the row above if `npm run check` fails; otherwise it is harmless. |
| Wrangler logs `CIMD (Client ID Metadata Document) is disabled` | Expected and harmless. claude.ai and Claude Code connect through standard dynamic client registration (`/register`), which does not need it. To enable CIMD anyway, add `"global_fetch_strictly_public"` to `compatibility_flags` in `wrangler.jsonc` and redeploy. |
| A vendor tool says `not authorized for ... (server ACL)` | The ACL is admin-only by default. Set `ADMIN_EMAIL`, or grant the person in the `ACL` var and run `npx wrangler deploy`. `ping` shows the active mode. |
| A vendor tool refuses a path or id ("contains '..'", "percent-encoding", "10 digits") | Pass plain ids: `act_<digits>/insights`, customer ids as 10 digits (dashes fine), query parameters in `params`. |
| claude.ai connector shows "couldn't connect" | Run `bash scripts/smoke-test.sh`. The `/mcp` POST must return 401 (the 401 starts sign-in), not 404 or 500. |

Re-audit the package itself anytime: `python3 verify_portable.py .`

Found a bug or a confusing step? Open an issue: https://github.com/alvinrgm/skill-shop/issues
