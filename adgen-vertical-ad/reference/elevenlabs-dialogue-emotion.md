# ElevenLabs Dialogue + Emotion — MANDATORY application rules (adgen)

**This is not optional background. It is a PRE-FLIGHT CHECKLIST. Any time you generate ANY ElevenLabs
audio in the adgen pipeline — character dialogue, narrator VO, the CTA line — you MUST apply the rules
below before you fire the call.** Researched against ElevenLabs official docs (eleven_v3,
public alpha). Sources at the bottom.

The two capabilities this doc unlocks, both of which past sessions were NOT using:
1. **Text to Dialogue** — a native multi-speaker endpoint. One call → two (or more) characters trade
   lines as a single, conversationally-aware audio (reactions, timing, interruptions modeled). Use this
   for any shot where characters talk to each other. Do NOT glue separate single-voice TTS clips together.
2. **Audio tags** — bracketed stage directions (`[nervous]`, `[sighs]`, `[whispers]`, `[strong Brooklyn
   accent]`) that make v3 deliver like a voice actor instead of a flat reader. Every line gets tagged.

---

## RULE 1 — Multi-character shot → Text to Dialogue (never concat single-voice clips)

If 2+ characters speak in a shot (or trade lines across a shot), generate the whole exchange in ONE
`text-to-dialogue` call. It models conversational flow — a character's line reacts to the previous one —
which concatenated single-voice TTS cannot do.

```
POST https://api.elevenlabs.io/v1/text-to-dialogue
?output_format=mp3_44100_128
{
  "inputs": [
    { "voice_id": "<fern_id>",  "text": "[nervous] aw c'mon... Spike, my leaves are DROOPING again." },
    { "voice_id": "<spike_id>", "text": "[deadpan][tired] The drooping?" },
    { "voice_id": "<fern_id>",  "text": "[exasperated] The soil. It's bone dry again." }
  ],
  "model_id": "eleven_v3",
  "settings": { "stability": 0.4, "similarity_boost": 0.75, "style": 0.12, "use_speaker_boost": true },
  "seed": 777,
  "apply_text_normalization": "auto"
}
```

- Limits: **≤10 unique voice_ids per request; ≤2000 characters total** across all `inputs`. A 15s shot
  is well under both. If a spot exceeds 2000 chars, split by SHOT (each shot = one dialogue call), which
  you want anyway for the contiguous-per-shot-segment method in `audio-pipeline.md`.
- **Use the `/v1/text-to-dialogue/with-timestamps` variant** when you need to cut the audio per-shot or
  per-speaker, or build captions: it returns `voice_segments[]` with `{voice_id, start_time_seconds,
  end_time_seconds, dialogue_input_index}` — exact boundaries, no whisper guessing.
- Single-speaker shots (one character, or a solo narrator beat) → ordinary `text-to-speech/{voice_id}`
  is fine. Still tag every line (Rule 2).
- Turns are SEQUENTIAL, not overlapping. `[interrupting]` / `[overlapping]` change delivery feel; they do
  not produce true simultaneous audio.

This composes with the contiguous-per-shot-segment method: generate ONE dialogue call PER SHOT (Fern +
Spike trading lines within that shot) → that per-shot audio is the `role: audio` ref for that shot's
seedance clip → concat. Voice stays locked; each clip lip-syncs to exactly its own audio.

---

## RULE 2 — Every single line gets emotion/delivery tags (voice-actor direction)

**Never submit a flat, untagged line.** v3 reads untagged text like a bored narrator. Each line carries
at least one tag matched to that character's emotional beat in that shot — pull the beat straight from
the character bible's `emotional_range` (e.g. Fern `panicked`, Spike `deadpan`).

Tags are inline `[tag]` in the `text` field (v3 only). Categorized, exact syntax:

- **Emotions:** `[happy]` `[excited]` `[sad]` `[angry]` `[nervous]` `[anxious]` `[curious]` `[frustrated]`
  `[exasperated]` `[tired]` `[awe]` `[calm]` `[impressed]` `[mischievously]` `[sternly]` `[dismissive]`
  `[sarcastically]` `[dramatically]` `[matter-of-fact]` `[deadpan]` `[cheerfully]`
