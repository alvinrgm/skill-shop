---
name: account-ops
description: >-
  Module C of the AI Account Manager — the Google account-ops recommender. Reads
  the living strategy + memory + the google-ads diagnose ladder/queue + live data,
  and produces a PRIORITIZED, recommend-only action set (scale / cut / fix / test)
  scored against "maximize conversion value subject to a ROAS floor" and filtered
  through the strategy's refusals (e.g. won't propose capping brand without an
  incrementality test). Recommend-only — you execute; never touches the account.
  Triggers on: "account ops for <client>", "what should we change on <client>",
  "optimization recommendations for <client>", "run the action queue for <client>",
  "what to scale/cut on <client>", /account-ops <client>. Google today; Meta
  optimization is creative-intel (E) + ad-spend-monitor.
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


# Account Ops (Google) — AM Module C

Decide what to change, the way an elite buyer decides it: efficient harvest to the
ROAS floor, scale winners, fix/cut losers, honor the strategy's refusals.
**Recommend-only** — you produce a ranked action set for the operator; you NEVER
change the account.

Project: the package `runtime/` dir · venv `.venv/bin/python`
Reuses the existing `google-ads/diagnose` doctrine (L0-L3 + gated queue) — do
not reinvent it.

## Flow
1. **Load the scaffold** (context + diagnose queue + doctrine):
   ```
   from lib import account_ops; s = account_ops.scaffold("<client>")
   ```
   `s["context"]` = the living strategy + memory + latest snapshot (READ IT — it
   carries the refusals and current bets). `s["queue_by_kind"]` = the diagnose
   queue, already mechanism-classified and gated (incl. memory-veto gates), split
   into scale / fix / investigate, sorted by dollars at stake. `s["doctrine"]` =
   the objective function.
2. **Confirm where needed (live data).** Many queue items are "investigate" —
   resolve them with the `google-ads/` scripts (search terms, QS, IS-lost,
   Standard-Shopping mirror existence) before recommending. Pull, don't guess.
3. **Write the recommendation set.** For each recommended action:
   - **Action** (scale X +Y% / cut Z / fix W / test V), concrete.
   - **Why**, tied to the doctrine + the strategy bet it serves, with the numbers.
   - **Expected impact** (dollars at stake from the queue) + **reversibility**.
   - **Refusal check**: explicitly honor strategy refusals. E.g. the W19 queue's
     "investigate brand decline" must NOT become "cut brand" — the strategy refuses
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
  ever, in this skill. (The budget-automation script is a separate, already-gated
  auto-actor; this skill does not invoke it.)
- Honor every refusal in `strategy.md` / memory standing notes. They override the
  raw queue. The diagnose queue already runs a memory-veto gate — respect its
  `gates.memory` citations and add the strategy's refusals on top.
- Sourced numbers only (eval-before-claiming). Tie each rec to a real metric.

## Off-switch
Delete this skill folder. The recommender lib is inert unless invoked.
