# ffmpeg cookbook

Every ffmpeg command pattern the adgen-vertical-ad pipeline uses, with comments. Copy-paste ready.

## Pre-flight

Always probe before and after operations to verify expected behavior:

```bash
# Get duration, codec, resolution
ffprobe -v error -show_entries stream=codec_type,codec_name,duration,width,height -of default=noprint_wrappers=1 input.mp4

# Get format-level info (file duration, size, bitrate)
ffprobe -v error -show_entries format=duration,size,bit_rate -of default=noprint_wrappers=1 input.mp4

# Quick duration only
ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 input.mp4
```

## Concatenation

### Concat clips with audio (linear stringout — DEFAULT for deliverables)

For N clips, use the concat filter:

```bash
ffmpeg -y \
  -i shot_01.mp4 -i shot_02.mp4 -i shot_03.mp4 -i shot_04.mp4 -i shot_05.mp4 -i shot_06.mp4 \
  -filter_complex "[0:v][0:a][1:v][1:a][2:v][2:a][3:v][3:a][4:v][4:a][5:v][5:a]concat=n=6:v=1:a=1[v][a]" \
  -map "[v]" -map "[a]" \
  -c:v libx264 -preset medium -crf 19 -pix_fmt yuv420p \
  -c:a aac -b:a 192k \
  stringout.mp4
```

Adjust `n=N` to match clip count. The pattern `[i:v][i:a]` repeats per clip.

**Hard cuts only.** No crossfades. This is the deliverable the operator edits in FCP.

### Concat WITHOUT audio (visuals-only stringout)

```bash
ffmpeg -y \
  -i shot_01.mp4 -i shot_02.mp4 ... \
  -filter_complex "[0:v][1:v]...concat=n=N:v=1[v]" \
  -map "[v]" \
  -c:v libx264 -preset medium -crf 19 \
  visuals_only.mp4
```

### Concat WITH crossfades (NOT for default deliverable — only when explicitly needed)

```bash
ffmpeg -y \
  -i a.mp4 -i b.mp4 -i c.mp4 \
  -filter_complex "\
    [0:v][1:v][2:v]concat=n=3:v=1[vraw]; \
    [vraw]trim=duration=DURATION,setpts=PTS-STARTPTS[v]; \
    [0:a][1:a]acrossfade=d=0.25:c1=tri:c2=tri[a01]; \
    [a01][2:a]acrossfade=d=0.25:c1=tri:c2=tri[a]" \
  -map "[v]" -map "[a]" \
  -c:v libx264 -preset medium -crf 19 -pix_fmt yuv420p \
  -c:a aac -b:a 192k \
  output.mp4
```

Each acrossfade subtracts its duration from total audio length. After N crossfades of duration D each, audio = sum(clip_durations) - N*D. Trim video to match by setting DURATION = sum_of_durations - N*D.

## Speed up / slow down

### Speed up audio (preserve pitch)

```bash
ffmpeg -y -i input.mp3 -filter:a "atempo=1.5" -codec:a libmp3lame -b:a 192k faster.mp3
```

`atempo` native range: 0.5-2.0. Chain for higher: `atempo=2.0,atempo=1.5` = 3.0x.

**Cap at 1.5x for music/dialogue.** Above that, audio sounds rushed even with pitch preservation.

### Speed up video (in sync with audio)

```bash
ffmpeg -y -i input.mp4 \
  -filter_complex "[0:v]setpts=PTS/1.5[v];[0:a]atempo=1.5[a]" \
  -map "[v]" -map "[a]" \
  -c:v libx264 -preset fast -crf 19 -c:a aac -b:a 192k \
  faster.mp4
```

`setpts=PTS/N` speeds video by factor N (e.g., 1.5 = 1.5x).

## Trim

### Trim from a start time for a duration

```bash
ffmpeg -y -i input.mp4 -ss <start_sec> -t <duration_sec> -c copy output.mp4
```

`-c copy` is fast (no re-encode) but only cuts on keyframes. For frame-accurate cuts:

```bash
ffmpeg -y -ss <start_sec> -i input.mp4 -t <duration_sec> -c:v libx264 -c:a aac output.mp4
```

(Note: `-ss` BEFORE `-i` is faster; AFTER `-i` is more accurate.)

### Trim front of clip

```bash
ffmpeg -y -ss 0.5 -i input.mp4 -c copy trimmed.mp4
```

⚠ Avoid trimming clips with baked-in lip sync — it shifts mouth movements out of phase with words. Regenerate the clip instead.

## Audio extraction / replacement

### Extract audio from video

```bash
ffmpeg -y -i video.mp4 -vn -acodec libmp3lame -b:a 192k audio.mp3
```

### Strip audio from video

