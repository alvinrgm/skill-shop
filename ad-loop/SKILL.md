---
name: ad-loop
description: >
  Static ad loop: brief in, finished static ads out. Runs a one-round intake
  interview (client + URL, win condition, angles, copy direction, North Stars),
  harvests the brand's assets from its URL (pack shots, palette, fonts, reviews,
  claim candidates, Ad Library page ids), builds the client layer, then runs a
  recursive quality loop (volume plate generation, scripted triage, build,
  a five-instrument judge battery, convergent fixes) until each ad clears an 85/100
  ship bar or plateaus with a named ceiling. Bare "/ad-loop" launches the journey
  from the interview; it resumes an in-flight concept only when one exists and
  nothing says "start fresh". Triggers on: "/ad-loop", "run the ad loop for
  <client>", "onboard <client> to the ad loop", "ad loop intake <url>", "make
  static ads for <client>", "iterate this ad until it's good", "loop this
  concept". Statics only, not video. Recommend-only: it never writes to an ad
  account unless the operator explicitly asks for a paused draft.
---

# Static ad loop

## FIRST RUN: onboarding gate

If `.onboarded` does NOT exist in this folder, do this BEFORE any ad work. Every
dependency is listed in `dependencies.yml` (the single source of truth); walk it.

1. Run `python3 config.py --init` first (stdlib only; creates the work root
   `AD_LOOP_HOME`, default `~/ad-loop-work`, with an empty loop-state, and never overwrites
   anything), then `bash doctor.sh` (Windows: `powershell -ExecutionPolicy Bypass -File
   doctor.ps1`) and read the ❌ lines.
