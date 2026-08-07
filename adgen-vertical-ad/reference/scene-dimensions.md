# Scene Dimensions — the shot grammar

The generalized set of inputs that define ANY shot — a single still, a contact-sheet panel, or
a Higgsfield/seedance video clip. Synthesized from the `image-prompt-writer` recipe, an earlier UGC pipeline's
"physics layer" (`photographySpecs.ts`), and adgen's hard-won practice. Don't merge those
systems — this is the shared *thinking* underneath all of them.

**Core principle:** the image/video model has a DEFAULT for every dimension you don't specify —
and the default is usually the generic, plasticky, dead-centre, flatly-lit "AI render" look.
**Every dimension you leave blank, the model fills for you.** This is the checklist that stops
that: decide each dimension deliberately, or knowingly let it ride. There is no secret
processing — these are all just prompt tokens. The entire win is *thinking through all of them*
instead of leaving gaps for the model to guess.

Use it as the **pre-step** before writing any contact sheet (Phase 3/4) or seedance prompt
(Phase 5). The `image-prompt-writer` recipe (Subject → Scene → Style → Lens → Lighting → Mood)
is just the still-image *subset* of this grammar.

---

## The dimensions (1–9 apply to EVERY shot)

### 1. Subject
identity (who/what) · pose / gesture · expression · wardrobe & styling · scale
- *contact sheet:* the entity rendered neutrally, from many angles/expressions
- *video:* + what the subject DOES over the clip (see Action, below)

### 2. Optics — the camera body
| Sub-dimension | Vocabulary |
|---|---|
| Focal length | 24mm wide · 28mm reportage · 35mm · 50mm natural · 85mm portrait · 90–100mm macro |
| Aperture / DoF | f/1.4 shallow (creamy bokeh) ↔ f/8–f/11 deep (sharp front-to-back) |
| Sensor / film | clean 16-bit 64-ISO ↔ 800-ISO digital noise · Kodak Portra 400 · Tri-X 400 · expired Polaroid |
| Distortion | 24mm barrel ↔ zero-distortion prime · chromatic aberration at edges |
| Height / angle | eye-level · low (hero) · high · overhead/top-down · Dutch |
| Shot size | extreme close-up · close-up · medium · full · wide |

### 3. Lighting
key direction (camera-L/R · back · top) · quality (hard ↔ soft/diffused) · ratio (high-key ↔
low-key, fill level) · colour temp / time-of-day (golden hour · overcast grey · 5000K neutral ·
night) · practicals (window · lamp · neon) · named setups (45° Rembrandt · 5-point softbox ·
single directional rake · dual-point rim)

### 4. Composition
placement (dead-centre ↔ off-centre, lower/upper third) · negative space (where + how much) ·
depth layering (FG / MID / BG) · leading lines · symmetry ↔ asymmetry · aspect/orientation
(9:16 · 4:5 · 16:9) · vertical-zone discipline (subject upper/mid third, props lower, clean
band for FCP captions/logo)

### 5. Environment
setting / location · set dressing & props (art-directed details — a flour scatter, a wooden
scoop) · background treatment (clean ↔ creamy bokeh ↔ busy) · continuity locks (what stays
fixed across shots)

### 6. Material / surface
specific material — NOT "metal" → "brushed steel with micro-scratches"; NOT "clay" →
"hand-thumbed plasticine with fingerprint impressions" · finish (matte tooth ↔ high-gloss) ·
the "no plastic sheen / no blown highlights" guardrail · specularity & reflections

### 7. Style / render register — pick the baseline look
| Register | Token gist |
|---|---|
| editorial / lifestyle | 35mm f/1.4, golden hour, Portra grain, warm cinematic, story-driven |
| studio / commercial | 85mm f/11, 5-pt softbox, sterile, zero distortion |
| iPhone / UGC | 24mm f/1.8, ISO-800 noise, handheld tilt, amateur (adgen routes this to `lib/keyframe.py`) |
| documentary / candid | 28mm reportage, Tri-X grain, unposed, available light |
| **3D-CGI / Octane render** | Octane/Redshift path-tracing, PBR materials, subsurface scattering, "impossible" hyperreal-3D perfection |
| claymation / stop-motion | hand-thumbed plasticine, fingerprint impressions, slight frame-to-frame judder |
| retro / analog | expired Polaroid / Super-8, light leaks, crushed blacks, soft vintage lens |
*(Quick baselines for the look — you still set the other dimensions on top. These mirror an earlier UGC pipeline's
`photographySpecs.ts` modes; reuse the vocabulary, no need to merge the code.)*

