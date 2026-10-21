# Voice consistency reference

How to keep character voices consistent across shots in a generative ad pipeline.

## HARD RULE: 11L is the DEFAULT voice source — architect at Phase 2, never bolt on as a Phase-5 rescue

Seedance is verified to lip-sync to an external `role: audio` ref, so for ANY
speaking character an ElevenLabs voice lip-synced inside seedance is now the DEFAULT (Strategy B). A
locked 11L voice is identical within-clip, across-clips, and across ads — it kills seedance native
audio's per-clip timbre drift. Full method + decision tree in `audio-pipeline.md`.

### Part A — Architect the 11L voice UPFRONT at Phase 2 (the default)

For any spot where a character speaks: pick/clone ONE locked voice per character, generate the full
track, cut into CONTIGUOUS per-shot segments, lip-sync each clip to its segment, concat. Decide at
Phase 2 from the breakdown.md voice columns. Use the operator's house narrator voice from the registry
below (ask them to pick one on the first spot if the registry is empty).

This is now the norm for: brand mascots (locked across ad 1 and ad 50), pharma/testimonial narrators,
dialogue spots, music/rap (Suno track as the audio ref). Seedance native voice (Strategy A) is the
EXCEPTION — pure-visual spots, or a deliberate cheap/throwaway test cut.

### Part B — Never bolt 11L on as a mid-Phase-5 RESCUE for one bad clip

The one thing 11L is still NOT for: improvising a toolchain swap in the middle of Phase 5 to "fix"
a single clip's voice/pronunciation/lip-sync. That breaks continuity. RE-FIRE that seedance clip with
its locked audio segment instead. Architect the voice upfront; don't patch mid-production.

### The distinction in one line

11L as the planned voice ARCHITECTURE at Phase 2 = the default and correct. Improvising a toolchain
swap mid-Phase-5 to patch one clip = still wrong; re-fire instead.

## The core technique for the Strategy-A EXCEPTION: identical prompt language

(This section applies when you're deliberately using seedance NATIVE voice — the exception path, e.g.
a fast throwaway cut. When using the 11L default, the voice is locked by the audio ref, not by prompt
language, so this matters less. Emotion-delivery and pronunciation tips below still apply either way.)

**Seedance generates voice fresh for every clip.** It does not have a "voice ID" or persistent character voice. The voice each clip produces is determined by the prompt language describing that voice.

To keep a character's voice consistent across shots:
1. Write a precise voice description ONCE.
2. Use that EXACT description, word-for-word, in every shot's prompt that features that character.
3. Don't paraphrase. Don't shorten. Don't decorate. Same words every time.

## Voice description examples (battle-tested)

### Example protagonist: Suds (an invented sponge sheriff)
```
"dry, steady, small-town sheriff voice with a slow drawl"
```
Used word-for-word in every shot the character speaks in. Identical wording is what lets the voice land close enough each time to read as "the same guy".

### Example antagonist: the Grease Baron (an invented singing villain)
```
"rich, pompous theatrical baritone, slow power-ballad delivery"
```
Note: a sung part like this is best generated externally (Suno), then passed as an audio ref. Native seedance can approximate but Suno is more reliable for music genres.

### Cold corporate narrator (used once, then removed for narrative reasons)
```
"cold corporate male narrator with detached voice"
```

## Voice consistency anti-patterns

**Don't do this** (voice will drift):
- Shot 1 prompt: "steady sheriff voice"
- Shot 2 prompt: "old lawman with a drawl"
- Shot 3 prompt: "dry voice, friendly"

Each variation will produce a noticeably different voice. The audience will hear "different person" each time.

**Do this** (voice stays close):
- Shot 1 prompt: "dry, steady, small-town sheriff voice with a slow drawl"
- Shot 2 prompt: "dry, steady, small-town sheriff voice with a slow drawl"
- Shot 3 prompt: "dry, steady, small-town sheriff voice with a slow drawl"

## Three-voice cast rule

**Max 3 distinct voices per ad:**
1. **Protagonist** — the character who carries the spot. Should narrate everything they're present for.
2. **Antagonist** — the foil (a singing villain, a rival brand mascot, etc.). One voice. Used in their dedicated section.
3. **Special** — narrator, second character, brief cameo. One voice, one purpose.

**4+ voices feels muddy.** Audience can't track who's speaking. Adds cognitive load.

If the script has 4+ speakers, re-architect:
- Can the protagonist narrate something currently assigned to the "narrator"?
- Can two minor characters be merged into one role?
- Can the "special" voice be cut entirely?

## When to use seedance NATIVE voice (the Strategy-A exception)

11L lip-synced in seedance is the DEFAULT. Drop to seedance native voice only when:

1. **No character speaks at all** — pure visual + music + SFX. Nothing to lock.
2. **Deliberate cheap/throwaway cut** — a fast test where cross-ad voice consistency doesn't matter yet, and the operator accepts the per-clip drift.

