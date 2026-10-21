# The client layer — the multi-client contract

**The rule, absolute:** everything client-specific lives HERE and nowhere else.
The laws, the rubric, the instruments, the anti-hack invariants and `learnings.md`
are written client-neutral, always. **Onboarding a new client to the loop is
writing their client layer — nothing else changes.**

A learning, a rubric line, or an instrument constant that mentions a client by
name is a smell. Restate it as the general rule plus a client example, or move it
into the client layer.

```
<work>/<client>/
├── brand/                      ← the client layer proper
│   ├── art-direction.md        ← THE AD BIBLE (§ below)
│   ├── bible.md                ← who they are, hard content rules, voice
│   ├── ad-creative-principles.md
│   ├── approved-claims.md      ← LEGAL SURFACE. human-approved only.
│   ├── claims-CANDIDATES.md    ← written by intake. never approved. never shipped from.
│   ├── tensions.md             ← the story premises worth building on, each VERIFIED
│   ├── product-images/         ← real pack shots at native resolution + INDEX.md
│   ├── north-star-picks/       ← HAND-PICKED by the operator. never harvested.
│   ├── reviews/                ← raw records + SUMMARY.md (persona + quote source)
│   ├── fonts/                  ← the client's own webfonts
│   ├── characters/             ← mascot / character refs, if any
│   ├── reference-photos/       ← real photography: refs, not necessarily heroes
│   └── adlib-pages.md           ← resolved Meta page ids + the harvest command
├── personas/                   ← the resonance judges
│   ├── README.md               ← the grounding rule + how to invoke
│   ├── sources.md              ← every source, linked
│   └── NN-<name>.md            ← one per persona, each with a JUDGE PROTOCOL
└── statics/
    ├── loop-<concept>/iter-NN/ ← builds
    └── loop-state/             ← per-client: charters, iterations.jsonl,
                                   verdict-bank additions, ELI5 files
```

`config.py` resolves all of these: `brand_dir(slug)`, `personas_dir(slug)`,
`statics_dir(slug)`, `client_loop_state(slug)`.

---

## What each file must contain

### `brand/art-direction.md` — the AD bible
The visual constitution. Without it the loop has no light logic to test against
and every physics finding is unanchored.

- **Palette** — site-exact hex values with their provenance (pulled from theme
  CSS, counted by frequency; never eyeballed). Which is field, which is ink,
  which is the ONE accent.
- **Grade** — the colour register. Film stock or an equivalent named reference,
  highlight roll-off, black level, saturation policy.
- **Light** — the world's light logic in one paragraph, concretely enough that a
  generation prompt and a physics probe can both be written from it. One key? What
  direction? What does a contact shadow look like on this brand's surfaces?
- **Type** — one display family + one workhorse family, with the actual font files
  in `brand/fonts/`. Case policy per element.
- **World** — what surfaces, props, and environments belong. What is banned.
- **Safe zones** — the delivery canvas, margins, feed chrome.
- **Never** list — the things that instantly read wrong for this brand.

### `brand/bible.md`
Who the brand is, who buys, and the **hard content rules**. Hard rules here
OVERRIDE any loop-level creative-license grant at the moment of delivery — a
waiver that lets the loop experiment with photoreal humans does not let a
photoreal human reach the client.

### `brand/approved-claims.md` — LEGAL SURFACE
Every claim the ad may make, verbatim, with its source. Nothing else may appear as
a claim in any ad.

Three rules that are not style preferences:
1. **The hedge is the load-bearing word.** A rewrite that "sounds better" usually
   got there by deleting the hedge, converting an approved tagline into an
   unapproved health claim.
2. **The hedge never takes the headline.** A hedged claim promoted to headline
   reads as the lawyer talking and manufactures the reader's objection. The unique
   checkable fact leads; the hedged claim supports.
3. **Attribution framing is itself a claims surface.** An eyebrow like "from the
   reviews" over any non-review text is exposure. Attribution labels may cover
   only byte-verified quoted material; brand-voiced lines live outside the
   attributed block.

Testimonials additionally: elide only whole trailing content, never an internal
qualifier; the provenance file must byte-match what ships; **verify the review's
PRODUCT LINE**, not only its text, rating and verified flag — platforms file a
review against the order line it was solicited for, which can be an accessory
rather than the product in the frame.

