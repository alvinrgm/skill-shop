---
name: strategy-review
description: >-
  Own the LIVING strategy/positioning layer for a client — the higher-level spine
  the weekly reporting + creative work operates against. Three modes: BACKFILL
  (build strategy.md from all historical context — reporting decks, client calls,
  memory, diagnose snapshots — via the strategy-crystallizer), DRIFT (weekly: check
  if this week's dynamics diverge from the strategy; propose a dated amendment,
  recommend-only), QBR (quarterly: full re-crystallization on the quarter's data +
  a QBR deck). Part of the AI Account Manager. Recommend-only — strategy edits are
  proposed for you to approve. Triggers on: "build the strategy for <client>",
  "backfill <client> strategy", "strategy drift check", "run the QBR for <client>",
  "refresh <client> strategy", "update positioning for <client>", /strategy-review
  <client>.
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


# Strategy Review — AM strategy spine

The reporting + creative analyses are only as good as the strategy + history
behind them. This skill owns the **living strategy layer**:
`runtime/clients/<slug>/strategy.md` (template in `_template/strategy.md`),
which sits ABOVE `memory.md` (tactical history). Built via the
**strategy-crystallizer** skill (Rumelt kernel). **Recommend-only**: you draft
strategy changes; you approve before they're committed as the live strategy.

Project: the package `runtime/` dir · roster: `runtime/clients/<slug>/`

## Mode: BACKFILL (first time, or to rebuild from scratch)
Goal: a strategy.md "fully loaded" with the client's real history + positioning.
1. Gather ALL historical context:
   - `account.md` + `memory.md` (standing notes + tactical history)
   - the latest diagnose snapshot(s) if you supply them (optional; `snapshots/<week>/SUMMARY.md`)
   - the **living reporting deck** (read via Drive; mine the strategic throughline
     across periods — what's been tested, decisions, dynamics; for big decks use a
     subagent + chunked reads)
   - **client/CMO calls** (e.g. via the Granola MCP) — positioning, ICP,
     constraints in the client's own words
   - any local engagement notes for the client
2. Run the **strategy-crystallizer** skill on that corpus → diagnosis (the crux),
   guiding policy, positioning/ICP, objective+constraints, channel strategy,
   current bets, refusals, key dynamics, success metrics, open questions.
3. Write `runtime/clients/<slug>/strategy.md` from the `_template/strategy.md`
   structure. Set Last reviewed + Next QBR. Quote the client's real words.
4. DM yourself the crystallized strategy for sign-off (recommend-only).

## Mode: DRIFT (weekly, after the report)
1. Load the context pack (`weekly_report.py context <client>`).
2. Compare this week's dynamics (from the weekly report) to the strategy's
   diagnosis / current bets / assumptions.
3. If a MATERIAL divergence (a bet is failing, a new dynamic emerged, the
   diagnosis is going stale, a refusal was violated by results): draft a dated
   changelog amendment to the relevant section of `strategy.md` and DM yourself to
   approve. If nothing material changed, say so and make no edit. Most weeks = no
   change; the value is catching the real inflection early.

## Mode: QBR (quarterly)
1. Pull the quarter's accumulated memory + snapshots + reporting + creative-intel
   findings.
2. Re-run the strategy-crystallizer fresh on the quarter (don't just tweak —
   re-diagnose). Produce the updated strategy.md (full changelog entry: what
   changed this quarter and why) for your approval.
3. Build a **QBR deck**: reuse the deck appender (`weekly_report.py`) patterns or
   a dedicated section — quarter-in-review (vs the success-metric scorecard),
   what we learned, the refreshed strategy + next-quarter bets. Native Slides via
   your deployed bridge. Recommend-only; review before it goes to the client.
4. Stamp Next QBR = +1 quarter.

## Rules
- Recommend-only: every strategy edit is proposed, not silently committed.
- Every change = a dated changelog line in strategy.md (what + why + trigger).
- Quote the client's own words for positioning where possible.
- The strategy spine is the SLOW layer; resist churn. Weekly drift should change
  it rarely; QBR is the real refresh cadence.

## Off-switch
Delete this skill folder. strategy.md files are plain docs.