### 8. Mood / intent
2–3 mood words · narrative beat / story role · brand register · palette (name 3–5 colours)

### 9. Consistency lock (multi-shot work)
object-lock + fail-conditions (what must NOT change) · reference roles (what each `--ref`
carries) · cross-shot continuity (identity · set geometry · voice)

---

## Video-only dimensions (seedance / Higgsfield) — layered ON TOP of 1–9

| Dimension | Notes |
|---|---|
| Camera MOVE | push-in · dolly · pan · crane · crash-zoom · locked. Be specific ("slow 2% push-in over 8s"), never "camera moves around". |
| Action over time | what changes second-to-second (gesture, pour, transform). Everything else stays put. |
| Duration / pacing | 4–15s (server clamps >15s). Match to dialogue length + a breath. |
| Audio | VO (ElevenLabs is the default voice source) + ambient/diegetic SFX. **ALWAYS append `NO MUSIC. NO MUSICAL SCORE. NO INSTRUMENTAL BACKING.`** — music is added in FCP at Phase 6. |
| Scene stability | locked-camera shots get the stability clause (`prompts/scene-stability-clause.md`) — nothing new appears mid-shot. |
| IP-safe translation | **NEVER name studios/films/archetypes in a seedance prompt** (Aardman → "hand-thumbed plasticine"; Dust Bowl → "parched plain"). Identity rides the `start_image`, not the text. Gemini stills are EXEMPT. See SKILL.md HARD RULE + `prompts/seedance-shot.md`. |
| Lip-sync | pass the 11L segment as `role: audio`; describe mouth movement, don't re-type the line. |

---

## What activates per format

| Dimension | Single still | Contact sheet | Seedance video |
|---|---|---|---|
| Subject · Material · Style · Mood | ✅ full | ✅ neutral, multi-angle | ✅ + action |
| Optics · Lighting · Composition | ✅ full art-direction | ✅ consistent across panels; vary ONLY angle + light + expression | ✅ + camera MOVE |
| Environment | ✅ | ✅ (env sheet = one set, many angles/times) | ✅ + stability lock |
| Consistency lock | for a series | ✅ **this is the whole job of a sheet** | ✅ via `start_image` + sheet ref |
| Camera move · Action · Audio · IP-safe · Lip-sync | — | — | ✅ the video-only layer |

- **Contact sheet** = lock dimensions 1–9, then vary ONLY angle + lighting + expression across the
  panels. Consistency is the point; everything else holds identical.
- **Seedance prompt** = carry 1–9 from the *approved start-frame*, add the video-only layer, then
  TRANSLATE any style-by-name into physical description (IP rule) and append the NO-MUSIC clause.

---

## The reason-through (run this before writing ANY prompt)

1. **Subject** — who/what, pose, expression, scale?
2. **Register** — which Style baseline (editorial / studio / UGC / CGI-Octane / claymation / …)?
3. **Optics** — focal length, DoF, sensor/grain, height/angle, shot size?
4. **Lighting** — direction, quality, ratio, colour temp, practicals?
5. **Composition** — placement, negative space, depth, aspect + zones?
6. **Environment** — setting, props, background, continuity?
7. **Material** — exact surfaces + the "no plastic sheen" guardrail?
8. **Mood** — 2–3 words + a named 3–5 colour palette?
9. **Consistency** — object-lock / fail-conditions / ref roles?
10. **(video only)** — camera move, action, duration, audio + NO MUSIC, stability, IP-safe translation, lip-sync?

Any box you skip, the model decides for you. Fill them deliberately, or skip on purpose — never
by accident.
