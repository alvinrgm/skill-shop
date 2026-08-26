# Asset audit reference

The hard rule that prevented us from re-burning credits on the burlap-bag mistake.

## Two phases of asset work

1. **Phase 1 audit** — what brand assets ALREADY EXIST (covered below). Run this first.
2. **Phase 3 sheet generation** — generate locked reference sheets for every recurring on-screen asset. Two sheet types:
   - **Character contact sheets** (per character) — see `SKILL.md` Phase 3 + `prompts/character-contact-sheet.md`
   - **Product contact sheets** (per product/recurring physical asset) — see `prompts/product-contact-sheet.md`

Both sheet types get uploaded to Higgsfield and passed into every shot prompt where that asset appears. Without locked sheets, the asset's appearance drifts across shots (wipe becomes cloth, bottle changes label, character changes face).

**Pet-wipes learning:** the wipe appeared in 3 shots and drifted every gen (cotton cloth, lavender pattern, off-white, paper towel). A product contact sheet at Phase 3 would have locked it once. ~100 credits in re-fires could have been avoided.

## The Phase 1 audit rule

**Before generating ANY brand-related asset, audit the brand folder for existing assets.**

Brand-related includes: logo, product images, packaging, hero shots, lifestyle photography, mascot characters, brand fonts, color palettes, prior ad campaigns.

## Folder structure this audit assumes

This audit runs against the two-level layout defined in `SKILL.md` ("Folder structure — the two-level law"):

```
$ADGEN_HOME/<brand>/
├── brand/            # brand-global kit — audit this for existing assets
└── concepts/<slug>/  # per-concept generated work — skim for reusable refs (locked characters, product composites)
```

Phase 0 (folder bootstrap) should already have created `brand/` and `concepts/`. This audit covers Phase 1's "what already exists" question.

## Audit procedure (run at Phase 1 of every ad)

```bash
BRAND="<brand-name>"
BRAND_DIR="$ADGEN_HOME/${BRAND}"

# 1. Does the brand folder exist, and is it migrated?
if [ ! -d "$BRAND_DIR" ]; then
  echo "FRESH BRAND — no folder yet. Phase 0 will create it:"
  echo "  mkdir -p $BRAND_DIR/brand/{product-images,reference-photos,refs/scraped} $BRAND_DIR/concepts"
elif [ ! -d "$BRAND_DIR/brand" ] && [ ! -d "$BRAND_DIR/concepts" ]; then
  echo "LEGACY FLAT FOLDER — brand kit and concept work are interleaved at the root."
  echo "STOP. Migrate to brand/ + concepts/<slug>/ before adding a new concept (see SKILL.md Phase 0)."
  ls -la "$BRAND_DIR"
else
  # 2. List the brand kit + concepts
  echo "=== brand-global kit (brand/) ==="
  ls -la "$BRAND_DIR/brand" 2>/dev/null
  echo "=== existing concepts (concepts/) ==="
  ls -la "$BRAND_DIR/concepts" 2>/dev/null

  # 3. Hunt for brand-global assets (should live under brand/)
  echo "=== logo files ==="
  find "$BRAND_DIR/brand" -iname "*logo*" -o -iname "*mark*" 2>/dev/null

  echo "=== product images ==="
  find "$BRAND_DIR/brand" -path '*product*' -type f 2>/dev/null
  find "$BRAND_DIR/brand" -iname "*hero*" -type f 2>/dev/null

  echo "=== brand bible / docs ==="
  find "$BRAND_DIR/brand" -iname "bible.md" -o -iname "brand*.md" -o -iname "voice*.md" 2>/dev/null

  echo "=== moodboard / references ==="
  find "$BRAND_DIR/brand" -path '*moodboard*' -type f 2>/dev/null
  find "$BRAND_DIR/brand" -path '*ref*' -type f 2>/dev/null

  echo "=== fonts ==="
  find "$BRAND_DIR/brand" -name "*.ttf" -o -name "*.otf" -o -name "font*" 2>/dev/null

  # 4. Reusable refs from prior concepts (candidates for the character-promotion rule)
  echo "=== prior ads / videos (concepts/) ==="
  find "$BRAND_DIR/concepts" -name "*.mp4" -o -name "*.mov" 2>/dev/null
  echo "=== locked characters from prior concepts ==="
  find "$BRAND_DIR/concepts" -path '*refs/characters*' -type f 2>/dev/null
  echo "=== promoted brand mascots (brand/characters/) ==="
  find "$BRAND_DIR/brand/characters" -type f 2>/dev/null

  # 5. Prior briefs (global pipeline briefs dir — separate from the brand folder)
  echo "=== prior briefs ==="
  find "$ADGEN_HOME/briefs" -iname "${BRAND}*.json" 2>/dev/null
fi
```

Run this. Read the output. THEN write the brief.

## Surfacing the audit to the operator

Don't just dump the file list. Synthesize:

```
=== Asset audit for <brand> ===

HAVE:
✓ Logo: refs/logo.png (PNG, transparent bg)
✓ Product hero: product images/heirloom_roast_front.png (front of bag, clean shot)
✓ Product back: product images/heirloom_roast_back.png
✓ Moodboard: 9 reference shots in moodboard/ (kitchens, brew bars, pour-overs)
✓ Brand bible: bible.md (voice + positioning notes)
✓ Prior ad: brand_spot_9x16.mp4 (previous spot for reference)

MISSING (will need to generate):
✗ Bean character refs (no character in existing assets — generative shot)
✗ 1968 lab setting (generative)
✗ Modern hybridized bean character (generative)
✗ Composed product hero in farmhouse setting (use existing product image as ref)

PROPOSAL:
- Use existing logo + product images directly. No re-creation.
- Generate the 3 missing assets (~30-50 credits each).

Greenlight to proceed?
```