Everything that used to be a "reason to escalate to 11L" is now just the default, handled at Phase 2:
- **Brand mascot voice locked across many ads** → 11L voice, lip-synced (identical ad #1 → ad #50).
- **Music / rap with specific lyrics** → Suno (or 11L) track as the audio ref.
- **Brand-critical pronunciation** → 11L nails it exactly; don't fight seedance TTS on brand names.
- **Specific actor / celebrity vibe** → 11L voice clones; seedance only does generic dialect.

## ElevenLabs voice registry (the operator's preferences)

Update this list as the operator specifies preferred voices. **Don't default to library voices** (Brian, Aria, Roger, etc.) — they sound stock.

| Voice name | Voice ID | Best for | Notes |
|---|---|---|---|
| _(your house narrator)_ | `<voice_id from your ElevenLabs Voices page>` | e.g. female VO, warm narrator | Ships empty. Add your picks here. |

(This registry starts empty and grows as new ads use new voices. Add an entry every time the operator specifies a voice. Voice ids are account-specific: a cloned or custom voice only works on the account that owns it.)

**Library voices (avoid for brand work):**
- Brian — too stock
- Aria, Roger, Sarah, Laura, Charlie, etc. — too widely used in other ads

## ElevenLabs settings that work for ad VO

```python
voice_settings = {
    "stability": 0.35,     # lower = more expressive/dynamic
    "similarity_boost": 0.75,
    "style": 0.7,          # higher = more stylistic variation (good for ads)
    "use_speaker_boost": True,
}
model_id = "eleven_v3"     # always use v3 — supports inline tags
```

Inline tags to include in the text:
- `[warm]`, `[gentle]`, `[whisper]`, `[urgent]`, `[excited]`, `[disgusted]`, `[sigh]`
- `[slow]` — useful for emphasizing key claims
- `[pause]` — for dramatic beats

Example:
```
"[warm] [slow] Cuts grease... rinses clean... and stays kind to your hands."
```

## Pronunciation tactics

When seedance or ElevenLabs mispronounces a word:

1. **Phonetic spelling in caps:** "PAH-lee-SOR-bate" instead of "polysorbate"
2. **Hyphenation:** "kih-NOO-ah" instead of "quinoa"
3. **Add stress markers in parens:** "Quinoa (KEEN-wah)"
4. **Substitute simpler word:** "no harsh additives" instead of "no polysorbate"
5. **Switch to ElevenLabs:** if it's a brand-critical word and substitution loses meaning

For BRAND NAMES that must be said correctly: always use ElevenLabs (or pre-recorded audio). Don't trust the model to nail "the brand's domain" — generate it externally and pass as audio ref.

## Voice character description framework

When designing a new character voice, describe these dimensions explicitly:

1. **Warmth:** warm / cool / neutral
2. **Texture:** smooth / gravelly / breathy / nasal
3. **Age implication:** young / middle-aged / old / ancient
4. **Era:** modern / old-timey / vintage / futuristic
5. **Region/dialect:** American midwest / British / Southern / generic American
6. **Pace:** fast / measured / slow
7. **Energy:** calm / animated / monotone / dramatic

Example (Suds, the invented sponge sheriff):
- Warmth: neutral
- Texture: dry
- Age: middle-aged
- Era: old-timey
- Region: small-town Western
- Pace: slow
- Energy: calm

Compose: "dry, steady, small-town sheriff voice with a slow drawl"

## The "same voice, different mood" trick

Seedance can vary the EMOTIONAL DELIVERY of the same character voice without changing the underlying voice. Just describe the emotional state separately:

- Shot 1 (calm): "Suds speaks steadily to camera with his slow drawl..."
- Shot 2 (scared): "Suds speaks with fear in his voice, his slow drawl cracking..."
- Shot 3 (angry): "Suds speaks with rising anger, his slow drawl getting harder..."

Voice description (the consistent part) is the same. Emotion (the variable part) is added separately. Result: same character, different mood, audience never confused about who's speaking.

## Voice diff testing

If the operator reports "the voice changed between shot X and shot Y":

1. ffprobe both clips, extract their audio:
   ```bash
   ffmpeg -i shot_X.mp4 -vn shot_X_audio.mp3
   ffmpeg -i shot_Y.mp4 -vn shot_Y_audio.mp3
   ```

2. Compare the prompt strings used for each. Look for:
   - Different voice description language (most common cause)
   - Different emotion descriptors (less critical, usually OK)
   - Different ambient/SFX descriptors (can affect voice timbre subtly)

3. If prompts were identical and voice still drifted — that's seedance's natural variation. Re-roll the offending shot.

4. If voice consistency matters MORE than alive/varied feel: switch that character to ElevenLabs voice clone.

## Hard rules

- ❌ Never paraphrase a character's voice description across shots
- ❌ Never use ElevenLabs library voices for brand work without the operator's explicit approval
- ❌ Never default to "warm narrator voice" — too generic, will produce inconsistent results
- ❌ Never have 4+ voices in one ad
- ✓ Always use the EXACT same voice description string for the same character in every shot
- ✓ Always log new voice IDs to this registry when the operator specifies one
- ✓ Always test pronunciation of brand-critical words with one cheap clip first
