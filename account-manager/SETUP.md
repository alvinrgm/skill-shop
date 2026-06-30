# AI Account Manager — Setup

A recommend-only AI account manager for paid-media agencies, built as Claude Code skills.
It pulls a client's weekly ad data, writes a BLUF/Minto analysis, updates a live Google Slides
reporting deck in place, runs account-ops + creative analysis, and DMs **you** to review —
it never messages a client or changes an ad account unattended.

This system was built against one operator's private infrastructure. This package is the
**build-your-own-infra** edition: anything you wouldn't already have ships either as vendored
code (the deck engine) or as a setup process (deploy your own bridge, create your own roster,
bring your own API keys). Nothing here calls anyone else's accounts.

---

## ⚡ One-paste install (fastest)

> **Paste this into Claude Code:**
> Set up the AI Account Manager from `<REPO-URL>`. Clone it, copy `skills/*` into
> `~/.claude/skills/`, run `pip install -r requirements.txt`, then run `bash doctor.sh` and walk
> me through each ❌ one at a time: give me the link, and offer to install packages / write my
> `runtime/.env` / help me deploy my own Apps Script bridge (`bridge/SETUP.md`) and connect any
> MCPs — verifying each as we go. When the required checks are green, write `.onboarded` and tell
> me the first command to run. Don't start any reporting run until setup is green.

The rest of this file is the manual fallback.

---

## What you set up (once)

| # | Thing | Required? | What it powers | Where |
|---|-------|-----------|----------------|-------|
| 1 | **Claude Code** | ✅ | runs the 6 skills | https://claude.com/claude-code |
| 2 | **Python deps** | ✅ | HTTP, charts, (opt) Gemini/Ads | `pip install -r requirements.txt` |
| 3 | **Your Apps Script bridge** | ✅ | all Slides/Docs/Sheets output | deploy `bridge/Code.gs` → `bridge/SETUP.md` |
| 4 | **Slack webhook** | ✅ | DMs you the BLUF to review | https://api.slack.com/messaging/webhooks |
| 5 | **A client roster entry** | ✅ | per-client config | `runtime/clients/<slug>/account.md` |
| 6 | Google Ads API | optional | account-ops, Google spend | https://developers.google.com/google-ads/api |
| 7 | Meta Marketing API | optional | Meta spend monitoring | https://developers.facebook.com/docs/marketing-apis |
| 8 | Triple Whale API | optional | blended attribution | https://developers.triplewhale.com |
| 9 | Gemini API | optional | creative-intel video CV | https://aistudio.google.com/apikey |
| 10 | Meta / Shopify / Granola MCP | optional | data pulls, attribution, call notes | per-user MCP connections |

**Run `bash doctor.sh` at any time** to see exactly where you stand — it checks each item and
prints the fix inline.

---

## Install

```bash
git clone --depth 1 <REPO-URL> account-manager-portable
cd account-manager-portable

# 1. Python deps
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# 2. Make the 6 skills available to Claude Code
cp -R skills/* ~/.claude/skills/        # or symlink each

# 3. Config
cp runtime/.env.example runtime/.env    # then fill it in (steps below)
```

## Configure

### 3 — Deploy your OWN Apps Script bridge (required)
The system writes Google Slides/Docs/Sheets through a tiny Apps Script web app that runs as
**your** Google account. You deploy your own; full walkthrough in **`bridge/SETUP.md`**. In short:
create a new Apps Script project → paste `bridge/Code.gs` → set your own `SECRET` const → enable
the Slides API → deploy as a web app → copy the `/exec` URL. Then in `runtime/.env`:
```
BRIDGE_URL=<your /exec url>
BRIDGE_SECRET=<the secret you set in Code.gs>
```
Verify: `python3 bridge/verify_bridge.py "$BRIDGE_URL" "$BRIDGE_SECRET"`

### 4 — Slack webhook (required)
Create an incoming webhook (https://api.slack.com/messaging/webhooks), then:
```
SLACK_WEBHOOK=<your webhook url>
```
This is the only outbound channel; it DMs you the BLUF + recommendations. It never messages clients.

### 5 — Create a client (required)
```bash
cp -R runtime/clients/_template runtime/clients/acme
```
Fill `runtime/clients/acme/account.md` (objective, ROAS floor, channels, data source, deck id) and,
once you have history, `strategy.md`. The `_template` is fully commented.

### 6–9 — Data sources (wire up only what you use)
Each is optional and documented in `runtime/.env.example` with its signup link. The reporting loop
runs on whichever data source you configure; creative-intel needs Gemini; ad-spend-monitor needs
Google Ads and/or Meta. See each component's own README.

### 10 — MCP connections (optional)
Meta Ads, Shopify, and Granola are per-user MCP connections (not `.env` keys). Connect them in
Claude Code (`claude mcp add ...`); the first run confirms the tools are live.

## Verify
```bash
bash doctor.sh        # ✅/❌ per dependency with the exact fix
```
All required green → you're set. Kick off with: **"build the weekly deck for acme"** (or
`/weekly-report acme`).

---

## What's in the box
- `skills/` — the 6 Claude Code skills: `weekly-report`, `weekly-am-cycle`, `account-ops`,
  `creative-intel`, `meta-ops`, `strategy-review`.
- `runtime/` — the engine: `lib/` (data fetchers, bridge client, deck builder, context spine),
  `clients/` (your roster; `_template` to copy), creative-intel + meta-ops analyzers.
- `deck-engine/` — vendored Slides builder (`dark_deck` + `patterns` + `deckkit`).
- `bridge/` — the Apps Script source you deploy yourself + its setup guide.
- `ad-spend-monitor/` — daily Google + Meta spend anomaly monitor (4 layers).
- `dependencies.yml` — the manifest everything above is generated from.
- `onboarding-deck.pdf` — a 7-slide visual walkthrough (what it does, what you set up, how it works, what it connects to, guardrails). Start here if you'd rather skim than read.

## License
CC BY 4.0 — see `LICENSE.txt`. Attribution appreciated; build on it freely.