2. Walk each ❌ one at a time. For each, say what it powers, give the link, and offer to
   run the fix:
   - **Python packages** (`python_deps`): offer a virtual environment in this folder
     (PEP 668 systems refuse a global pip install):
     `python3 -m venv .venv && . .venv/bin/activate && python3 -m pip install -r requirements.txt`.
     Once `.venv` exists, every script and `doctor.sh` use it automatically.
   - **Node.js 20+ + npm** (`node`, `npm`): the static-kit renderer turns every ad into
     pixels. Point them to <https://nodejs.org/> (or `brew install node`).
   - **Chromium for the renderer** (`chromium_node`): offer
     `cd runtime/static-kit && npm install && npx playwright install chromium`
     (on Linux: `npx playwright install --with-deps chromium`).
   - **Chromium for Python** (`chromium_python`): powers the inspo harvester, the Ad
     Library page-id lookup and the feed mock. Offer `python3 -m playwright install chromium`
     (both sides pin Playwright 1.62.0, so this reuses the renderer's download).
   - **ffmpeg / ffprobe** (`ffmpeg`): the feed-gate composites each ad into phone chrome
     and runs the ablations. Offer `brew install ffmpeg` (or `apt install ffmpeg`).
   - **Gemini API key** (`gemini_key`, `GEMINI_API_KEY`). REQUIRED, and the most
     important step: it powers ALL plate generation and every vision instrument.
       1. Send them to <https://aistudio.google.com/apikey>.
       2. Sign in with a Google account and click **Create API key**.
       3. They paste it into `.env` (copy `.env.example` first) as `GEMINI_API_KEY=...`.
          If they paste it in chat instead, YOU write it to `.env` and never echo it back.
       4. Verify for real: `python3 loop-engine/selftest.py --live` makes one real vision
          call. Fix and re-run until it passes.
     Image generation is billed by Google per image (see the pricing link in
     `dependencies.yml`); the loop's spend guard caps plates per batch.
3. Run `python3 config.py` (prints the resolved environment) and
   `python3 loop-engine/selftest.py` (no API calls; must print 8/8).
4. Optional inputs, never blockers:
   - **North Stars** (`north_stars`): 5-15 elite static ads (any brand) that set the bar,
     dropped into `<work>/north-stars/`. If they have none, the launch interview proposes
     candidates from the Ad Library and the operator confirms.
   - **Meta Ads connector** (`meta_ads`): only needed if they want finished ads uploaded as
     PAUSED drafts. Without it the loop stops at an upload packet.
5. Re-run `bash doctor.sh`. When every REQUIRED dep is ✅, write `.onboarded` and offer the
   first run: "Give me a brand URL and I'll start the intake interview."

The one input every run needs is the **client brand URL** (`client_url`), asked in the
interview. On later runs `.onboarded` exists: skip straight to the work.

---

Runs a static ad through as many instrumented rounds as it takes to be genuinely good, or
to prove it cannot get there and say exactly why. Client-agnostic by construction:
onboarding a new client is writing their per-client layer, nothing else. Standalone: every
piece it needs ships in this folder.

**Paths.** `<pkg>` is this folder. `<work>` is the work root `config.py` prints
(`AD_LOOP_HOME`). Per client: `<work>/<client>/`.

| piece | where |
|---|---|
| design laws (the taste law) | `design/design-laws.md` |
| build pipeline | `reference/build.md` + `runtime/static-kit/` |
| instruments | `loop-engine/` (vision, triage, physics, zones, device, glance, claims) |
| feed survival gate | `runtime/feed-gate/` |
| image generator | `runtime/gen/gen_image.py` |
| asset Library | `runtime/lib/asset_library.py`, `runtime/lib/ref_sheet.py` |
| copy gate | `runtime/scrub/scrub.py` (+ `ai-isms.txt`) |
| judge prompts, rubric, logging | `reference/` |

## Library first

Every client has ONE asset Library at `<work>/<client>/library/` (`library.json` plus files
by type: product, location, character, plate, reference). Before making or hunting for a
reference image, ask it; after making a keeper, register it.

```bash
python3 runtime/lib/asset_library.py seed <client>      # register intake's pack shots (library/seed.json)
python3 runtime/lib/asset_library.py list <client>
python3 runtime/lib/asset_library.py refs <client> <id> # approved entries only
python3 runtime/lib/asset_library.py add <client> --type plate ...
python3 runtime/lib/asset_library.py gate <client> <id> --print
python3 runtime/lib/ref_sheet.py --type product|location|character ...
```

Only `approved` entries come back from `refs`, so a draft never silently seeds a paid
roll. Record every use (`use --by <concept>`). The charter reads the Library for the pack
and location refs before any generation; a plate that wins triage is registered
(`add --type plate`) and its print gate is written by `gate --print`.

## 0a. The front door: mode routing

**Bare `/ad-loop` (or "run the ad loop for <client>") = LAUNCH**: the end-to-end workflow,
starting with a one-round intake interview (client + URL, win condition, angle priorities,
copy direction, hard rules, North Stars, cadence), then URL asset harvest, client layer,
charter, and the loop through to finished ads. The operator answers one round and can walk
away. Full sequence and question pack: `reference/launch-intake.md`.

LAUNCH always begins with **PREFLIGHT** (`reference/launch-intake.md` stage 0):
`python3 config.py` green, or a guided setup conversation. A new machine gets onboarding,
not an error. Key-presence checks go through `config.py`
(`python3 -c "import config; print(config.gemini_key_present())"`), **never a shell
`grep` or `cat` of `.env`**: that would put the key in the transcript.

RESUME (report state, continue the loop) happens ONLY when an in-flight concept exists for
the named client AND nothing in the ask says "start fresh". When in doubt, ask one line:
"launch fresh, or resume <concept> at iteration N?" Never assume resume. The journey is
the product; the state machinery is plumbing.

## 0b. Cold-session bootstrap: the exact read order

A fresh session with zero conversation memory must be able to run an iteration. Read in
this order, every time, before doing anything:

| # | read | why |
|---|---|---|
| 1 | `python3 config.py` | resolves every path and key and prints what is missing. Fix any REQUIRED line first. |
| 2 | `<work>/loop-state/learnings.md` | the numbered doctrine store. **All of it.** It is the compounding asset and it grows during a run, so re-read it after any long dispatch. Cite by block; never renumber. |
| 3 | `reference/RUBRIC.md` (and `<work>/loop-state/RUBRIC.md` if it has diverged) | how "good" is judged. |
| 4 | `design/design-laws.md` | the laws. Read them; do not restate them. |
| 5 | `<work>/loop-state/verdict-bank/README.md` | the operator's real verdicts in their exact words. |
| 6 | `<client>/brand/art-direction.md` + `bible.md` + `ad-creative-principles.md` + `approved-claims.md` | the client layer. See `reference/client-layer.md`. |
| 7 | `<client>/personas/README.md` + the persona files | the resonance judges and their JUDGE PROTOCOL. |
| 8 | the tail of `<client>/statics/loop-state/iterations.jsonl` (`config.client_iterations(slug)`) | where this concept actually is. This is the ONE home for the log; write nowhere else. |
| 9 | the North-Star folder (`config.NORTH_STARS`) | the operator's hand-picked bar. Look at the images, do not just list them. |

Then, and only then, state where the loop stands and what iteration N+1 is.

**The disk contract.** This folder plus the state files above are the loop's ENTIRE
state. Every verdict, score and learning is written to disk the moment it exists. A
compaction or a session death costs a re-read, never a finding.

---

## 1. Doctrine: the five governing beliefs

These outrank convenience, a judge's opinion and the orchestrator's own preference.

### WIDE, NOT NARROW
Never narrow the play just to stay safe; uphold quality while staying wide.

**No lane is ever banned.** Organic macro, full generated scenes, characters, humans,
type-only: all open. Quality is upheld by volume batches, instrumented triage and the
gates, **never by shrinking the creative surface**.

- A judged kill closes a **FILE** and teaches a **FILTER**. It never closes a lane.
- A learning may add a filter or a technique. It may **not** close a lane.
- Lane bans require a failed VOLUME batch plus triage, never a first roll.
- Scene rule: generate the whole world in ONE render. Compositing pieces is what gets
  caught: a single render has no seam to measure.
- Character rule: cull on anatomy across a volume batch BEFORE composing.

### ASSETS ARE THE ENGINE, NOT THE BOTTLENECK
In a generative workflow a missing asset is a **generation brief**, never a blocker.
Recommending a photo shoot before running a volume batch is the banned move.

The architecture: **up to 15 plates per shot at 1K** (`config.VOLUME_BATCH_CAP` /
`VOLUME_PLATE_SIZE`; 4K is for the locked winner only, because volume times 4K is what
makes a day expensive) → the scripted physics and anatomy instruments run as
**PRE-FILTERS over the batch** (not as executioners after a single build) → compose only
from survivors. Every named tell from every kill becomes the next batch's prompt
constraint. A typical survival curve: a full batch narrows to a minority of physics-clean plates and
a handful of fully clean ones.

Real assets stay welcome as refs and pack shots. Provenance is necessary and never
sufficient: see PERCEPTION IS THE VERDICT.

### ONE DESIGNED SYSTEM
Type, plates, cutouts, field and light are conceived **together**, on one grid, one
palette, one light logic, never layered onto an image after the fact. The deletion test:
if an element could be removed without re-composing the ad, it was decoration; recompose
(design-laws section G).

### PERCEPTION IS THE VERDICT
The gate question is never "is it real". It is "does it read real at this size, in this
context". Real things read as fake in several ways: downsampled real seals, a tight-cropped
real photo, flat real label print on a curved pack. Corollary: **fluent garble is worse
than mush.** Any visible printed word must be letter-perfect or out of frame / in shadow.
"Not extractable" is not a passing grade.

Worse than garble: **a generated product INVENTS claims on its own label**, in the pack's
real typeface, crisply, and it reliably reaches for the most compliance-loaded claim in
the category. So the claims audit covers the **photographed pack's rendered text**, not
only the code-set type layer.

### EMOTION BEATS POLISH
Well-made, tasteful and forgettable is worse than ugly. The craft instruments saturate near
75. The remaining 10+ points are **always feeling**: appetite, ache, a person. **Craft debt
is finite; feeling debt is the ceiling.** An ad that clears every instrument and moves
nobody has not passed; it has plateaued.

---

## 2. The iteration algorithm

```
CHARTER (once per ad): angle + persona + archetype family + 3 North-Star refs
                       + the story premise, VERIFIED against the brand's own
                       record before any design
                       + the COPY DIRECTION card, if a direction is being set
                       (reference/copy-steering.md); it joins the SEALED brief
                       + the instrument LANE declaration (section 3)
i = 0
repeat:
  i += 1
  1. DIVERGE   generate 8-12 genuinely different concept options for the angle,
               score them against the charter, keep the best 2-3. Ban-list = every
               killed concept in the ledger + this loop's iterations.jsonl. Re-run
               whenever the concept is stuck, plateaued or optionless.
  2. VOLUME    up to 15 plates per shot at 1K (print config.plate_spend(n) first;
               the winner is re-generated at 4K) via runtime/gen/gen_image.py,
               prompts built from clause blocks where every clause is a NAMED
               KILL-TELL restated as a positive constraint (reference/volume-prompts.md).
  3. TRIAGE    the scripted cascade as a PRE-FILTER over the batch:
               physics (A row-luminance / B shadow behaviour / C hue
               preservation / D legibility) then vision (letter-perfect print,
               global illumination, 4x forensics). Compose only from survivors.
               Rank candidate plates by FULL-FRAME downsample `s` FIRST; cropping
               only ever lowers it, so scale class is decided before any layout.
  4. BUILD     winning concept + surviving plate → one designed system, per
               design/design-laws.md and reference/build.md. Checkpoint to disk.
  5. GATES     the five-instrument battery below, fresh judges, in parallel.
               ANY fatal = immediate fix, no debate, no averaging.
  6. FIX       targeted fixes from the critic + twin deltas. MAX 2 FIX ROUNDS
               per concept; then the CONCEPT is killed and step 1 re-runs with
               it banned. Never polish a dead concept.
  7. LOG       iterations.jsonl + learnings.md, the moment each finding exists.
until  SHIP BAR (85/100):
         all fatals cleared
       + not picked as non-human in the blind lineup
       + persona engages for CITED reasons
       + a real idea present (the twin or a read judge can STATE the claim)
       - minor law marginals tolerated, logged as polish debt
   OR  PLATEAU (2 iterations, no score movement) → deliver best-of + the ceiling, NAMED
   OR  ITERATION CAP (6) → same honest delivery
```

The **95 bar** = indistinguishable in the North-Star lineup. Reserved for "perfect"; not
required to ship.

### Batch shape: ONE CONCEPT AT A TIME
Iterated to perfect. Never parallel charters. The second charter starts only after the
first ships or is consciously abandoned. (Volume batches are parallel *within* a concept;
that is the engine, not a second charter.)

### The monotone gate
Iteration N must beat iteration N-1 in blind ranking. A loss is a **regression**:
auto-revert to the prior best and take a different fix path. No round's output ever
replaces a prior best it lost to. Two rounds with no rank improvement trigger the plateau
protocol, never silent grinding.

### Regression memory
Every defect ever flagged on this concept is re-checked EVERY round. It lives in
`iterations.jsonl`. A fix that reintroduces an old defect is not a fix.

### Documented-exception discipline
A gate may be failed **on purpose**, once, when the arithmetic forces it, and then the
arithmetic gets published. "The target was missed by 3 points and here is the inequality
that forces it" is reviewable; quietly shipping a smaller number is not. An undocumented
gate failure is a bug in the loop, not a judgment call.

### Skill discretion
The orchestrator may invoke any installed skill at any loop point on its own judgment, but
nothing here REQUIRES another skill. Useful pairings when installed: a structured-debate
skill (for example `dialectical-debate`) when two judges deadlock on a judgment call, and
a strategy skill (for example `strategy-crystallizer`) if the ANGLE itself comes into
question. The copy gate (`runtime/scrub/scrub.py check`) runs on every copy pass,
mechanically, exit-1 fatal.

**Mid-loop copy steering.** `steer copy: <direction>` at any point writes or updates the
copy-direction card with the operator's verbatim words as provenance. The CURRENT round
finishes its judging pass; the NEXT build writes copy against the new card. Copy-only
steering does **not** reset the visual loop: plates, layout and the monotone gate carry
forward, only the copy layer and its gates re-run. Logged as `copy_steer` in
`iterations.jsonl`. Full protocol, and the hard legal gate on naming competitors:
`reference/copy-steering.md`.

---

## 3. The five instruments

Full fill-in judge prompts: **`reference/judge-prompts.md`**. Scoring contract and
fatals: **`reference/RUBRIC.md`**. Scripted implementations: **`loop-engine/`**. How to
build a volume batch that survives triage: **`reference/volume-prompts.md`**. What gets
written where, and when: **`reference/logging.md`**.

| # | instrument | what it decides | fatal on |
|---|---|---|---|
| 1 | **Verdict-Bank taste twin** | the one-line message the operator would send back, in their register, plus ship/kill | none (advisory until the bank holds genuinely held-out draws) |
| 2 | **Reconstruction gap** | does the ad SAY the thing: 1.5s glance → 10s read → recall with the ad REMOVED | wrong product/category from the glance · zero benefits recalled · an unintended negative dominating recall · a defect dominating recall |
| 3 | **Comparative lineup** | blind rank + "which of these was NOT made by a human design team" | picked as the non-human one · loses to iteration N-1 (regression) |
| 4 | **Craft pass** | the fix list: laws A-G audit, glitch pass at 1:1, letter-perfect print audit, feed-gate | anything visibly broken/warped/artifacted · crisp-and-wrong printed letters |
| 5 | **Copy gates** | scrub.py (mechanical), persona resonance, copy grammar | a listed phrase (exit 1) · an unapproved claim · concession leading · zero benefits |

Instrument 1 carries a **qualification gate**: before its verdict counts, the same judge
instance must reproduce ship/kill plus the kill reason on 3 randomly drawn Bank items,
including at least one ship-class item. Wrong → disqualified, fresh judge resampled (cap 3;
if all 3 fail, the BANK is flagged for review, never bypassed). On a new client with an
empty bank, instrument 1 stands down and says so.

Instrument 3 is also the **compounding meter**. Both conditions to ship: beats the current
best with a stated reason, AND stops being pickable as the non-human one.

Instrument 4 proves nothing about good. Passing it is not a ship signal; failing a fatal in
it is a kill.

Instrument 5 is **co-equal with visual**. A visually perfect ad with dead copy is killed,
not shipped.

### The true dispatch cost: five instruments is not five agents

**One fully judged round costs about 11 judge dispatches plus 1 builder.**
`reference/judge-prompts.md` expands the five instruments into separate agents, and 4a/4b
carry an explicit anti-merge instruction (an agent asked for laws AND glitches finds fewer
of both). Budget from this table:

| dispatch | instrument | agent or script |
|---|---|---|
| 1 | 1a twin qualification | AGENT |
| 2 | 1b twin verdict | AGENT |
| 3 | 2 reconstruction gap (3 stages, one agent) | AGENT |
| 4 | 3 comparative lineup | AGENT |
| 5 | 4a laws auditor | AGENT |
| 6 | 4b glitch pass | AGENT (never merged with 4a) |
| 7..n | 5b persona gate, **ONE AGENT PER PERSONA** | AGENT |
| - | 4c letter-perfect print | **SCRIPT** `loop-engine/vision.py print` |
| - | 4d global illumination | **SCRIPT** `loop-engine/vision.py gi` |
| - | 4e feed-gate | **SCRIPT** `runtime/feed-gate/ablate.py` |
| - | glance simulation | **SCRIPT** `loop-engine/glance.py` |
| - | claims / quote verification | **SCRIPT** `loop-engine/claims.py` |
| - | 5a AI-isms copy gate | **SCRIPT** `runtime/scrub/scrub.py check` (exit-1 fatal) |
| - | 5c copy grammar | orchestrator checklist |
| +1 | the BUILD | AGENT (builder) |

The orchestrator runs the SCRIPT rows itself at zero dispatch cost ("the model
transcribes, the script decides"). When the budget is tight, recover these first. When it
still does not cover the agent rows, publish the arithmetic under documented-exception
discipline BEFORE dispatching. Merging 4a with 4b is a real degradation with a known
direction (fewer findings from both) and is recorded as one.

### Instrument lane-gating: an out-of-lane instrument returns a confident wrong verdict

Full table: `reference/RUBRIC.md` → Instrument LANE-GATING.

| instrument | applies to | does NOT apply to |
|---|---|---|
| **4d global illumination** | photographic / photoreal-scene lanes with a key light and a ground plane | flat vector, illustrated and hybrid lanes: flat artwork has no key, so it convicts every photo-on-illustration ad. Design-law 10 blesses that lane. |
| **4c letter-perfect print** | the **PACKAGING region only**: crop to the object first | the ad's own code-set type. Whole-frame, it scores headlines as fabricated pack claims. |

**Declare the lane at charter, before the round.** An out-of-lane result is logged
`N/A (out of lane)`, never as a fatal and never in the grade.

### Anti-hack invariants (violating any of these is a loop bug)

1. **Judges never see the brief, prior scores or the iteration number.** Judge calibration
   materials are ONLY: the verdict-bank README, `runtime/taste-brief.md` and the North-Star
   folder. `iterations.jsonl`, `learnings.md` and build notes are never judge inputs.
2. **The builder never judges its own fix.** Fresh judges every round.
3. **No score averaging, ever.** Fatal lists only. A visibly broken ad can still average 8/10.
4. **Regression memory**: every prior defect re-checked every round.
5. **Frozen canary**: iteration 1's render is re-judged by fresh judges every 3rd round. If
   its verdicts drift, the JUDGES have drifted; recalibrate against the Bank first.
6. **North-Star comparison pairs rotate every round.** Rotation blocks memorised pastiche.
7. **Letter and print audits are fresh-eyes FILTERS, never builder self-QA.** A builder who
   chose the plate will certify print that independent judges read as garble in seconds.
8. **A sharpened instrument must re-fail the artifact it was written for.** If the fixed
   ruler stops failing the file that exposed it, you fixed the score, not the ruler. Prove
   it in a `prove_instruments.py`.
9. **QA zones are computed, never hand-typed.** Every instrument box binds to the measured
   ink bbox, every run.
10. **Thresholds never move mid-experiment.** A wrong instrument is fixed BEFORE its output
    is reported, and validated against a corpus, never against the ad that exposed it.

---

## 4. Orchestrator duties

The orchestrator dispatches, verifies and writes state. It does not generate or judge
creative, with one mandatory exception.

**The 1:1 ALL-finals counted view.** Every final is opened at full resolution by the
orchestrator itself. N finals = N Read calls, and the count is STATED in the iteration
log. Broken renders ship when nobody looks at the file.

**Same-day writes, at the moment they exist** (schemas: `reference/logging.md`):
- `iterations.jsonl`: one row per round: concept, instrument outputs, fix list, what
  changed, rank vs prior, grade /100, trend, the regression re-check, and any documented
  exception with its arithmetic.
- `learnings.md`: every kill or fix reason distilled to a reusable ONE-LINE RULE, written
  client-neutral (state the general rule plus a client example). Rules that recur twice
  get promoted into `design/design-laws.md`, dated and cited, edited with care and never
  wholesale.
- **Verdicts captured in the human's EXACT WORDS.** Not paraphrased, not cleaned up. The
  exact words are the verdict bank's value; a summary of them is worth nothing. Append to
  the Bank AND the ledger the same day, then re-run the twin over the full bank and log its
  accuracy.

**ELI5 at concept close.** When a concept ships or closes, write a plain-language
explainer: what was tried, what killed it, what the ceiling was, what a non-specialist
should take away. It goes next to the state files (`loop-state/ELI5-<concept>.md`).

**Stall protocol.** Every subagent brief mandates checkpoint-to-disk and a small-step tool
cadence. Resume a stalled agent pointing it at its checkpoint ("check disk before
redoing"), or dispatch a FRESH agent pointed at the checkpoint file. Never restart a long
build from zero because a worker went quiet.

**Convergence honesty.** "Ship" from the twin means "this would survive next to the North
Stars". It is a calibrated prediction of the operator's eye, not the operator's eye. At
every plateau or ship, send ONE contact sheet (`runtime/static-kit/tools/sheet.py`) plus
one line per ad. The operator's reply ("ship" / "kill: <reason>") is appended to the bank
and sharpens the twin. It is skippable; the loop continues either way.

**Recommend-only.** The loop NEVER writes to an ad account on its own. A shipped concept
ends as an **upload packet** in `<work>/<client>/statics/loop-<concept>/ship/`. Offer terms
and any new claim need explicit human confirmation before anything ships. Only when the
operator explicitly says "upload <concept> as a paused draft" does
**`reference/meta-upload.md`** apply: PAUSED/draft only, claims gate first, the one-ad rule
for multi-ratio statics, the silent image_url trap, and per-placement preview verification
before "uploaded" may be reported. Activating, budgets, bids and targeting are out of scope.

### Model roles

| role | model | job |
|---|---|---|
| **Orchestrator** | the strongest reasoning model available | charters, concept selection, rubric evolution, verdict synthesis, learnings distillation, all human-facing judgment. Thin: dispatches, verifies, writes state. |
| **Builders** | a strong model | one-designed-system production per the design laws |
| **Gate critics** | a strong model, fresh, parallel, one lens each | the five instruments |
| **Taste twin** | the strongest available if budget allows | the Bank-calibrated verdict |

When the strongest reasoning model is unavailable, the loop PAUSES rubric evolution and
charter judgment. Building and judging can continue.

**Agent tooling: check the toolset, not just the role name.** Builders need **Bash +
Write** (they run `node render.js` and their own `qa/qa.py`). Researchers need **Write**
(the disk contract is not optional). Judges need Read at minimum; a judge that must run a
script is a script, not a judge. If a dispatch reports no Bash or no Write tool, re-dispatch
the job to a general-purpose agent; transcribing its output by hand leaves no checkpoint.

**Cost.** Plates and vision calls bill the Gemini key in `.env`. Volume times 4K is the
cost driver, which is why the spend guard in `config.py` caps a batch at 15 plates at 1K by
default and `config.plate_spend(n)` raises above the cap. Raise caps only with the
operator's say-so. Never route statics through a credit-billing image service.

## 4.5 The COMPILE pass: compounding must compress time, not just raise quality

Every ~25 new learnings (count the numbered rows in `learnings.md` added since the last
`[COMPILED]` marker), run a COMPILE pass before the next build:
1. **Migrate** every prose learning that CAN live in structure into structure: template
   invariants, instrument constants, prompt-clause constants (`volume-prompts.md`), config
   defaults. Mark the prose row `[COMPILED → <file>]`.
2. **Consolidate** the filter cascade: merge overlapping checks, retire ones a structural
   guard now makes unreachable, re-order by kill-rate per cost.
3. **Prune the boot read-set**: builders read ONLY un-compiled learnings plus the compiled
   index (one line each).
4. **Measure it**: log boot-read size and median iteration wall-time before and after in
   `iterations.jsonl`. A compile pass that does not cut both failed.

## 5. Copy steering (charter-time or mid-loop; `reference/copy-steering.md`)

The operator directs the MESSAGING without touching the visual loop. At charter, the intake
round sets the copy direction (stance / enemy / mode / constraints; defaults make skipping
safe). At ANY point, "steer copy: <direction>" writes a copy-direction card with the
operator's verbatim words as provenance; the next build generates against it, and the
sealed brief carries it so judges evaluate against the declared direction. HARD GATE:
naming a competitor requires the client's rules to allow it (many ban it; then
counterposition runs implicit) and operator sign-off every time. Comparative claims are a
heightened legal surface.

## 6. Running it

```bash
# 0. sanity (from this folder)
python3 config.py

# 1. NEW CLIENT: bootstrap the layer from a URL
python3 scripts/intake.py --url https://<brand-site> --slug <client>
python3 runtime/lib/asset_library.py seed <client>
#    then complete the [GAP]s: art direction, personas, approved claims, North Stars.
#    VERIFY brand/pack-strings.json: intake writes it as a DRAFT so the print gate can
#    run on day one, and its _STATUS block stays until a human has read the pack at 1:1.
#    Any `rejected` row in brand/adlib-pages.md resolved to NOTHING; do not harvest from
#    its candidates. See reference/client-layer.md and reference/intake.md.

# 2. VOLUME: print the spend first, then generate, then triage as a PRE-FILTER
python3 -c 'import config; print(config.plate_spend(15))'
python3 runtime/gen/gen_image.py --prompt "<clause-block prompt>" --ref <pack.png> --size 1K --out PLATES/p01.png
E=loop-engine
python3 $E/vision.py localise --plates 'PLATES/*.png' --out QA/boxes.json --subject "the product package"
python3 $E/triage.py  --plates 'PLATES/*.png' --boxes QA/boxes.json --ref <real-pack-shot.png>
#   -> the SURVIVAL CURVE is the output. Then vision-filter the survivors only:
python3 $E/vision.py print --plates 'PLATES/{survivors}.png' --out QA/ --client <client>
python3 $E/vision.py gi    --plates 'PLATES/{survivors}.png' --out QA/

# 3. BUILD via the static-kit (reference/build.md)
cd runtime/static-kit && node render.js <batch.json> && cd -

# 4. GATE
python3 $E/glance.py <final.png> --out QA/
python3 $E/claims.py QA/quote-spec.json            # --print-example for the spec shape
python3 runtime/feed-gate/ablate.py <final.png> --modes chrome,phone,desat
python3 runtime/scrub/scrub.py check <copy.txt>
#    plus the judge prompts in reference/judge-prompts.md, dispatched to FRESH
#    subagents, one lens each, in parallel.
```

Run `python3 runtime/gen/gen_image.py --help` for the generator's exact flags.

**`zones`, `physics` and `device` are LIBRARY modules, not CLIs**, by design. Each
iteration writes its own small `qa/qa.py` that imports them and binds this ad's specifics:

```python
import sys
sys.path.insert(0, "<pkg>/loop-engine")
import zones, device
q = zones.ZoneQA(final="final_1080.png", plate="plates/scene_1080.png")
q.find_blocks(); q.margins(); q.fold_and_headline(anchor={...})
q.wcag_lines(); q.wcag_elements(elements); q.flatness_halo()
device.invariant_column(...)          # only if the concept HAS a device
print(q.fails)                         # a list. never a score.
```

That per-iteration file is also where a **new** instrument gets written when this round's
concept needs one, and it must then **re-fail the artifact that exposed the gap**.

Sanity-check the whole engine any time: `python3 loop-engine/selftest.py` (no API calls;
`--live` adds one real vision call).

## 6.5 One driver per work root (concurrency rule)

Before dispatching ANY build or judge work, check `<work>/loop-state/ORCHESTRATOR.md`. If it
names another session with a heartbeat under ~2 hours, this session is a READER: report
state, answer questions, never dispatch. To take the wheel, write your own session marker
and timestamp there (only when the prior driver is stale or the operator says switch). Two
orchestrators dispatching into one loop-state produce duplicate iterations and colliding
learnings numbers.

## 7. Hard rules

- **Type is always code-set** in the static-kit. Never model-rendered text, never
  hand-placed in an image editor.
- **The pack label is always the real photograph** (law 8), or a generated plate whose
  print passed the letter-perfect filter at delivery scale.
- **Images on the Gemini key only.** Never a credit-billing image service.
- **Claims compliance is not waivable.** Creative-license waivers (photoreal humans or
  animals, register experiments) apply to LOOP EXPERIMENTS only and re-attach at client
  delivery; the human decides what actually ships. The approved-claims list is legal
  surface. An approved claim's hedge is the load-bearing word; a rewrite that "sounds
  better" usually got there by deleting it.
- **Autonomy and the claims fatal BOTH hold; the standing policy is how** (full text:
  `reference/client-layer.md` → STANDING POLICY). On a new client the approved list is
  empty. **While `approved-claims.md` is empty, an autonomous build may write against ONLY
  (a) attributed verbatim customer quotes and (b) text verbatim-legible on the product in
  REAL photography** (never a generated pack). Everything else is built but flagged
  `[NEEDS APPROVAL]` with its source string, and that build goes **to the OPERATOR only**
  (never to a client, an ad account or a platform) until a human signs the rows. The loop
  never writes content into `approved-claims.md`.
- **No live ad-account writes by default.** Upload packets only; a paused draft only on the
  operator's explicit words (`reference/meta-upload.md`).
- **Per-client hard rules override everything here.** Read the client's `bible.md` first.
- **File org:** outputs under `<work>/<client>/statics/`, kit changes in
  `runtime/static-kit`, state in `loop-state/`. Never create a parallel structure for a
  concern that already has a home.
- **Never fork `design/design-laws.md`.** Point at it. Promote a twice-recurring learning
  INTO it, dated and cited.

## Off-switch

Stop the loop session. Delete this folder to remove the skill. The work root
(`learnings.md`, `ledger.jsonl`, the verdict bank, the inspo corpus and the client layers)
is yours and stays regardless.
