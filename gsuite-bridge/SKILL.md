---
name: gsuite-bridge
description: >
  Give Claude Code full native control of YOUR Google Workspace — create, read, edit,
  restyle, and delete Google Slides, Docs, Sheets, and Drive files in place, running AS
  your own Google account (no per-file sharing). Centerpiece: read the formatting + style
  of an EXISTING Google Slides deck and make new or target slides ADHERE to it (theme
  colors, fonts, sizes, table styling). Triggers on: "build a Google Slides deck",
  "edit my Google Doc / Sheet / Slides", "make this deck match <existing deck>", "apply
  our brand style to these slides", "format these slides like <template>", "create a
  Google Doc with headings/tables", "clean up the formatting in this deck", "manage my
  Drive files", or /gsuite-bridge. Works on any deck/doc/sheet your Google account owns.
---

<!-- ════════════════════════════════════════════════════════════════════════
     FIRST-RUN ONBOARDING GATE
     Runs BEFORE the workflow on a fresh install. Mirrors dependencies.yml + doctor.sh.
     ════════════════════════════════════════════════════════════════════════ -->

## ⚙️ First run? Onboard before you do anything else

**Gate:** if `.onboarded` does NOT exist in this skill's folder, do NOT start any task.
Onboard first. If `.onboarded` exists, skip this section and proceed.
(Re-onboard anytime by saying "re-run setup" or deleting `.onboarded`.)

### Onboarding flow

1. **Health check.** Run `bash doctor.sh`. Read the ✅/❌ list. If everything required is ✅
   (including the live `verify_bridge` line), jump to step 5.

