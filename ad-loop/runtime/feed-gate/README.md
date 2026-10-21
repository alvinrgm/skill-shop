# feed-gate — the feed-survival gate

Judges a static ad the way a phone-scrolling human would actually encounter it:
at thumbnail size, half-covered by app chrome or the fold, in peripheral vision.
Statics only (PNG/JPG).

Two instruments:

| | what it does |
|---|---|
| **`feedmock/`** | renders the candidate INTO a pixel-accurate Instagram feed / Reels mock at true phone scale, between organic-looking neighbours (your inspo corpus, or neutral placeholders), and computes chrome collisions geometrically |
| **`ablate.py`** | mutilates the ad the way the medium does and measures the DELTA in extractable meaning between original and mutant |

---

## THE HONESTY RAIL — read this before quoting any result

**This gate measures whether the MEDIUM CAN KILL THE AD. It never measures
whether anyone would stop scrolling for it.**

A clean sweep grants exactly one thing: **"not killed by the medium."**
It does **not** grant *ship*.

An ad can pass every mode here and still be completely boring, and boring is
by far the more common way an ad fails. Boring detection belongs to the judge
battery (SKILL.md section 3) and the persona panel — not to this folder. Never
let a green battery launder a weak concept.

---

## Usage

```bash
# harness: see it on the surface + geometric collision report
python3 feedmock/render_infeed.py <ad.png> \
        [--surface feed|reels] [--out DIR] [--brand NAME] \
        [--scales 1,3] [--no-detect]

# battery: the death modes
python3 ablate.py <ad.png> [--surface feed|reels] [--out DIR] \
        [--modes chrome,phone,desat] [--workers 4] [--no-cache]

# both, over YOUR calibration set (calibration/set.json), printing the table
python3 calibrate.py [--only NAME,...] [--skip-harness]

# print the geometry this whole gate is built on
python3 geometry.py
```

Surface defaults to `reels` for 9:16 assets and `feed` for everything else.
Extractions are cached under `out/<ad>/extractions/`; re-runs are nearly free.
Pass `--no-cache` after changing a mutation.

### Harness output (`out/<ad>/`)
```
01-first-encounter.png[@3x]   the ad mid-viewport, as a scroller first meets it
02-in-view.png[@3x]           fully in view, all chrome present
03-scrolled-past.png[@3x]     60% scrolled past
chrome-overlay.png            transparent-slot chrome layer (3x)
collision.json / collision.md the geometric collision report
```

### Battery modes

| mode | simulates | fails when |
|---|---|---|
| `chrome` | IG chrome over the ad / the fold under it | meaning LOST → layout fix |
| `phone` | true ~180px visual size | meaning LOST → legibility fix |
| `desat` | peripheral vision, chroma dropped | meaning LOST → advisory only |

The delta report is natively fix-shaped: it names **which element died in which
mutation**, with the original value, so the fix is legible at a glance.

---

## How it works

**Geometry (`geometry.py`) is the single source of truth.** Nothing downstream
hardcodes a pixel. Two classes of number live there, and the file is explicit
about which is which:

- **Meta-published (high confidence).** Meta's ads guide states, verbatim, to
  leave "roughly 14% of the top, 35% of the bottom, and 6% on each side" of a
  9:16 Reels asset free of text, logos, or key creative. That is the
  load-bearing constraint, and because it is defined on the *asset* it survives
  every letterbox-vs-cover-fill question.
- **Component estimates (low confidence, tagged `unverified`).** Instagram does
  not publish the height of its top bar, post header, action rail, or CTA row.
  Those are estimates from teardowns plus iOS conventions, kept in ONE tunable
  block so a single real 3x screenshot measurement upgrades every downstream
  report at once. Do not cite them as measured fact.

**Chrome is a scrim, not a black box.** Chrome rects carry an `opacity`:
the tab bar and the cover-fill side crop are genuinely opaque (1.0), while the
caption / username / CTA band is a gradient scrim (~0.72) that large
high-contrast type survives and small low-contrast type does not. Modelling all
chrome as solid black was the first calibration pass's biggest error — it wiped
burned captions that survive fine in reality and made an elite ad look dead.

**Feed's weapon is the fold, not occlusion — so fold `chrome` is scored
RELATIVE, not absolute.** Instagram chrome never overlays a feed post; it
stacks above and below. So for the feed surface, `chrome` blacks out everything
*not yet on screen at the moment the scroll decision is made* — for a 4:5
static, **77% of the creative** (23% visible at first encounter). That fraction
is a property of the FORMAT, not the ad: every elite 4:5 corpus static also
loses whatever lives below that line, so an absolute loss bar measures the
format constant and fails elite controls. Fold-dominated chrome is therefore scored against the
elite reference distribution in `calibration/chrome-feed-ref.json` — an ad
fails only when it loses strictly more than `max(elite p75 + 0.25, elite max)`
under the identical occlusion. The 23% first-encounter visibility is reported
in every run as a **fold-composition input for design** (put the hook above
the line), never as a gate failure. Rebuild the reference:
`python3 calibrate.py --build-chrome-ref`.

**Collision separates two different things.** *Obscured* = real chrome or a real
crop physically covers the element. *Margin* = the element merely sits inside
Meta's advisory safe-zone band or below the fold — common and normal for a
product, only a real problem for text, logo, or CTA.

Gemini (`lib/gemini.py`) is used for two things only: extracting what meaning
survives a mutant, and localising element bounding boxes. Key is
`GEMINI_API_KEY` from the environment or the package `.env`. Never a
credit-billing generation service.

---

## Calibration

The contract: **elite ads should largely survive, and the battery should localise
concrete failures in ads a human already killed.** If elite ads fail broadly, the
thresholds are wrong: tune them, don't rationalise the result.

Declare your own set in `calibration/set.json` (copy `calibration/set.example.json`:
3+ long-running elite ads from your inspo corpus, 2+ ads a human killed), then:

```bash
python3 calibrate.py                    # prints the mode-by-mode calibration table
python3 calibrate.py --build-chrome-ref # rebuild the fold reference from YOUR corpus
```

What the shipped calibration established (on a private corpus of elite DTC ads and a
batch of statics a human had killed):

- **Neither blind nor trigger-happy.** About 1 failed mode in 18 elite mode-runs; the
  killed statics each failed on the defect a human had named (body copy unreadable at
  true phone size).
- **The fold is a format constant.** Every elite 4:5 static loses whatever sits below
  the first-encounter line (23% visible). An absolute loss bar measured the format, not
  the ad, and failed elite controls, so feed `chrome` is scored RELATIVE to
  `calibration/chrome-feed-ref.json` (12 anonymised elite 4:5 statics). Fails only
  above `max(elite p75 + 0.25, elite max)`.
- **Chrome is a scrim, not a black box.** Modelling all chrome as solid black wiped
  burned captions that survive fine in reality and made an elite ad look dead.
- **A clean sweep means "not killed by the medium". It never means ship.**

---

## Related files

- `../../SKILL.md` section 3, instrument 4e (feed-gate is one row of the craft pass)
- `../../design/design-laws.md` section F (the judge gate)
