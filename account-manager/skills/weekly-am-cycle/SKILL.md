---
name: weekly-am-cycle
description: >-
  The full recurring weekly AI Account Manager cycle for your clients — the
  orchestrator a scheduled local routine invokes (and that you can run by hand).
  Per client it: loads strategy+memory context, runs the serving/disapproval +
  freshness checks, pulls the week's data from the client's LOCKED core data source,
  frames a Barbara-Minto/BLUF analysis, updates the live reporting deck in place (the
  dark dense reporting format with screenshot placeholders), saves to memory, writes
  recommendations, and DMs you via Slack. EXECUTION of approved ad-account changes is
  the AM's job too, but happens INTERACTIVELY after you approve the specific change —
  never unattended. Triggers on: "run the weekly account manager cycle", "weekly AM
  run", "run the weekly-am-cycle", "execute the approved <client> changes",
  /weekly-am-cycle.
---

<!-- ════════════════════════════════════════════════════════════════════════
     FIRST-RUN ONBOARDING GATE
     Runs BEFORE the workflow on a fresh install. Generated from dependencies.yml.
     ════════════════════════════════════════════════════════════════════════ -->

## ⚙️ First run? Onboard before doing anything else

**Gate:** locate the `account-manager` package directory (where `SETUP.md`, `doctor.sh`,
and `dependencies.yml` live — the repo the skills were copied from). If a `.onboarded` file does
NOT exist there, do NOT start any reporting/cycle run — onboard first. If it exists, skip this
section. (Re-onboard anytime: delete `.onboarded` or say "re-run setup".)

### Onboarding flow
1. **Health check.** `cd` to the package dir and run `bash doctor.sh`. Read the ✅/❌ list. If all
   REQUIRED items are ✅ and MCP tools are present (step 3), jump to step 4.
2. **Walk each ❌ one at a time, in order.** Look it up in `dependencies.yml`. For each: say what
   it powers in one line, give the real `get_url`, then *offer to do the work* (it's their machine):
   - **python** → "want me to run `pip install -r requirements.txt`?" → run on yes, re-check.
   - **env-key** (SLACK_WEBHOOK, GEMINI_API_KEY, GOOGLE_ADS_*, META_ACCESS_TOKEN, TRIPLEWHALE_API_KEY)
     → "grab it from `<get_url>`, paste it, I'll write it to `runtime/.env`." Write `KEY=value`
     (create from `runtime/.env.example` if absent). **Never echo a key back.**
   - **Apps Script bridge** (BRIDGE_URL/BRIDGE_SECRET) → walk them through `bridge/SETUP.md` to
     deploy THEIR OWN bridge, then verify with `python3 bridge/verify_bridge.py`.
   - **roster** → offer to `cp -R runtime/clients/_template runtime/clients/<slug>` and help fill
     `account.md`.
3. **MCP connections** (Meta Ads, Shopify, Granola — optional). Give the connect command
   (`claude mcp add ...`), note a restart may be needed, then **verify the tools are actually
   callable** (a shell script can't — this is why the gate exists). Skip any the user doesn't want.
4. **Confirm green & mark done.** Re-run `bash doctor.sh`. When required items are ✅, write
   `.onboarded` in the package dir (`date > .onboarded`). Then give the first kickoff line:
   **"build the weekly deck for <your-client-slug>"** and one line on what happens next.

Keep it warm and brief — one dependency per exchange, link + action, move on.

<!-- ═══════════════════════ END ONBOARDING GATE ═══════════════════════════ -->

# Weekly AM Cycle (orchestrator)

Canonical role + scope: `runtime/AM-SCOPE.md`.
Reporting deck spec: `runtime/REPORTING-SPEC.md`.
This skill SEQUENCES the pieces that already exist — it does not reinvent them.

**Autonomy model.** The scheduled weekly run goes: analyze → build the deck → write recs →
TAP you. It does **NOT change ad accounts unattended** (no approval is available in a
scheduled run). **Execution of approved changes IS the AM's job** — but it happens in the
**interactive Execution mode** below, after you approve the specific change. Never send
anything to a client; never push to production / deploy.

System home: the package `runtime/` dir ·
venv: the package `.venv` (install the optional `google-ads` library into it for the serving check).

## Roster
Every client with an `## AM reporting` section in `runtime/clients/<slug>/account.md`
(`weekly_report.py roster`). Some clients also run Meta.

## Per-client weekly sequence (the scheduled run)
1. **Load context:** `runtime/.venv/bin/python weekly_report.py context <client>` — read the
   living strategy + memory first. Honor the refusals and measurement lens.
2. **Deterministic checks:** `runtime/.venv/bin/python serving_check.py --dry` (serving/
   disapproval; needs the optional `google-ads` library + OAuth — skip if you don't use Google) + `weekly_report.py check <client>` (freshness). Note any issues; don't report on
   stale data.
3. **Pull the week's data** from the client's **LOCKED `core_data_source`** in account.md
   (e.g. `google_ads`, `triple_whale`, `google_ads_looker`). Show the **actual purchase-value
   ROAS**. Do NOT editorialize about an "add-to-cart mirage" or "fake ROAS" — just report the
   real numbers.
4. **Analyze — Barbara-Minto / BLUF.** Answer first. Telegraphic. Surface only what's **new or
   strategy-following** (updates, not everything). No em-dashes.
5. **Update the live reporting deck IN PLACE** per `REPORTING-SPEC.md`: dark brand, modeled
   order — **Cover → Date → Big point → Reporting slide(s) → Deep dives → Action items → Budget
   pacing → Strategy recap**. Reporting slides are **2-pane, dense, small font**: analysis on the
   LEFT (metric takeaway + bold **Observations** / **Next steps** bullets), and a **screenshot
   PLACEHOLDER on the RIGHT** — the human AM pastes the real data table; **you do NOT render the
   data table**. Additive only; **render-and-eyeball every changed slide** (verify the render, not
   the API). Reference build: a short script using the vendored `deck-engine/` + the panel
   placeholder (see `runtime/example_report_add.py`).
6. **Save to memory:** append a dated tactical entry to `<client>/memory.md`; flag any strategy drift.
7. **Write recommendations** (account-ops) — prioritized.

## Tap you (hand-off)
DM via Slack (`runtime/lib/slack.py`) a per-client summary: BLUF, deck link, serving flags,
and the top recs awaiting approval. You approve; execution follows in interactive mode.

## Execution mode (interactive, post-approval — the corrected scope)
When you explicitly approve recommendations (e.g. "execute the approved changes"),
**EXECUTE them via the ad APIs** — Google Ads (`ads:write`) and Meta (`ads_update_entity` etc.).
Rules: one change at a time; confirm each maps to a rec you actually approved; after each, log
exactly what was changed to `<client>/memory.md`. **Never execute a change you haven't explicitly
approved, and never execute in the unattended scheduled run.**

## Hard rules (every run)
- Execute account changes ONLY on explicit per-change approval; never unattended, never unapproved.
- Never send anything to a client; never push to production / deploy.
- Reporting: the human pastes the data screenshot; you build the placeholder + analysis. No mirage
  framing; show real purchase-value ROAS.
- Additive deck writes; render-and-eyeball every changed slide. **Never delete/trash/move a deck
  without explicit per-deck approval.**
- Sourced numbers; real-purchase lens.

## Run modes
- **Scheduled routine (optional, one you set up yourself):** runs the per-client sequence + tap for the whole roster. No execution.
- **Interactive:** "run the weekly-am-cycle for <client>" (one client) · "execute the approved
  <client> changes" (execution mode).

## Off-switch
Delete this skill folder, or disable any scheduled routine you created for it.