2. **Deploy the Apps Script** (the one manual step that isn't a key). Open `SETUP.md` and
   walk the user through the 6 deploy steps at <https://script.google.com>: paste
   `apps-script/Code.gs`, paste `apps-script/appsscript.json`, set a random `SECRET` at the
   top of `Code.gs`, deploy as a Web App (**Execute as: Me**, **Who has access: Anyone**),
   authorize, and **enable the Slides API** under Services. They copy back the `/exec` URL.

3. **Write `.env`.** Create `.env` from `.env.example`. Put the `/exec` URL in
   `GSUITE_BRIDGE_URL` and the SAME secret you set in `Code.gs` into `GSUITE_BRIDGE_SECRET`.
   (Generate a secret with `python3 -c "import secrets; print('gsb-'+secrets.token_hex(16))"`.)
   **Never echo the secret back in chat.**

4. **Verify live.** Run `bash doctor.sh` again (or `python3 scripts/verify_bridge.py`). The
   `[slides]` line must pass — if it 403s, the Slides API isn't enabled yet (SETUP.md step 5).

5. **Mark done.** When all required checks are ✅, write `.onboarded` (`date > .onboarded`),
   confirm which Google account the bridge runs as, and give the first kickoff line (below).

Keep it warm and brief — one step per exchange. The goal is first output in minutes.

<!-- ═══════════════════════ END ONBOARDING GATE ═══════════════════════════ -->

---

# gsuite-bridge — native Google Workspace control for Claude Code

## What this gives you

A tiny Apps Script Web App (`apps-script/Code.gs`) that you deploy under **your own**
Google account. Because it **executes as you**, Claude can natively create, read, edit,
restyle, and delete every Google **Slides, Docs, Sheet, and Drive** file your account
owns — with **no per-file sharing dance**. Everything goes through one secret-gated HTTPS
endpoint; the Python client in `scripts/` wraps it.

**The headline capability: style adherence.** Most "AI made me a deck" output looks generic
because it ignores your existing design language. This skill reads a reference deck's actual
formatting — theme colors, fonts, title/body/table styles — into a portable **style spec**,
then stamps that spec onto new slides or an existing target deck. New work looks like it
belongs.

## The model (read once)

- **One endpoint, one secret.** Every request is a JSON POST carrying your `secret`. The
  URL is unguessable and the secret gates it — treat URL+secret like a credential.
- **Runs as you.** The script holds Docs/Sheets/Slides/Drive OAuth scopes for the account
  that deployed it. It can edit or delete anything that account owns. That power is the
  point; it's also why the secret matters.
- **Two layers of API.** Convenience actions (`create_doc`, `create_sheet`, Drive ops…) for
  common work, and a `google_api` **passthrough** that calls *any* Docs/Sheets/Slides/Drive
  REST method for everything else (all Slides work flows through this).

## Kickoff lines

- **Build a deck in your style:** "Build a 6-slide deck on <topic> styled like
  <existing deck URL or ID>."
- **Restyle an existing deck:** "Make <deck URL> match the style of <reference deck URL>."
- **Doc/Sheet:** "Create a Google Doc titled X with these sections…" / "Make a Sheet with
  these tabs…"
- **Drive:** "Find / rename / move / copy / delete <file>."

---

## Core workflow A — match an existing deck's style (the centerpiece)

Three scripts, one idea: **learn a look, then apply it.**

```bash
# 1. LEARN — read the reference deck's real formatting into a portable spec.
python3 scripts/extract_style.py <REFERENCE_PRESENTATION_ID> brand.json

# 2a. APPLY to an existing target deck (style-only; never touches content):
python3 scripts/apply_style.py <TARGET_PRESENTATION_ID> brand.json

# 2b. …or BUILD new slides that inherit the spec:
python3 - <<'PY'
import json, deckkit as dk
st  = dk.Style(json.load(open("brand.json")))
pid = dk.copy_template("<REFERENCE_PRESENTATION_ID>", "New deck")  # inherit theme+layouts
dk.wipe_slides(pid)                                                # FIRST BUILD ONLY
dk.add_cover(pid, "Title", "Subtitle · 2026", st, logo_url="https://…/logo.png")
dk.add_text_slide(pid, 1, "Context", [("h","Today"),("b","point one"),("b","point two")], st)
dk.add_table_slide(pid, 2, "The data", ["Metric","Value"], [["CPA","$31"],["ROAS","4.2"]], st)
dk.set_autofit_none(pid)
print("https://docs.google.com/presentation/d/%s/edit" % pid)
PY
```

`<PRESENTATION_ID>` is the long id in the deck URL: `…/presentation/d/<ID>/edit`.

**What the style spec captures** (`extract_style.py` output): theme color palette, page size,
layout map, and the real title / subtitle / body / table-header / table-body formatting
(font family, size, weight, color) sampled from the deck's actual slides. It resolves
`themeColor` references to concrete hex so the spec is portable.

**Two ways to inherit a look, and when to use each:**
- **`copy_template(REF_ID, name)`** duplicates the reference deck → the new deck literally
  shares its theme, masters, and layouts. Best when the reference *is* your template.
- **`extract_style` + `apply_style` / `dk.Style(spec)`** carries the look onto a *different*
  deck that has its own theme. Best for restyling something that already exists.

**Verify visually.** After building or restyling, screenshot a slide and look at it:
```python
import deckkit as dk; dk.render("<PID>", 0, "/tmp/slide0.png")
```

## Core workflow B — Docs

```python
import bridge
bridge.call({"action": "create_doc", "title": "Brief", "contentBlocks": [
  {"type": "heading1", "text": "Q3 Brief"},
  {"type": "paragraph", "runs": [{"text": "Goal: ", "bold": True}, {"text": "ship the redesign."}]},
  {"type": "bullet", "text": "First point"},
  {"type": "table", "headerRow": True, "rows": [["Metric","Value"],["CPA","$31"]]},
  {"type": "callout", "text": "Key guardrail.", "bg": "#F2F2F2"},
]})
```
Block types: `heading1/2/3`, `paragraph` (with `align`), `bullet`/`numbered` (with `nesting`),
`divider`, `table` (`headerRow`, `headerBg`, `headerFg`), `callout`. Any block takes `text`
or `runs:[{text,bold,italic,strikethrough,color,bg,link,size}]`. Surgical edits:
`doc_find_replace` (RE2 regex), `doc_insert_image`. Comments: `read_comments`,
`create_comment`, `reply_comment`, `resolve_comment`, `delete_comment`.

## Core workflow C — Sheets

`create_sheet` (multi-tab), `update_sheet`, `read_sheet`, `find_row`, `sheet_write_range`
(values or formulas), `sheet_format` (background, font, number format, alignment, merge),
`sheet_freeze`, `add_tab`/`rename_tab`/`delete_tab`. For charts / conditional formatting,
use the `google_api` passthrough → `sheets` `spreadsheets:batchUpdate`.

## Core workflow D — Drive

`list_files`, `file_info`, `rename_file`, `move_file`, `copy_file`, `share_file`
(outward-facing — grants access, use deliberately), `delete_file` (Trash by default;
`permanent:true` to hard-delete).

## The escape hatch — `google_api`

Anything the convenience actions don't cover:
```python
import bridge
# read a presentation's theme + slide structure:
bridge.api("slides", "GET", f"/v1/presentations/{pid}")
# structural batch edit on any surface:
bridge.api("slides", "POST", f"/v1/presentations/{pid}:batchUpdate", {"requests": [ ... ]})
bridge.api("docs",   "POST", f"/v1/documents/{did}:batchUpdate",     {"requests": [ ... ]})
bridge.api("sheets", "POST", f"/v4/spreadsheets/{sid}:batchUpdate",  {"requests": [ ... ]})
```

---

## Golden rules (these prevent the two ways this goes wrong)

1. **NEVER wipe-and-recreate a live deck/doc the user may have edited.** `create_deck`,
   `wipe_slides`, and `update_doc` with `contentBlocks` are **first-build only**. Once a file
   exists and a human has touched it, make **surgical in-place edits** (granular `add_*`,
   `apply_style`, `doc_find_replace`, `updateTextStyle`) — a full rebuild destroys their work.
   The live file is the source of truth, not your build script.
2. **Restyling is style-only.** `apply_style.py` changes text styles, table fills, and
   autofit — never content. It's idempotent and safe to re-run on a live deck.
3. **Confirm destructive or outward-facing actions.** `delete_file` (especially
   `permanent:true`) and `share_file` are hard to reverse — confirm before running them on
   anything you didn't just create. Before overwriting a file, read it first; if its contents
   contradict how it was described, surface that instead of proceeding.
4. **Turn autofit off for uniform decks.** `set_autofit_none` / the BODY autofit reset is the
   fix for "why are my body sizes inconsistent?" — placeholder autofit silently shrinks text.
5. **Verify by looking.** Render a slide or `read_doc` after a change; don't trust the
   `success` flag alone.

---

## Files in this package

| File | What it is |
|---|---|
| `apps-script/Code.gs` | The engine — deploy this as a Web App under your Google account. |
| `apps-script/appsscript.json` | Manifest granting the Docs/Sheets/Slides/Drive scopes. |
| `scripts/bridge.py` | The Python client — reads `.env`, exposes `call()` + `api()`. |
| `scripts/verify_bridge.py` | Post-deploy check (creates + trashes a Doc, Sheet, deck). |
| `scripts/extract_style.py` | **Learn** a reference deck's style → `style.json`. |
| `scripts/apply_style.py` | **Apply** a style spec to a target deck (content-safe). |
| `scripts/deckkit.py` | Spec-driven slide builders (cover, text, table, callout, render). |
| `scripts/gslib.py` | Shared color/unit/font helpers. |
| `SETUP.md` | Deploy + config runbook (one-paste install at the top). |
| `doctor.sh` / `dependencies.yml` | Health check + the manifest it's generated from. |

---

**Created by Alvin Ding.**

A portable Google Workspace control + Slides style-matching skill for Claude Code, generalized
from an internal agency deck-automation workflow.

**Licence:** Released under the
[Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/)
licence — share and adapt freely with attribution. See `LICENSE.txt`.

**Feedback & Support:** Methodology questions or improvements → open an issue on this skill's
GitHub repository (Issues tab). Public feedback helps the next person. If something is Claude
misapplying the skill rather than the method itself, point that out and it gets corrected.
