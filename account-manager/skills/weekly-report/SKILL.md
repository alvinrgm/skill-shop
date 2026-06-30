---
name: weekly-report
description: >-
  Build a client's weekly performance reporting deck the way a senior account
  manager would — pull the week's ad data, write a Barbara-Minto / BLUF analysis,
  and PREPEND a new house-style period block into the client's LIVE Google Slides
  reporting deck (additive only, never rebuilds), then DM you the BLUF to review
  before you send it to the client. Part of the AI Account Manager system (see the
  package `runtime/` dir). Triggers on: "build the weekly deck for <client>",
  "weekly report for <client>", "<client> weekly reporting", "update <client>'s
  reporting deck", "run the weekly report", /weekly-report <client>. Clients are
  whatever you configure in the roster. Recommend-only: never sends to the client,
  never changes ad accounts.
---

<!-- ═══════════ FIRST-RUN ONBOARDING GATE (make-portable) ═══════════ -->
## ⚙️ First run? Onboard before doing anything else

**Gate:** locate the `account-manager-portable` package dir (where `SETUP.md`, `doctor.sh`, and
`dependencies.yml` live — the repo these skills were copied from). If a `.onboarded` file does NOT
exist there, do NOT start this skill's workflow — onboard first:
1. `cd` to the package dir, run `bash doctor.sh`, read the ✅/❌ list.
2. Walk each ❌ one at a time (look it up in `dependencies.yml` / `SETUP.md`): say what it powers,
   give the real link, then offer to do it — run `pip install -r requirements.txt`, write a key to
   `runtime/.env` (never echo it back), help deploy their OWN Apps Script bridge (`bridge/SETUP.md`),
   copy a roster from `runtime/clients/_template`, or connect an MCP (then verify the tools are live).
3. Re-run `bash doctor.sh`; when required items are ✅, write `.onboarded` and give the first
   kickoff line for this skill.

If `.onboarded` exists, skip this section and proceed normally. (Re-onboard: delete `.onboarded`.)
<!-- ═══════════ END ONBOARDING GATE ═══════════ -->


# Weekly Report — AI Account Manager (Module B)

You are doing the recurring reporting work a senior account manager owns: turn a
week of ad data into a sharp, on-brand period section appended to the client's
living reporting deck. **Judgment is yours; the deterministic, deck-mutating work
is in scripts.** Never hand-edit the live deck via the API yourself — always go
through `weekly_report.py append`, which is additive, verified, and rolls back on
failure.

Project home: the package `runtime/` dir.
Run scripts with its venv: `runtime/.venv/bin/python`

## Hard invariants (do not violate)
- **Additive only.** New slides prepend at the top (under the cover). The
  appender NEVER edits or deletes an existing slide. This is the
  "never destructively rebuild a live artifact" rule, enforced in code.
- **Recommend-only.** The deck update is for you to review; you never send it
  to the client and never change a Meta/Google account.
- **Preview before live.** Always do a `--staging` pass and eyeball a thumbnail
  before the real prepend.
- **Gate on freshness.** If the data is stale, STOP and surface it — never
  report on stale numbers.

## The flow

### 0. Resolve the client + config
`cd runtime`
`.venv/bin/python weekly_report.py roster` to list configured clients.
Config lives in the canonical roster: `runtime/clients/<slug>/account.md`
under `## AM reporting`. Key knobs you must honor:
- `headline_metric` — `nc_roas` (lead "Xx ROAS and Yx NC ROAS"),
  `revenue_wow` (lead "Revenue ±%; ROAS ±%"), `roas_cpa`.
- `observation_split` — `platform` (Google block then Meta block),
  `segment` (per product/category segment),
  `combined` (one Weekly Observations slide).
- `comparison_window` — `wow` (single week vs prior) or `two_full_weeks`
  (deltas vs trailing 2 full weeks; add footer "*previous 2 full weeks").
- `divider_label` — the dashboard label on the divider slide.
- `attribution_source` — the truth-check layer. `triple_whale`/`northbeam_ga4`
  are external attribution tools; if not connected → fall back to
  `attribution_fallback` (Shopify or platform) and add a one-line caveat to the
  BLUF (e.g. "platform-attributed; Northbeam pending"). Shopify can be wired via
  the Shopify MCP.