- **Non-verbal reactions:** `[laughs]` `[laughs softly]` `[sighs]` `[sighs softly]` `[groans]`
  `[clears throat]` `[gulps]` `[gasps]` `[crying]` `[exhales]`
- **Delivery / pacing:** `[whispers]` `[shouting]` `[speaking softly]` `[pause]` `[long pause]` `[rushed]`
  `[drawn out]` `[stammers]` `[hesitates]` `[dramatic tone]`
- **Conversational dynamics (dialogue endpoint):** `[interrupting]` `[overlapping]`
- **Accents / character:** `[New York accent]` `[strong Brooklyn accent]` `[Southern US accent]`
  `[British accent]` ... + character voices (`[evil scientist voice]`, `[childlike tone]`, etc.)
- **SFX (use sparingly — we add SFX in FCP):** `[gunshot]` `[applause]` `[door creaks]`

The official tag list is non-exhaustive — v3 responds to many natural-language descriptors. Experiment,
but start from the list above.

**How to tag like a director, not a vandal:**
- Place the tag immediately before the words it governs: `[whispers] ...what's that light?`
- Layer for nuance: `[nervous][whispers]`, `[tired][deadpan]`, `[frustrated] [sighs]`.
- Surround the tag with emotionally-consistent text — `[excited] we're bouncin'!` lands; `[excited]
  please hold` fights the voice and fails.
- **Punctuation IS delivery:** ellipses `...` = weight/pause; ALL-CAPS word = emphasis (`TRENCH FOOT!`);
  a mid-line dash `like this—` = cut-off/interruption.
- Minimum viable length: at least a couple of sentences of context per call; single bare words read
  inconsistently. (Per-shot dialogue calls satisfy this naturally.)
- **Match tag to base-voice capability.** Tags are stage directions, not magic — a calm voice won't
  convincingly `[shouting]`. Cast a voice that can already do the register, then tag it.

---

## RULE 3 — Voice settings for expressive ad VO (lock these)

```
model_id:          "eleven_v3"          # ALWAYS v3 — only v3 honors audio tags
stability:         0.40                  # Creative range (0.35–0.45). Lower = more emotional variance.
similarity_boost:  0.75
style:             0.12                  # 0.0–0.15; nudge to 0.2 only if emotion is underpowered (adds latency)
use_speaker_boost: true
```

- **NEVER use Robust / high-stability (>0.6) for tagged ad VO** — Robust mode is near-deterministic but
  largely IGNORES audio tags. It's for IVR/corporate narration only. Our spots are character-driven →
  Creative range, always.
- v3 is nondeterministic: **generate 2–3 takes and pick the best.** Budget for it. Don't fire once and ship.
- Use Instant-Voice-Clone (IVC) or library voices. **Professional Voice Clones (PVC) are NOT yet
  optimized for v3 — they may read tags aloud instead of performing them.** Avoid PVC for tagged work.

---

## RULE 4 — Keep a character's voice IDENTICAL across shots

Lock all of these per character, for every shot in the spot (and ideally the whole brand):
- Same `voice_id` (obviously) + same `voice_settings` (any change shifts timbre).
- Fixed `seed` per character (best-effort determinism; not guaranteed, but helps).
- `previous_request_ids` (array, **max 3**) — pass the `request_id`(s) of this character's prior
  generations so the model has real prior-audio context. Stronger than text alone. **Store every
  `request_id`** as you go.
- `previous_text` / `next_text` — pass the neighbouring lines so prosody flows across the cut.

There is no hard "voice lock" — v3's expressiveness means some shot-to-shot variation is inherent. The
levers above minimize it; regenerate-and-select closes the rest.

---

## RULE 5 — Accents

- Syntax: `[strong <region> accent]` (e.g. `[strong Brooklyn accent]`, `[New York accent]`). `[strong X
  accent]` beats bare `[X accent]`.
- **Voice-dependent and experimental.** A neutral base voice pushed by an accent tag alone is unreliable
  for production. The reliable path: cast a voice that ALREADY carries some of the region's cadence, then
  reinforce with the tag. If a hard accent is brand-critical and no library voice fits, flag it to the operator
  (option: source/clone an accented voice) rather than shipping a weak generic-pushed-via-tag take.

