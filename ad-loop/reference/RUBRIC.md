# The Loop Rubric — how "good" is judged

Portable seed. `python3 config.py --init` copies it to `<work>/loop-state/RUBRIC.md`,
which becomes the live, versioned rubric. Origin: a divergence pass over four candidate
scoring mechanisms; baseline
checklist-scoring was **killed at leverage 1** because it had already empirically
failed — two checklist-passing batches died in front of the operator.

**Laws source of truth:** `design/design-laws.md` (in this package)
(§A composition, §B image, §C type, §D device, §E copy, §F the judge gate, §G
one-designed-system). This file never restates a law and never forks that file.

This file is under version control. Every edit is **dated**, and must not drop
accuracy against the Verdict Bank.

---

## Prime directive

**No scalar averages, ever.** An ad ships when it clears EVERY instrument below.
One fatal kills regardless of how many other checks pass — an ad with one glaring
"robot glitch" can average 8/10 on everything else and would ship on an average.

**Whatever this rubric rewards, the loop becomes.** So the rubric itself is
versioned and validated against real human verdicts, not against its own outputs.

The `/100` grade in `iterations.jsonl` exists **only as a trend line** for the
orchestrator. It is never a ship signal, never averaged across instruments, and
never shown to a judge.

---

## The five instruments, in order

### 1. Verdict-Bank judge (the taste twin)

- Judge sees ONLY the rendered ad. Never the brief, never the iteration number,
  never prior scores.
- Output: the one-line message the operator would send back, in their register,
  plus ship/kill and the reason.
- **Qualification gate:** before its verdict counts, the same judge instance must
  reproduce ship/kill + kill-reason class on 3 randomly drawn Bank items, mixing
  ≥1 ship-class item. Wrong → disqualified, fresh judge resampled (cap 3). If all
  3 fail, the **BANK is flagged for review**, never bypassed.
- **The Bank** (`<work>/loop-state/verdict-bank/`): one row per labeled ad —
  image path, the operator's exact words, ship/kill, kill-reason class. EVERY
  future one-liner is appended same-day. The bank growing IS the loop learning.
  Prompt edits are validated against the FULL bank before adoption, and the bank
  is never edited to fit a judge.
- **Known limits, logged not hidden:** a small bank concentrates on a handful of
  kill-shapes and the twin may be blind to an unnamed failure mode; and
  qualification on bank-KNOWN items measures recall, not prediction. The twin is
  therefore **advisory — a tie-breaker, never an overruler** — until the bank
  supports genuinely held-out draws. Twin ship + lineup kill is the system
  working. **Twin verdicts never overrule a lineup fatal** (no averaging).
- Only a REAL human verdict enters the Bank. Loop-internal twin verdicts go to
  `iterations.jsonl`.

### 2. Reconstruction gap (does the ad SAY the thing)

Fresh brief-blind judges, three stages: 1.5s glance (downscaled + blurred) → 10s
read → **ad removed from context**, answer from memory.

Score = the diff against the SEALED brief, which the judge never sees. Every
mismatch is a fix instruction, verbatim.

**Fatals:** wrong product/category from the glance · zero benefits recalled · an
unintended negative dominating recall · a defect dominating recall · the
last-read element is the disclaimer or the concession.

**Known limit:** comprehension is not beauty. Alone, this instrument breeds
legible generic ads. It never ships anything alone; instrument 3 holds taste.

### 3. Comparative lineup (the isolation fix)

The candidate is judged IN A LINEUP, blind, shuffled: current-best iteration + 2
North Stars drawn **fresh each round** (rotation blocks memorised pastiche).

Two questions: rank them; **which of these was NOT made by a human design team,
and what gives it away** (forensic, pointing at pixels).

**Ship requires BOTH:** beats the current-best with a stated reason, AND stops
being pickable as the non-human one.

**This is the compounding meter.** Iteration N must beat N-1 in blind ranking. A
loss = regression → auto-revert to prior best, take a different fix path. Two
rounds with no rank improvement = plateau protocol, never silent grinding.

### 4. Craft pass (fix-list generator, never the ship signal)

