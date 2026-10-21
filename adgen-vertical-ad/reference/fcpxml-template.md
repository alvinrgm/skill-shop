# FCPXML template reference (FCP 12.2)

Generate `.fcpxml` files that FCP 12.2 imports cleanly with all assets pre-linked. The operator opens the file → FCP creates a real project → they edit.

## What FCPXML is (and isn't)

→ A plain-text XML interchange format published by Apple.
→ Contains project settings, asset references (by file path), and timeline structure.
→ FCP imports it to create a project; FCP exports it for handoff to other tools.
→ NOT a binary FCP project format (.fcpbundle is binary, can only be opened by FCP).
→ Generating .fcpxml does NOT require FCP to be installed.

## Schema version

FCP 12.2 → use **FCPXML 1.13** (the most recent documented version as of mid-2026). If FCP 12.2 ships with 1.14 by the time this is updated, target 1.14 — they're backwards-compatible.

## Library / event / project hierarchy — FLAT (no project-grouping folders)

**The structure is exactly three levels:** `<library>` → `<event>` → `<project>`. There is no valid way to wrap a project in a `<folder>` via FCPXML. Both attempted past-session patches that put `<folder>` in were rejected by FCP with explicit DTD errors:

| Where `<folder>` was attempted | FCP DTD error |
|---|---|
| Direct child of `<library>` | `Element library content does not follow the DTD, expecting (event \| smart-collection)*, got (folder)` |
| Direct child of `<event>` | `Element event content does not follow the DTD, expecting (clip \| audition \| mc-clip \| ref-clip \| sync-clip \| asset-clip \| collection-folder \| keyword-collection \| smart-collection \| project)*, got (folder)` |

The `<folder>` element exists in FCPXML's vocabulary for organizing clips inside events as `<collection-folder>` / `<keyword-collection>` — those group **clips**, not projects. Don't try to repurpose them for project grouping.

**Implication:** if the operator (or any user) wants more than one organizational level after the library, the second level must be encoded into either the **event name** or the **project name**.

## adgen conventions for FCPXML imports

These are codified in `SKILL.md` Phase 7 — repeated here as the canonical schema mapping:

| FCPXML element | Content | Example |
|---|---|---|
| `<library>` | The operator's active library (must be set in FCP before import) | `Client ads` |
| `<event name="...">` | Client name (ONE event per client) | `Acme Co`, `Example Brand` |
| `<project name="...">` | Concept name (siblings within the client event) | `Sink Showdown`, `Pharma Parody v4` |
| project-name suffix | Timeline iteration | `Sink Showdown — v1`, `... — 9x16`, `... — 4x5` |

Re-imports with the same event name **merge in place** (no duplicate events spawn). If a stale event name lingers from a prior convention (e.g., an older per-concept event created before the one-event-per-client convention), the operator merges it by dragging contents inside the same library — same-library drag is a move, not a copy — then deletes the empty source event.

**Canonical CLI for the generator:**
```
python3 scripts/fcpxml_gen.py \
  --output final/project.fcpxml \
  --project-name "<Concept>" \
  --event "<Client>" \
  clips/shot_*.mp4
```

The `--folder` flag is deprecated. It warns and is ignored — FCPXML doesn't permit project-grouping folders.

The DOCTYPE declaration:
```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE fcpxml>
<fcpxml version="1.13">
```

## Minimum viable FCPXML structure

Every FCPXML needs:
1. `<resources>` — declare formats, assets, and effects used
2. `<library>` — wraps an `<event>` which wraps a `<project>`
3. `<project>` contains a `<sequence>` which contains `<spine>` (the timeline)

Skeleton:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE fcpxml>
<fcpxml version="1.13">
  <resources>
    <format id="r1" name="FFVideoFormat720x1280p2997"
            frameDuration="1001/30000s" width="720" height="1280"
            colorSpace="1-1-1 (Rec. 709)"/>
    <asset id="a1" name="shot_01" uid="<unique-id>"
           src="file://$ADGEN_HOME/<brand>/concepts/<slug>/clips/shot_01.mp4"
           start="0s" duration="<dur-rational>" hasVideo="1" hasAudio="1"
           format="r1" videoSources="1" audioSources="1" audioChannels="2" audioRate="48000"/>
    <!-- repeat <asset> for each clip -->
  </resources>

  <library>
    <event name="<brand> ad">
      <project name="<brand>_v1">
        <sequence format="r1" duration="<total-dur-rational>"
                  tcStart="0s" tcFormat="NDF"
                  audioLayout="stereo" audioRate="48k">
          <spine>
            <asset-clip ref="a1" offset="0s" name="shot_01"
                        duration="<clip-dur-rational>"
                        audioRole="dialogue"/>
            <asset-clip ref="a2" offset="<accumulated-offset>" name="shot_02"
                        duration="<clip-dur-rational>"
                        audioRole="dialogue"/>
            <!-- repeat for each clip in order -->
          </spine>
        </sequence>
      </project>
    </event>
  </library>
