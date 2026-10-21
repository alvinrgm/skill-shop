# AM Reporting Deck — Spec

> Canonical spec the `weekly-report` / `weekly-am-cycle` skills build to. Modeled on a reference
> reporting deck + the elite-agency standard, rendered in a dark brand look. This is a REPORTING
> deck, not a pitch deck.

## 1. Per-client CORE DATA SOURCE (locked)
Every reporting deck's headline numbers come from ONE locked source per client, declared in
`clients/<slug>/account.md` under `## AM reporting` as `core_data_source`. The skill
reads it and pulls the headline metrics from ONLY that source. Fallbacks are caveated, never the
headline.

| Field (example)  | Value                | Headline read |
|------------------|----------------------|---------------|
| `core_data_source` | `google_ads`       | real purchases (your primary purchase conversion action), NOT add-to-cart |

Other supported values: `triple_whale` (New-Customer ROAS + blended via the TW Summary API) and
`google_ads_looker` (platform revenue / ROAS WoW via Looker). Pick ONE per account.

(Action: add `core_data_source` to each account.md. If a client's `attribution_source` is set to
something that's wrong for reporting — e.g. `shopify` when the deck should read straight Google Ads —
keep `attribution_source` as a separate field if useful, but `core_data_source` is what the deck pulls.)

## 2. No screenshots — native tables ARE the evidence layer
We settled that dashboard screenshots are not feasible (no image hosting/capture path). So native
tables, pulled from the client's `core_data_source`, render the SAME data the screenshots would
have shown. Screenshots are OUT, permanently, unless re-opened explicitly.

RULE CHANGES (stale screenshot rules to remove):
- `lib/deck.py`: drop the screenshot placeholder text and the screenshot-placeholder slide; replace
  with a native data table from `core_data_source`.
- `BRIEF.md`: update Module B/D wording ("screenshotted into decks" / "placeholder for the dashboard
  screenshot") → "native tables rendered from the client's locked core_data_source."

## 3. Reporting deck structure (dark look; per-period block, newest prepended)
1. **Period divider** — "M/D · Weekly dashboard"
2. **Weekly Observations** — metric headline + **Observation / Next steps / Action taken**; window
   footnote. [core_data_source]
3. **KPI scorecard** — Metric | Last wk | Prior wk | WoW | Status (RAG vs goal/floor). [core_data_source]
4. **Campaign breakdown** — Campaign | Status | Spend | Purchases | Revenue | ROAS. [core_data_source]
5. **Budget pacing** — MTD spend vs pace · projected EOM · vs target. [Google Ads budgets + spend]
6. **Deep dive(s)** — recurring named "test" slides that mature week to week (e.g. Demand Gen status).
7. **Account-specific deep dive** — varies by account (e.g. a conversion-tracking or attribution check).
8. **Action items** — Action | Note | Status; owner inline. The running ledger.

## 4. Budget pacing method
When a client's `monthly_budget` is `TBD`, derive the monthly pace from the sum of ACTIVE campaigns'
daily budgets (same method as `ad-spend-monitor`): pace = Σ(daily budgets) × days; show MTD spend vs
MTD pace and projected EOM. Label the basis ("implied from daily budgets · no fixed monthly mandate").

## 5. Worked example (synthetic — round placeholder numbers, real-purchase lens, WoW current vs prior week)
This is a teaching example with made-up numbers, not a real account.
- **Scorecard:** Spend $2,000 / $2,000 / 0% / On plan · Real purchases 50 / 40 / +10 / On track ·
  Real revenue $5,000 / $4,000 / +$1,000 / On track · Purchase ROAS 2.50 / 2.00 / +0.50 / Above floor.
- **Campaign table:** Brand (ENABLED) $200 · 10 · $1,000 · 5.00 — PMax - Core (ENABLED) $1,000 · 30 ·
  $3,000 · 3.00 — PMax - Category A (ENABLED) $500 · 10 · $1,000 · 2.00 — Demand Gen (ENABLED) $300 · 0 · $0 · 0.00.
- **Budget pacing:** pull MTD spend + active daily budgets; show MTD vs pace + projected EOM.
- **Demand Gen deep dive:** spending but zero purchases; check disapprovals + conversion setup, list the fix order.
- **Action items:** Fix Demand Gen (agency) · Protect Brand (agency) · Confirm PMax optimizes to real
  purchases (agency) · Client inputs: margin/LTV/budget mandate (client).

## 6. Process rules (every build)
- Build INTO the existing client deck (its `deck_id` from `account.md`), additively / in place.
  Never rebuild from scratch, never a new file per change.
- NEVER delete / trash / move any deck without explicit per-deck approval.
- Render every changed slide and EYEBALL it before "done." Verify the render, not the declared height.

## 7. Build sequence (only after you approve this spec)
1. Add `core_data_source` to each client's account.md.
2. Update `lib/deck.py` + `BRIEF.md` to drop screenshots → native tables.
3. Add the **budget pacing** slide + **campaign-breakdown** table into the existing deck, in place.
4. Render + eyeball; review.
5. (Later, separate approval) codify all of this into the `weekly-report` skill so every client follows it.
