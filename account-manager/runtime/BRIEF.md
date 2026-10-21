# AI Account Manager — Brief

**Autonomy:** recommend-only. Nothing sends to clients or changes ad accounts unattended. The ONE sanctioned live write is the weekly deck append (additive prepend only, never edits/deletes existing slides).

## Goal
Do the recurring work an agency account manager does across the roster, as an AI system the operator supervises.

## What the account manager owned (dependency order)
1. **Module D — Data pipeline** (foundation): per-client raw-data sheets fed by Looker-native (Google), Adveronix (Meta), TikTok connectors, with joins/blends → rendered as **native data tables** from each client's locked `core_data_source` (screenshots deprecated — REPORTING-SPEC.md).
2. **Module B — Weekly reporting decks**: one living Google Slides deck per client, newest period **prepended on top**, Barbara-Minto / BLUF house style.
3. **Module A — Client comms**: tend client Slack, triage + reply.
4. **Module C — Account ops**: analyze + change Meta/Google. (Changes are gated; recs ride inside Module B's deck.)

## Roster
One folder per client under `clients/<slug>/` (see `clients/_template/`).

## Phase 1 scope (this build)
- **Backbone**: `clients/<slug>/account.md` config + `lib/` readers + audit log.
- **Module D-lite**: daily data-health monitor (alert on stale/broken raw-data sheets; NOT auto-fix). Full pipeline auto-maintenance + new-client onboarding = later phase (needs per-client mapping).
- **Module B**: `/weekly-report <client>` skill — pull data → BLUF analysis → prepend a house-style period block into the live deck → Slack DM.

## Phase 2+ (designed-for, not built now)
Module A comms drafts · Module C standalone account-ops recommender · full data-pipeline auto-maintenance · Monday auto-cron for decks.

## House style (reverse-engineered from live decks)
Per-period block, newest on top:
1. Dated divider (`M/D` + dashboard label e.g. "Weekly dashboard")
2. KPI scorecard + campaign-breakdown slides — **native data tables** rendered from the locked `core_data_source` (carry the same data screenshots used to; screenshots deprecated)
3. Top-line Observations — BLUF metric verdict first (e.g. `Xx ROAS and Yx NC ROAS`), then `Observation/Insights` bullets, then `Next steps/Action taken`. Split **by platform**, **by segment**, or **combined** — set per client.
4. Single-topic deep-dive slides (tests/anomalies)
5. `Action items` closer — native table rolling up every Next-step, inline `(done)` status.

## Per-client config knobs
`headline_metric` (NC ROAS vs Revenue-WoW) · `observation_split` (platform/segment/combined) · `attribution_source` (TripleWhale / Northbeam+GA4 / Shopify + blended slot) · `comparison_window` (2-full-weeks footer vs single-week WoW) · `divider_label` · `deck_id` · raw-data sheet IDs + tab map · meta act_id · google customer_id · shopify.

## Hard invariants
- Deck writes: **insert-at-top only**; never modify/delete existing slides (the "never destructively rebuild a live artifact" rule, enforced in code).
- recommend-only everywhere except the sanctioned additive deck prepend.
- No prod deploys; no external sends without per-action approval (decks notify the operator, don't auto-send to clients).

## Connected services (verified in stack)
Apps Script bridge (Slides/Sheets/Drive) ✓ · Meta Ads MCP ✓ · Google Ads scripts (OAuth) ✓ · Shopify MCP ✓ · Slack webhook ✓ · Drive connector (read) ✓.
NOT connected: Triple Whale, Northbeam (blended slot left in config for later). Looker Studio has no write API (maintain = keep source sheets fresh + alert on stale).

## Off-switch
Delete `~/.claude/skills/weekly-report/`; `launchctl unload` the Module D plist. Backbone is inert data/libs.

## Success check
`/weekly-report <client>` → correct new period prepended atop the live deck (BLUF verdict, real WoW numbers, action-items table), nothing below altered, Slack DM received.