</fcpxml>
```

## Time format — rational seconds

FCPXML expresses time as **rational fractions** (numerator/denominator) in seconds.

For 30 fps content (typical seedance output):
- 1 frame = `1001/30000s` (NTSC 29.97) or `1/30s` (true 30)
- 1 second = `30000/30000s` or `30/30s`

For 24 fps:
- 1 frame = `1/24s`

For 60 fps:
- 1 frame = `1/60s`

**Convert seconds to rational:**

```python
def seconds_to_rational(seconds, fps=30):
    if fps == 29.97:
        # NTSC frame duration is 1001/30000s
        frames = round(seconds * 30000 / 1001)
        return f"{frames * 1001}/30000s"
    else:
        return f"{int(seconds * fps)}/{fps}s"
```

**Important:** `start`, `offset`, and `duration` ALL use rational seconds. Mismatched precision creates "drift" warnings in FCP.

## Asset declaration

Each clip must be declared as an `<asset>` in `<resources>` BEFORE being referenced in the timeline.

**CRITICAL — file path goes in a `<media-rep>` CHILD element, NOT as a `src` attribute on the asset.** This trips up most FCPXML generators. FCPXML 1.10+ moved `src` from being an attribute on `<asset>` to being an attribute on a child `<media-rep>` element.

```xml
<asset id="a1"
       name="shot_01"
       uid="A1B2C3D4-E5F6-7890-ABCD-EF1234567890"
       start="0s"
       duration="151151/30000s"
       hasVideo="1" hasAudio="1"
       format="r1"
       videoSources="1"
       audioSources="1"
       audioChannels="2"
       audioRate="48000">
  <media-rep kind="original-media"
             src="file://$ADGEN_HOME/acme/concepts/2025-03-14-sink-showdown-suds/clips/shot_01.mp4"/>
</asset>
```

**The DTD error you'll see if you forget this:**
```
DTD validation failed. (Element asset content does not follow the DTD,
expecting (media-rep+, metadata?), got
No declaration for attribute src of element asset
```

Translation: the asset element has no children when the DTD wants at least one media-rep child, and `src` was put in the wrong place. Fix: move `src` into a `<media-rep>` child.

The `kind` attribute on media-rep should be `"original-media"` (other valid values exist for proxies and analyzed media but not relevant here).

Required attributes:
- `id` — unique within the file (a1, a2, a3...)
- `name` — human-readable name in FCP
- `uid` — globally unique ID (UUID4 is fine)
- `src` — `file://` URL to the actual file on disk (absolute path required)
- `duration` — clip's full duration in rational seconds
- `hasVideo`, `hasAudio` — "1" if present
- `format` — references a `<format>` defined earlier
- `videoSources`, `audioSources` — usually "1"
- `audioChannels` — "1" mono or "2" stereo
- `audioRate` — sample rate in Hz (typically 48000 for video)

**Generate UIDs deterministically** so re-running the generator on the same files produces the same UIDs (avoids re-import duplicates):

```python
import hashlib
def stable_uid(file_path):
    h = hashlib.sha1(file_path.encode()).hexdigest().upper()
    # Format as UUID-like
    return f"{h[0:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"
```

## Timeline (spine)

The `<spine>` is the main timeline. Each `<asset-clip>` is a clip on the spine at a specific offset.

```xml
<spine>
  <asset-clip ref="a1" offset="0s" name="shot_01"
              duration="151151/30000s"
              audioRole="dialogue"/>
  <asset-clip ref="a2" offset="151151/30000s" name="shot_02"
              duration="241241/30000s"
              audioRole="dialogue"/>
  <asset-clip ref="a3" offset="392392/30000s" name="shot_03"
              duration="666666/30000s"
              audioRole="dialogue"/>
</spine>
```

Each clip's `offset` = sum of all prior clip durations (since they're back-to-back).

`audioRole` controls how FCP categorizes the audio for mixing — use:
- `dialogue` for VO + character speech
- `music` for music beds
- `effects` for SFX
- Or custom roles like `dialogue.suds` for sub-lanes