```bash
ffmpeg -y -i video.mp4 -an -c:v copy silent.mp4
```

### Replace audio in video

```bash
ffmpeg -y -i video.mp4 -i new_audio.mp3 \
  -map 0:v -map 1:a \
  -c:v copy -c:a aac -b:a 192k -shortest \
  output.mp4
```

`-shortest` trims to whichever stream ends first. Use when audio and video lengths differ.

### Mix two audio tracks

```bash
ffmpeg -y -i voice.mp3 -i music.mp3 \
  -filter_complex "[0:a]volume=1.0[v];[1:a]volume=0.3[m];[v][m]amix=inputs=2:duration=longest[a]" \
  -map "[a]" \
  -c:a libmp3lame -b:a 192k \
  mixed.mp3
```

## Ken-burns over a still image (for static + product / food / logo shots)

This is the alternative to seedance for static shots, AND the PREFERRED path for label-heavy
product hero shots (seedance warps typography and packaging geometry — see PITFALLS "product/label
shots warp in seedance"). Free, fast, controllable, and the locked 4K product composite keeps
perfect text.

### Centered slow zoom-in (the DEFAULT — product stays centered, never drifts off-frame)

```bash
# duration + fps drive d. Seedance outputs 24fps → match it (see PITFALLS fps-mismatch).
DUR=5; FPS=24; FRAMES=$((DUR*FPS))

ffmpeg -y -loop 1 -framerate $FPS -i product_hero.png \
  -vf "scale=2160:3840:force_original_aspect_ratio=increase,crop=2160:3840,\
zoompan=z='min(zoom+0.0006,1.08)':d=$FRAMES:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':fps=$FPS:s=720x1280,\
format=yuv420p" \
  -t $DUR \
  -c:v libx264 -preset medium -crf 19 -pix_fmt yuv420p \
  ken_burns.mp4
```

Why this version (the old one cropped into a CORNER and pushed the product off-screen):

- **`scale=2160:3840` (a 3× intermediate) + `crop=2160:3840`** — scaling to a large canvas first
  makes zoompan's per-frame x/y rounding sub-pixel at the 720×1280 output, which kills the
  jitter/corner-drift. `force_original_aspect_ratio=increase` then `crop` fills 9:16 with the
  product centered (no letterbox). The old recipe scaled to a tiny 1080×1920, so integer x/y
  rounding accumulated and the frame walked toward a corner.
- **`x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'`** — dead-center zoom. Combined with a product
  composite that's framed centered (the Phase 4 product hero has the product centered with clean
  negative space top/bottom), the product sits in the middle the entire time and never leaves frame.
- **`z='min(zoom+0.0006,1.08)'`** — reaches only ~1.08 (8% zoom) over the whole clip. SLOW enough
  to be almost imperceptible — a gentle push-in, not a lunge. Bump to `+0.001 / 1.12` only if you
  want it slightly more noticeable. The old `+0.0015 / 1.3` was a fast 30% lunge.
- **`fps=$FPS` inside zoompan + `-framerate $FPS` on input** — locks output framerate to match
  the seedance clips (24fps) so the concat doesn't trigger a runaway re-encode.

**The product must be centered IN THE STILL.** If the product composite is off-center, a centered
zoom pushes toward the image center, not the product. Frame product hero composites centered at
Phase 4 (the template already does this).

### Centered slow pan + zoom (only when a drift is explicitly wanted)

Keep the pan tiny so the product never exits the safe area. `sin()` amplitude is in source pixels
(here ±60 of a 2160-wide canvas ≈ ±2% of output width — barely perceptible):

```bash
DUR=6; FPS=24; FRAMES=$((DUR*FPS))
ffmpeg -y -loop 1 -framerate $FPS -i still.png \
  -vf "scale=2160:3840:force_original_aspect_ratio=increase,crop=2160:3840,\
zoompan=z='min(zoom+0.0006,1.08)':d=$FRAMES:x='iw/2-(iw/zoom/2)+sin(on/$FRAMES*3.14)*60':y='ih/2-(ih/zoom/2)':fps=$FPS:s=720x1280,\
format=yuv420p" \
  -t $DUR \
  -c:v libx264 -preset medium -crf 19 -pix_fmt yuv420p \
  pan_zoom.mp4
```

### Add audio to a ken-burns video (e.g., overlay an ElevenLabs VO)

```bash
# 1. Generate the ken-burns silent
ffmpeg -y -loop 1 -i still.png ... -an silent.mp4

# 2. Overlay audio
ffmpeg -y -i silent.mp4 -i vo.mp3 \
  -map 0:v -map 1:a \
  -c:v copy -c:a aac -b:a 192k -shortest \
  product_shot.mp4
```

## Format conversion

### Convert .mov to .mp4 (mostly metadata, fast)

