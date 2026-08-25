# gsuite-bridge

**Native Google Workspace control for Claude Code — with Slides style-matching.**

Deploy one small Apps Script under your own Google account and Claude Code can create, read,
edit, restyle, and delete your Google **Slides, Docs, Sheets, and Drive** files in place —
running *as you*, with no per-file sharing.

The headline feature: **read an existing deck's formatting and make new or target slides
adhere to it** — theme colors, fonts, sizes, table styling. AI decks stop looking generic.

```bash
# learn a deck's look → build matching slides, or restyle another deck to match
python3 scripts/extract_style.py <REFERENCE_DECK_ID> brand.json
python3 scripts/apply_style.py   <TARGET_DECK_ID>    brand.json
```

## Get started

1. Read **[SETUP.md](SETUP.md)** — deploy the Apps Script (~10 min) and fill `.env`.
   (Or paste the one-paste block at the top of SETUP.md into Claude Code and let it walk you.)
2. `bash doctor.sh` until green.
3. In Claude Code: *"build a 6-slide deck on \<topic\> styled like \<existing deck URL\>."*

## What's inside

- `apps-script/` — the engine (`Code.gs`) + manifest you deploy.
- `scripts/` — the Python client: `bridge.py`, `verify_bridge.py`, and the style trio
  (`extract_style.py`, `apply_style.py`, `deckkit.py`) + shared `gslib.py`.
- `SKILL.md` — the Claude Code skill (capabilities, workflows, golden rules).
- `doctor.sh` / `dependencies.yml` — health check + manifest.

## Safety

Runs with full Drive scope **as your account** — it can edit/delete anything you own. The URL +
secret are a credential; don't share them. Golden rule: never wipe-and-recreate a live deck a
human may have edited — make in-place edits. Full notes in `SKILL.md` and `SETUP.md`.

## Licence

[CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) — see [LICENSE.txt](LICENSE.txt).
Created by Alvin Ding. Feedback → this repo's Issues.


---
Built and battle-tested at [Rise Growth Marketing](https://www.risegm.com/skills?utm_source=github&utm_medium=skill&utm_content=gsuite-bridge). More free skills, and the story of the systems behind them, at that link.
