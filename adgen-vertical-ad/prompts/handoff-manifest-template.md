# Handoff manifest template — FCP-ready deliverable folder

The handoff folder is the end-state deliverable: separate-tracks assets that the operator can drop into FCP and assemble. It's the equivalent of a film production's "rushes" or "selects + tracks" delivery to the editor.

## Why this exists

Plan the handoff folder at Phase 1 as the canonical deliverable. Don't build it reactively at Phase 7 after an auto-stringout gets rejected and the operator asks for stems.

The auto-stringout (a single mp4 with all clips concatenated and audio mixed by ffmpeg) is fragile. Auto-mix decisions about ducking, overlay timing, and ambient bed transitions cannot match what the operator would do in FCP with proper editing eyes/ears. The handoff folder bypasses the fragile auto-mix and gives the operator the raw parallel tracks.

## When to build

Build the handoff folder at every Phase 7 completion. Build it BEFORE the auto-stringout. Build it incrementally as Phase 5 / 6 clips land — don't wait for a "final" pass.

## Required structure

```
$ADGEN_HOME/<brand>/concepts/<slug>/handoff/
├── MANIFEST.md              ← shot order + per-shot audio strategy + narrator script + in-scene dialogue verbatim
├── video_silent/            ← V-only stems (h264, no audio) for clean FCP timeline drop
│   ├── shot_01_<name>_silent.mp4
│   ├── shot_02_<name>_silent.mp4
│   └── ... (one per shot)
├── video_with_audio/        ← Reference cuts with seedance audio baked in (for context / fallback)
│   ├── shot_01_<name>.mp4
│   └── ... (one per shot)
├── audio_seedance/          ← Per-shot seedance audio extracted (in-scene character dialogue + native ambient)
│   ├── shot_01_<name>_seedance.mp3
│   └── ... (one per shot)
├── audio_narrator/          ← 11L narrator stems (whichever 11L voice was used)
│   ├── narrator_01_dawn.mp3
│   ├── narrator_02_warm_water.mp3
│   └── ... (one per narrator beat in the breakdown)
├── audio_music/             ← Suno music bed if generated (one continuous track across spot)
│   └── bed_<style>_<duration>s.mp3
└── refs/                    ← Optional: copies of key visual refs for FCP-side reference
    ├── product_front.png
    ├── logo.png
    └── ...
```

## MANIFEST.md required sections

The MANIFEST.md inside `handoff/` is the source-of-truth for the editor. Required sections:

### 1 — Folder structure overview
4-track explanation (silent video / seedance audio / 11L narrator / music bed). Plain language.

### 2 — Shot table

Same shot # / sec / shot name structure as breakdown.md, plus per-shot audio strategy column:

| # | shot file | sec | audio strategy in FCP |
|---|---|---|---|
| 1 | `video_silent/shot_01_dawn_silent.mp4` | 5.04 | Narrator `01_dawn` carries. NO seedance dialogue. Use the seedance audio stem only as ducked room tone (~10%). |
| 6 | `video_silent/shot_06_still_cold_silent.mp4` | 4.04 | Hybrid. seedance `06_still_cold_seedance.mp3` for Otto's "Still cold." in-scene. Narrator `06_remarkable.mp3` overlays at t=2.5s. |
| ... | ... | ... | ... |

### 3 — Audio mix logic

Three tracks in FCP:
→ **A1 (11L narrator)** — drop 11L stems at corresponding shot start-points
→ **A2 (seedance dialogue + ambient)** — use for in-scene shots; duck under the narrator on hybrid shots
→ **A3 (Music bed)** — Suno track if generated; overlay at low volume for cohesion

### 4 — Verbatim transcripts

Two sub-sections:

**Narrator script:**
```
[01_dawn]       Dawn, on the fourth floor. The herd begins to gather.
[02_warm_water] By ten, his water has gone warm. He drinks it anyway. Survival demands it.
...
```

**Seedance in-scene dialogue (verified via whisper):**
```
[06_still_cold] OTTO: "Still cold."
...
```

These are the verified-landed lines from whisper transcription. Editor can scan for "what's the actual dialogue" without re-watching clips.

### 5 — What's NOT in handoff

Be explicit about what the operator still has to do in FCP:
→ Suno music bed (if not generated)
→ Captions (Captionator pass)
→ End-card typography
→ 4:5 / 1:1 reframe (after 9:16 locks)
→ Color grading
→ Final mix + export

### 6 — Files at risk / flag for review

Be honest. Surface known-imperfect clips:
→ "shot_05 ice rattle — verify the bottle reads as the hero bottle, not a generic one"
→ "shot_02_warm_water cup — verify no props pop in mid-shot on the desk"
→ "Otto's seedance voice in shot 6 and the 11L narrator are two different voices by design — expected, not a consistency bug"

### 7 — Absolute paths

End with absolute paths so the editor can `cd` to the folder without thinking:
```
absolute root → $ADGEN_HOME/<brand>/concepts/<slug>/handoff/
```

## Build script (canonical pattern)

Save as `$ADGEN_HOME/<brand>/concepts/<slug>/build_handoff.sh` (the script lives in the concept folder, alongside the clips/audio it operates on). Pattern:

```bash
#!/bin/bash
set -e
cd $ADGEN_HOME/<brand>/concepts/<slug>

mkdir -p handoff/{video_silent,video_with_audio,audio_seedance,audio_narrator,audio_music,refs}

# Map shot canonical-name → canonical mp4 (read from refs/current.yml or hardcoded)
declare -A v3_clips=(
  ["01_dawn"]="shot_01_dawn_v3.mp4"
  ["02_warm_water"]="shot_02_warm_water_v3.mp4"
  # ... one entry per shot
)

# Generate silent stems + audio stems + reference cuts
for name in "${!v3_clips[@]}"; do
  src=${v3_clips[$name]}
  ffmpeg -loglevel error -y -i clips/$src -an -c:v copy handoff/video_silent/shot_${name}_silent.mp4
  ffmpeg -loglevel error -y -i clips/$src -vn -acodec libmp3lame -b:a 192k handoff/audio_seedance/shot_${name}_seedance.mp3
  cp clips/$src handoff/video_with_audio/shot_${name}.mp4
done

# Copy 11L narrator stems
cp audio/narrator/*.mp3 handoff/audio_narrator/

# Copy music bed if exists
[ -f audio/music_bed.mp3 ] && cp audio/music_bed.mp3 handoff/audio_music/

# Copy key refs (concept product composite from this concept; logo from the brand-global kit)
cp refs/product/hero_bottle_front.png handoff/refs/
cp ../../brand/logo.png handoff/refs/

# Build manifest (separately — too long for shell here)
python3 scripts/build_manifest.py
```

## Phase 1 deliverable plan

At Phase 1 brief.md, lock the handoff structure under "Handoff plan" section. Required entries:

→ Target duration
→ Number of shots
→ Audio architecture (Strategy A / B / hybrid)
→ Voice cast: per-character voice source
→ Music plan (Suno bed / per-clip / silent)
→ Captions plan
→ Reframe plan
→ Expected deliverables folder structure (cite this template)

Once Phase 1 brief is approved, the handoff structure is locked. Phase 7 build script generates the folder; the structure was decided up front.