### 0.5 Load the context pack (do this BEFORE any analysis)
The report is only as good as the strategic + historical context behind it.
Load it first so your analysis operates against the strategy, not floating free:
```
.venv/bin/python weekly_report.py context <client>
```
This renders the **living strategy** (`strategy.md` — diagnosis, positioning,
current bets, refusals), the **account config**, the **memory** (standing notes +
tactical history — what's been tried, what we learned), and the **latest diagnose
snapshot**. Read it. Your BLUF, observations, and recommendations must reflect it
(e.g. don't recommend cutting brand if a standing note says brand is incremental;
frame WoW moves against the current bets). If it warns "no strategy.md yet", note
that and lean on memory + account until the strategy backfill runs (see the
`strategy-review` skill).

### 1. Freshness gate
`.venv/bin/python weekly_report.py check <client>`
If it prints STALE, STOP. DM which sheet is stale and do not proceed.

### 2. Pull the week's data
Compute the window from `comparison_window` (see Date math below).
- **Raw-data sheets** (the deterministic source): read the client's daily feed
  tab(s) via the bridge. From Python:
  `from lib import sheets_data; rows = sheets_data.read_tab(sheet_id, tab_title)`
  Sheet IDs + tabs are in the config / shown by `check`. A typical daily feed tab
  is an Adveronix/materialized export and reads fine.
  - **CONNECTED-SHEET CAVEAT:** some tabs are Google-native "connected sheets"
    (a BigQuery/Looker data source), e.g. an "Original Conversion Values" tab.
    Those return EMPTY via the Sheets values API. For a tab that reads back 0 rows
    but the deck/dashboard clearly has data, pull Google numbers from the
    `runtime/../google-ads/` scripts (Ads API directly) instead, not the sheet.
    Freshness still works on these (Drive modifiedTime), only value extraction
    doesn't.
- **Google Ads** detail if needed: the scripts in the `google-ads/` tooling (OAuth
  set up).
- **Attribution truth-check**: if `attribution_source: shopify`, call the
  Shopify MCP for the period's revenue/orders to sanity-check platform ROAS. If
  it references Triple Whale / Northbeam (not connected), use the fallback and
  caveat. NEVER invent blended numbers.
- Compute the deltas yourself (WoW or vs 2 full weeks). Show your math in the
  audit if non-obvious.
- **Budget pacing** (reuse the existing ad-spend-monitor work — don't reinvent):
  targets come from `ad-spend-monitor/history/budgets/<slug>-<YYYY-MM>.json`
  (extracted from the client's budget sheet); MTD spend from
  `ad-spend-monitor/history/spend/<slug>-<YYYY-MM>.jsonl` (latest line) or a fresh
  Meta-MCP / google-ads pull. Pacing math is the monitor's
  (`lib/layers/pacing.py`): `projected_EOM = MTD * days_in_month / days_elapsed`;
  guardrails >102% red over, >101% yellow, <90% yellow under, <85% red under;
  grace days 1-3. Report per-platform + combined, with as-of dates (flag if a
  platform's spend is stale / token needs refresh).

### 3. Write the BLUF analysis → payload.json
Author the period block in the deck's house voice (see House style). Write a
JSON file (e.g. `/tmp/<client>_weekly.json`) matching this schema:
```json
{
  "period_label": "6/25",
  "divider_label": "<from config>",
  "dashboard": {"title": "Data dash", "metrics": ["Spend $X", "Revenue $Y", "ROAS Zx", "NC ROAS Wx"]},
  "pacing": {"title": "Budget pacing — ...", "bold_labels": ["Meta","Google"],
             "bullets": ["Meta", "MTD $X -> projected EOM $Y vs $T target = Z% <status>", ...]},
  "sections": [{"title": "...", "bullets": [...], "bold_labels": [...]}],
  "appendix": {"label": "Appendix — Analysis (<date>)", "slides": [{"title": "...", "bullets": [...]}]},
  "observations": [
    {"title": "<BLUF verdict — metric first>",
     "observation": ["telegraphic bullet", "bullet"],
     "next_steps": ["imperative action"]}
  ],
  "deep_dives": [
    {"title": "<single-topic test/anomaly>", "observation": [...], "next_steps": [...]}
  ],
  "action_items": [
    {"action": "Increase tROAS 15%", "notes": "owner/context", "status": ""}
  ]
}
```
- `observations` count/shape follows `observation_split` (one block per
  platform / per segment / one combined).
- `action_items` roll up every `next_steps` line from this period (current
  period only — no carry-forward in v1). `notes` ≈ owner/context, `status` ≈ ""
  or "Sent 6/18" or "(done)".

### 4. Preview on staging, eyeball, then go live
```
.venv/bin/python weekly_report.py append <client> --payload /tmp/<client>_weekly.json --staging
```
This builds the block in a COPY and prints its URL (`--staging` suppresses the
DM). Render thumbnails to sanity-check the divider + an observation slide:
```
.venv/bin/python weekly_report.py thumbnail <staging_deck_id> --slide 1 --out /tmp/d.png
.venv/bin/python weekly_report.py thumbnail <staging_deck_id> --slide 3 --out /tmp/o.png
```
Read those PNGs, confirm it reads right and the numbers are correct. Then the
real prepend (omit `--staging` → prepends into the live deck and DMs you):
```
.venv/bin/python weekly_report.py append <client> --payload /tmp/<client>_weekly.json
```
Then clean up the staging copy:
`.venv/bin/python weekly_report.py rm-staging <staging_deck_id>`
(`append` flags: `--no-notify` skips the DM on a live run; `--insert-index N`
overrides. In the payload only `period_label` is required; everything else is
optional.)

### 5. Report back
Confirm: which deck, how many slides added, the BLUF line, the deck URL, and
that you should review before sending to the client. The script already DMs you;
echo the same in chat.

### 6. Update memory + check strategy drift (closes the learning loop)
Institutional knowledge must accumulate, or next week starts blind again.
- **Append to memory**: record this period's key dynamics + any decisions as a
  tactical-history entry:
  `from lib import context; context.append_memory("<client>", "<YYYY-Www>", action, result, lesson)`
- **Strategy drift check**: compare this week's dynamics to the living strategy's
  diagnosis/bets/assumptions. If something MATERIAL diverged (a bet is failing, a
  new dynamic emerged, the diagnosis is stale), DON'T silently edit the strategy —
  draft a dated amendment and DM you to approve (recommend-only). Hand off to the
  `strategy-review` skill (drift mode) for the actual edit. Minor weeks need no
  strategy change — only flag real divergence.

## Date math (be exact — wrong windows = wrong numbers)
- **wow**: this report covers the last complete Mon–Sun week (D = last Sunday).
  Compare to the week before (the prior Mon–Sun). Divider date = the report run
  date (M/D). Abort if the feed doesn't cover the full window.
- **two_full_weeks**: metrics vs the trailing 2 full weeks; footer the
  observation bullets with "*previous 2 full weeks". Divider date = run date.

## House style (match the existing decks)
- **BLUF first.** Every observation slide title is the verdict with the number up
  front: "6.3x ROAS and 2.25x NC ROAS" / "Non-Brand: Revenue -15%; ROAS -40%".
- **Two-part body:** an `Observation` block (the diagnosis, telegraphic bullets
  with the numbers) then a `Next steps` block (imperative actions). The script
  bolds those labels.
- **Telegraphic analyst voice** — metrics + a decision, not prose. Working
  vocab: ROAS, NC ROAS, TROAS, TCPA, CPA, AOV, CPC, CTR, CPM, MER, WoW.
- **No em dashes** in the copy. No AI-isms. Numbers are sourced from the feeds,
  never invented.
- **Action items** closer always present.
- **Dashboard slide**: metric summary bullets + a placeholder box for the
  Looker/GDS screenshot (you paste it). v1 has no native chart embed — the
  numbers live in the observation slides.

## A client with no reporting deck yet
If a client has only a pitch/Opportunities deck, the first time it needs
reporting, create a reporting deck once, add its `deck_id` to
`runtime/clients/<slug>/account.md` under `## AM reporting`, then this flow
applies (append-only from then on). Don't auto-create silently — tell the user
you're creating its first reporting deck.

## Off-switch
Delete this skill folder. The deck appender + scripts live in the package
`runtime/` dir and do nothing unless invoked.
