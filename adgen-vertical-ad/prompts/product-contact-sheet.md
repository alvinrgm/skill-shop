# Product contact sheet prompt template

Generate locked reference sheets for every recurring on-screen product. Two sheets per product: packaging + bare product. Built at Phase 3, uploaded to Higgsfield, referenced in every shot prompt where the product appears.

## Why

Generative video models invent a new version of any product every shot unless given a strong visual reference. In one past spot, a small dropper bottle drifted across 5+ generations (spray bottle, pump bottle, unlabeled vial, glass jar) because there was no locked product reference. ~100 credits in re-fires could have been avoided.

This works the same way character contact sheets do — generate the grid once, lock the appearance, reuse the media_id everywhere.

## When to generate

For ANY of these:
- A branded product that appears in the CTA / hero shot
- A product that appears in 2+ shots (will drift across shots)
- A product that has specific brand requirements (color, material, finish, packaging design)
- A product whose appearance is plot-relevant (e.g., the bottle the characters react to)

Skip ONLY if:
- The product appears in exactly 1 shot AND is sourced from an existing brand photo passed as image ref AND has no extra detail needed

## Sheet 1 — Packaging contact sheet

**Goal:** lock the product's package appearance from all angles.

**Generation params:** generate via **`scripts/gen_image.py`** (Gemini Nano Banana Pro — NEVER the Higgsfield MCP, image-gen HARD RULE). Flags: `--aspect 16:9 --size 4K` (locked reference → 4K). Pass the real brand product photo via `--ref`.

**Prompt template:**

```
Product packaging contact sheet for {brand} {product-name}, 6-panel grid on a clean
neutral grey background, soft even studio lighting, no shadows, no reflections.

Top row (3 panels, left to right):
  1. FRONT — straight-on view of the package, full vertical, centered
  2. BACK — straight-on rear view, label/ingredients visible
  3. 3/4 LEFT — three-quarter view from the left, showing depth

Bottom row (3 panels, left to right):
  4. 3/4 RIGHT — three-quarter view from the right
  5. TOP — top-down view, lid/cap visible
  6. HERO PULL — the package with a single {product unit} peeking from the dispenser
     opening, mid-pull (the iconic brand pose)

Each panel labeled at the bottom in small white serif text. Grid lines thin and
neutral grey. All panels match identically in lighting, color temperature, and scale.

The product is: {detailed visual description from brand assets — colors, materials,
typography, logos, exact label text, dimensions}.

CRITICAL: preserve the actual brand identity exactly. Do not invent colors, logos,
or label text. Match the reference image of the real package.
```

**Pass as `medias`:** the actual brand product photo as `role: image` ref. **Do not invent the brand.**

**Save to:** `$ADGEN_HOME/<brand>/concepts/<slug>/refs/product/<name>_pack_sheet.png`

## Sheet 2 — Bare product contact sheet

**Goal:** lock the product OUTSIDE the package — what it looks like in use.

**Generation params:** same as Sheet 1 — **`scripts/gen_image.py`** (Gemini Nano Banana Pro, NEVER the Higgsfield MCP). `--aspect 16:9 --size 4K`. Pass the brand product photo + (once generated) the packaging contact sheet via `--ref`.

**Prompt template:**

```
Bare product contact sheet for {brand} {product-name} — the product itself, OUTSIDE
its packaging, 4-panel grid on a clean neutral grey background, soft studio lighting.

Top row (2 panels):
  1. FLAT — the product laid flat / fully visible, top-down view, full extent
  2. IN-HAND — a hand holding the product naturally as you'd use it

Bottom row (2 panels):
  3. IN-USE — the product mid-stroke / mid-action / mid-application
  4. TEXTURE MACRO — extreme close-up of the surface, showing material detail

Each panel labeled at the bottom in small white serif text. Grid lines thin and
neutral grey. All panels match identically in lighting and color temperature.

The product is: {detailed visual description — material, color, surface, texture,
size relative to the hand, any specific physical properties that matter for the spot}.

CRITICAL color/material spec:
  - Color: {e.g., "ONE solid uniform pure white, no patterns, no logos, no prints"}
  - Material: {e.g., "thin disposable non-woven cleansing tissue, slightly damp sheen"}
  - NOT: {e.g., "NOT a spray bottle, NOT a pump, NOT clear glass"}

Match the actual product. Do not invent variations.
```

**Pass as `medias`:** the brand product photo + the packaging contact sheet (once generated) as image refs.

**Save to:** `$ADGEN_HOME/<brand>/concepts/<slug>/refs/product/<name>_bare_sheet.png`

## After both sheets are generated

1. Upload both to Higgsfield via `media_upload` → get media_ids
2. Confirm uploads via `media_confirm`
3. Update `refs/asset-lock.yml` with:
   - `packaging_media_id`
   - `bare_product_media_id`
   - `description_for_prompts` paragraph that captures the locked spec
4. Surface both sheets to the operator in chat with the locked spec paragraph for approval.

## Using the sheets in Phase 5 video gen

For every shot where the product appears:
- Pass `packaging_media_id` and/or `bare_product_media_id` as image refs in the seedance call.
- Paste the `description_for_prompts` paragraph verbatim into the prompt's product section.
- Do NOT paraphrase. Same words every time = same product every time.

## Example: a dropper bottle (invented product, what should have happened)

Phase 3 outputs:
- `refs/product/dropper_pack_sheet.png` — 6-panel of the boxed bottle
- `refs/product/dropper_bare_sheet.png` — 4-panel of the bare bottle (standing, in-hand, mid-squeeze, cap macro)
- `refs/asset-lock.yml` entry:
  ```yaml
  - name: dropper_bottle
    role: hero product, resolves the spot
    appears_in_shots: [4, 5, 6]
    visual_lock:
      type: bare-product
      material: small amber glass bottle with a black rubber-bulb dropper cap
      color: warm amber glass, black cap, plain cream label band
      surface: glossy glass, soft highlight on the shoulder
      forbidden_appearances:
        - spray bottle or pump bottle
        - clear or blue glass
        - box or outer carton visible (this sheet is for the bare bottle, packaging is separate sheet)
    reference_sheets:
      packaging_sheet: refs/product/dropper_pack_sheet.png
      packaging_media_id: <uuid>
      bare_product_sheet: refs/product/dropper_bare_sheet.png
      bare_product_media_id: <uuid>
    description_for_prompts: |
      A small amber glass dropper bottle, about the height of a thumb, with a black
      rubber-bulb dropper cap and a plain cream label band. NOT a spray bottle, NOT a
      pump, NOT clear glass. Same amber color, same cap, same label band in every shot.
  ```

Then every Phase 5 shot prompt that featured the bottle would have used `bare_product_media_id` as an image ref AND pasted the description paragraph verbatim. Zero drift.

## Cost

Generated on your **Gemini key** via `gen_image.py` — **not** Higgsfield credits. The cost that matters is downstream: a locked product sheet prevents the ~100 Higgsfield credits in Phase 5 re-fires that drift otherwise causes (e.g. the bottle drifting across 5+ gens).
