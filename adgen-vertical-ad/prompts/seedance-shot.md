# seedance-shot prompt template

Used in Phase 5 of the adgen-vertical-ad pipeline for every video clip generation.

## ⚠ HARD RULE — NEVER GENERATE MUSIC IN SEEDANCE

**Every seedance prompt MUST explicitly say `NO MUSIC.`** No exceptions.

Reason: music is added in FCP at Phase 6 from a single suno-generated bed that
plays continuously under the spot, ducks for VO beats, and fades on the end
card. If seedance bakes per-clip music into the video, those clips become
unusable for FCP assembly — every cut would have a different music bed colliding
with the suno score, and we can't strip the music without also losing ambient
SFX.

The auto-generated music seedance produces is also stylistically wrong (often
generic cinematic strings, dramatic swells) and breaks the deadpan claymation
register every adgen brand wants.

**The hard rule in practice:**
- Every prompt ends with (or includes prominently): `NO MUSIC. NO MUSICAL SCORE. NO INSTRUMENTAL BACKING.`
- Ambient SFX (wind, footsteps, dust howl, kitchen tick, fluorescent buzz) are FINE — those are diegetic and useful.
- If you discover after the fact that a delivered clip has music baked in, that clip must be regenerated, NOT just muted in FCP (muting also kills the ambient SFX track).

## ⚠ HARD RULE — IP-SAFE VOCAB IS BAKED IN HERE (construct clean, don't scrub later)

Seedance's `ip_detected` filter blocks jobs (credits charged, no cancel, no refund) when studio /
film / iconic-imagery vocabulary STACKS. The fix is PROACTIVE: build the seedance prompt from
physical descriptions using the table below, so the banned vocab never enters the prompt. Do NOT
write a studio-named prompt and then try to remove it.

**Gemini image prompts are EXEMPT** — you MAY name "Aardman / Laika stop-motion style" in a Gemini
Nano Banana image prompt (no ip_detected filter there, and it helps). The ban is ONLY on the
seedance VIDEO prompt. When you adapt a Gemini start-frame prompt into a seedance prompt, TRANSLATE
the style language as a deliberate step:

| NEVER write in a seedance prompt | Write this instead |
|---|---|
| Aardman / Pixar / Laika / Ghibli / DreamWorks style | "hand-thumbed plasticine clay surface with visible fingerprint impressions and slight frame-to-frame judder" (claymation) |
| "the claymation [Character]" / restating identity | "the clay character from the start frame" / "the figure from the reference image" (start_image carries identity) |
| Dust Bowl / sepia dramatic plain | "open parched plain" / "dim brown-tan plain" |
| Grapes of Wrath / Of Mice and Men / Yellowstone | (drop entirely — describe the scene physically) |
| cowboy hat | wide-brim hat / brimmed hat |
| old-Western drawl | deep slow drawl |
| plaid flannel | checked shirt |
| bandana | neckerchief |
| prairie | open field |
| Sam Elliott / John Dutton / "Most Interesting Man" / Sheriff Woody | (drop — describe the person physically) |

**Decision rule:** describe ACTION + ENVIRONMENT physically. Identity is carried by the start_image
and the contact-sheet ref, NOT by naming a studio or character. The brand NAME spoken in audio is
safe (tested clean) — the trigger is text-prompt vocabulary stacking, not audio content.

**Final tripwire:** before EVERY `generate_video`, pipe the prompt through
`scripts/lint_seedance_prompt.sh`. It blocks on banned vocab, music language, and a missing NO-MUSIC
clause. It's a net for slips — the mechanism is constructing clean from this table.

## Reason through the dimensions first

Before writing, run the shot through `reference/scene-dimensions.md` — the generalized shot grammar. Carry dimensions 1–9 from the approved start-frame, then deliberately set the **video-only layer**: camera move, action-over-time, duration, audio (+ `NO MUSIC`), scene stability, IP-safe translation, lip-sync. Anything you leave blank, seedance fills with its default.

## The structure

Every seedance video prompt should contain these elements, in roughly this order:

1. **Style declaration** — claymation / pixar / etc, kept identical across the whole ad
2. **Camera + composition** — the visual move (push-in, dolly-around, crash zoom, wide pan)
3. **Setting** — environment, lighting, time of day, mood
4. **Character action** — what the character does, with consistent character description
5. **VOICE prompt** — `AUDIO:` section with the EXACT voice description string for that character (verbatim across shots) plus the dialogue line in single quotes
6. **Background SFX notes** — ambient/diegetic SFX only (wind, footsteps, kitchen tick, dust howl). NEVER music.
7. **Anti-instructions** — what the model should NOT do. ALWAYS include `NO MUSIC. NO MUSICAL SCORE. NO INSTRUMENTAL BACKING.` Also typically: NO other voices, NO captions, NO logos in frame.

## Template

```
[Style declaration]. [Camera move + composition]. [Setting + lighting + mood].

[Character description — same wording every shot for the same character], [character action / what's happening]. [Camera detail — push-in, dolly speed, etc.].

AUDIO: [Voice description — VERBATIM across all shots for this character] says [emotional state]: '[exact dialogue line]'. Background: [ambient + SFX]. [Music: yes/no]. [Anti-instructions: NO other voices, etc.].
```

## Filled example (hero intro shot)

The examples below use an invented claymation mascot (Suds, a kitchen-sponge sheriff) to show the shape of a good prompt. Swap in your own characters.

