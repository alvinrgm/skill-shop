# Meta Account-Ops Rubric — what elite Meta advertisers audit

The knowledge base the `meta-ops` audit scores against. Module E (Meta) is the
Meta sibling of Module C (Google). Recommend-only. Score each dimension, surface
gaps vs best practice AND vs the client's strategy. Pair every finding with the
MCP tool that evidences it. Best-practice targets are defaults — the strategy +
memory override them (e.g. a deliberate ABO/transparency choice is not a "gap").

## 0. Start here
- **Meta Opportunity Score** (`ads_get_opportunity_score`) — Meta's own 0–100 +
  ranked recommendations (CBO, Advantage+ Audience, Automatic Placements, CAPI,
  Shops, scale-good-campaign). Use as a prior, not gospel; reconcile with strategy.
- **Industry benchmarks** (`ads_insights_industry_benchmark`, by topic:
  AUDIENCE / BUDGET_AND_BIDDING / CAMPAIGN_DIMENSIONS / PLACEMENTS / SIGNALS /
  MEASUREMENT / CREATIVE) and **auction-ranking benchmarks**
  (`ads_insights_auction_ranking_benchmarks` — overlap/fragmentation).

## 1. Campaign structure & setup
Pull: `ads_get_ad_entities` level=campaign (objective, buying_type, daily/lifetime_budget, bid_strategy, spend).
- **Consolidation:** few, well-fed campaigns beat many fragmented ones. Red flag:
  many ASC/prospecting campaigns competing for the same audience (auction overlap,
  budget fragmentation, slower learning). Target: consolidate to a small set.
- **CBO vs ABO:** Advantage campaign budget (CBO) lets Meta allocate; ABO fixes it
  per ad set. Best practice trends CBO for prospecting unless there's a reason to
  fix budgets. Red flag: ABO everywhere with no CBO comparison ever run. (Honor
  strategy: a deliberate ABO choice for control is valid.)
- **Objective consistency:** all conversion/sales campaigns on OUTCOME_SALES.
  Red flag: mixed objectives, traffic/engagement objectives masquerading as DR.
- **ASC adoption:** Advantage+ Shopping is the modern prospecting workhorse — good
  to use, bad to fragment into many parallel ASCs.

## 2. Audience utilization
Pull: `ads_get_ad_account_custom_audiences`; ad-set targeting; auction overlap.
- **Broad vs fragmented:** modern Meta rewards broad + strong signal + ASC over
  many narrow interest/LAL ad sets. Red flag: lots of small interest ad sets.
- **Audience hygiene:** Red flags — stale or unmaintained audiences left ACTIVE;
  many overlapping lookalikes of the same seed at different percentages;
  empty/broken custom audiences (tiny or zero size = not populating);
  missing or unmaintained exclusions.
- **Retargeting + exclusions:** healthy RT coverage; **new-customer exclusion**
  applied where prospecting (so spend isn't recycling existing customers — ties to
  NC-ROAS steering). Red flag: prospecting without an existing-customer exclusion.
- **Advantage+ Audience:** opp score often recommends it; consider vs manual.

## 3. Bidding & budget
Pull: campaign/adset bid_strategy, daily/lifetime_budget, optimization_goal, spend.
- **Bid strategy fit:** lowest-cost (Highest volume) = max volume, no cost control;
  cost cap / bid cap / **minimum ROAS / highest value** = control. For a ROAS-floor
  business, consider value/minimum-ROAS bidding on scaled, stable campaigns to
  enforce the floor; keep lowest-cost on prospecting/learning. Red flag: zero
  value-based bidding anywhere despite a hard ROAS floor.
- **Optimization goal:** should be OFFSITE_CONVERSIONS (purchase) or VALUE for DR.
  Red flag: ad sets optimizing to LPV/clicks/engagement while expecting purchases.
- **Budget adequacy / learning:** an ad set needs ~50 optimization events/week to
  exit learning. Red flag: many tiny ad sets ($20–50/day) at low AOV → stuck in
  "learning limited," fragmented spend. Consolidate budget into fewer ad sets.

## 4. Placements
- **Advantage+ (automatic) placements** > manual in most cases (more auctions,
  cheaper results). Red flag: manual placements without a tested reason; Reels/
  Stories excluded. Opp score `AUTOMATIC_PLACEMENTS` flags this.

## 5. Measurement & attribution
Pull: adset `attribution_setting`; experiments (`ads_experiment_list_tests`).
- **Attribution consistency:** pick a standard (e.g. 7d-click/1d-view) and apply
  it. Red flag: mixed windows across ad sets (some 1d-click-only undercounts and
  distorts comparison). 
- **Incrementality / lift:** elite accounts run lift/geo tests, not just
  last-click. Good: an incrementality-attributed test exists. Tie to the strategy's
  NC-ROAS steering + any brand incrementality test the strategy calls for.
- **NC steering:** is new-customer ROAS the optimization target (value rules,
  exclusions, TW/Northbeam sync)? 

## 6. Signals (the highest-leverage, most-ignored)
Pull: `ads_get_opportunity_score` (capi_event_coverage), datasets/pixel tools.
- **CAPI coverage:** server-side Conversions API coverage for Purchase. Meta's own
  data: 75%+ coverage ≈ much lower CPA. Red flag: low CAPI coverage = the single
  biggest fix on most accounts. Almost always top priority.
- **Event quality / dedup:** pixel+CAPI deduplicated, EMQ high, purchase value
  passed.

## 7. Creative (Module E's original scope — now one dimension)
Run the `creative-intel` skill: volume, refresh cadence, hook/retention/winners,
format mix (image+video), UGC vs studio, the cross-video drivers + experiments.
- Red flags: few active creatives, no refresh cadence, ad-underservice (a few ads
  eat all spend), single format.

## Scoring + output
For each dimension: **status** (strong / ok / gap), the **evidence** (tool +
numbers), the **recommendation** (recommend-only, concrete), **expected lift**
(use opp-score points / benchmark deltas where available), **effort/reversibility**,
and a **strategy check** (does the client's strategy already justify the current
state?). Rank recommendations by lift × fit. NEVER execute changes.
