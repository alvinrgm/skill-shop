# Volume prompts — the asset engine

How to generate plates that survive triage, instead of 5 that don't. **Batch cap 15 at 1K
(config.VOLUME_BATCH_CAP / VOLUME_PLATE_SIZE); 4K only for the locked winner.**

**The governing finding (measured):** prompt clauses that encode
known kill-tells as **positive constraints** work at the batch level. In a prior
run, the variant whose scene text most directly restated the tells
passed physics about twice as often as the batch overall. Clause blocks are not
prompt decoration — they are the filter, moved upstream.

**The second finding:** a declared light direction is a
*suggestion* to the model — obeyed only about half the time. So is a declared
**occlusion** ("bury the lower panel in loose product", "put it below the sun's hard
edge": routinely ignored) and so is a **framing** instruction about the hero (routinely
ignored). Never
assume the prompt's window side, occlusion or crop survived. Generate volume and
**filter** for what actually happened.

The general rule: **hiding a region of the product is a CROP decision or a SCALE
decision. It is not a prompt decision.**

---

## THE PLATE-FORMAT RULE — bleed vs band is decided at GENERATION time

**Before a single plate is generated, declare how the plate meets the canvas.** It
is a prompt decision, and it is the one format decision that cannot be taken later.

| plate format | what the prompt must say | what the build may then do |
|---|---|---|
| **BLEED** — the plate is the whole canvas | the scene fills the frame edge to edge, **no border, no frame, no inset panel, no vignette-as-frame, no drawn margin, no rounded corner, no card** | place it full-frame; type sits on the scene |
| **BAND** — the plate occupies part of the canvas, the rest is a flat field | the scene is a **full-bleed image that will be cropped**, still no border of its own; the band edge is cut by the builder, not drawn by the model | crop to the band; the flat field is code-set, never generated |

**The blocking fatal this prevents:** a background rendered with its own border
cannot be half-placed. Once the model draws a frame, every crop slices through it and
every full-frame placement inherits a border nobody designed. There is no fix in the
build — the plate is spent and the batch has to be regenerated. Cheap to declare,
un-recoverable to discover late.

Two corollaries, both consistent with the finding above (a declared framing is a
suggestion, routinely ignored):

- **Never name the empty thing.** *"Leave a corridor empty"* is reliably rendered as
  *"draw a corridor"* — a lighter rectangle **with outlines**, whose own edges then
  break the quiet run the corridor existed to provide (12 of 12 in a test batch). Ask for
  the region by describing what the surrounding scene **does**: *"the tabletop
  continues unbroken and unlit across the middle third, nothing resting on it"*.
  A declared EMPTY REGION can be obeyed as a DRAWN OBJECT.
- **Gate on it.** The declared format is a MEASURED check on the batch — scan the
  plate's outer rows and columns for a continuous edge run — not an assumption that
  the clause was obeyed. Declared is what the model was asked for; measured is what
  it did.

---

## The architecture

```
prompts.py
├── shared clause BLOCKS   — one per kill-tell family, reused across every variant
├── VARIANTS               — 4-6 scene descriptions that differ in angle, light,
│                            scale and which element is the focal plane
└── build(scene, focus)    — scene text + "\n\n" + the assembled clause tail
```

Each variant is generated N times (temperature does the rest). 5 variants × 8
plates = 40. The real pack shot is passed as `--ref` on **every** call — the pack
may never be invented by a model.

Every clause carries, in a comment, **the numbered tell it encodes**. That comment
is the contract: when a new kill-tell is named, a clause is added and the mapping
is updated. A clause with no tell behind it is decoration and gets cut.

---

## The clause blocks

Adapt the nouns to the client's world; keep the structure and the physics. The worked
example below is a **rigid box (or jar) of a packaged product on a tabletop** — an
example; adapt every noun to your own product.