---

## RULE 6 — Pacing: do NOT over-pause, and budget the duration

Audio tags and punctuation that add *weight* compound badly with slow/deadpan/authoritative voices and make narration DRAG. This bit a past comedy spot: a British-deadpan narrator with `[pause]` tags + `...` ellipses between every sentence read at ~40s total against a 30s target; one 4-sentence product-feature line ran 19s alone.

- **Default to NO `[pause]` between sentences, and no `...` ellipses, in narrator/VO lines.** A plain period is already a beat. Reserve `[pause]` / `...` for a single deliberate comedic hold, not as connective tissue between every sentence.
- **Slower voices need FEWER pause cues, not more.** Deadpan / authoritative / older-male voices already read slow; pause tags stack on top. Cast-appropriate tags only.
- **Budget duration up front and MEASURE it.** Know each line's target seconds from the breakdown. After generating, `ffprobe -show_entries format=duration` every clip and compare to target. Sum the narrator track against the spot's total target.
- **If a line runs long, the fix order is: (1) remove pause/ellipsis cues, (2) tighten punctuation, (3) TRIM WORDS.** De-gapping alone won't save a genuinely word-heavy line — a 4-feature product drop has to lose features or words to hit ~10s. Measure after each fix.
- **Word-count rule of thumb:** a deadpan English VO lands ~2–2.3 words/sec *with* tight punctuation. So a 10s feature line ≈ 22 words MAX. Count before you generate.

## PRE-FLIGHT CHECKLIST — must pass before EVERY ElevenLabs generation

- [ ] Multi-character shot → **Text to Dialogue** (one call, `inputs[]`), not concatenated TTS.
- [ ] **Every line has ≥1 audio tag** matched to that character's emotional beat for the shot (from the bible's `emotional_range`).
- [ ] `model_id: eleven_v3`, `stability 0.35–0.45`, `style 0.1–0.15`, `use_speaker_boost: true`. NOT Robust.
- [ ] Voice **locked per character** across all shots: same voice_id + settings + seed; pass `previous_request_ids` (≤3) for continuity; store each `request_id`.
- [ ] Generated **2–3 takes**, listened, picked the best (v3 is nondeterministic).
- [ ] Accent needed → `[strong X accent]` AND a base voice that already has the cadence (else flag to the operator).
- [ ] Punctuation used as delivery (`...` pauses, CAPS emphasis, `—` cut-offs).
- [ ] **Pacing (Rule 6):** no `[pause]`/`...` connective tissue between sentences; duration `ffprobe`-measured against the breakdown target; long lines trimmed (≈2 words/sec deadpan → ~22 words per 10s).

---

## Code (lib/elevenlabs.py)

- `ElevenLabs().tts(voice_name, text, out_path, ...)` — single voice (v3, tags supported).
- `ElevenLabs().dialogue(turns, out_path, ...)` — **multi-speaker.** `turns` = list of
  `{"voice": <name|id>, "text": "[tag] line"}`; renders one unified conversational audio via
  `/v1/text-to-dialogue`. Use for any 2+ character shot. Returns `{path, request_id, ...}`; capture
  `request_id` for Rule-4 continuity.

Both default to `eleven_v3` + the Rule-3 expressive settings. Don't hand-roll raw requests when the lib
covers it.

---

## Sources (ElevenLabs official)
- Text to Dialogue: https://elevenlabs.io/docs/api-reference/text-to-dialogue/convert · /convert-with-timestamps · https://elevenlabs.io/docs/overview/capabilities/text-to-dialogue
- Text to Speech: https://elevenlabs.io/docs/api-reference/text-to-speech/convert
- Audio tags: https://elevenlabs.io/blog/v3-audiotags · https://elevenlabs.io/blog/eleven-v3-character-direction · https://elevenlabs.io/blog/eleven-v3-audio-tags-emulating-accents-with-precision
- Best practices: https://elevenlabs.io/docs/overview/capabilities/text-to-speech/best-practices
- Voice settings: https://elevenlabs.io/docs/api-reference/voices/settings/get
