---
name: account-ops
description: >-
  Module C of the AI Account Manager — the Google account-ops recommender. Reads
  the living strategy + memory + live data (+ an optional diagnose queue you supply),
  and produces a PRIORITIZED, recommend-only action set (scale / cut / fix / test)
  scored against "maximize conversion value subject to a ROAS floor" and filtered
  through the strategy's refusals (e.g. won't propose capping brand without an
  incrementality test). Recommend-only — you execute; never touches the account.
  Triggers on: "account ops for <client>", "what should we change on <client>",
  "optimization recommendations for <client>", "run the action queue for <client>",
  "what to scale/cut on <client>", /account-ops <client>. Google today; Meta
  optimization is creative-intel (E) + ad-spend-monitor.
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


# Account Ops (Google) — AM Module C

Decide what to change, the way an elite buyer decides it: efficient harvest to the
ROAS floor, scale winners, fix/cut losers, honor the strategy's refusals.
**Recommend-only** — you produce a ranked action set for the operator; you NEVER
change the account.

Project: the package `runtime/` dir · venv `.venv/bin/python`
**Bring your own diagnose step (optional).** This package does NOT ship a Google Ads
diagnose tool. If you have one, have it write
`runtime/clients/<slug>/snapshots/<YYYY-Www>/queue.json`
(`{"generated": "...", "items": [{"kind": "scale|fix|investigate", "rank_score": N,
"predicted_lift": {"abs_delta_at_stake": N}, ...}]}`) and optionally a `SUMMARY.md`
next to it; the scaffold below reads them. Without it the queue is simply empty and
you build the recommendations from the context + live data (Google Ads API / MCP)
yourself.

## Flow
1. **Load the scaffold** (context + optional diagnose queue + doctrine):
   ```
   from lib import account_ops; s = account_ops.scaffold("<client>")
   ```
   `s["context"]` = the living strategy + memory + latest snapshot (READ IT — it
   carries the refusals and current bets). `s["queue_by_kind"]` = your diagnose
   queue (if you supplied one), split into scale / fix / investigate, sorted by
   dollars at stake; empty if you didn't. `s["doctrine"]` =
   the objective function.
2. **Confirm where needed (live data).** Many queue items are "investigate" —
   resolve them with live Google Ads data (API or MCP: search terms, QS, IS-lost,
   Standard-Shopping mirror existence) before recommending. Pull, don't guess.
3. **Write the recommendation set.** For each recommended action:
   - **Action** (scale X +Y% / cut Z / fix W / test V), concrete.
   - **Why**, tied to the doctrine + the strategy bet it serves, with the numbers.
   - **Expected impact** (dollars at stake from the queue) + **reversibility**.
   - **Refusal check**: explicitly honor strategy refusals. E.g. an
     "investigate brand decline" queue item must NOT become "cut brand" — the strategy refuses
     blanket brand caps without an incrementality test; recommend the test instead.
   - **Confidence** (high/med/low) + what would raise it.
   Rank by dollars at stake × strategy relevance. Surface SCALE and CUT with equal
   weight (don't only recommend scaling).
4. **Persist + notify** (recommend-only):
   `account_ops.write_recommendations("<client>", "<YYYY-Www>", md)` then DM yourself
   the top 3 + the doc link via Slack. The recommendations also feed the weekly
   deck's recommendations slide and the action-items table.
5. **Close the loop:** append the decisions to `memory.md` (`context.append_memory`)
   once you act, so next cycle knows what was tried.

## Hard rules
- Recommend-only. No `ads_update_entity`, no budget edits, no Apps Script changes —
  ever, in this skill. (Any budget automation you run elsewhere is separate;
  this skill never invokes it.)
- Honor every refusal in `strategy.md` / memory standing notes. They override the
  raw queue. If your diagnose queue carries its own gates (e.g. `gates.memory`
  citations), respect them and add the strategy's refusals on top.
- Sourced numbers only (verify before you claim). Tie each rec to a real metric.

## Off-switch
Delete this skill folder. The recommender lib is inert unless invoked.
