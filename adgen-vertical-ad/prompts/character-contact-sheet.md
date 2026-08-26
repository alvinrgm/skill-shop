# Character contact sheet prompt template

Used in Phase 3 of the adgen-vertical-ad pipeline to generate a 3x3 grid identity reference for each named character.

## Why we do this

Seedance lacks a persistent character ID. Every video gen freshly interprets the character. To keep identity consistent across shots, pass a contact sheet as `role: image` with every video gen for that character.

The contact sheet shows the character from multiple angles + expressions + detail studies, giving seedance a complete visual map to anchor on.

## Template

Replace bracketed sections per character.

```
Generate a character reference sheet for an animated character.

CHARACTER: [Character name] — [one-line description of what they are and their narrative role].

PHYSICAL DESIGN:
[Detailed visual description — every distinguishing feature. Include:
- Body type / proportions
- Color palette
- Distinguishing features (hat, mustache, glasses, accessories, props)
- Texture (claymation/pixar/2D/realistic)
- Any branded elements (uniform, logo placement)
- What it does NOT have (e.g., "no body, no arms, no legs — just the coffee plant with a face")]

STYLE:
[Aesthetic — claymation, stop-motion, pixar 3D, hand-drawn 2D, photorealistic, etc.
Reference works if helpful: "Aardman / Wallace and Gromit warmth", "Pixar Cars / Ratatouille polish", "Lego minifigure", etc.
Texture details: "visible thumbprint imperfections", "glossy plastic surface", "matte hand-carved wood", etc.
Color mood: "warm amber and golden", "cool industrial gray", "saturated playful neon"]

CHARACTER SHEET LAYOUT (single image, neutral [color] background):
- TOP ROW: Front view, 3/4 left view, side profile, 3/4 right view, back view (all 5 full-body, evenly spaced, same scale)
- MIDDLE ROW: 5 head close-ups showing different EXPRESSIONS — [list 5 expressions relevant to the character's emotional range, e.g., "calm/wise, warmly smiling, surprised, scared/wide-eyed, sad/melancholy"]
- BOTTOM ROW: 3 detail studies — [list 3 distinguishing details to study close-up, e.g., "close-up of mustache and hat", "close-up of the bean's surface crease", "detail of suspenders"]

All in the [style] aesthetic, consistent [light type] lighting, neutral [color] background.

Aspect ratio: 16:9 horizontal. High detail, character-sheet quality.
```

## Example — Berto (the wholesome bean farmer protagonist)

```
Generate a character reference sheet for an animated character.

CHARACTER: Berto — an anthropomorphized heirloom coffee plant from the 1890s. He is the protagonist of a stop-motion animated short. He is a wholesome, warm, slightly weathered highland farmer character.

PHYSICAL DESIGN:
- A single tall heirloom coffee plant (4-5 feet, slender), topped by one oversized warm-brown coffee bean with detailed surface texture
- The oversized TOP BEAN has a face: kind crinkled eyes, weathered farmer features
- A bushy gray-brown HANDLEBAR MUSTACHE on the top bean
- A small WEATHERED BROWN STRAW HAT tilted slightly to one side, sitting on top of the bean
- NO body, NO arms, NO legs — just the plant with a face on the top bean

STYLE:
- Hand-carved wooden folk-art aesthetic, like a stop-motion claymation character (Aardman / Wallace and Gromit warmth, but more carved-wood than plasticine)
- Visible thumbprint imperfections, hand-sculpted texture
- Warm golden-amber color palette
- 1900-era Americana wholesome feel — like something a craftsman would whittle on a mountain farm porch

CHARACTER SHEET LAYOUT (single image, neutral cream background):
- TOP ROW: Front view, 3/4 left view, side profile, 3/4 right view, back view (all 5 full-body, evenly spaced, same scale)
- MIDDLE ROW: 5 head close-ups showing different EXPRESSIONS — calm/wise, warmly smiling, surprised, scared/wide-eyed, sad/melancholy
- BOTTOM ROW: 3 detail studies — close-up of the handlebar mustache, close-up of the straw hat, close-up of the bean's crease and surface texture

All in the hand-carved folk-art style, consistent soft warm lighting, neutral cream background.

Aspect ratio: 16:9 horizontal. High detail, character-sheet quality.
```

## Example — Instant Bean (the corrupted antagonist)

For evolved/related characters, ALSO pass the OG character image as `role: image` ref so the lineage is preserved (the modern version should look like a corruption of the original, not a different character).