## Multiple audio tracks (lanes)

To put separate audio on different lanes (e.g., VO on A1, music on A2):

```xml
<asset-clip ref="a_vo" offset="0s" duration="..." lane="-1" audioRole="dialogue"/>
<asset-clip ref="a_music" offset="0s" duration="..." lane="-2" audioRole="music"/>
```

`lane` is an integer:
- 0 = primary spine
- -1, -2, -3... = audio lanes below the primary
- 1, 2, 3... = video lanes above (for picture-in-picture etc.)

## Project / sequence settings

```xml
<project name="acme_ad_v1">
  <sequence format="r1"
            duration="3000000/30000s"
            tcStart="0s"
            tcFormat="NDF"
            audioLayout="stereo"
            audioRate="48k">
```

- `format` references the `<format>` defined in resources
- `duration` = total length of the timeline in rational seconds
- `tcStart` = start timecode (almost always "0s")
- `tcFormat` = "NDF" (non-drop-frame) for 30 fps; "DF" for 29.97 broadcast
- `audioLayout` = "stereo" or "mono"
- `audioRate` = "48k" or "44.1k" or "96k"

## Frame rate detection

Always probe the source clips with ffprobe to confirm the actual frame rate:

```bash
ffprobe -v error -select_streams v:0 -show_entries stream=r_frame_rate -of default=noprint_wrappers=1:nokey=1 input.mp4
```

Common returns:
- `30/1` = 30 fps
- `30000/1001` = 29.97 fps (NTSC)
- `24/1` = 24 fps

Match the FCPXML format declaration accordingly. Seedance typically outputs `30/1`.

## Generating the FCPXML programmatically

Pseudocode for `scripts/fcpxml_gen.py`:

```python
from pathlib import Path
from xml.etree.ElementTree import Element, SubElement, tostring
from xml.dom import minidom
import hashlib
import json

def fps_to_rational_per_frame(fps_num, fps_den):
    return f"{fps_den}/{fps_num}s"

def seconds_to_rational(seconds, fps_num, fps_den):
    # rational = (seconds * fps_num) / fps_num, expressed as N/D s
    frames = round(seconds * fps_num / fps_den)
    return f"{frames * fps_den}/{fps_num}s"

def stable_uid(path):
    h = hashlib.sha1(path.encode()).hexdigest().upper()
    return f"{h[0:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"

def probe_clip(path):
    """Use ffprobe to get duration, fps, dimensions."""
    import subprocess, json
    out = subprocess.check_output([
        "ffprobe", "-v", "error", "-print_format", "json",
        "-show_streams", "-show_format", str(path)
    ])
    info = json.loads(out)
    vstream = next(s for s in info["streams"] if s["codec_type"] == "video")
    astream = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    fps_num, fps_den = map(int, vstream["r_frame_rate"].split("/"))
    return {
        "duration": float(info["format"]["duration"]),
        "fps_num": fps_num,
        "fps_den": fps_den,
        "width": int(vstream["width"]),
        "height": int(vstream["height"]),
        "has_audio": astream is not None,
    }

def build_fcpxml(clips_in_order, project_name, output_path):
    """clips_in_order: list of dicts with 'path', 'name'."""
    fcpxml = Element("fcpxml", version="1.13")
    resources = SubElement(fcpxml, "resources")

    # Probe first clip to get the format
    first = probe_clip(clips_in_order[0]["path"])
    fps_num = first["fps_num"]
    fps_den = first["fps_den"]
    width = first["width"]
    height = first["height"]

    fmt = SubElement(resources, "format",
        id="r1",
        name=f"FFVideoFormat{width}x{height}p{fps_num // fps_den}",
        frameDuration=fps_to_rational_per_frame(fps_num, fps_den),
        width=str(width), height=str(height),
        colorSpace="1-1-1 (Rec. 709)")

    # Add asset for each clip
    asset_ids = []
    for i, clip in enumerate(clips_in_order):
        info = probe_clip(clip["path"])
        aid = f"a{i+1}"
        asset_ids.append(aid)
        SubElement(resources, "asset",
            id=aid,
            name=clip["name"],
            uid=stable_uid(clip["path"]),
            src=f"file://{Path(clip['path']).resolve()}",
            start="0s",
            duration=seconds_to_rational(info["duration"], fps_num, fps_den),
            hasVideo="1",
            hasAudio="1" if info["has_audio"] else "0",
            format="r1",
            videoSources="1",
            audioSources="1" if info["has_audio"] else "0",
            audioChannels="2",
            audioRate="48000")

    # Library / event / project / sequence / spine
    library = SubElement(fcpxml, "library")
    event = SubElement(library, "event", name=f"{project_name} ad")
    project = SubElement(event, "project", name=project_name)

    total_dur_sec = sum(probe_clip(c["path"])["duration"] for c in clips_in_order)
    sequence = SubElement(project, "sequence",
        format="r1",
        duration=seconds_to_rational(total_dur_sec, fps_num, fps_den),
        tcStart="0s",
        tcFormat="NDF",
        audioLayout="stereo",
        audioRate="48k")
    spine = SubElement(sequence, "spine")

    offset_sec = 0.0
    for i, clip in enumerate(clips_in_order):
        info = probe_clip(clip["path"])
        SubElement(spine, "asset-clip",
            ref=asset_ids[i],
            offset=seconds_to_rational(offset_sec, fps_num, fps_den),
            name=clip["name"],
            duration=seconds_to_rational(info["duration"], fps_num, fps_den),
            audioRole="dialogue")
        offset_sec += info["duration"]

    # Pretty-print
    rough = tostring(fcpxml, encoding="UTF-8").decode()
    pretty = minidom.parseString(rough).toprettyxml(indent="  ", encoding="UTF-8").decode()
    # Add the DOCTYPE manually
    pretty = pretty.replace(
        '<?xml version="1.0" encoding="UTF-8"?>',
        '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE fcpxml>'
    )
    Path(output_path).write_text(pretty)
```