Laws §A-G audit citing law numbers · glitch pass at 1:1 ("does ANYTHING look
broken/warped/artifacted?" — fatal if yes) · **letter-perfect print audit** as an
independent vision pass at delivery-then-magnified scale (crisp-and-wrong is an
instant kill; "not extractable" is not a passing grade) · **global-illumination
pass** (one key? every object casting consistently? orphan shadows? ghost arcs?)
· feed-gate fold/phone/desat.

Output is a fix list. Passing proves nothing about good; failing any fatal kills.

### 5. Copy gates (co-equal with visual)

- `runtime/scrub/scrub.py check` against the banned-phrase list — mechanical, **exit-1 fatal**.
- Persona resonance — traceable reactions, default scroll-past, `[extrapolation]`
  tags on anything not in the evidence file.
- Copy grammar from the North-Star picks: headline 3-7 words, declarative category
  claim; benefits concrete and numeric, ALWAYS present; concession never leads
  (law 28); the hedge never takes the headline; register per law 27.
- Any claim not on the client's approved list is a fatal, full stop. Claims are
  legal surface and are never waived by a creative-license grant.

---

## Instrument LANE-GATING

**An instrument applied outside the lane it was written for produces a confident
wrong verdict, and a confident wrong verdict costs more than no verdict.** The two
rows below fail in opposite directions.

| instrument | APPLIES TO | DOES NOT APPLY TO | what happens if it is run out of lane |
|---|---|---|---|
| **4d global illumination** (`vision.py gi`) | photographic and photoreal-scene lanes: a rendered world with a key light, cast shadows and a ground plane | flat vector / illustrated / graphic-field lanes, and hybrids — a photoreal cutout standing on flat artwork | Returns `incoherent · single_key=False` on **every** photo-on-illustration ad, because flat artwork has no key light to be coherent with. That is the instrument reporting its own assumption. It is **not a kill.** design-law 10 explicitly blesses the hybrid lane; a GI verdict may not overrule a law. Record it as N/A-out-of-lane, and if it points at a real two-material-systems problem, that belongs to instrument 4a as a law-21 question. |
| **4c letter-perfect print audit** (`vision.py print`) | the **PACKAGING region only** — crop to the object before magnifying, and score only strings transcribed off the product | the ad's own code-set type layer: headline, benefits, eyebrow, compliance microtype, URL | Reads the ad's headline as package print and scores it against the pack's truth list, so correct code-set copy returns as fabricated pack claims. Typical symptom: `wrong=3 ['<headline word>', '<benefit line>', '<stat>']` on a clean ad. Re-run scoped to the pack region as it actually ships → `pass=True, wrong=0`. **Report the fault, do not move the bar** — the fix belongs upstream in the crop: this is the "pack print counted as ad text" failure running in reverse. |

Two general rules fall out and bind every instrument, present and future:

1. **Declare the lane before the round, not after the verdict.** An
   out-of-lane finding is recorded as `N/A — out of lane` with the lane named. It
   never enters the fatal list and it never enters the grade.
2. **An instrument that cannot fail cleanly in a lane cannot ship a kill in that
   lane.** If the mismatch is only noticed once the verdict is inconvenient, the
   lane declaration was skipped — that is a loop bug, not a judgment call.

---

## Anti-hack invariants

Violating any of these is a **loop bug**, not a judgment call.

1. Judges never see the brief, prior scores, or the iteration number. Calibration
   materials are ONLY the verdict-bank README + the taste brief + the picks
   folder. `iterations.jsonl`, `learnings.md` and build-notes are loop-state and
   are NEVER judge inputs.
2. The builder never judges its own fix. Fresh judges every round.
3. No score averaging. Fatal lists only.
4. **Regression memory** — every defect ever flagged on this concept is re-checked
   every round. Lives in `iterations.jsonl`.
5. **Frozen canary** — iteration 1's render is re-judged by fresh judges every 3rd
   round. Verdict drift means the JUDGES drifted; recalibrate against the Bank
   before trusting new scores.
6. North-Star comparison pairs rotate every round.
7. **Letter/print audits are fresh-eyes filters, never builder self-QA.**
8. **A sharpened instrument must re-fail the artifact it was written for.** If the
   fixed ruler stops failing the file that exposed it, you fixed the score, not
   the ruler. Prove it in a `prove_instruments.py`.
9. **QA zones are computed, never hand-typed.** Every instrument box binds to the
   measured ink bbox, every run.
10. **Thresholds never move mid-experiment.** A wrong instrument is fixed BEFORE
    its output is reported and validated against the corpus, never against the ad
    that exposed it.

---

## The ship bar

**85/100 ships:**
- all fatals cleared
- not picked as non-human in the blind lineup
- persona engages for CITED reasons
- a real idea present — the twin or a read judge can STATE the claim
- minor law marginals tolerated and logged as **polish debt**

**95 = indistinguishable in the North-Star lineup.** Reserved for "perfect". Not
required to ship.

**Plateau close:** 2 iterations with no score movement → deliver best-of plus the
ceiling, NAMED. A named ceiling is a finding. Silent grinding is not.

**Iteration cap: 6.** Same honest delivery.

**Max 2 fix rounds per concept**, then the concept is killed and divergence
re-runs with it banned. Never polish a dead concept.

---

## Compounding contract

- `iterations.jsonl` — every round: concept, instrument outputs, fix list, what
  changed, rank-vs-prior, grade, trend.
- `learnings.md` — every kill/fix reason distilled to a reusable one-line rule at
  the moment it happens, written **client-neutral**. Rules recurring twice get
  promoted into `design-laws.md`, dated and cited.
- **Monotone gate:** no round's output ever replaces a prior best it lost to.
- **Bank growth:** every human one-liner appended same-day, in their exact words;
  the twin is re-run over the full bank after every append and its accuracy
  logged.

---

## Adapting this rubric to a new client

Nothing above changes. What changes is entirely in the client layer
(`reference/client-layer.md`):

| rubric element | where the client-specific version lives |
|---|---|
| Verdict Bank | starts EMPTY for a new client. The loop runs on the shared taste brief + North-Star picks until the first real verdicts land. Say so out loud — an empty bank means the twin is uncalibrated, not that it is neutral. |
| Personas | `<client>/personas/` with JUDGE PROTOCOL sections |
| Approved claims | `<client>/brand/approved-claims.md` |
| Register / voice | `<client>/brand/bible.md` + `ad-creative-principles.md` |
| North Stars | the shared picks folder, plus any client-specific picks the operator adds |
| Reference object for the physics filters | the client's own real pack shot |
| Hard content rules (e.g. no medical claims) | `<client>/brand/bible.md` — these OVERRIDE any loop-level creative-license grant at delivery |

A rubric edit that only makes sense for one client is a smell. Restate it as the
general rule plus a client example, or put it in the client layer.
