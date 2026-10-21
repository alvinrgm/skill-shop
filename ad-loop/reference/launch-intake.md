# Launch intake — the conversation that starts everything (mode: LAUNCH)

Bare `/ad-loop` (or "run the ad loop for <client>") on a client with no
in-flight concept = **LAUNCH**: an end-to-end run that begins with a
one-round intake interview, flows through URL asset harvest, charters the
first concept, and enters the loop — one continuous journey to finished ads.
The operator answers one round of questions and can walk away.

Ask directly: ONE batched round, every question with a default so skipping is
safe, and a one-line "why I'm asking" on each. No drip-feeding questions across
turns; the operator answers once and walks away.

## 0. PREFLIGHT (guided setup — first run, or any missing requirement)

`python3 config.py` (from the package folder) before anything else. If the work root
does not exist yet, `python3 config.py --init` creates it.

- **All green → proceed silently.** Preflight is invisible when healthy.
- **Any REQUIRED item missing → flip into SETUP mode**, one item at a time:
  - **`GEMINI_API_KEY`** — explain where to get one (Google AI Studio → API keys),
    exactly where to put it (the `.env` `config.py` names), then **VERIFY with a
    minimal live generation call (~$0)** before proceeding. Never proceed on a
    pasted-but-unverified key.
  - **Missing runtime piece** (static-kit `node_modules`, Playwright Chromium) — run
    the exact install line `bash doctor.sh` prints, then re-check.
  - **Missing directories** — create them. That part is automatic, not
    conversational.
- **Never ask the operator to paste a key into chat if a safer path exists** (they
  edit the `.env` themselves). If they do paste it, write it to the `.env` and tell
  them it landed there.
- **No video-generation or credit-billing image service is part of statics
  preflight.** Never request one here.

**Key-presence checks go through `config.py`, never through a shell `grep`/`cat` of
a `.env`.** Printing a `.env` puts the key in the transcript, and many setups run a
hook that blocks shell commands touching `.env` files. The sanctioned call is
`python3 -c "import config; print(config.gemini_key_present())"`, which returns
`(present?, where)` and never prints the key.

## The question pack (4-7 questions, one round)

1. **Client + URL** — brand name and homepage URL. (No default — this is the
   one required answer. Everything else can be skipped.)
2. **What does a win look like?** — e.g. "3 shippable statics on new angles" /
   "beat the incumbent ad" / "explore wide". Default: 3 shippable statics,
   distinctly different concepts.
3. **Angle priorities** — which selling angles matter most (or "mine the
   reviews and propose")? Default: propose from harvested evidence.
4. **Copy direction** — any standing stance? Counterposition against a specific
   competitor? (→ writes the copy-direction card per copy-steering.md; the
   legal/brand gate on naming applies.) Default: customer-voice, evidence-led.
5. **Hard rules** — anything banned (imagery, claims, tone) beyond what the
   site/brand shows? Default: none beyond harvested brand rules; claims always
   human-approved regardless.
6. **North Stars** — 5-15 ads (any brand) that hit the bar, dropped in a folder
   or named for harvest. Default: harvest elite same-category actives via Ad
   Library and confirm the picks with the operator at first judging.
7. **Cadence + ship bar** — walk-away autonomous until plateau (default), or
   checkpoint per iteration? Ship bar default 85.

Record every answer verbatim in **`<client>/statics/loop-state/launch-brief.md`** —
`config.client_launch_brief(slug)`, the same per-client home as `iterations.jsonl`
and the ELI5 files. Answers are charter provenance AND verdict-bank seed material.

## The launch sequence (no further operator input required)

```
0. PREFLIGHT  — config.py green, or the guided setup above
1. INTERVIEW  — the round above → statics/loop-state/launch-brief.md
2. HARVEST    — scripts/intake.py --url <url> --slug <client>   (assets,
                palette, fonts, reviews, claim candidates, page-ids)
3. LAYER      — complete the client layer from harvest + brief: AD-bible
                skeleton, approved-claims scaffold ([NEEDS HUMAN APPROVAL]
                rows surfaced to operator)
3b. PERSONA RESEARCH (real research, not just seeds) —
                a dedicated research pass builds 2-3 REAL buyer personas:
                harvested site reviews + competitor product reviews + public
                forum/community language (WebSearch/WebFetch, public only),
                every trait/objection/vocabulary item QUOTE-GROUNDED with
                source links, each persona carrying a JUDGE PROTOCOL
                (never flatters, default scroll-past, cites its quotes,
                [extrapolation] tags on uncited reactions). A thin honest
                persona beats a rich fake one — [GAP]s where evidence is
                missing. Write each persona's sources to
                <client>/personas/sources.md (one line per quote: text, URL).
4. CHARTER    — concept 1 from the brief's angle priorities + harvested
                evidence (+ a divergence pass if optionless: SKILL.md section 2 step 1)
5. LOOP       — the iteration algorithm (SKILL.md §2) to ship or plateau
6. REPORT     — finished ads + honest state + the operator's decision list
```

Stage gates that surface to the operator mid-journey (async, never blocking):
claim approvals, North-Star confirmation, any client-rule conflict, plateau
reports. Everything else runs.

## Mode routing (the front door, canonical)

| invocation | state | mode |
|---|---|---|
| `/ad-loop` or "run the ad loop for <client>" | no in-flight concept for that client | **LAUNCH** (this doc) |
| same | in-flight concept exists | **RESUME**: report state, continue the loop from its next step |
| "ad loop intake <url>" | any | HARVEST only (stage 2 standalone) |
| "iterate this ad / loop this concept" | operator supplies the ad/concept | loop entry at CHARTER with the supplied subject |
| "steer copy: ..." | any | copy-direction card update (copy-steering.md) |
