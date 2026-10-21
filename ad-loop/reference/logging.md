# State schemas — what gets written, where, and when

The loop's entire memory. A fresh session reconstructs the run from these files
and nothing else. **Every write happens the moment the thing exists**, not at the
end of a round and never at the end of a session.

**ONE home per file.** Everything per-client lives under
`<client>/statics/loop-state/` — resolved by `config.client_loop_state(slug)` and
its helpers. Everything client-neutral lives under the global `<work>/loop-state/`.
There is no third location and no "check here first, then there."

| file | resolver | scope | holds |
|---|---|---|---|
| `<work>/loop-state/learnings.md` | `config.LEARNINGS` | **GLOBAL, client-neutral** | numbered one-line rules. Never forked per client. |
| `<work>/loop-state/RUBRIC.md` | `config.RUBRIC_LIVE` | global | the live rubric |
| `<work>/loop-state/verdict-bank/` | `config.VERDICT_BANK` | global | labeled ads + the human's exact words |
| `<work>/ledger.jsonl` | `config.LEDGER` | global | every ad ever built + its human verdict |
| `<client>/statics/loop-state/launch-brief.md` | `config.client_launch_brief(slug)` | per client | the launch interview's verbatim answers |
| `<client>/statics/loop-state/iterations.jsonl` | `config.client_iterations(slug)` | per client-family | one row per round |
| `<client>/statics/loop-state/ELI5-<concept>.md` | `config.client_loop_state(slug)` | per concept | the plain-language close-out |
| `<client>/statics/loop-<concept>/iter-NN/` | `config.iteration_dir(...)` | per round | the build, plates, qa output, build-notes |

Never write a round to two places "to be safe" — that is how a later session gets
half a history and believes it has all of it.

---

## 1. `iterations.jsonl`

One JSON object per line. Append-only. Never rewrite a prior line.

### Row type A — loop start / charter

```json
{"ts":"<ISO8601>","event":"loop-start","iteration":0,
 "charter":{
   "concept":"<slug>",
   "angle":"<the one angle — never blended>",
   "persona":"<which judge persona this is aimed at>",
   "archetype":"<from the design-laws archetype menu>",
   "north_star_refs":["<id> (<what it teaches>)", "...×3"],
   "premise":"<the story claim>",
   "premise_verified":"<what was checked, against which client-owned source>",
   "mode":"single-concept-to-perfect"}}
```

`premise_verified` is not optional. A charter's premise is a CLAIM until it is
checked against the brand's own record — and a premise can be half-true.

### Row type B — an iteration verdict

```json
{"ts":"<ISO8601>","iteration":N,"concept":"<slug>",
 "verdict":"SHIP|FIX|KILL",
 "grade":<0-100>, "trend":"<N-1 -> N, and why>",
 "monotone_gate":"<beat prior best? or REGRESSION -> reverted to iter-M>",
 "instruments":{
   "taste_twin":{"verdict":"...","qualification":"3/3 on draws (ids ...)",
                 "one_liner":"<in their register>","note":"..."},
   "glance":{"brand_registered":bool,"product_form":"...","would_stop":bool,
             "headline_legible":bool,"numerals_survive_blur":bool},
   "reconstruction_gap":{"fatals":["..."],"finds":["..."],"wins":["..."]},
   "lineup":{"rank":"K/N vs <which North Stars>","picked_as_nonhuman":bool,
             "confidence":"...","tells":["..."],"highest_leverage":"..."},
   "craft":{"laws_fails":["law NN: ..."],"glitch":["..."],
            "print_audit":{"letter_perfect":[...],"wrong":[...],"pass":bool},
            "gi":{"single_key":bool,"verdict":"coherent|incoherent"},
            "feed_gate":{"chrome":"pass|fail","phone":"...","desat":"..."}},
   "copy":{"scrub_ai":"pass|FAIL <phrase>","personas":{"<name>":"..."},
           "grammar":["..."]}},
 "regression_check":"<every prior defect on this concept, re-checked: list + status>",
 "fix_rounds_used":<0|1|2>,
 "decision":"<what happens next, and why>",
 "known_weaknesses":["<named, not hidden>"],
 "documented_exceptions":[{"gate":"law 2 product coverage",
                           "shipped":"15%","required":"40-70%",
                           "arithmetic":"<the inequality that forces it>"}],
 "learnings_added":[NN,NN],
 "artifacts":["<abs path>"],
 "orchestrator_note":"<including the counted 1:1 view: 'N finals, N Read calls'>"}
```