### PRODUCT ACCURACY — *the pack may never be invented*
Name the package's real geometry, panels, marks, wordmark and colour bands as they
appear in the reference. State its relationship to gravity ("stands upright and
square to gravity, never tilted, its flat base resting squarely on the surface").

### LABEL PHYSICS — *tell 15: label print does not ride curvature*
> the printing rides the package's real form — on a jar, letterforms compress and
> bend where the surface turns away from camera and bands curve around the body; on a
> box, print stays flat on each face and foreshortens across the turned side — and the
> ink sits IN the material's finish, taking the same directional light as the surface
> around it.

### MATERIAL DISPLACEMENT — *tell 15: loose material does not displace*
If the scene has any loose material around the product (scattered pieces, a cloth, a
surface texture), it must be **displaced by the object**: pushed aside where the
object's weight sits, sparser in the open, with a clean visible contact line, and
individual pieces at the edges of the scatter. *"Behaves as settled matter with
weight, never as an airbrushed haze or a symmetrical puff."*

### SUBJECT STRUCTURE — *tell 1: generated organic macro = procedural pumice*
The one clause most specific to the subject, and the one you must rewrite for every
product. For any organic or natural surface in frame (fruit, wood grain, a cut
ingredient): structure of clearly DIFFERENT sizes, irregularly distributed, with the
small asymmetries and damage real material carries. *"Never a uniform texture and never
a repeating pattern."*

Note the lane inversion: in a **hand-made-material** lane, the same
4x zoom that kills generated organic realism is the PROOF — thumbprints, tool
marks, seams and caught lint are what the material is supposed to have. There, the
fatal inverts to melted, airbrushed, plastic-smooth surfaces. Choose the lane and
the audit changes sides.

### ONE LIGHT — *tells 11, 33: no light exchange; achromatic umbra*
> a single real window out of frame is the only light source, its shape readable
> on the surface as a hard-edged rectangle with a soft penumbra. The light falls
> off LATERALLY so the far side is visibly dimmer. Every shadow points the same
> way. Contact shadows are darkest exactly at the seam and soften continuously
> with distance. **Shadows keep the colour of the surface they fall across — a
> darker version of that surface's own hue, never neutral grey.** Light bounces off the surface back up into
> the underside of the object, and a faint spill from the pack's colour band tints
> the material beside it.

This single clause is what filters B and C are measuring. Write it, then measure
it — never one without the other.

### CAMERA TRUTH — *tell 34: real photos read fake without depth cues*
> shallow depth of field with ONE real focal plane — `{focus}` is critically
> sharp, and sharpness falls away smoothly both in front of and behind it, never a
> uniform blur applied to a whole background. Fine 35mm grain across the entire
> frame, slightly coarser in the shadows. A slight natural lens vignette.

`{focus}` is per-variant and is the variant's real design decision.

### SINGULARITY — *tell 15: duplicated / mirrored debris*
> EVERY OBJECT APPEARS EXACTLY ONCE: one pack, one subject torn into its pieces,
> no repeated or mirrored fragments, no duplicated label elements, no cloned wood
> grain, no second mark.

### REGISTER — *the AD bible's grade, as a clause*
Who took this photograph and on what. Named film-stock colour behaviour (warm
midtones, highlight roll-off, lifted blacks never crushed, moderate contrast,
low-to-mid saturation — *the warmth comes from the sunlight, not a saturation
push*). Then the **NEVER list**, explicitly: no wet glaze, no specular sheen, no
steam plume, no studio rim light, no black slate, no white seamless, no colour
gel, no props beyond what is described.

The never-list is the highest-value part of this clause. Every item on it is
something a model reaches for by default and the brand does not do.

---

## Variant design

Variants are not paraphrases. Each isolates a different **physics risk** so the
batch tests the lane rather than one framing:

| variant shape | what it tests |
|---|---|
| raking side light, eye-level three-quarter, object left / subject right | the canonical register; lateral falloff |
| LOW, near surface level, subject nearest camera, pack behind and soft | whether depth-of-field ORDERING survives |
| 45° down-angle on a heavily covered surface | material displacement as the primary subject |
| beside the window, three-quarter backlight, higher contrast | whether backlit structure keeps its walls rather than blowing out |
| tightest crop, softest diffuse light | the scene at the scale where every physics tell is largest |

Declare the window side per variant. Then **record it and gate on the MEASURED
lateral gradient, not the declared one** — the declared side is what the model was
asked for; the measured gradient is what it did.

---

## The compounding rule

After every triage run:

1. For each plate that died, name the tell in the words a judge used.
2. If it is a NEW tell, write a new clause encoding it as a positive constraint,
   and add the row to the clause→tell mapping.
3. If an existing clause was present and the tell appeared anyway, that clause is
   **not working** — rewrite it more concretely (name the physical mechanism, not
   the adjective), or accept that the constraint is unreachable by prompt and
   becomes a filter-only check.
4. Iterate variants **like the winners they are**: the variant with the best
   physics survival rate seeds the next batch's shared scene grammar.

A lane is only banned when a VOLUME batch plus triage fails. Never from a first
roll.

---

## What volume + filters actually bought (the measured baseline)

- A volume batch routinely narrows to a minority of physics-clean plates and a handful of
  fully clean ones, at approximately zero cost.
- The physics survivors carried **single-light consistency** — the property no
  composite bought across a whole session of building.
- Filters A (flat mathematical fields) and C (achromatic umbras) almost never
  kill a single render: it structurally cannot fail those two classes. Keep them for
  composites; put single-render triage weight on **B (shadow behaviour)** and **D
  (micro-detail / legibility)**.
- The lane's residual ceiling was pack **micro-text**. Tested and rejected: flat
  paste (destroys earned curvature), perspective-warp relight (reads as a decal),
  prompt-side band exclusion (ignored 6/6). The remaining routes are compositional
  — crop or occlude the micro band (plates are huge, so crop freedom is real), or
  choose a framing where only headline-scale print appears.
- **A zero-survivor batch is a RESULT** when the filters that killed it are new and
  validated. A later targeted batch returned zero against a
  letter-perfect print filter that re-failed its own predecessor's artifact, plus a
  global-illumination filter catching what the physics cascade is structurally
  blind to. That gate was worth more than the ad the batch was meant to feed.
  **Report the curve; never lower a filter written this morning to justify the
  plates generated this afternoon.**
- **`s` is a threshold PER PRINTED LINE, never per pack**. Measure
  the real pack's whole ladder of stem heights first — a headline band, a
  sub-line, a body line, a micro strip all have different values, and the window
  where "small print gone, brand line intact" lives is an *interval* between two of
  them. Compute the ladder before declaring a scale route open or closed.
- **On a GENERATED pack, `s` is necessary and never sufficient**,
  because the generator sets the type size: the model re-draws the label at
  whatever size the composition suggests, so a plate can satisfy `s` and still
  render legible-and-wrong small print. Use `s` only to choose which plates are
  worth measuring; gate on the rendered stem heights measured on the delivered
  frame.
- But: **a garbled band between the product and the prop cannot be cropped out.**
  Check the vertical order of "the defect" and "the thing the concept needs"
  before promising a crop will solve it.
- And: **covering a defect on the product's own label with a graphic bar is not an
  occlusion, it is a different kill** — simultaneously the scene-hero rule, the
  flat-ink-over-a-photographic-field fatal (law 21), and a breach of label fidelity
  (law 8). When the only available
  occluder sits on the hero, the answer is a different plate.