```
Claymation stop-motion shot. Slow subtle camera push-in toward character. A kitchen counter at dawn, a tall pile of dirty dishes in the background, warm soft window light, calm before-the-storm atmosphere.

The sponge sheriff character (a yellow kitchen sponge with a green scrubber top, squinting eyes, gray walrus mustache, tiny tan cowboy hat, tin star) speaks directly to camera with quiet confidence, his mustache moves as he talks, he tips his hat.

AUDIO: Dry, steady, small-town sheriff voice with a slow drawl says clearly: 'Name's Suds. This here sink stays clean on my watch.' Background: faint dripping tap, distant birdsong through the window, a lone harmonica-like whistle of wind. NO music. Calm, steady atmosphere.
```

## Filled example (performance shot with external audio ref)

When passing external audio (Suno, ElevenLabs), DON'T include the lyrics in the prompt — the audio carries them. Describe only the visual performance and energy:

```
Music-video shot, claymation stop-motion aesthetic. Low-angle hero shot, slow push-in, then dolly-around the character. The bottom of a dark kitchen sink lit like a stage, a single dramatic spotlight from above.

The grease villain character (a glossy amber-brown blob with heavy-lidded eyes, a crown of burnt crumbs, a cape of gray dishwater) sings to camera, lip-syncing precisely to the provided audio track. His body sways with the melody, mouth wide on the long notes, theatrical and smug.

[Background details — stacked dirty pans as a backdrop, a dripping tap as a metronome, etc.]
```

## Filled example (action shot)

```
Claymation stop-motion shot. Camera locked, slight ominous push-in. The kitchen sink at night, cold blue light from the window, murky water filling the basin.

The sponge sheriff character (yellow sponge, green scrubber top, gray walrus mustache, tiny tan cowboy hat, wide frightened eyes) is pinned against the side of the basin as glossy tendrils of grease rise from the drain and wrap around him. His hat falls off and floats away. He strains against the tendrils.

AUDIO: Dry, steady, small-town sheriff voice (the same Suds voice as other shots), straining: 'Not... my... sink!' His voice cracks into a shout as he is pulled under. Background SFX: gurgling drain, squelching grease, a low ominous hum. NO music. NO other voices.
```

## Filled example (product hero / CTA shot)

```
Cinematic product hero shot, claymation stop-motion aesthetic. Slow elegant camera push-in toward the dish-soap bottle (exactly as in the start frame), standing on the edge of a clean, gleaming sink. Subtle gentle motion: a few soap bubbles drift upward, soft morning window light, very slight tilt-shift miniature feel.

AUDIO: The same dry, steady, small-town sheriff voice (Suds character voice from other shots) with a confident closing tone says clearly: '[Brand name]. Clean plates, kind hands.' Background: very soft kitchen ambient, a single sustained warm guitar note. Closing CTA atmosphere — confident, conclusive. Pronounce the brand name clearly.
```

## Voice description registry (use these EXACT strings)

For consistency across shots, use these exact voice descriptions:

| Character | Exact voice description |
|---|---|
| Suds (example: sponge sheriff) | "dry, steady, small-town sheriff voice with a slow drawl" |
| Grease Baron (example: singing villain) | (uses external Suno audio — no native voice) |
| Cold corporate narrator (rarely used) | "cold corporate male narrator with detached voice" |

When you add a new character, define their voice description ONCE in `reference/voice-consistency.md` and use that exact string verbatim in every prompt.

## Anti-instructions to include

When you want a specific behavior, also state what you DON'T want:

- "NO music" — when you want only ambient, no soundtrack
- "NO other voices, only [Character]'s voice" — when only one character should speak
- "NO captions, NO text overlay" — those are added in FCP, not generated
- "NO logo overlay" — for shots where the brand should appear naturally only

## NSFW sanitization checklist

Before sending the prompt, scan for and replace:

- "bombs", "weapons", "war", "kill" → reword
- "cut down", "stab", "wound" → reword
- "pumped full of", "drugged", "needle" (drug context) → reword
- Brand names that may trigger trademark issues → use generic alternatives or remove

See `reference/PITFALLS.md` for the full trigger word list and proven replacements.

## Generation params (defaults)

```python
mcp.generate_video(params={
    "model": "seedance_2_0",
    "prompt": "<the structured prompt above>",
    "aspect_ratio": "9:16",
    "duration": 5,           # 4-15 sec range; match to dialogue length + breath
    "mode": "fast",          # always fast for vertical 720p output
    "resolution": "720p",
    "medias": [
        {"role": "start_image", "value": "<scene_start_frame_job_id>"},
        # Add character contact sheet as identity lock:
        {"role": "image", "value": "<character_sheet_job_id>"},
        # DEFAULT for any speaking character (Strategy B): pass this shot's CONTIGUOUS
        # 11L voice segment so seedance lip-syncs the mouth to the locked voice. When you
        # pass audio, DON'T also write the dialogue in the prompt — the audio carries it;
        # describe only the visual performance + mouth movement.
        {"role": "audio", "value": "<11L_segment_media_id>"}
        # Omit audio ONLY for Strategy A (no spoken voice / cheap throwaway cut).
    ],
})
```

## Quality checklist before generating

```
[ ] Style declaration matches every other shot in this ad
[ ] Camera move is specific (not generic "camera moves around")
[ ] Setting + lighting fit the spot's mood arc
[ ] Character described in full, with same wording as other shots
[ ] Voice description string matches the registry exactly
[ ] Dialogue line is in single quotes, complete, with proper punctuation
[ ] Background SFX / music explicitly stated
[ ] Anti-instructions included for unwanted elements
[ ] NSFW trigger words scanned and replaced
[ ] Duration is 4-15 sec
[ ] Start frame and contact sheet refs queued
```
