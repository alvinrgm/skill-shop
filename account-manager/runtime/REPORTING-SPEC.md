# AM Reporting Deck — Spec

> Canonical spec the `weekly-report` / `weekly-am-cycle` skills build to. Modeled on a reference
> reporting deck + the elite-agency standard, rendered in a dark brand look. This is a REPORTING
> deck, not a pitch deck.

## 1. Per-client CORE DATA SOURCE (locked)
Every reporting deck's headline numbers come from ONE locked source per client, declared in
`clients/<slug>/account.md` under `## AM reporting` as `core_data_source`. The skill
reads it and pulls the headline metrics from ONLY that source. Fallbacks are caveated, never the
headline.

| Client (example) | core_data_source     | Headline read |
|------------------|----------------------|---------------|
| client A         | `google_ads`         | real purchases (`Google Shopping App Purchase`), NOT add-to-cart |
| client B         | `triple_whale`       | New-Customer ROAS + blended (TW Summary API) |
| client C         | `google_ads_looker`  | revenue / ROAS WoW (platform via Looker; northbeam_ga4 not connected → caveat) |

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
1. **Period divider** — "M/D · Data dash"
2. **Weekly Observations** — metric headline + **Observation / Next steps / Action taken**; window
   footnote. [core_data_source]
3. **KPI scorecard** — Metric | Last wk | Prior wk | WoW | Status (RAG vs goal/floor). [core_data_source]
4. **Campaign breakdown** — Campaign | Status | Spend | Purchases | Revenue | ROAS. [core_data_source]
5. **Budget pacing** — MTD spend vs pace · projected EOM · vs target. [Google Ads budgets + spend]
6. **Deep dive(s)** — recurring named "test" slides that mature week to week (e.g. Demand Gen status).
7. **Client-specific deep dive** — varies (e.g. the add-to-cart mirage on a client whose Google conversions over-count add-to-cart vs real purchases).
8. **Action items** — Action | Note | Status; owner inline. The running ledger.

## 4. Budget pacing method
When a client's `monthly_budget` is `TBD`, derive the monthly pace from the sum of ACTIVE campaigns'
daily budgets (same method as `ad-spend-monitor`): pace = Σ(daily budgets) × days; show MTD spend vs
MTD pace and projected EOM. Label the basis ("implied from daily budgets · no fixed monthly mandate").

## 5. Worked example (illustrative — real-purchase lens, WoW current vs prior week)
This is a teaching example, not a real client. It shows the deck structure on a hypothetical account.
- **Scorecard:** Spend $373 / $659 / -43% / Pulled back · Real purchases 0 / 1 / -1 / Below ·
  Real revenue $0 / $136 / -$136 / Below · Purchase ROAS 0.00 / 0.21 / n/a / Below floor.
- **Campaign table:** PMAX | High Intent (ENABLED) $239.58 · 0 · $0 · 0.00 — PMAX | Category
  (PAUSED) $125.50 · 0 · $0 · 0.00 — Brand (ENABLED) $7.75 · 0 · $0 · 0.00.
- **Budget pacing:** pull MTD spend + active daily budgets; show MTD vs pace + projected EOM.
- **Demand Gen deep dive:** ENABLED but NOT_ELIGIBLE, $0/0 impressions; disapprovals + fix order.
- **ATC mirage:** Add-to-cart 74/$8,747 → 20/$2,400 · Begin checkout n/a → 4/$600 · Real purchase
  1/$136 → 0/$0. (Lesson: report on real purchases, not the inflated add-to-cart proxy.)
- **Action items:** Fix+ship Demand Gen (agency+client) · Protect Brand (agency) · Re-point PMAX
  High Intent off ATC (agency) · Client inputs: margin/LTV/budget mandate (client).

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