## Hard rules

❌ **Never invent a generic version of an asset that already exists in the brand folder.**

Examples of what this means in practice:

| Wrong | Right |
|---|---|
| Generate a fake burlap bag with the brand logo printed on it | Use the existing product hero image (`heirloom_roast_front.png`) as a `role: image` ref to nano_banana_2 to compose it in a scene |
| Recreate the brand logo in a stylized way | Use the existing logo PNG. Pass it as image ref, reference it in prompt as "the brand logo from the reference image" |
| Generate a synthetic product photo | Use the existing product photo |
| Make up brand colors | Read them from the brand bible or the existing logo |

❌ **Never skip the audit because "this is a new brand"** — even on a brand new brand, check the folder. Sometimes the operator has already started something there.

❌ **Never assume an asset is too low-quality to use.** A real product photo at 1080p beats a generated synthetic product photo at 4k for trust + brand consistency.

✓ **Always cite the audit results in the brief.** The operator needs to verify you actually checked.

✓ **Always offer to use existing assets as references for new compositions.** Don't generate from scratch when you can extend.

✓ **Always download newly-scraped PDP images to `brand/refs/scraped/`** (brand-global — reusable by every concept) so they exist on disk and the next session can find them.

## When the audit is incomplete

Sometimes the brand folder has assets that aren't where you'd expect — especially on a brand whose folder predates the two-level law, or one the operator populated by hand:

- Logo might be in `brand/`, `refs/`, `assets/`, `branding/`, root, or anywhere
- Product images might be in `brand/product-images/`, `product images/` (with space), `products/`, `images/`, or named like `IMG_8085.HEIC`
- Brand bible might be `brand/bible.md`, `bible.md`, `brand.md`, `voice.md`, `BRAND.md`

If you find brand-global assets loose at the brand root (not yet under `brand/`), that's a sign the folder hasn't been migrated — flag it and fold them into `brand/` as part of Phase 0 migration.

**Cast a wide net:** the find commands above use multiple naming patterns. If you don't find something obvious, try grep:

```bash
grep -r -l "<brand-name>" "$BRAND_DIR" 2>/dev/null | head
```

If you genuinely can't find an asset that should exist, ASK operator: "Couldn't find a logo file in the brand folder. Do you have one to drop in, or should I generate?" Don't silently invent.

## .HEIC files

Apple iPhone screenshots often save as `.HEIC` instead of `.PNG`. They're images but most tools can't read them directly. Convert with sips:

```bash
sips -s format png input.HEIC --out output.png
```

If you see `.HEIC` files in the brand folder, convert before using.

## When the audit reveals conflicts

If you find:
- Two different versions of the logo (old + new)
- Multiple product image variants
- Conflicting brand voice docs

ASK: "Found two logo files: `logo_v1.png` and `logo_v2_new.png`. Which is current?" Don't pick.

## Asset versioning convention

When generating new assets that will be reused across ads, name them with a version stamp (paths are concept-relative — `concepts/<slug>/refs/...`):

```
refs/characters/berto_v1.png    # First generation
refs/characters/berto_v2.png    # After the operator's revision
refs/characters/berto_v2_sheet.png  # Contact sheet for v2
```

Don't overwrite. Old versions are useful for A/B comparison and rollback. If a character gets reused in a later concept, promote the locked version to `brand/characters/<name>/` per the character-promotion rule.

## Hand-off context

When you finish an ad and the brand folder gains new generated assets, leave a note in `$ADGEN_HOME/<brand>/brand/asset_inventory.md` — the inventory is brand-global, indexing both the shared kit and what each concept generated:

```markdown
# <brand> asset inventory

## Brand-global kit (brand/ — provided by the operator / brand, or promoted)
- brand/logo.png — primary logo
- brand/product-images/heirloom_roast_front.png — flagship product hero, front
- brand/product-images/heirloom_roast_back.png — flagship product hero, back
- brand/characters/berto/ — promoted brand mascot (sheet + bible), reused across concepts

## Per-concept generated assets
### concepts/2026-04-acme-ad/
- refs/characters/berto_v2.png — Berto hero ref (1890s bean farmer character)
- refs/characters/berto_v2_sheet.png — Berto 3x3 contact sheet
- refs/characters/instant_bean_v1.png — Hybridized instant bean (rapper antagonist)
- refs/environments/1968_lab.png — Mid-century laboratory abduction setting
- refs/environments/plantation_field.png — Industrial coffee plantation
- refs/scenes/shot_01_field_intro.png — Berto in golden coffee farm hillside at sunrise
- refs/scenes/shot_06_bag_hero.png — the coffee brand bag in farmhouse kitchen

### Voice IDs used
- Berto: seedance native, prompt "warm gravelly old-timey highland farmer voice"
- Instant bean rapper: external Suno track (audio file in audio/bean_rap_full.mp3)

## Last updated: <iso date>
```

This gives the next ad project a head-start. If a new ad for the brand needs the Berto character, the next session can REUSE `berto_v2_sheet.png` instead of regenerating.
