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

## CRITICAL: the contact sheet is NOT the cut-to-cut continuity lock — the LOCKED PLATE is (added 2026-06-18)

**The single biggest misuse of this template:** generating each shot's start-frame independently against the multi-angle contact sheet, expecting the room to stay identical across cuts. It won't. The contact sheet's whole job is to show the room from MANY angles + lighting states so the model UNDERSTANDS the space — which is exactly why it's ambiguous as a continuity lock. Six different views in → the model picks/blends a different room each generation → cabinets shift, the floor-number panel renders 1-digit in one shot and 2-digit in the next, lighting wanders. (This cost a re-roll on the "Undetected" spot elevator spot, 2026-06-18: floor display read "03" / "2" / "05" across three start-frames, plus a doubled display in one.)

**The fix — lock a single PLATE for any master set reused across 2+ cuts:**
1. After (or instead of) the multi-angle sheet, generate ONE canonical EMPTY plate: a single frame of the set at the ONE hero camera + ONE lighting state, no characters. 4K, the shot aspect (9:16). Save as `refs/environments/<setting>_plate.png`.
2. Generate EVERY start-frame in that set by passing the plate as the **PRIMARY `--ref`** (first ref, before the character sheets) with explicit prompt language: "use this EXACT room — identical geometry, identical camera, identical fixtures — place the characters INSIDE it." The plate dominates; the model adds people instead of re-inventing the room.
3. **Pin every text / digit / label element in WORDS, per shot.** Models reinvent on-screen text every generation. Spec it rigidly: "ONE amber floor indicator above the doors, ALWAYS exactly 2 digits, reads 04" — and give the per-shot value (04 → 02 → 01). For the PRODUCT label specifically, don't even use video — ken-burns over the 4K still (seedance warps text regardless).

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
     at [time of day 1, e.g., overcast pre-noon / muted gray]
  2. MEDIUM — eye-level medium showing the hero area of the room (where most
     action happens — e.g., kitchen island) at the SAME time of day as panel 1
  3. ALT ANGLE — opposite-side view of the same room at the same time of day,
     showing the geometry from a different perspective

Bottom row (3 panels, left to right):
  4. WIDE WARM — same wide angle as panel 1 but lit at [time of day 2, e.g.,
     warm late-morning golden window light]
  5. NIGHT — same medium angle as panel 2 but lit at [time of day 3, e.g.,
     single warm pendant lamp + cool moonlight from window]
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

## Example — Dad's kitchen (the "ask your abuelo" spot)

```
Environment reference contact sheet for "Dad's suburban family kitchen" — the
master set of a vertical pharma-style ad parody. 6-panel grid on a clean
neutral background with thin gray dividers and small white serif labels.

THE SET:
- A modest suburban American family kitchen, ~12 feet wide, lived-in but
  slightly-too-clean for the ad's mockumentary register
- Walls: white painted upper section, white subway-tile backsplash above the
  counter (square ceramic with clean light-gray grout)
- Upper cabinets: flat-panel cream / off-white, simple recessed handles
- Counter: warm wooden butcher-block (honey tone)
- Lower cabinets: same cream as upper, flat-panel
- Floor: light oak engineered hardwood
- Hanging pendant lamp: single warm-bronze fixture above the kitchen island,
  Edison-style bulb visible, fabric cord drop
- Kitchen island: same butcher-block counter, two simple wooden stools at the
  far side, an open pile of mail and a coffee mug
- Window: one large window above the sink, frosted morning light, simple
  white roman-blind half-raised
- Appliances: stainless 2-slot toaster on the left counter, stainless KitchenAid
  stand mixer on the back counter
- Vibe: lived-in suburban American kitchen, slightly-too-clean for the
  pharma-parody register, NOT a magazine-staged farmhouse, NOT a studio set

PANEL LAYOUT:

Top row:
  1. WIDE COLD — wide-angle showing the full kitchen with the island in
     foreground, lit at overcast pre-noon gray window light from camera-left,
     low saturation muted slate-gray / cream / oat palette (the "before"
     register)
  2. MEDIUM COLD — eye-level medium on the kitchen island showing the mug,
     mail, and stools at the SAME overcast pre-noon gray lighting
  3. ALT ANGLE — opposite view showing the back counter with the stand mixer
     and toaster, same overcast pre-noon lighting

Bottom row:
  4. WIDE WARM — same wide angle as panel 1 but lit at warm late-morning
     golden window light from camera-left (the "after" register), restored
     saturation, warm cream / golden honey / soft kraft palette
  5. NIGHT — same medium angle as panel 2 but lit at night by ONLY the warm
     pendant lamp above the island plus cool blue moonlight through the
     window, high contrast deep shadows, slight chiaroscuro
  6. DETAIL STUDY — close-up of the white subway tile + grout + the seam
     where the warm butcher-block counter meets the tile, neutral lighting,
     showing texture and material fidelity

CONTINUITY LOCKS:
- The kitchen island stays in the same position in panels 1, 2, 4, 5.
- The stand mixer stays in the same position on the back counter in panels
  1, 3, 4. (Panel 5 may not show it depending on angle.)
- The pendant lamp position is fixed above the island in panels 1, 2, 4, 5.
- The window position above the sink is fixed in all wide shots.
- Only LIGHTING and CAMERA ANGLE vary. Geometry is locked.
- Each panel labeled at the bottom in small clean white serif text.

STYLE: Realism-leaning 3D Pixar render (Soul / Lightyear register, NOT Toy
Story exaggeration). Suburban-mockumentary register: slightly-too-clean,
calm, photographic. High-fidelity surface shaders, soft cinematic depth of
field on close-ups, gentle film grain.

Color palette across the set: cream / off-white / warm honey wood / pale
slate gray / soft warm bronze (the pendant lamp).

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
# Compose the start-frame prompt with the image-prompt-writer recipe
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

**Setting changes structurally between shots** (e.g., "the kitchen, but in shot 5 the family-photo wall now has a hole punched in it"): treat as TWO settings. Contact sheet each separately. Then in the prompt for the changed shot, reference both sheets and describe the change.

## Cost

~30-50 credits per environment contact sheet at 2k. For a typical spot with 1-2 master sets, that's ~30-100 credits added to Phase 3. Saves an estimated 100+ credits in Phase 5 re-fires per master set, so net positive on credits AND time.
