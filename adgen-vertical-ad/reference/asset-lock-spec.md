# Asset lock spec

Template for locking the visual appearance of recurring on-screen assets across an ad's shots. Built once at Phase 1-3, frozen by Phase 4.

## Why

Generative video models invent new versions of objects every shot unless given a strong reference. The pet wipe drifted across 5+ versions in one session (cotton cloth, lavender pattern, off-white, paper towel) because there was no locked visual spec.

A per-project asset lock pins each recurring asset to a single visual spec, with a contact sheet media ID that gets referenced in every shot's prompt.

## File location

`$ADGEN_HOME/<brand>/concepts/<slug>/refs/asset-lock.yml` — concept-level (each concept locks its own asset appearances). If an asset is a promoted brand mascot, its lock entry can also live in `brand/characters/<name>/asset-lock.yml` and be referenced from the concept.

Built at Phase 3 alongside character bibles. One entry per recurring asset.

## Schema

```yaml
brand: <brand-name>
assets:
  - name: <short-key, e.g., "wipe", "bottle", "pack">
    role: <one-line, e.g., "the hero product that resolves the spot">
    appears_in_shots: [4, 5, 6]   # which shot numbers feature it

    visual_lock:
      type: <packaging | bare-product | both>
      material: <e.g., "thin non-woven disposable wipe — like a baby-wipe pull">
      color: <e.g., "pure uniform white. No patterns, no logos, no tints">
      surface: <e.g., "smooth, slightly damp sheen, fine-textured">
      size: <e.g., "8 by 8 inches">
      forbidden_appearances:
        - <e.g., "cotton cloth or fabric texture">
        - <e.g., "lavender stitching or pattern">
        - <e.g., "brand logo or pack visible">
        - <e.g., "tinted by ambient lighting">

    reference_sheets:
      packaging_sheet: refs/product/<name>_pack_sheet.png
      packaging_media_id: <higgsfield UUID, filled after upload>
      bare_product_sheet: refs/product/<name>_bare_sheet.png
      bare_product_media_id: <higgsfield UUID, filled after upload>

    description_for_prompts: |
      The exact paragraph to paste into every shot prompt where this asset appears.
      Should match the visual_lock fields verbatim.
      Example: "a thin disposable non-woven wet wipe — smooth fine surface, slightly
      damp sheen, soft and flexible, the kind you pull from a baby wipe pack. NOT a
      cotton cloth, NOT a towel, NOT a fabric. The wipe is ONE SOLID UNIFORM PURE
      WHITE COLOR, no patterns, no logos, no prints, no shading variations."
```

## How to use during Phase 5 (video gen)

For every shot that features a locked asset:
1. Pass the relevant `media_id` (packaging_media_id and/or bare_product_media_id) as an `image` ref in the seedance call.
2. Paste `description_for_prompts` verbatim into the seedance prompt's asset section.
3. Do NOT paraphrase the description — voice consistency rules apply to visual assets too.

## When to build the lock

- **Phase 3** — generate the contact sheets per `prompts/product-contact-sheet.md`, upload to Higgsfield, fill in the YAML.
- **Surface to the operator** alongside character bibles. They approve the visual spec once. After approval, the lock is frozen.

If a new recurring asset gets added to the script mid-production (rare), build its lock entry the same way before generating any shot featuring it.

## Anti-pattern: re-describing the asset each shot

❌ Shot 4 prompt: "the wipe sweeps in"
❌ Shot 5 prompt: "the wipe is held by the hand"
❌ Shot 6 prompt: "a plain white wipe descends"

✓ Every shot prompt pastes the same `description_for_prompts` paragraph verbatim AND passes the same `media_id` as an image ref. The model gets the same input every time → it draws the same wipe every time.
