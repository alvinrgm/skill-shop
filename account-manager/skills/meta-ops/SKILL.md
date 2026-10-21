---
name: meta-ops
description: >-
  Module E of the AI Account Manager — the full Meta account-ops analyzer (the
  Meta sibling of Module C / Google). Audits a Meta ad account the way an elite
  buyer does — campaign structure & setup, audience utilization, bidding & budget,
  placements, measurement/attribution, signals (CAPI), and creative (via
  creative-intel) — scored against best practices (meta-ops/rubric.md) + Meta's
  own opportunity score + the client's living strategy, and produces a prioritized,
  RECOMMEND-ONLY action set. Never changes the account. Triggers on: "meta audit
  for <client>", "audit our meta account", "meta account ops for <client>",
  "what should we change on meta", "meta optimization for <client>", "review meta
  structure/audiences/bidding for <client>", /meta-ops <client>. Works for any
  Meta client you configure.
---

<!-- ═══════════ FIRST-RUN ONBOARDING GATE ═══════════ -->
## ⚙️ First run? Onboard before doing anything else

**Gate:** locate the `account-manager` package dir (where `SETUP.md`, `doctor.sh`, and
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


# Meta Account-Ops — AM Module E (full Meta analyzer)

The Meta equivalent of the Google diagnose ladder + recommender. Audit the account
across every dimension an elite Meta buyer cares about, score against
`runtime/meta-ops/rubric.md` + Meta's opportunity score + the living strategy, and
output a ranked **recommend-only** action set. **Never touch the account** (no
`ads_update_entity`, no budget/audience/bid edits — ever).

Project: the package `runtime/` dir · venv `.venv/bin/python`
Rubric: `runtime/meta-ops/rubric.md`.
Meta data is MCP-only → this is a Claude-in-the-loop skill: you pull via the Meta
Ads MCP, hand JSON to the deterministic helpers, and write the judgment.

## Flow
### 0. Load context
`weekly_report.py context <client>` — read the strategy (objective, NC-ROAS
steering, refusals, bets) BEFORE auditing. The strategy can justify an apparent
"gap" (e.g. a deliberate ABO/transparency choice). Get the Meta `act` id from
`account.md` (`meta_account_id`).

### 1. Pull the audit data (Meta MCP)
- **Opportunity score:** `ads_get_opportunity_score(act)` — score + ranked recs
  (CAPI, CBO, Advantage+ Audience/Placements, Shops, scale). The prior.
- **Structure:** `ads_get_ad_entities` level=campaign (objective, buying_type,
  daily/lifetime_budget, bid_strategy, spend) and level=adset (optimization_goal,
  bid_strategy, daily_budget, attribution_setting, spend).
- **Audiences:** `ads_get_ad_account_custom_audiences(act)` — subtype, delivery_status,
  size; spot stale "[Not maintained]" still ACTIVE, overlapping LALs, empty (~20).
- **Auction/overlap:** `ads_insights_auction_ranking_benchmarks(act)` — fragmentation.
- **Benchmarks:** `ads_insights_industry_benchmark(act, conversation_topic=...)`
  per dimension as needed.
- **Experiments:** `ads_experiment_list_tests(act)` — is lift/A-B testing happening?

### 2. Score each dimension (run the helper for the structural flags)
```
from meta_ops_audit import audit   # account-manager/meta-ops/audit.py
flags = audit(campaigns_json, adsets_json, audiences_json, opp_score_json)
```
Returns deterministic flags: CBO/ABO split, ASC fragmentation count, bid-strategy
mix, optimization-goal mix, attribution-window consistency, learning-risk small
ad sets, stale/overlapping/empty audience counts, top opp-score lifts. Then apply
the rubric's 7 dimensions (§1 structure, §2 audiences, §3 bidding/budget, §4
placements, §5 measurement, §6 signals, §7 creative) — judgment on top of flags.

### 3. Creative dimension
Run / fold in the `creative-intel` skill output (hook/retention/winners, format
mix, refresh cadence). It's dimension §7, not the whole audit.

### 4. Write the recommendation set (recommend-only)
Per dimension: status (strong/ok/gap) · evidence (tool + numbers) · recommendation
(concrete) · expected lift (opp-score points / benchmark delta) · effort &
reversibility · strategy check (does the strategy already justify it?). Rank by
lift × fit. Honor strategy refusals. Surface BOTH quick wins (CAPI, kill stale
audiences) and structural plays (consolidate ASC, CBO test, value bidding).
Persist: `lib/account_ops.write_recommendations(client, period, md)` (or a
META-OPS-<period>.md in the snapshot dir) + DM yourself the top 3 + link. Feed the
weekly deck's Meta section.

### 5. Close the loop
Append notable findings/decisions to `memory.md` (`context.append_memory`).

## Hard rules
- Recommend-only. No account mutations of any kind in this skill.
- Best-practice targets are defaults; the strategy/memory override them — always
  run the strategy check before calling something a gap.
- Sourced numbers only (opp score, benchmarks, real entity data). No invented lifts.
- Signals (CAPI) is usually the highest-leverage fix — check it first.

## Off-switch
Delete this skill folder. Helpers under `runtime/meta-ops/` are inert unless invoked.
