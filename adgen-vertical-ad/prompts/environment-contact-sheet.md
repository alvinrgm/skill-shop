# Environment contact sheet prompt template

Used in Phase 3 of the adgen-vertical-ad pipeline to generate a multi-angle + multi-time-of-day reference grid for every **master set** — any setting that appears in 2+ shots.

## Why we do this

Generative video and image models invent a fresh interpretation of any environment every shot unless given a strong visual reference. A single PNG ref locks ONE angle at ONE time of day. A master set used across 4 shots with different framing, camera angles, and lighting needs more.

Without an environment contact sheet:
→ Kitchen cabinets reposition between shots
→ Counter material changes (wood → marble → wood)
→ Wall tile pattern varies
→ Fixtures and lamps drift in position
→ Window positions shift
→ Time-of-day continuity breaks

This template solves the same drift problem character contact sheets and product contact sheets solve — generate the grid once, lock the appearance, reuse the media_id everywhere.

## CRITICAL: the contact sheet is NOT the cut-to-cut continuity lock — the LOCKED PLATE is

**The single biggest misuse of this template:** generating each shot's start-frame independently against the multi-angle contact sheet, expecting the room to stay identical across cuts. It won't. The contact sheet's whole job is to show the room from MANY angles + lighting states so the model UNDERSTANDS the space — which is exactly why it's ambiguous as a continuity lock. Six different views in → the model picks/blends a different room each generation → cabinets shift, a wall sign renders one word in one shot and a different word in the next, lighting wanders.

**The fix — lock a single PLATE for any master set reused across 2+ cuts:**
1. After (or instead of) the multi-angle sheet, generate ONE canonical EMPTY plate: a single frame of the set at the ONE hero camera + ONE lighting state, no characters. 4K, the shot aspect (9:16). Save as `refs/environments/<setting>_plate.png`.
2. Generate EVERY start-frame in that set by passing the plate as the **PRIMARY `--ref`** (first ref, before the character sheets) with explicit prompt language: "use this EXACT room — identical geometry, identical camera, identical fixtures — place the characters INSIDE it." The plate dominates; the model adds people instead of re-inventing the room.
3. **Pin every text / digit / label element in WORDS, per shot.** Models reinvent on-screen text every generation. Spec it rigidly: "ONE round wall clock above the whiteboard, plain white face, black hands, hands at 9:10" — and give the per-shot value (9:10 → 9:25 → 9:40). For the PRODUCT label specifically, don't even use video — ken-burns over the 4K still (seedance warps text regardless).

