# Asset lock spec

Template for locking the visual appearance of recurring on-screen assets across an ad's shots. Built once at Phase 1-3, frozen by Phase 4.

## Why

Generative video models invent new versions of objects every shot unless given a strong reference. A small dropper bottle drifted across 5+ versions in one session (spray bottle, pump bottle, clear vial, glass jar) because there was no locked visual spec.

A per-project asset lock pins each recurring asset to a single visual spec, with a contact sheet media ID that gets referenced in every shot's prompt.

## File location

`$ADGEN_HOME/<brand>/concepts/<slug>/refs/asset-lock.yml` — concept-level (each concept locks its own asset appearances). If an asset is a promoted brand mascot, its lock entry can also live in `brand/characters/<name>/asset-lock.yml` and be referenced from the concept.

Built at Phase 3 alongside character bibles. One entry per recurring asset.

## Schema

```yaml
brand: <brand-name>
assets:
  - name: <short-key, e.g., "dropper", "bottle", "pack">
    role: <one-line, e.g., "the hero product that resolves the spot">
    appears_in_shots: [4, 5, 6]   # which shot numbers feature it

    visual_lock:
      type: <packaging | bare-product | both>
      material: <e.g., "small amber glass bottle with a black rubber-bulb dropper cap">
      color: <e.g., "warm amber glass, black cap, plain cream label band">
      surface: <e.g., "glossy glass, soft highlight on the shoulder">
      size: <e.g., "about 3 inches tall">
      forbidden_appearances:
        - <e.g., "clear or blue glass">
        - <e.g., "spray nozzle or pump top">
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
      Example: "a small amber glass dropper bottle, about the height of a thumb, with
      a black rubber-bulb dropper cap and a plain cream label band. NOT a spray
      bottle, NOT a pump, NOT clear glass. Same amber color, same cap, same label
      band in every shot."
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

❌ Shot 4 prompt: "the bottle slides in"
❌ Shot 5 prompt: "the dropper is held by the hand"
❌ Shot 6 prompt: "a small brown bottle descends"

✓ Every shot prompt pastes the same `description_for_prompts` paragraph verbatim AND passes the same `media_id` as an image ref. The model gets the same input every time → it draws the same bottle every time.