```
Generate a character reference sheet for an animated character.

CHARACTER: The hybridized 2026 mutant version of Berto — what big-agriculture turned him into after experimenting on him in 1968. He is a tragic antagonist figure: the same bean character DNA, but corrupted by industrial breeding. He raps in deadpan autotune style, miserable but flexing on you.

PHYSICAL DESIGN:
- The SAME bean character DNA as Berto (see reference image), but transformed by industrial hybridization
- Now SHORT and SQUAT (half the height of original Berto — semi-dwarf, like yield-bred beans)
- The bean body is unnaturally BULBOUS, overgrown, almost obscene — bred for yield, way too dense and heavy for the stalk
- Texture is GLOSSY and PLASTIC-looking (lost the warm matte hand-carved quality of the original)
- VACANT, glazed, dead-inside eyes — soul drained out
- Mouth slightly open in a permanent deadpan rapper expression
- NO mustache, NO hat (those are gone)
- THICK GOLD CHAINS hanging around the thick stalk neck (multiple chains, layered, hip-hop style)
- Color: pale washed-out yellow, almost sickly — not the warm golden-amber of the original
- Slight slumped posture, like he's tired of being alive

STYLE:
- Same general hand-carved folk-art / stop-motion aesthetic as the original Berto character (visual continuity — they're family), but CORRUPTED — glossier, colder, more uncanny
- Industrial dystopian energy
- Aardman / Chicken Run claymation feel but darker and sadder

CHARACTER SHEET LAYOUT (single image, neutral cool gray background):
- TOP ROW: Front view, 3/4 left view, side profile, 3/4 right view, back view (all 5 full-body, showing the squat proportions, evenly spaced)
- MIDDLE ROW: 5 head close-ups — vacant deadpan default, autotuned rapping with mouth open, brief sad cracked expression, defeated/broken, hollow stare into camera
- BOTTOM ROW: 3 detail studies — close-up of the gold chains, close-up of the vacant eye, close-up of the bulbous bred-for-yield bean body

All in the corrupted hand-carved folk-art style, consistent flat industrial lighting, neutral cool gray background.

Aspect ratio: 16:9 horizontal. High detail, character-sheet quality.
```

## Generation params

Generate via the canonical Gemini path — **`scripts/gen_image.py`** (Nano Banana Pro), NEVER the Higgsfield MCP `generate_image` (that bills Higgsfield credits — image-gen HARD RULE). A contact sheet is a locked reference → **4K** (the default, per the 4K core-ref rule). Aspect `16:9` for the grid.

```bash
python3 ~/.claude/skills/adgen-vertical-ad/scripts/gen_image.py \
  --out <name>_sheet.png \
  --prompt-file <name>_sheet_prompt.txt \
  --aspect 16:9 --size 4K \
  --ref <original_character_front.png>   # evolved characters: pass the OG character ref to preserve lineage
```

## Storage

Save to `$ADGEN_HOME/<brand>/concepts/<slug>/refs/characters/<name>_sheet.png` (concept-level). If this character is a promoted brand mascot, save under `$ADGEN_HOME/<brand>/brand/characters/<name>/<name>_sheet.png` instead and reference it from each concept.

Use this filename convention:
- `<character>_hero.png` — single full-body hero ref (1k, 9:16, no grid)
- `<character>_sheet.png` — the 3x3 contact sheet (2k, 16:9)

## Using the contact sheet for video gen

For every seedance call featuring this character, pass the contact sheet as an additional image ref:

```python
mcp.generate_video(params={
    "model": "seedance_2_0",
    "prompt": "<shot prompt>",
    "medias": [
        {"role": "start_image", "value": "<scene_start_frame_job_id>"},
        {"role": "image", "value": "<contact_sheet_job_id>"},  # identity lock
        # optional audio:
        # {"role": "audio", "value": "<audio_media_id>"}
    ],
    ...
})
```

The contact sheet anchors the character's identity. Seedance uses it to keep features (mustache, hat, color, proportions) consistent shot to shot.

## When to regenerate the contact sheet

- Character design changes mid-project (the operator requests a different hat, color, expression range)
- Generated sheet has off-model elements that would propagate to video clips
- New ad in a series wants a slightly different mood for the same character

Don't regenerate "for fun" — once approved, the sheet is the authoritative identity reference. Stability across shots is the whole point.