**Division of labor, so it's unambiguous:**
→ room geometry / lighting / fixtures → the **plate** (the lock)
→ text / numbers / labels → **explicit word-spec per shot** (+ ken-burns for the product label)
→ faces / wardrobe → the **character contact sheets** (what they're genuinely good at)
→ within a single video clip → seedance re-renders from the start-frame, so review each clip and re-fire if it drifts

The multi-angle contact sheet below is still useful for understanding the space and for single-shot settings. But for a same-set spot, the PLATE is the continuity lock. Record it in `asset-lock.yml` as `canonical_plate:` alongside the `contact_sheet:`.

## When to generate

For ANY of these:
- A setting that appears in 2+ shots in the script
- A "master set" (the hero environment of the spot — usually a home, office, kitchen, studio)
- A setting that appears at multiple times of day (morning + night, before + after states)
- A setting where camera angle changes shot-to-shot (wide / medium / close on same room)

Skip ONLY if:
- The setting appears in exactly 1 shot AND has no camera-angle variation within that shot

## Template

Replace bracketed sections per environment.

```
Environment reference contact sheet for [setting name], 6-panel grid on a clean
neutral background with thin gray dividers and small white serif labels under
each panel. All 6 panels show the SAME ROOM — identical geometry, identical
materials, identical fixtures, identical decor — varied only by camera angle
and time-of-day lighting per panel.

THE SET: [Detailed description of the environment. Include:
- Room type and approximate size
- Wall materials and color
- Floor materials
- Ceiling height and treatment
- Fixed furniture (cabinets, counters, sofas, tables) — locked positions
- Fixtures (lamps, lights, faucets) — locked positions
- Decor (artwork, plants, rugs) — locked positions
- Windows (number, position, light direction)
- Doors (number, position)
- The "vibe" of the room — lived-in suburban / staged magazine / cluttered creative / etc.]

PANEL LAYOUT:

Top row (3 panels, left to right):
  1. WIDE — wide-angle view of the full room showing the master spatial layout
     at [time of day 1]
  2. MEDIUM — eye-level medium showing the hero area of the room (where most
     action happens — e.g., a desk cluster) at the SAME time of day as panel 1
  3. ALT ANGLE — opposite-side view of the same room at the same time of day,
     showing the geometry from a different perspective

Bottom row (3 panels, left to right):
  4. WIDE WARM — same wide angle as panel 1 but lit at [time of day 2]
  5. NIGHT — same medium angle as panel 2 but lit at [time of day 3]
  6. DETAIL STUDY — close-up of a signature element of the room (a key wall,
     the counter material, a key fixture) showing the texture and material
     fidelity at neutral lighting

CONTINUITY LOCKS:
- Every panel must show the same physical room. Cabinet positions must NOT
  shift between panels. Counter must be the same material everywhere. Tile
  pattern must be identical. Furniture must NOT teleport.
- Only LIGHTING and CAMERA ANGLE vary between panels. Geometry is locked.
- Each panel labeled at the bottom in small clean white serif text.

STYLE: [aesthetic — photographic / 3D pixar render / claymation / etc.]
[lighting register — soft cinematic / harsh industrial / warm domestic / etc.]
[color palette — list the 3-5 dominant colors of the room]

Aspect ratio: 16:9 horizontal. High detail, environment-reference quality.
NO characters in any panel. NO captions other than the panel labels.
NO product placement.
```

## Example — the fourth-floor office (the invented wildlife-documentary spoof)

```
Environment reference contact sheet for "the fourth-floor open-plan office" —
the master set of a vertical wildlife-documentary-style spoof. 6-panel grid on
a clean neutral background with thin gray dividers and small white serif labels.

THE SET:
- A mid-size open-plan office floor, ~40 feet deep, four rows of white
  sit-stand desks separated by low fabric partitions (sage green)
- Ceiling: exposed white-painted ductwork, long linear LED fixtures running
  front-to-back in four parallel strips
- Floor: charcoal low-pile carpet tiles with a subtle checkerboard of two grays
- Back wall: floor-to-ceiling windows with thin black mullions, city rooftops
  beyond, a row of potted snake plants on the sill
- Left wall: a long whiteboard with faint ghosted marker residue, a wall clock
- Kitchenette alcove at the far right: pale birch cabinets, a stainless sink,
  a blue-jugged water cooler against the end wall
- Desks: monitors on arms, a few lanyards and notebooks, one desk lamp per row
- Vibe: ordinary, slightly-too-tidy corporate floor that a nature-doc camera
  can treat as a habitat — NOT a glossy startup showroom, NOT a studio set

PANEL LAYOUT:

Top row:
  1. WIDE DAWN — long-lens wide from the back-left corner looking across all
     four desk rows, lights half-off, cool blue pre-dawn window light,
     low saturation slate / charcoal / pale sage palette
  2. MEDIUM MORNING — eye-level medium on the third-row desk cluster at
     mid-morning, overhead LEDs fully on, flat even white light
  3. ALT ANGLE — reverse view from the windows toward the whiteboard wall and
     the kitchenette alcove, same mid-morning lighting

Bottom row:
  4. KITCHENETTE — medium on the alcove: cabinets, sink, water cooler, under
     the same overhead LEDs plus a small under-cabinet strip light
  5. LATE AFTERNOON — same wide angle as panel 1 but lit by low warm amber
     sun raking through the windows, long partition shadows across the carpet
  6. DETAIL STUDY — close-up of a desk edge where the white laminate meets a
     sage fabric partition, neutral lighting, showing texture and material
     fidelity

CONTINUITY LOCKS:
- The four desk rows and the partitions stay in the same positions in panels
  1, 2, 3, 5.
- The water cooler stays at the end wall of the kitchenette in panels 3 and 4.
- The LED strips run front-to-back in every panel that shows the ceiling.
- The window wall position is fixed in all wide shots.
- Only LIGHTING and CAMERA ANGLE vary. Geometry is locked.
- Each panel labeled at the bottom in small clean white serif text.

STYLE: Photographic, observational-documentary register: long-lens
compression, natural-looking light, shallow depth of field on mediums,
gentle film grain. Calm and slightly austere.

Color palette across the set: white / charcoal / pale sage / brushed steel /
warm amber (late-afternoon light only).

Aspect ratio: 16:9 horizontal. High detail, environment-reference quality.
NO characters in any panel. NO captions other than the panel labels.
NO product placement.
```

## Generation params

Generate via **`scripts/gen_image.py`** (Gemini Nano Banana Pro), NEVER the Higgsfield MCP `generate_image` (image-gen HARD RULE — the MCP bills Higgsfield credits). Contact sheet = locked reference → **4K**. Aspect `16:9` for the grid.

```bash
python3 ~/.claude/skills/adgen-vertical-ad/scripts/gen_image.py \
  --out <setting>_sheet.png \
  --prompt-file <setting>_sheet_prompt.txt \
  --aspect 16:9 --size 4K \
  --ref <existing_space_photo_or_prior_render.png>   # optional: real space / moodboard / OG env ref for evolved settings
```

## Storage

Save to `$ADGEN_HOME/<brand>/concepts/<slug>/refs/environments/<setting>_sheet.png`.

Use this filename convention:
- `<setting>_sheet.png` — the multi-panel environment contact sheet (2k, 16:9)

If a setting also gets a single canonical hero plate (rare — only when one specific angle is THE hero of the spot), save additionally as `<setting>_hero.png`.

## Using the contact sheet for Phase 4 + Phase 5

**At Phase 4 (scene start-frames):**
For every shot that takes place in this setting, pass the environment contact sheet as `role: image` ref alongside the character contact sheet:

```bash
# Compose the start-frame prompt with the still-image recipe
# (Subject → Scene → Photography Style → Lens → Lighting → Mood), then generate via Gemini:
python3 ~/.claude/skills/adgen-vertical-ad/scripts/gen_image.py \
  --out refs/scenes/shot_NN_start.png \
  --prompt-file shot_NN_start_prompt.txt \
  --aspect 9:16 --size 1K \
  --ref refs/environments/<setting>_sheet.png \
  --ref refs/characters/<name>_sheet.png
```
(Start-frames are per-shot working frames, not locked refs → 1K/9:16 is fine. Pass the env + character sheets via `--ref` for set + identity lock.)

**At Phase 5 (video gen):**
Pass the environment contact sheet as an additional `role: image` ref in the seedance call, OR rely on the scene start-frame (which already had it baked in) as the start_image. The set geometry will hold across shots.

## When to regenerate the environment contact sheet

- Set design changes mid-project (the operator requests different cabinet style, different counter material)
- Generated sheet has off-spec elements that would propagate to all shots in that setting
- Adding a new time-of-day variant (e.g., adding "afternoon" to a sheet that only locked morning + night)

Don't regenerate "for fun" — once approved, the sheet is the authoritative spatial reference. Stability across shots is the whole point.

## Edge cases

**Setting appears in multiple shots but with no camera-angle variation** (always the same wide shot, same time of day): a single env ref at Phase 4 is technically sufficient. But still prefer a contact sheet if budget allows — locks against unexpected drift.

**Setting is an exterior** (street, field, beach): adapt the panel layout. Replace "WIDE / MEDIUM / ALT ANGLE / WIDE WARM / NIGHT / DETAIL" with appropriate panels for the exterior. The continuity-lock principle is the same: same physical location across all panels, only lighting + angle varies.

**Setting changes structurally between shots** (e.g., "the office, but in a later shot the whiteboard has been knocked over"): treat as TWO settings. Contact sheet each separately. Then in the prompt for the changed shot, reference both sheets and describe the change.

## Cost

~30-50 credits per environment contact sheet at 2k. For a typical spot with 1-2 master sets, that's ~30-100 credits added to Phase 3. Saves an estimated 100+ credits in Phase 5 re-fires per master set, so net positive on credits AND time.
