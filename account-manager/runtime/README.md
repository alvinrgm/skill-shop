# AI Account Manager

An AI system that does the recurring work of an agency account manager.
Recommend-only: it analyzes and drafts; you review and send.
Full brief: [BRIEF.md](BRIEF.md).

## What it does (Phase 1)
1. **Weekly reporting decks** (Module B) — `weekly-report` skill: pulls the
   week's ad data, writes a BLUF/Minto analysis, and **prepends** a house-style
   period block into the client's LIVE Google Slides reporting deck (additive
   only, verified, auto-rollback), then DMs you to review.
2. **Data-health monitor** (Module D-lite) — `health_monitor.py`: daily check
   that each client's raw-data sheets are fresh (Adveronix→Meta, Looker-native→
   Google, TikTok). Alerts you on stale/broken feeds. Does NOT auto-fix.

Designed-for, not built yet: client-comms drafts (Module A), standalone
account-ops recommender (Module C), full data-pipeline auto-maintenance,
native chart embeds, Monday auto-cron for decks.

## Layout
```
account-manager/
  BRIEF.md              # the spec
  .env                  # bridge URL+secret, Slack webhook (gitignored)
  .venv/                # python env (matplotlib for future charts)
  lib/
    bridge.py           # Apps Script bridge client (Slides/Sheets/Drive)
    clients.py          # reads the roster (clients/<slug>/account.md → ## AM reporting)
    deck.py             # the deck appender: prepend period block, verify, rollback
    sheets_data.py      # raw-data sheet freshness + reads
    slack.py            # Slack DM
    audit.py            # append-only audit log → history/audit/<date>.jsonl
  weekly_report.py      # orchestrator CLI: check | append | roster
  health_monitor.py     # Module D-lite daily health sweep
  launchd/com.am-health.plist
  history/audit/        # what the system did
```

## Config = the roster (one source of truth)
Per-client config lives in `clients/<slug>/account.md` under an
`## AM reporting` section (deck_id, headline_metric, observation_split,
attribution_source, comparison_window, data_sheet_ids, insert_index). This is the
same roster ad-spend-monitor reads — one source of truth. (The roster dir defaults
to the package's `clients/`; override with the `AM_ROSTER_DIR` env var.)

## Run it
```
cd <package-root>
.venv/bin/python weekly_report.py roster                 # list clients
.venv/bin/python weekly_report.py check <client>         # freshness gate
.venv/bin/python weekly_report.py append <client> --payload p.json --staging   # safe preview (copy), no DM
.venv/bin/python weekly_report.py append <client> --payload p.json             # live prepend + DM you
.venv/bin/python weekly_report.py append <client> --payload p.json --no-notify # live prepend, skip the DM
.venv/bin/python weekly_report.py thumbnail <deck_id> --slide 1 --out /tmp/x.png  # render a slide to PNG
.venv/bin/python weekly_report.py rm-staging <deck_id>   # trash a staging copy (--permanent to hard-delete)
.venv/bin/python health_monitor.py --dry                 # health sweep, no alert
.venv/bin/python health_monitor.py                       # alert only if issues
```

`append` flags: `--staging` (operate on a copy, suppresses the DM), `--no-notify`
(skip the Slack DM even on a live run), `--insert-index N` (override).
Payload: only `period_label` is strictly required; `dashboard`, `observations`,
`deep_dives`, `action_items` are all optional (omit what a client doesn't need).
The normal weekly path is the `weekly-report` skill ("build the weekly deck for
<client>"), which drives this with Claude in the loop for the analysis.

## Preview a staged deck (thumbnail sanity check)
```
.venv/bin/python weekly_report.py thumbnail <staging_deck_id> --slide 1 --out /tmp/divider.png
.venv/bin/python weekly_report.py thumbnail <staging_deck_id> --slide 3 --out /tmp/obs.png
```
(Slide 0 is the cover; a freshly prepended period starts at slide 1.)

## Off-switch
- Weekly decks: delete `~/.claude/skills/weekly-report/`.
- Health monitor: `launchctl unload ~/Library/LaunchAgents/com.am-health.plist`
  (and remove the file). Nothing else runs unattended.

## Safety
- Deck writes are additive-only and verified; a failed batch deletes only the
  slides it created (never touches existing slides).
- Recommend-only: no client sends, no ad-account changes.
- All Google access is via your own deployed Apps Script bridge.
