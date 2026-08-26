# Audio pipeline reference

The single biggest source of wasted credits and iteration loops in past ad sessions. Read carefully.

> **COMPANION DOC — READ + APPLY `reference/elevenlabs-dialogue-emotion.md` for the HOW of every 11L
> call.** This file (audio-pipeline.md) governs the ARCHITECTURE (which strategy, contiguous segments,
> drift avoidance). That file governs the GENERATION CRAFT and is a MANDATORY pre-flight: **Text to
> Dialogue** for any 2+ character shot (not concatenated clips), an **audio tag on every line**,
> expressive v3 settings, voice+seed lock. Both apply to every talking spot.

## DEFAULT = ElevenLabs voice, lip-synced inside seedance (verified 2026-06-04)

**For any character that SPEAKS, default to ElevenLabs voice lip-synced inside seedance via
`role: audio`.** This is verified-true behavior: seedance_2_0 accepts an external audio ref and
lip-syncs the character's mouth to it TIGHT within a clip (see `higgsfield-models.md` "Lip sync"
+ the live `generate_video` schema: "seedance_2_0 accepts audio via medias"). This is Strategy B
below.

Why this is the default now (it used to be the exception):
- **Voice is locked everywhere.** A cloned/chosen 11L voice is identical within a clip, across
  clips, and across ADS. Seedance native audio drifts per-clip (the #1 past complaint) — a mascot
  sounded different shot-to-shot. 11L kills that.
- **Exact pronunciation + cadence + emotion** — brand names, technical terms, the CTA line all
  land exactly, every time. No re-firing seedance to fix "glyphosate" gibberish.
- **Lip-sync works** — seedance moves the mouth to the provided audio, so it doesn't look dubbed.

This replaces the old "11L is forbidden / 11L only for narrator spots" rule. The old fear was
cross-clip drift from overlaying a continuous track on per-clip-synced visuals — that failure mode
is REAL but is avoided by the contiguous-segment method (below), not by avoiding 11L.

### The one rule that makes 11L safe: contiguous per-shot segments

Drift happens ONLY when you overlay one continuous track on top of independently-synced clips.
Don't do that. Instead:

1. Write/generate the FULL 11L voice track for the spot first (one voice, locked).
2. Cut it into **contiguous, non-overlapping** per-shot segments at clean word/breath gaps
   (whisper word-timestamps → cut at silences; each segment ≥4s for seedance's minimum).
3. Generate each seedance clip with `role: audio` → its own segment + the shot's start frame.
   Each clip lip-syncs to its own segment.
4. Concat clips with their (now-correct) baked audio. Because the segments were contiguous, the
   assembled audio is continuous AND every clip's lip-sync was locked to exactly the audio it plays.
5. Do NOT also overlay the full track in post — it's already there, per-clip.

## Decision tree — run this at Phase 2 (before any generation)

Forced by the breakdown.md `In-scene dialogue` / `Narrator VO` columns:

```
Does any character SPEAK on screen (in-scene dialogue OR carried narrator)?
│
├── Yes  → STRATEGY B (DEFAULT) — ElevenLabs voice, lip-synced in seedance via role:audio
│        Pick/clone ONE locked voice per character. Generate the full 11L track, cut into
│        contiguous per-shot segments, lip-sync each clip to its segment, concat. Voice is
│        locked within-clip, across-clips, and across-ads.
│        Use for: ~every spot with talking characters — mascots, testimonials, pharma parody,
│        dialogue spots. This is now the norm, not the exception.
│
└── No spoken voice (pure visual + music + SFX)  → STRATEGY A — seedance native / no voice track
         No dialogue to lock. Let seedance carry ambient + SFX (or go silent), add a Suno music
         bed in FCP. Also fine as a deliberate CHEAP/THROWAWAY path for a quick test cut where
         cross-ad voice consistency doesn't matter yet.
```

**Escape hatch (Strategy A for a talking spot):** only when the operator explicitly wants the fast/cheap
seedance-native take (skip the 11L setup) and accepts that the voice will drift between clips and
won't match the next ad. Even then, use IDENTICAL voice-description prompt language for a character
in every shot. Default is still B.

**Past mistake (the coffee brand "ask your abuelo," May 2026):** defaulted to seedance-native because it
was the cheap default and the old rule discouraged 11L. The spot needed locked voice (couplabeers
structure, 8 narrator beats). Took v1 → v2 → v3 and ~200 wasted credits to pivot. With 11L-as-
default, v1 would have shipped clean.

## The fundamental rule

**Pick ONE voice SOURCE per character and lock it for the whole spot (and ideally the whole brand).**
Don't use 11L for a character in shot 1 and seedance-native for the same character in shot 4 — that
swaps timbre mid-spot. One source per voice, locked.

The drift trap to never repeat: per-clip-synced visuals + a SEPARATE continuous overlay track that
wasn't the thing each clip was synced to. Use the contiguous-segment method above and this can't
happen. Past sessions burned 4+ stitch iterations on this exact mistake.

## The two valid strategies

### Strategy A — Per-clip native audio (default)

Each video clip generated with seedance native audio enabled (default). Voice + ambient + SFX baked into each clip. In assembly, concat clips with their audio intact.

**Pros:**
- Voice feels alive and varied per shot (each clip's audio is generated fresh)
- Lip sync is locked WITHIN each clip
- No mixing complexity in post

**Cons:**
- Voice consistency drifts subtly across clips (different generation each time)
- Tiny audio discontinuities at cut points (different ambient per clip)
- Can't easily separate voice from ambient in post

**When to use:** spots with NO spoken voice (pure visual + music + SFX), or a deliberate
cheap/throwaway test cut. NOT the default for talking spots anymore — Strategy B (11L lip-sync) is.

**If you do use it for a talking spot (escape hatch only):** use IDENTICAL prompt language for the same character in every shot. Example: every Berto shot includes "warm gravelly old-timey highland farmer voice" word-for-word. Variation in description = variation in voice. Accept that the voice still drifts clip-to-clip and won't match the next ad — that's exactly why B is the default.

### Strategy B — Continuous external audio + visuals lip-synced to it

External audio (Suno music, ElevenLabs VO, full continuous track) is the master. Each video clip is generated with `role: audio` ref pointing to the relevant audio segment. In assembly, concat the visuals; the audio plays continuously.

**Pros:**
- Locked voice / music throughout (no per-clip drift)
- Specific lyrics / cadence preserved (rap, jingle, brand voice clone)
- Lip sync precise to known audio

**Cons:**
- More setup (chunk audio, upload each segment, track UUIDs)
- If concatenating multiple clips, drift can accumulate at cut boundaries
- Tight coupling between audio cuts and video cuts

**When to use:** the DEFAULT for any talking spot — mascots, testimonials, pharma parody, dialogue. Also music videos / rap shots with specific lyrics (Suno track as the audio ref). Anytime voice/lyrics/cadence must stay locked.

## The drift problem (the mistake we made)

If you generate 5 video clips each lip-synced to its own audio segment, then OVERLAY a continuous audio track over the concatenated visuals:

- Each clip's lip sync was timed for its specific audio segment
- The overlaid continuous track has slightly different timing
- By clip 3 or 4, lips are visibly off the words

**This is irreversible once the clips are generated.** Trimming visuals doesn't fix it (lip movements are locked in the clip).

**The fix is upstream, not downstream.** Decide the audio strategy BEFORE generating clips.

## Audio for music videos / rap shots — the right way

When the spot has a music section:

1. **Generate or source the full audio track first** (Suno, ElevenLabs, hand-recorded — doesn't matter, must be the FINAL audio).

2. **Transcribe with timestamps** to find lyric boundaries:
   ```bash
   whisper input.mp3 --model base --language en --word_timestamps True --output_format json --output_dir /tmp
   ```
   The JSON has per-word start times. Use those to find clean cut points (silent gaps between bars).

3. **Pre-cut audio per shot** at exact bar boundaries:
   ```bash
   ffmpeg -y -i full.mp3 -ss 0 -t 5.0 -codec:a libmp3lame -b:a 192k segment_1.mp3
   ffmpeg -y -i full.mp3 -ss 5.0 -t 5.0 -codec:a libmp3lame -b:a 192k segment_2.mp3
   ```
   Make sure each segment is ≥4 sec (seedance minimum). Avoid overlapping segments — that creates drift in concat.

4. **Upload each segment** to Higgsfield as `role: audio`, get the media_id.

5. **Generate each video clip** with the corresponding audio segment as ref + the appropriate start frame.

6. **Concat the clips with their native audio intact.** Each clip already has the right audio segment baked in. Total assembly audio is continuous because the segments were contiguous (no gaps, no overlaps).

7. **Do NOT overlay the original full track.** It's already there in the per-clip audio.

## ffmpeg recipes for audio

### Trim a section
```bash
ffmpeg -y -i input.mp3 -ss <start_sec> -t <duration_sec> -codec:a libmp3lame -b:a 192k output.mp3
```

### Speed up audio (preserve pitch)
```bash
ffmpeg -y -i input.mp3 -filter:a "atempo=1.5" -codec:a libmp3lame -b:a 192k faster.mp3
```
**Cap at 1.5x for music/dialogue.** Above that, audio sounds rushed even though pitch is preserved. atempo's native range is 0.5-2.0; chain for higher (`atempo=2.0,atempo=1.5` for 3x).

### Replace audio in a video
```bash
ffmpeg -y -i video.mp4 -i new_audio.mp3 -map 0:v -map 1:a -c:v copy -c:a aac -b:a 192k -shortest output.mp4
```

### Strip audio from video
```bash
ffmpeg -y -i video.mp4 -an -c:v copy silent.mp4
```

### Extract audio from video
```bash
ffmpeg -y -i video.mp4 -vn -acodec libmp3lame -b:a 192k audio.mp3
```

### Concat clips with audio crossfades (only when explicitly needed — usually NOT)
```bash
ffmpeg -y \
  -i a.mp4 -i b.mp4 -i c.mp4 \
  -filter_complex "\
    [0:v][1:v][2:v]concat=n=3:v=1[v]; \
    [0:a][1:a]acrossfade=d=0.25:c1=tri:c2=tri[a01]; \
    [a01][2:a]acrossfade=d=0.25:c1=tri:c2=tri[a]" \
  -map "[v]" -map "[a]" \
  -c:v libx264 -c:a aac \
  output.mp4
```
Note: each crossfade subtracts from total duration. After N crossfades, audio is shorter than video by `N * crossfade_duration`. Trim video to match or accept silent tail.

**For the linear stringout deliverable: NO crossfades.** Hard cuts only.

## Higgsfield audio upload pattern

```python
# 1. Request presigned URL
result = mcp.media_upload(filename="audio.mp3", content_type="audio/mpeg")
media_id = result["uploads"][0]["media_id"]
upload_url = result["uploads"][0]["upload_url"]

# 2. PUT the file
curl -X PUT -H "Content-Type: audio/mpeg" --data-binary @audio.mp3 "<upload_url>"

# 3. Confirm
mcp.media_confirm(type="audio", media_id=media_id)

# 4. Use media_id in seedance call as role: audio
mcp.generate_video(params={
    "model": "seedance_2_0",
    "medias": [
        {"role": "start_image", "value": "<image_job_id>"},
        {"role": "audio", "value": media_id}
    ],
    ...
})
```

## ElevenLabs integration

Already wired in `$ADGEN_HOME/lib/elevenlabs.py`. API key in `$ADGEN_HOME/.env`.

```bash
cd $ADGEN_HOME && export $(grep -v '^#' .env | xargs)
python3 -c "
import sys
sys.path.insert(0, '$ADGEN_HOME')
from lib.elevenlabs import ElevenLabs
from pathlib import Path

el = ElevenLabs()
result = el.tts(
    voice_name='<name from RECOMMENDED_VOICES dict>',
    text='[warm] [slow] Your line here.',
    out_path=Path('/path/to/output.mp3'),
    stability=0.4,
    style=0.6,
)
"
```

For voice IDs not in the lib's hardcoded dict (e.g., custom voices the operator specifies), call the API directly with the voice_id:

```python
import os, requests
voice_id = "<id>"
r = requests.post(
    f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
    headers={"xi-api-key": os.environ["ELEVENLABS_API_KEY"], "Accept": "audio/mpeg"},
    json={
        "text": "...",
        "model_id": "eleven_v3",
        "voice_settings": {"stability": 0.35, "similarity_boost": 0.75, "style": 0.7, "use_speaker_boost": True},
    },
)
out_path.write_bytes(r.content)
```

ElevenLabs v3 supports inline emotional tags: `[warm]`, `[slow]`, `[whisper]`, `[urgent]`, `[excited]`, `[disgusted]`, `[sigh]`. Use them.

## Audio length matching

When overlaying ElevenLabs VO onto a video clip:

1. Generate VO at natural pace (don't cram it).
2. Measure VO duration with ffprobe.
3. If VO is longer than video clip:
   - **Preferred:** speed VO up with `atempo` (cap 1.5x)
   - **If VO is much longer:** rewrite the line shorter, OR extend the video clip duration
4. If VO is shorter than video clip: leave silence at end (often natural — beat after CTA).

## Audio formats

- **MP3:** for VO, music, general audio. 192kbps via `libmp3lame -b:a 192k` is the standard.
- **AAC:** for video audio tracks (in mp4 containers). Use `-c:a aac -b:a 192k` when muxing.
- **WAV:** when needed for highest quality (rare for our pipeline).

Higgsfield audio uploads accept `audio/mpeg` content type for both .mp3 and .mov-with-mp3-inside files. For .mov audio extraction:

```bash
ffmpeg -y -i input.mov -codec:a libmp3lame -b:a 192k output.mp3
```

## Common audio mistakes (don't repeat)

- ❌ Generating 5 clips with audio refs, then overlaying full track on top → DRIFT
- ❌ Trimming a clip to "fix" sync → makes it worse, lip movements lock to original timing
- ❌ Speeding audio past 1.5x → sounds rushed even with pitch preservation
- ❌ Not pre-cutting audio at silent gaps → cut clicks audible at boundaries
- ❌ Using ElevenLabs library voices for brand work → sounds stock
- ❌ Mixing seedance native audio in some clips and overlaid VO in others → inconsistent voice quality across the spot

## When in doubt

If a character speaks → Strategy B (11L voice, lip-synced in seedance, contiguous segments). It's
the default because it locks the voice within-clip, across-clips, and across-ads. Only drop to
Strategy A when there's no spoken voice at all, or the operator explicitly wants a fast/cheap throwaway
cut and accepts the voice drift.
