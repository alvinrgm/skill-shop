# Handoff manifest template — FCP-ready deliverable folder

The handoff folder is the end-state deliverable: separate-tracks assets that the operator can drop into FCP and assemble. It's the equivalent of a film production's "rushes" or "selects + tracks" delivery to the editor.

## Why this exists

Past mistake (a pharma-ad-parody spot): only built the handoff folder reactively after the operator said "this auto-stringout is unusable, give me the stems." Should have been planned at Phase 1 as the canonical deliverable, not invented at Phase 7 after auto-assembly failures.

The auto-stringout (a single mp4 with all clips concatenated and audio mixed by ffmpeg) is fragile. Auto-mix decisions about ducking, overlay timing, and ambient bed transitions cannot match what the operator would do in FCP with proper editing eyes/ears. The handoff folder bypasses the fragile auto-mix and gives the operator the raw parallel tracks.

## When to build

Build the handoff folder at every Phase 7 completion. Build it BEFORE the auto-stringout. Build it incrementally as Phase 5 / 6 clips land — don't wait for a "final" pass.

## Required structure

```
$ADGEN_HOME/<brand>/concepts/<slug>/handoff/
├── MANIFEST.md              ← 12-shot order + per-shot audio strategy + narrator script + in-scene dialogue verbatim
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
│   ├── narrator_01_intro.mp3
│   ├── narrator_02_neighbor.mp3
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
| 1 | `video_silent/shot_01_intro_silent.mp4` | 5.04 | Narrator `01_intro` carries. NO seedance dialogue. Skip seedance audio stem entirely (or use ducked at 10% as ambient bed). |
| 2 | `video_silent/shot_02_cookout_silent.mp4` | 5.04 | Hybrid. seedance `02_cookout_seedance.mp3` for the neighbor's "Trust me" in-scene. Narrator `02_neighbor.mp3` overlays at t=2.5s. |
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
[01_intro]    For years... Hank's dinners had lost their spark.
[02_neighbor] Then a neighbor told him about small-batch heat.
...
```

**Seedance in-scene dialogue (verified via whisper):**
```
[02_cookout]   NEIGHBOR: "Trust me. Two drops."
[03_transform] HANK: "Linda. Have you always been this radiant?"
               WIFE: "...Hank?"
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
→ "shot_05c theater — verify the bottle reads as the hero bottle, not a generic one"
→ "shot_02_cookout bottle stability — verify label stays facing camera the full 5s"
→ "voice consistency between seedance Hank shots and the 11L narrator may feel like 'two different people' — that's expected since they ARE two different voices by design"

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
  ["01_intro"]="shot_01_intro_v3.mp4"
  ["02_cookout"]="shot_02_cookout_v3.mp4"
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
