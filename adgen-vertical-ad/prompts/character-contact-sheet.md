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
- What it does NOT have (e.g., "no legs, no fingers — just the sponge body with stubby arms")]

STYLE:
[Aesthetic — claymation, stop-motion, pixar 3D, hand-drawn 2D, photorealistic, etc.
Reference works if helpful: "Aardman / Wallace and Gromit warmth", "Pixar Cars / Ratatouille polish", "Lego minifigure", etc.
Texture details: "visible thumbprint imperfections", "glossy plastic surface", "matte hand-carved wood", etc.
Color mood: "warm amber and golden", "cool industrial gray", "saturated playful neon"]

CHARACTER SHEET LAYOUT (single image, neutral [color] background):
- TOP ROW: Front view, 3/4 left view, side profile, 3/4 right view, back view (all 5 full-body, evenly spaced, same scale)
- MIDDLE ROW: 5 head close-ups showing different EXPRESSIONS — [list 5 expressions relevant to the character's emotional range, e.g., "calm/wise, warmly smiling, surprised, scared/wide-eyed, sad/melancholy"]
- BOTTOM ROW: 3 detail studies — [list 3 distinguishing details to study close-up, e.g., "close-up of mustache and hat", "close-up of the sponge's pore texture", "detail of the badge"]

All in the [style] aesthetic, consistent [light type] lighting, neutral [color] background.

Aspect ratio: 16:9 horizontal. High detail, character-sheet quality.
```

## Example — Suds (an invented sponge-sheriff protagonist, for illustration only)

```
Generate a character reference sheet for an animated character.

CHARACTER: Suds — an anthropomorphized kitchen sponge who acts as the sheriff of the sink. He is the protagonist of a stop-motion animated short. He is a steady, squinting, quietly brave small-town lawman.

PHYSICAL DESIGN:
- A rectangular yellow kitchen sponge (palm-sized), with a dark green scrubber layer on top that reads like a flat-top haircut
- A face on the front of the sponge: narrow squinting eyes, thick brown eyebrows, a small determined mouth
- A neat gray WALRUS MUSTACHE
- A tiny tan COWBOY HAT, slightly too small, tilted forward
- A small tin SHERIFF'S STAR pinned to the front
- Two short stubby clay arms, NO legs, NO fingers

STYLE:
- Plasticine stop-motion claymation, visible thumbprint imperfections, hand-sculpted texture
- Warm morning palette: butter yellow, sage green, soft tan
- Small-town western feel, but at kitchen-counter scale

CHARACTER SHEET LAYOUT (single image, neutral cream background):
- TOP ROW: Front view, 3/4 left view, side profile, 3/4 right view, back view (all 5 full-body, evenly spaced, same scale)
- MIDDLE ROW: 5 head close-ups showing different EXPRESSIONS — calm squint, half smile, surprised, scared/wide-eyed, determined glare
- BOTTOM ROW: 3 detail studies — close-up of the mustache and hat brim, close-up of the sponge pore texture, close-up of the sheriff's star

All in the claymation style, consistent soft warm lighting, neutral cream background.

Aspect ratio: 16:9 horizontal. High detail, character-sheet quality.
```

## Example — the Grease Baron (an invented antagonist)

For evolved/related characters (a corrupted twin, an older self, a villain built from the hero's world), ALSO pass the original character image as `role: image` ref so the lineage is preserved and the two read as belonging to the same world.

```
Generate a character reference sheet for an animated character.

CHARACTER: The Grease Baron — a blob of congealed cooking grease that rules the bottom of the sink. He is a pompous, theatrical villain who sings a slow power ballad about every pan he has ruined.

PHYSICAL DESIGN:
- A rounded, slumping BLOB of glossy amber-brown grease, about twice the height of Suds (see reference image for scale and world)
- Small heavy-lidded eyes and a wide, smug mouth
- A lopsided CROWN made of burnt crumbs and a bent bottle cap
- A dribbling CAPE of gray dishwater draped behind him
- Bits of old food suspended inside the translucent body
- NO arms, NO legs — he oozes

STYLE:
- Same claymation world as Suds (visual continuity), but GLOSSY, wet-looking and slightly translucent
- Colder, murkier palette: amber-brown, olive, dishwater gray
- Theatrical villain energy, more pantomime than horror

CHARACTER SHEET LAYOUT (single image, neutral cool gray background):
- TOP ROW: Front view, 3/4 left view, side profile, 3/4 right view, back view (all 5 full-body, evenly spaced)
- MIDDLE ROW: 5 head close-ups — smug default, mid-song with mouth wide open, outraged, wobbling in fear, dissolving
- BOTTOM ROW: 3 detail studies — close-up of the crumb crown, close-up of the food bits inside the body, close-up of the dishwater cape

All in the glossy claymation style, consistent flat kitchen lighting, neutral cool gray background.

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