```bash
ffmpeg -y -i input.mov -c copy output.mp4
```

If audio is mp3 inside mov (common with .mov containers carrying audio only):

```bash
ffmpeg -y -i input.mov -codec:a libmp3lame -b:a 192k output.mp3
```

### Convert .HEIC iPhone screenshots to .png

```bash
sips -s format png input.HEIC --out output.png
```

(`sips` is built-in macOS, not ffmpeg.)

## Whisper transcription (for finding lyric timestamps)

For pre-cutting audio at lyric / bar boundaries, transcribe with whisper to get word-level timestamps:

```bash
# One-time install if missing
pip3 install --quiet --user openai-whisper

# Run with word timestamps
whisper input.mp3 \
  --model base \
  --language en \
  --word_timestamps True \
  --output_format json \
  --output_dir /tmp
```

Parse the JSON for word-level timing:

```python
import json
d = json.load(open('/tmp/input.json'))
for s in d['segments']:
    if 'words' in s:
        for w in s['words']:
            print(f"{w['start']:6.2f}s  {w['word']}")
```

Use the timing to find silent gaps between bars (good cut points) or precise word starts (for sync editing).

## Verification recipes

### Anomaly detection — scene change detection (catch stray frames)

```bash
ffmpeg -i video.mp4 -vf "select='gt(scene,0.3)',showinfo" -f null - 2>&1 | grep showinfo
```

Reports timestamps where scene change > 30% (likely a cut). Compare against intended cut times. Unexpected hits = stray frame or internal jump cut.

### Stuck / duplicate frame detection

```bash
ffmpeg -i video.mp4 -vf "freezedetect" -f null - 2>&1 | grep freeze
```

### Contact sheet (visual sweep)

```bash
mkdir -p /tmp/watchback
ffmpeg -y -i video.mp4 -vf "fps=2,scale=240:-1,tile=10x999" /tmp/watchback/sheet.jpg
```

Tune fps (1-4) and tile width to keep result <3MB and ≤2000px in either dimension. Read the resulting jpg with the Read tool. Scan for orientation flips, caption regressions, jump cuts, missing content.

## libx264 dimension rule

Widths and heights MUST be divisible by 2 or libx264 rejects with error. For vertical 9:16 use 720x1280 (not 720x1281). For 4:5 use 1080x1350 (not 900x1125).

## Encoding presets

For quality vs speed tradeoff:

- `-preset ultrafast`: fastest, largest file
- `-preset fast`: balanced for iterations
- `-preset medium`: balanced for deliverables (default)
- `-preset slow`: smaller files, longer encode
- `-preset veryslow`: smallest files, much longer

Use `medium` for deliverables. `fast` for iteration.

## CRF (quality)

`-crf 19` is high quality (visually lossless for most sources)
`-crf 23` is default (good quality)
`-crf 28` is lower quality but smaller files

Use 19 for deliverables, 23 for iterations.

## Pixel format

Always set `-pix_fmt yuv420p` for compatibility (FCP, web players, mobile). Without it, some sources produce videos that don't play in Safari / iOS / FCP.

## Common ffmpeg errors

| Error | Cause | Fix |
|---|---|---|
| "height not divisible by 2" | libx264 rejecting odd dimensions | Use even dimensions (720, 1080, 1280, 1920) |
| "Invalid argument" on `-shortest` with concat filter | filter_complex doesn't always honor -shortest | Use explicit trim filter to set duration |
| "Stream specifier ':a' in filtergraph matches no streams" | Trying to map audio from a clip that has no audio | Check input with ffprobe first; only map audio if it exists |
| "Could not write header for output file" | Output codec not compatible with output container | Match codec to container (.mp4 + libx264/aac, .webm + libvpx/libopus) |

## Pipeline-specific helpers

### Linear stringout helper

Wrap the concat command in a script for reuse:

```bash
# scripts/stringout.sh
#!/bin/bash
# Usage: ./stringout.sh shot_01.mp4 shot_02.mp4 ... output.mp4

OUTPUT="${@: -1}"
INPUTS=("${@:1:$#-1}")
N="${#INPUTS[@]}"

INPUT_ARGS=""
FILTER=""
for i in $(seq 0 $((N-1))); do
  INPUT_ARGS+=" -i ${INPUTS[$i]}"
  FILTER+="[${i}:v][${i}:a]"
done
FILTER+="concat=n=${N}:v=1:a=1[v][a]"

ffmpeg -y $INPUT_ARGS \
  -filter_complex "$FILTER" \
  -map "[v]" -map "[a]" \
  -c:v libx264 -preset medium -crf 19 -pix_fmt yuv420p \
  -c:a aac -b:a 192k \
  "$OUTPUT"
```