## Validation

You can't run FCP to validate, but you can:

1. **XML well-formedness:**
   ```bash
   xmllint --noout final/project.fcpxml && echo "valid XML" || echo "INVALID"
   ```

2. **Schema validation** (if you have the DTD):
   ```bash
   xmllint --noout --dtdvalid path/to/fcpxml.dtd final/project.fcpxml
   ```
   The DTD ships with FCP. On the operator's machine: `/Applications/Final Cut Pro.app/Contents/Resources/fcpxml.dtd`.

3. **Path resolution check:**
   ```python
   import re, os
   xml = open("final/project.fcpxml").read()
   for path in re.findall(r'src="file://([^"]+)"', xml):
       if not os.path.exists(path):
           print(f"MISSING: {path}")
   ```
   All asset paths must exist on disk. If any are missing, FCP will show "missing media" warnings.

4. **First-time real test:** The operator opens it. If FCP errors on import, the error message will identify the issue (usually schema version, missing DTD, or path resolution). Fix and regenerate.

## Common FCPXML mistakes

❌ Using relative paths in `src` — FCP won't find the files. Always absolute.
❌ Mismatched fps in format vs source clips — FCP will conform but you'll get conform warnings.
❌ `duration` attribute as decimal seconds (`5.04s`) — must be rational (`151200/30000s`).
❌ Forgetting `<!DOCTYPE fcpxml>` — some FCP versions reject without it.
❌ Re-using the same `uid` across runs — duplicates assets in FCP library.
❌ Asset ref before declaration — `<asset-clip ref="a1">` before `<asset id="a1">` exists.
❌ Forgetting to escape special characters in names (& should be `&amp;`).

## Testing the FCPXML on the operator's first open

When the operator first opens a generated .fcpxml, ask them to report:
- Does it open? (Yes/No)
- Any error dialog? (Capture the text)
- Any "missing media" warnings? (Which clips?)
- Does the timeline look right? (Clips in order, correct durations?)
- Does audio play? (For each clip)

If any "no", iterate on the generator. After 1-2 fixes the schema usually settles for that FCP version.

## What FCP fills in (so you don't have to)

After import, FCP automatically:
- Generates thumbnails for each clip
- Detects scene changes (optional metadata addition)
- Creates audio waveforms for the timeline view
- Builds proxies if you have proxy generation enabled

You don't need to include any of this in the FCPXML.

## What you can NOT include in FCPXML

These are runtime / FCP-internal:
- Color grades (LUTs, custom corrections)
- Effects from the FCP Effects browser
- Title templates from Motion
- Compound clips that don't already exist as files
- Speed ramps with curves (basic speed yes, custom curves no)
- Captions / subtitles (those are CEA-608/708 data baked into video, or a separate caption file)

If the operator needs any of these, they add them in FCP after import. The generated FCPXML is the foundation, not the finished cut.