**Non-negotiable fields:** `regression_check` (the whack-a-mole block),
`documented_exceptions` (a gate failed on purpose publishes its arithmetic), and
the counted 1:1 view in `orchestrator_note`.

### Row type C — a volume batch

```json
{"ts":"...","event":"volume","concept":"<slug>","batch":"volume-NN",
 "generated":<N>,"variants":{"<variant>":<n>,"...":"..."},
 "survival_curve":{"bag located":<n>,"after A":<n>,"after B":<n>,"after C":<n>,"after D":<n>},
 "survivors":["<plate id>","..."],
 "vision_kills":{"print":["..."],"gi":["..."]},
 "fully_clean":["<plate id>","..."],
 "scale_class":{"<plate>":{"full_frame_s":2.177,"verdict":"out — over readability threshold"}},
 "new_tells":["<tell> -> <clause added to prompts.py>"],
 "cost":"~$0 (Gemini-class key)"}
```

Rank plates by **full-frame downsample `s` FIRST** — cropping only lowers it, so
scale-class is decided before any layout, and a two-minute check saves a build.

### Row type D — concept close

```json
{"ts":"...","event":"concept-close","concept":"<slug>",
 "CONCEPT_N_CLOSED":"<ceiling, NAMED>",
 "best_iteration":N,"best_grade":<n>,
 "why_it_stopped":"plateau|cap|ship",
 "unlock":"<what would raise the ceiling — and whether it is a method ceiling
            or a real asset ceiling>",
 "eli5":"<path to the ELI5 file>"}
```

Distinguish a **method ceiling** from an **asset ceiling**. The night this loop
was built, a conclusion that "every route runs through a real photo shoot" was
overturned: it was small-n generation plus post-hoc judging — a method ceiling
wearing an asset ceiling's clothes.

---

## 2. `learnings.md`

Sequentially numbered, grouped by the iteration that produced them.

**Format:** `NN. **<the rule, bolded, as an imperative or a general claim>.**
<one to four lines of why, with the measurement or the exact kill-words that
prove it.>`

Rules:
- Written **client-neutral, always.** A learning that names a client is a smell —
  restate as the general rule plus a client example.
- Written **at the moment the finding exists**, not at session end.
- A learning that is later overturned is marked `[SUPERSEDED by NN]` with the
  original struck, **never deleted**. The correction block is part of the record —
  the fact that a conclusion was wrong is itself a learning.
- A rule that recurs twice is **promoted into `design/design-laws.md`**, dated and
  cited. Promotion is a surgical edit, never a rewrite.
- If a learning is about the RUBRIC or an instrument rather than about ads, label
  it `Rubric meta:` — those drive instrument sharpening, not design decisions.

---

## 3. Verdict Bank — the append protocol

Runs the same day, every time, no exceptions:

1. The human's one-liner lands (any channel) → append a row to the bank README
   **in their exact words** + append to `ledger.jsonl`.
2. Re-run the twin's qualification prompt over the **FULL** bank; log its accuracy
   in `iterations.jsonl`.
3. If accuracy dropped, **the prompt does not change until it recovers on the new
   bank.** The bank is never edited to fit the judge.

Bank row: `| id | image path | verdict | kill-reason class |` plus the exact words.
Split verdicts are first-class (`visual ratified, copy below bar`) — they are the
most informative rows in the bank.

Positive references: the operator's hand-picked North-Star folder counts as
verdict=SHIP items for qualification draws. A kill-heavy bank produces a judge
that can only recognise failure.

---

## 4. `ELI5-<concept>.md`

Written at concept close, next to the state files. Plain language, no jargon,
readable by someone who was asleep:

- what we were trying to make, in one sentence
- what we tried, in order, and what each attempt taught
- what killed it, or what let it ship
- the ceiling, named, and whether it is a method or an asset ceiling
- what a non-specialist should take away
- what the next concept starts knowing that this one did not

This is what makes the night legible the next morning. A run with no ELI5 is a run
whose findings live only in a JSONL nobody will open.

---

## 5. `build-notes.md` (per iteration)

The builder's own record, inside `iter-NN/`. It is **loop-state, not a judge
input** — never point a judge at it.

Holds: the concept card (hook / archetype / device / world / image plan), which
plate was selected and its full-frame `s`, every measurement taken during the
build, every tuning pass and what it changed, and the arithmetic behind any
documented exception. If a number was fitted to a real reference, the reference
and the fit both go here — *"fitted to a measured falloff curve"* is a claim a
critic can check; *"looks right"* is not.
