# Document Bridge — deploy your own

A small Google Apps Script web app that executes **as your own Google account**, so
the automated client (the account-manager runtime + deck engine) can natively
create and edit Google **Docs, Sheets, Slides, and Drive** files you own — no
per-file sharing, no browser in the loop. It also exposes a `google_api` REST
passthrough so any Docs/Sheets/Drive/Slides method is reachable.

**You deploy this yourself.** Nothing is pre-hosted. On deploy you get a private
`/exec` URL; you choose your own secret. The URL + secret go into your `.env`.

---

## 1. Set your secret

Open `Code.gs` and change this line near the top to any long, random string:

```js
const SECRET = 'CHANGE-ME-set-your-own-long-random-secret';
```

Keep this value — you'll paste the same string into your `.env` in step 7. Treat
the exec URL + secret like a credential; don't commit either anywhere public.

---

## 2. Create the Apps Script project

1. Decide **which Google account should own the created files** and sign into it in
   Chrome (e.g. an agency/Workspace account). The bridge runs *as the deploying
   account*, so whatever account you authorize is the owner of everything it makes.
2. Go to **https://script.google.com** → **New project**.
3. **Paste `Code.gs`.** Delete the default `myFunction()` stub, paste the entire
   contents of `Code.gs` (with your secret set), and save (⌘S / Ctrl+S). Rename the
   project to something like `Document Bridge`.
4. **Add the manifest.** Project Settings (⚙️ left rail) → tick **"Show
   appsscript.json manifest file in editor."** Back in the editor, open
   `appsscript.json` and replace its contents with the `appsscript.json` from this
   folder (this grants the Docs/Sheets/Slides/Drive scopes; no Gmail access). Save.

---

## 3. Deploy as a web app

1. **Deploy → New deployment** → gear icon → **Web app**. Set:
   - **Description:** `document-bridge v1`
   - **Execute as:** **Me** (the account whose files you want it to manage)
   - **Who has access:** **Anyone** (the URL is unguessable + secret-gated)
   - Click **Deploy**.
2. **Authorize** when prompted → choose your account → "Advanced" → "Go to
   Document Bridge (unsafe)" (normal for your own unverified script) → **Allow**.
   It will ask for Docs/Sheets/Slides/Drive/external-request scopes — that's
   expected.
3. **Copy the Web app URL** (ends in `/exec`).

> If you ever change `Code.gs`, you must redeploy for it to go live:
> **Deploy → Manage deployments → edit (✏️) → New version → Deploy.** Editing the
> code alone does NOT update the live URL.

---

## 4. Enable the Slides REST API (REQUIRED for Slides)

A fresh Apps Script project doesn't have the Slides API turned on, so the
`google_api → slides` passthrough 403s until you enable it. In the editor:
left sidebar → **Services** (**+**) → **Slides API** → **Add**. Re-authorize if
prompted. (Docs/Sheets/Drive work without this; only Slides needs it because the
bridge calls the Slides *REST* endpoint directly.) No new deployment version is
needed — API enablement is project-level.

---

## 5. Put the URL + secret in your `.env`

Add these to the package `.env` (see `runtime/.env.example`):

```
BRIDGE_URL=<the /exec URL from step 3>
BRIDGE_SECRET=<the same secret you set in Code.gs>
```

> Note: the deck engine (`deck-engine/deckkit.py`) reads `BRIDGE_URL` from the
> environment. If you use the deck engine, also set `BRIDGE_URL` to the same
> `/exec` URL (or export it alongside `BRIDGE_URL`).

---

## 6. Verify

```bash
python3 bridge/verify_bridge.py "<EXEC_URL>" "<SECRET>"
```

It confirms the bridge can report which account it runs as and can create + delete
a throwaway Doc, Sheet, and Slides deck. Throwaway files are auto-trashed. Expect
**ALL GREEN**.

---

## API surface (what the bridge can do)

POST JSON to the exec URL; every request must include `"secret": "<your secret>"`.
`action` selects the operation:

- **Docs:** `create_doc`, `update_doc`, `read_doc`, `doc_find_replace`,
  `doc_insert_image`
- **Doc comments:** `read_comments`, `create_comment`, `reply_comment`,
  `resolve_comment`, `delete_comment`
- **Sheets:** `create_sheet`, `update_sheet`, `read_sheet`, `find_row`,
  `sheet_write_range`, `sheet_clear_range`, `sheet_format`, `sheet_freeze`,
  `add_tab`, `delete_tab`, `rename_tab`
- **Drive:** `delete_file`, `move_file`, `rename_file`, `copy_file`, `list_files`,
  `file_info`, `share_file`
- **Generic passthrough:** `google_api` — call any Docs/Sheets/Drive/Slides REST
  method with the script's OAuth token. Covers anything the convenience actions
  don't (structural doc edits, conditional formatting, charts, the entire Slides
  API, etc.).

### Rich content block schema (`contentBlocks` / `appendBlocks`)

`create_doc` and `update_doc` accept a `contentBlocks` array. Block types:

```
{ type: 'heading1' | 'heading2' | 'heading3', text | runs }
{ type: 'paragraph', text | runs, align?: 'LEFT'|'CENTER'|'RIGHT' }
{ type: 'bullet' | 'numbered', text | runs, nesting?: 0-3 }
{ type: 'divider' }
{ type: 'table', rows: [[cell, ...], ...], headerRow?: bool, headerBg?: '#hex', headerFg?: '#hex' }
     cell = plain string OR { text | runs, bold?, italic?, color?, bg? }
{ type: 'callout', text | runs, bg?: '#hex' }   // single-cell shaded block
```

`runs` lets you mix formatting in one paragraph; each run supports
`text, bold, italic, strikethrough, color (hex), bg (hex), link (url), size (pt)`:

```
runs: [
  { text: 'Label: ', bold: true },
  { text: 'value', italic: true }
]
```

---

## Security notes

- "Who has access: Anyone" means anyone with the URL can hit it — but every request
  requires your secret, so the URL alone is useless. Don't paste the URL+secret into
  anything public.
- The bridge runs with **full Drive scope as the deploying account** — it can
  create/edit/delete files that account owns. It requests no Gmail scopes.
  That's the capability the workflow needs; treat the exec URL + secret as a
  credential.

## Off-switch

- Pause: **Deploy → Manage deployments → Archive** the deployment (URL stops
  responding).
- Kill: delete the Apps Script project from the owning account's Drive.
