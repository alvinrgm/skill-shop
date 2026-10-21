# gsuite-bridge — setup

Give Claude Code native control of your Google Slides, Docs, Sheets, and Drive — and the
ability to make new slides match the style of an existing deck. One-time deploy, ~10 minutes.

---

## Fastest path — one paste into Claude Code

> **Paste this into Claude Code (after the package is at `~/.claude/skills/gsuite-bridge`):**
> Onboard me into the `gsuite-bridge` skill at `~/.claude/skills/gsuite-bridge`: read its
> `SKILL.md`, run `bash doctor.sh`, then walk me through setup one step at a time — help me
> deploy `apps-script/Code.gs` as a Google Apps Script Web App (give me each click), have me
> set a random `SECRET`, write my `.env` for me (URL + matching secret), remind me to enable
> the Slides API, then run `verify_bridge.py` to confirm it's live. Mark `.onboarded` when
> green and give me my first kickoff line. Don't start any real task until setup is green.

The rest of this file is the manual fallback.

---

## Accounts / prerequisites

| Need | Where | Cost |
|---|---|---|
| A Google or Google Workspace account | the one whose Drive you want to control | free |
| Python 3.7+ | `python3 --version` (preinstalled on macOS) | free |
| Claude Code | you already have it | — |

No third-party Python packages. No paid APIs. The bridge uses your Google account's own quota.

---

## Deploy the Apps Script (one-time) — signed in as the account you want to control

1. **Sign in** to <https://script.google.com> as the Google account whose Docs/Sheets/Slides/
   Drive you want Claude to manage. (Use the account switcher / a clean Chrome profile so you
   don't deploy under the wrong identity.)
2. **New project.** Delete the default `myFunction()` stub. Paste the entire contents of
   `apps-script/Code.gs`. Rename the project (e.g. "gsuite-bridge").
3. **Set your secret.** At the top of `Code.gs`, change
   `const SECRET = 'CHANGE_ME_TO_A_LONG_RANDOM_STRING';` to a real random string. Generate one:
   ```bash
   python3 -c "import secrets; print('gsb-'+secrets.token_hex(16))"
   ```
   Keep it handy — it goes in `.env` too. Save (⌘/Ctrl-S).
4. **Add the manifest.** Project Settings (⚙️) → tick **"Show appsscript.json manifest file in
   editor."** Back in the editor, open `appsscript.json` and replace its contents with
   `apps-script/appsscript.json` from this package (this grants the Slides + Drive scopes). Save.
5. **Enable the Slides API.** Left sidebar → **Services** (**+**) → **Slides API** → **Add.**
   (Docs/Sheets/Drive work without this; only the Slides REST passthrough needs it, and a fresh
   project has it OFF — so the slides path 403s until you do this.)
6. **Deploy.** Deploy → **New deployment** → gear → **Web app**:
   - **Execute as:** **Me** ← this is the whole point (it runs as you).
   - **Who has access:** **Anyone** (the URL is unguessable and the secret gates every request).
   - **Deploy.** Authorize when prompted: pick your account → Advanced → "Go to … (unsafe)"
     (normal for your own unverified script) → Allow the Docs/Sheets/Slides/Drive/external
     scopes.
7. **Copy the Web app URL** (ends in `/exec`).

> Changed `Code.gs` later? You must **Deploy → Manage deployments → edit (✏️) → New version →
> Deploy** for the change to go live. Editing alone doesn't update the live URL.

---

## Configure the client

```bash
cp .env.example .env
```
Edit `.env`:
- `GSUITE_BRIDGE_URL` = the `/exec` URL from step 7.
- `GSUITE_BRIDGE_SECRET` = the **same** secret you set in `Code.gs` step 3.

---

## Verify

```bash
bash doctor.sh
# or directly:
python3 scripts/verify_bridge.py
```
Expect the identity line (which account it runs as) plus **OK** for Docs, Sheets, and Slides.
Throwaway test files are created and trashed automatically. If `[slides]` 403s, redo step 5
(Slides API not enabled).

---

## First runs

```bash
# Learn an existing deck's style, then build new slides that match it:
python3 scripts/extract_style.py <REFERENCE_PRESENTATION_ID> brand.json
# …then ask Claude: "build a deck on <topic> styled with brand.json"

# Or restyle a target deck to match a reference:
python3 scripts/apply_style.py <TARGET_PRESENTATION_ID> brand.json
```
`<PRESENTATION_ID>` is the long id in the URL: `…/presentation/d/<ID>/edit`.

---

## Security notes

- **Who has access: Anyone** means anyone with the URL can hit it — but every request requires
  your secret, so a leaked URL alone is useless. Don't paste URL+secret anywhere public.
- The bridge has **full Drive scope as your account** — it can edit/delete any file you own.
  That's the capability; it's also why the secret is sensitive. Treat URL+secret as a credential.
- The real `.env` is gitignored and never shipped. Only `.env.example` is in the package.

## Off-switch

- **Pause:** Deploy → Manage deployments → **Archive** the deployment (URL stops responding).
- **Kill:** delete the Apps Script project from your Drive. (Revoke its access anytime at
  <https://myaccount.google.com/permissions>.)