`claims-CANDIDATES.md` (intake's output) is never a substitute. Promotion from
candidates to approved is a **human act**.

#### STANDING POLICY — what an autonomous build may say while the approved list is EMPTY

On a brand-new client the approved list is empty **by construction** (only a human
may fill it), and the cadence answer is usually "autonomous, walk away". Read
naively those two facts make every ad a claims fatal before it is built, which
would mean the loop cannot run on any new client. It can. Both rules hold at once,
and this is how:

**While `approved-claims.md` is empty, an autonomous build may write against ONLY
these two surfaces:**

- **(a) Attributed verbatim customer quotes.** Byte-exact from a raw review record,
  visibly in quotation marks, and **attributed** — a name or handle plus the record
  id in the provenance file. Unattributed first-person is not in this set, and two quotes may never be spliced into one.
- **(b) Text that is verbatim-legible on the product in REAL photography.** What the
  pack itself says, read off a real pack shot at 1:1 and transcribed into
  `brand/pack-strings.json`. Not a generated pack — a generated label invents claims
  in the pack's own typeface, so a generated plate's print is never in
  this set no matter how crisp it renders.

**Everything else — every benefit line, every number, every category claim, every
paraphrase of site copy — lands in the build flagged `[NEEDS APPROVAL]`**, with its
verbatim source string and source URL, exactly as `claims-CANDIDATES.md` carries
them. The build still happens. The flags travel with it.

**Where that build may go:** to the **OPERATOR**, and nowhere else. Never to the
client, never to an ad account, never to a platform, until a human has signed the
rows. A flagged build is a draft for review, not a deliverable, and the report says
so in the same breath as the ad.

**What this policy is NOT.** It is not an approval and it does not soften instrument
5's fatal: at delivery, an unapproved claim is still a fatal, full stop. It is a
scoping rule for what the loop is allowed to BUILD while the async claim-approval
stage gate is open. Nor does an operator constraint convert into an approval —
"no medical claims beyond what their site claims" scopes a permitted set; it is not
a signature, and it does not put site copy on the approved list.

**The one file rule that never bends:** the loop does not write content into
`approved-claims.md`. When operator-scoped permissions need recording, they go in a
**separately named** file (e.g. `brand/claims-OPERATOR-SCOPED.md`) that says on its
face that it is not an approval. The value of the approved file is that it cannot
have been forged.

**The claims audit covers the PHOTOGRAPHED PACK's rendered text, not only the
code-set type layer.** A generated product does not merely garble its label — it
invents claims on it, in the pack's own typeface, crisply, and the claim a model
reaches for is reliably the most compliance-loaded one in the category. Garble
announces itself; invented copy reads as fact. Every string the print audit
transcribes off the product goes through this file exactly like a headline, and a
plausible-but-absent brand claim is a kill.

### `brand/tensions.md`
The story premises worth building an ad on — and the verification of each. **A
charter's premise is a CLAIM until it is checked against the brand's own record.**
A premise can be half-true: one half documented verbatim on the client's own
pages, the other half existing only in third-party press or in a mascot's
fictional backstory. Verify at charter time, ship the verified half, and never let
character mythology promote itself into on-ad fact.

### `brand/product-images/` + `INDEX.md`
Real pack shots at **native resolution**, with dimensions and alpha status
recorded per file. This is not bookkeeping — it is arithmetic the whole build
depends on:

- Law 29: never enlarge past native resolution. A macro crop of a normal pack shot
  reads as a broken render.
- **Product prominence and generated micro-text legibility are the SAME KNOB.**
  With `s` = the pack's delivery downsample against the real shot, every quantity
  that matters is `k/s`: the micro-strip cap, the headline-band cap, the pack
  width. There is no crop, no plate and no inset that escapes it, because both
  numbers are the same fraction. Record the native width or the arithmetic cannot
  be run.
- **Record the STEM-HEIGHT LADDER, not one number.** `s` is a threshold **per
  printed line**, never per pack: measure each printed line's stem height on the
  real shot with one stated method (e.g. p85 vertical stem) — headline band,
  sub-line, body line, ingredient line, micro strip. "Small print gone, brand line
  intact" then lives in a computable *interval* between two rungs. Without the
  ladder, a scale route gets declared open or closed on a guess.
- On a **generated** pack, `s` is necessary and never sufficient — the model sets
  the type size, so a plate can satisfy `s` and still render legible-and-wrong
  small print. Use `s` to pick which plates to measure; gate on stem heights
  measured on the delivered frame.
- A **soft-edge alpha** matte is a real photographic matte; a hard 0% soft edge is
  the cutout tell.

### `brand/north-star-picks/`
**Hand-picked by the operator. Never harvested, never auto-filled.** These are the
calibration input for the taste twin and the lineup draws. A harvested corpus
(`static-kit/inspo/`) is a different thing — it teaches the laws; the picks
declare the bar.

Write down the grammar read: what these picks have in common, in the operator's
terms. That read is what a judge is actually calibrated on.

### `brand/reviews/`
Raw records verbatim (never summarised into the store) plus `SUMMARY.md` with two
derived lists: **persona seed material** (recurring arcs and phrases, with record
ids) and **verdict-quote candidates** (verified, high-rating, whole-unit, short —
each carrying its id, author, date and product line).

### `personas/`
The resonance judges. The grounding rule is absolute:

> Every trait, complaint, love, objection, and vocabulary item must trace to a
> quoted, linked, real source. No invented psychology. Where evidence is thin the
> file says **[GAP]** and names what is missing. A thin honest persona beats a
> rich fake one.

Each file ends with a **JUDGE PROTOCOL** section defining the three questions
(would you stop / would you believe it / would you buy), the one-line idiom
answer, and the honesty rail: **the persona defaults to scrolling past**, and
anything untraceable is tagged `[extrapolation]`.

A persona cannot judge design craft. It judges the purchase. When a persona and a
craft critic disagree about a device, the persona wins; when they disagree about
rhythm, punctuation or a doubled logo, the critic wins.

---

## Loop-readiness checklist

A client is loop-ready when all of these are true. Anything false is a `[GAP]`
that the loop must state out loud rather than paper over.

- [ ] `art-direction.md` exists and declares a light logic concrete enough to
      write both a generation prompt and a physics probe from
- [ ] `bible.md` lists the hard content rules
- [ ] `approved-claims.md` has at least one human-approved claim
- [ ] ≥1 real pack shot at native resolution, with dimensions recorded
- [ ] the client's own fonts are on disk (or an explicit substitute is named)
- [ ] the palette is site-exact with provenance
- [ ] ≥1 persona with a JUDGE PROTOCOL and honest [GAP] sections
- [ ] North-Star picks chosen by the operator, with the grammar read written down
- [ ] `tensions.md` has ≥1 VERIFIED premise
- [ ] the Meta Ad Library page id is resolved (theirs, plus competitors worth
      harvesting)
- [ ] the Verdict Bank is either populated or **explicitly declared empty** — an
      empty bank means the twin is uncalibrated, not that it is neutral

`scripts/intake.py` gets you most of the way from a URL. It cannot get: art
direction, brand tensions, North-Star picks, approved claims, or anything behind a
login. Those are human acts, and intake marks them `[GAP]` rather than inventing
them.

## Instrument pointer files (required by loop-engine)
| file | contents | consumer |
|---|---|---|
| `brand/pack-reference.txt` | one line: repo-relative path to the real reference pack shot filter D calibrates against | `loop-engine/physics.ref_pack_for()` / `triage.py --client` |
| `brand/pack-strings.json` | the pack's real printed strings, verbatim (the letter-perfect filter's truth list — a missing file degrades loudly, never silently) | `loop-engine/vision.load_truth()` |

**`pack-strings.json` is written as a DRAFT by intake** (step `packstrings`): pack-shot OCR
at high confidence plus copy-derived strings, each with its provenance. Without it the print
gate is **unrunnable on a freshly-onboarded client** until a human transcribes the package by
hand, which is a gate nobody runs.

The draft is not a substitute for the transcription, and its `_STATUS` header says so:

- **Only `crisp` OCR transcriptions enter `strings`.** `soft` and `unresolvable` ones are listed
  separately and deliberately held out. A guessed string in the truth list silently launders a
  real garble into a pass — the one failure this gate exists to catch — so the draft errs toward
  a missing string, which fails loudly instead.
- **A human must still read the pack at 1:1**, add every printed line that is missing (seal lines
  and small print are the usual omissions), delete anything the pack does not print, and then
  **delete the `_STATUS` block**. Its absence is the signal that a human has been through the file.
- Intake never overwrites an existing `pack-strings.json`.
