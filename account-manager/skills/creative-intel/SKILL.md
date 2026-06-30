---
name: creative-intel
description: >-
  Meta creative intelligence — analyze video ads second-by-second with computer
  vision (script, on-screen text, shots, pacing, hook), align that to each ad's
  retention curve + hook/CTR/CVR/ROAS, run a cross-video regression to find which
  creative features ASSOCIATE with performance, mine comments, and propose Meta
  A/B experiments (the rigorous causal path). Recommend-only. Part of the AI
  Account Manager (see the package `runtime/` dir). Triggers on: "creative
  analysis for <client>", "analyze our Meta video ads", "what's driving hook rate
  / CTR on <client>", "which creatives are winning and why", "creative intel",
  "tear down our ads", /creative-intel <client>. Works for any Meta client (+
  competitor benchmarking via the Ads Library).
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


# Creative Intelligence (Meta) — AM Module E

Find what in the *creative itself* drives performance. The hard honesty up front,
because it shapes every claim you make:

- **Meta exposes quartile retention only** (p25/p50/p75/p95/p100 + thruplay + 3s),
  NOT a per-second curve (`video_play_curve_actions` is not available). So the
  *creative* is analyzed per-second; *retention* is quartile-resolution.
- **Observational data cannot prove causation** (audience, budget, bid, placement
  all move with creative). Cross-video findings are CORRELATIONAL — label them so,
  with effect size + sample size. The rigorous causal path is the **A/B experiment
  proposals**, which are recommend-only.
- **Recommend-only**: never changes an account; never creates an experiment without
  your explicit approval.

Code: the package `runtime/creative-intel/` dir · venv:
`runtime/.venv/bin/python`

## Pipeline

### 0. Load the context pack first
`runtime/.venv/bin/python weekly_report.py context <client>`
Read the living strategy + memory before judging creatives — what's the positioning,
what hooks/angles have been tried, what won/failed before. Creative findings must be
read against this (e.g. a "winning" hook that contradicts a known failed test is a
flag, not a recommendation). Write notable creative learnings back to memory at the
end (`context.append_memory`).

### 1. Pull Meta data (you, via the Meta Ads MCP)
For the client's ad account (the `act` id is in `account.md` as `meta_account_id`),
pull ad-level video ads over the window with `ads_get_ad_entities` (level=ad),
fields: `impressions, reach, spend, ctr, video_p25/p50/p75/p95/p100_watched_actions,
video_thruplay_watched_actions` + outcomes via the actions breakdown (purchases,
link clicks → derive CVR, ROAS). Get creatives + the video_id per ad with
`ads_get_creatives` / `ads_get_ad_videos`. (Scripts can't call MCP — this step is
yours; hand the numbers to the scripts as JSON.)

### 2. Get the video file for each ad
- **Your ads:** match the Meta video title to the SOURCE file (if you made them) —
  search your ad-production folders and project tree for the .mp4. Source files are
  cleaner than re-downloading from Meta (the permalink isn't a direct mp4).
- **Competitors (benchmarking):** `ads_library_search` for the category/competitor,
  download the library video, analyze the same way. Label as competitor.

### 3. CV per ad (script)
`creative-intel/cv_analyze.py --video PATH --out cv_<label>.json --label <name>`
→ per-second timeline (shot, on-screen text, verbatim script, cuts, product, hook)
+ ad-level descriptors (style, hook archetype, time-to-product, cuts/10s, text
density, claim type, CTA timing, tone, pacing). Uses Gemini (reads the package
`.env` for `GEMINI_API_KEY`). Runs on each ad's video.

### 4. Align retention to creative (script/lib)
`from align import align; align(cv_dict, metrics_dict)` → maps the quartile
drop-offs + hook onto the per-second timeline: hook rate (p25/impr), hold
(p100/p25), the retention curve annotated with what's on screen at each point, and
the BIGGEST DROP with its creative cause ("89% gone by ~7s, at the factory cut").
Within-video, descriptive.

### 5. Cross-video regression (script/lib)
Build one record per ad: `{"label","features": <cv descriptors + duration>,
"metrics": {hook_rate, ctr, cvr, roas, spend}}`. Then
`from analyze import analyze; analyze(records)` → ranked associations of each
feature vs each outcome, with Pearson r / level-lift, sample size, and a
low-confidence flag for n<6. ALWAYS present these as correlational with the
built-in caveat — never as "X causes Y".

### 6. Comment mining (you, via MCP)
For top ads, pull the post comments (`ads_get_ig_media` / the creative's
object_story_id) and cluster sentiment + themes (what resonates / objections).
Qualitative layer on the quant.

### 7. Experiment proposals (script/lib)
`from experiments import propose; propose(analysis_dict)` → ranked Meta A/B test
proposals (hypothesis, control vs variant, primary metric, budget/cell, run days).
**Recommend-only.** Create a test only after you approve, via
`ads_experiment_abtest_create_test`.

### 8. Report
Assemble a Creative Intelligence report: per-ad teardown (aligned retention + the
drop + hook read), the cross-video drivers (honestly labeled), comment themes, and
the experiment slate. Deliver as a Google Doc via your deployed bridge (see
`bridge/SETUP.md`) and/or feed the weekly deck's creative section. DM yourself the
headline via Slack. Log to `history/audit/`.

## Honesty rules (enforce on every output)
- Per-second is the CREATIVE; retention is QUARTILE. Say so.
- Cross-video = correlational, confounded, n-flagged. Never "causes".
- Experiments are the only causal claim path, and they're proposals until approved.
- Sourced numbers only — no invented metrics.

## Off-switch
Delete this skill folder. The scripts under `runtime/creative-intel/` do nothing
unless invoked.
