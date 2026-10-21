#!/usr/bin/env python3
"""Generate an FCPXML 1.13 file from a list of clips + audio tracks, ready for Final Cut Pro 12.2 import.

HARD RULE: Every audio file referenced in the project MUST be placed on the
spine — not just declared as a resource. The narrator track, music bed, and per-clip stems
all go on the timeline as connected clips at negative lanes. Opening the FCPXML must show
a complete playable cut with all audio audible — no manual dragging from the event browser
required. See `reference/PITFALLS.md` "Every audio + video track MUST be on the FCPXML
spine" for the canonical statement.

Usage (video clips only — Strategy A spot):
    python3 fcpxml_gen.py --output project.fcpxml --project-name "acme_v1" \
        clip1.mp4 clip2.mp4 clip3.mp4 ...

Usage (with narrator overlay — Strategy B spot, REQUIRED for any spot with 11L VO):
    python3 fcpxml_gen.py --output project.fcpxml --project-name "acme_v1" \
        --narrator audio/narrator_50s.mp3 \
        --music audio/music_bed.mp3 \
        clip1.mp4 clip2.mp4 ...

Each --narrator / --music / --stems flag attaches the audio as a connected clip on
the spine at the correct lane:
- --narrator → lane -1, role "narration", spans the full timeline
- --music    → lane -2, role "music",     spans the full timeline
- --stems    → lane -3, role "dialogue",  per-clip stems (pass once per shot, same order as clips)

Or from a YAML manifest:
    python3 fcpxml_gen.py --manifest manifest.yml --output project.fcpxml

manifest.yml format:
    project_name: acme_v1
    clips:
      - path: ./clips/shot_01.mp4
        name: shot_01_intro
      ...
    narrator: ./audio/narrator_50s.mp3   # optional
    music: ./audio/music_bed.mp3          # optional
    stems:                                # optional, one per clip if used
      - ./audio/stems/shot_01_native.mp3
      ...

Each clip is probed with ffprobe for duration, fps, dimensions, and audio presence.
Output FCPXML places clips on V1, narrator on lane -1, music on lane -2, stems on lane -3.

Open the output .fcpxml by double-clicking on macOS — FCP creates a new project
with all assets pre-linked AND placed on the timeline. No manual wiring required.
"""

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from xml.dom import minidom
from xml.etree.ElementTree import Element, SubElement, tostring


def probe(path):
    """Run ffprobe and return clip metadata."""
    out = subprocess.check_output([
        "ffprobe", "-v", "error", "-print_format", "json",
        "-show_streams", "-show_format", str(path)
    ])
    info = json.loads(out)
    vstream = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
    astream = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    if not vstream:
        raise ValueError(f"{path} has no video stream")
    fps_num, fps_den = map(int, vstream["r_frame_rate"].split("/"))
    return {
        "duration": float(info["format"]["duration"]),
        "fps_num": fps_num,
        "fps_den": fps_den,
        "width": int(vstream["width"]),
        "height": int(vstream["height"]),
        "has_audio": astream is not None,
    }


def probe_audio(path):
    """Run ffprobe on an audio file and return duration."""
    out = subprocess.check_output([
        "ffprobe", "-v", "error", "-print_format", "json",
        "-show_streams", "-show_format", str(path)
    ])
    info = json.loads(out)
    astream = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    if not astream:
        raise ValueError(f"{path} has no audio stream")
    return {"duration": float(info["format"]["duration"])}


def discover_audio(audio_dir, n_clips):
    """Auto-discover audio files in a concept's audio/ folder and classify them by filename.

    PROACTIVE half of the "every audio track on the timeline" rule: instead of relying on the
    caller to remember --narrator/--music/--stems, scan the folder and place everything found.
    BACKSTOP half: any audio file that can't be classified is reported so nothing silently drops
    off the timeline (the failure mode that produced silent-video-on-open).

    Returns (narrator_path, music_path, stems_list, unclassified_list).
    - narrator: first file matching narrator/narration/voiceover/_vo/full_vo
    - music:    first file matching music/_bed/suno/score/soundtrack
    - stems:    files matching shot<NN>...(audio|stem|native), ordered by shot number, length n_clips
    - unclassified: audio files matched none of the above (caller WARNS)
    """
    import re
    audio_exts = (".mp3", ".wav", ".m4a", ".aac", ".flac")
    files = sorted(
        p for p in Path(audio_dir).iterdir()
        if p.is_file() and p.suffix.lower() in audio_exts
    )
    narrator = None
    music = None
    stems_by_shot = {}
    unclassified = []
    for p in files:
        name = p.name.lower()
        shot_m = re.search(r"shot[_-]?(\d+)", name)
        if shot_m and re.search(r"audio|stem|native", name):
            stems_by_shot[int(shot_m.group(1))] = str(p)
        elif re.search(r"narrator|narration|voiceover|full_vo|[_-]vo[_.-]", name):
            if narrator is None:
                narrator = str(p)
            else:
                unclassified.append(str(p))  # 2nd narrator-ish file — surface it
        elif re.search(r"music|[_-]bed[_.-]|suno|score|soundtrack", name):
            if music is None:
                music = str(p)
            else:
                unclassified.append(str(p))
        else:
            unclassified.append(str(p))

    stems = None
    if stems_by_shot:
        # map shot numbers to clip indices in order; pad/truncate to n_clips
        ordered = [stems_by_shot.get(i + 1) for i in range(n_clips)]
        # if shot numbers don't start at 1 / aren't contiguous, fall back to sorted order
        if not any(ordered):
            vals = [stems_by_shot[k] for k in sorted(stems_by_shot)]
            ordered = (vals + [None] * n_clips)[:n_clips]
        stems = ordered

    return narrator, music, stems, unclassified


def stable_uid(path):
    """Generate a deterministic UUID-style ID from the absolute file path.

    FCP libraries cache the uid → file binding at the library level (not just
    the event/project level). Once a uid is cached, FCP enforces it on every
    re-import of that file. If a re-import provides a DIFFERENT uid for the
    same file, FCP rejects with: "The media already exists in the library
    with a different unique identifier."

    PATH-BASED hashing is the right scheme because:
    1. It produces deterministic uids without reading file bytes (fast).
    2. FCP caches the FIRST uid it sees for a file. Once cached, ALL future
       re-imports must reproduce that same uid → path-based with the same
       (stable) path always reproduces.
    3. Content-based hashing was tried once — it broke for projects
       whose assets were already cached under path-based uids. Switching
       hash schemes mid-project means every uid changes, and FCP refuses
       the new import.

    Two known gotchas on path-based:
    → If the concept folder gets RENAMED, every clip's uid changes →
      regenerated FCPXML conflicts with FCP's cached uids. Recovery requires
      fully evicting the prior import (delete project + clips from event +
      empty library trash + restart FCP), or matching the new path before
      regenerating.
    → If a clip is MOVED to a different folder, same problem.

    To minimize folder churn: lock the concept slug at Phase 1 and don't
    rename it. If a rename is unavoidable, regenerate the FCPXML BEFORE
    the operator imports, so the first cached uid uses the final path.
    """
    h = hashlib.sha1(str(path).encode()).hexdigest().upper()
    return f"{h[0:8]}-{h[8:12]}-{h[12:16]}-{h[16:20]}-{h[20:32]}"


def seconds_to_rational(seconds, fps_num, fps_den):
    """Convert seconds to FCPXML rational time (e.g., '151151/30000s' for 5.04s at 30fps)."""
    frames = round(seconds * fps_num / fps_den)
    return f"{frames * fps_den}/{fps_num}s"


def fps_to_frame_duration(fps_num, fps_den):
    """e.g., 30fps → '1/30s', 29.97fps (30000/1001) → '1001/30000s'."""
    return f"{fps_den}/{fps_num}s"


def build_fcpxml(clips, project_name, event_name=None, folder_name=None,
                 narrator=None, music=None, stems=None):
    """Build the FCPXML element tree.

    Audio tracks (narrator / music / stems) are placed on the spine as connected
    clips at negative lanes per the HARD RULE in the module docstring + PITFALLS.md.
    """
    if not clips:
        raise ValueError("No clips provided")

    # Probe all clips, validate consistency
    probed = []
    for c in clips:
        info = probe(c["path"])
        probed.append({**c, **info})

    # Probe audio extras (narrator + music + stems)
    narrator_info = probe_audio(narrator) if narrator else None
    music_info = probe_audio(music) if music else None
    stems_info = []
    if stems:
        if len(stems) != len(clips):
            print(f"WARNING: {len(stems)} stems given but {len(clips)} clips — stems will skip mismatched indices",
                  file=sys.stderr)
        for s in stems:
            stems_info.append(probe_audio(s) if s else None)

    # All clips should match the first clip's format. If not, warn.
    first = probed[0]
    for p in probed[1:]:
        if (p["width"], p["height"]) != (first["width"], first["height"]):
            print(f"WARNING: {p['path']} is {p['width']}x{p['height']}, expected {first['width']}x{first['height']}",
                  file=sys.stderr)
        if (p["fps_num"], p["fps_den"]) != (first["fps_num"], first["fps_den"]):
            print(f"WARNING: {p['path']} is {p['fps_num']}/{p['fps_den']} fps, expected {first['fps_num']}/{first['fps_den']}",
                  file=sys.stderr)

    fps_num = first["fps_num"]
    fps_den = first["fps_den"]
    width = first["width"]
    height = first["height"]
    fps = fps_num / fps_den

    # Build the XML tree
    fcpxml = Element("fcpxml", version="1.13")
    resources = SubElement(fcpxml, "resources")

    # Format declaration
    format_name = f"FFVideoFormat{width}x{height}p{int(round(fps))}"
    SubElement(resources, "format",
        id="r1",
        name=format_name,
        frameDuration=fps_to_frame_duration(fps_num, fps_den),
        width=str(width),
        height=str(height),
        colorSpace="1-1-1 (Rec. 709)")

    # Asset declarations
    # FCPXML 1.10+ requires <media-rep> as a child of <asset> for the file path.
    # The `src` attribute on <asset> directly is deprecated and FCP 11+/12+ rejects it.
    for i, p in enumerate(probed):
        asset = SubElement(resources, "asset",
            id=f"a{i+1}",
            name=p["name"],
            uid=stable_uid(p["path"]),
            start="0s",
            duration=seconds_to_rational(p["duration"], fps_num, fps_den),
            hasVideo="1",
            hasAudio="1" if p["has_audio"] else "0",
            format="r1",
            videoSources="1",
            audioSources="1" if p["has_audio"] else "0",
            audioChannels="2",
            audioRate="48000")
        # The actual file location lives inside <media-rep>:
        SubElement(asset, "media-rep",
            kind="original-media",
            src=f"file://{Path(p['path']).resolve()}")

    # Audio asset declarations (narrator + music + stems)
    next_asset_id = len(probed) + 1
    narrator_asset_id = None
    music_asset_id = None
    stem_asset_ids = []

    if narrator_info:
        narrator_asset_id = f"a{next_asset_id}"
        next_asset_id += 1
        asset = SubElement(resources, "asset",
            id=narrator_asset_id,
            name=f"narrator_{Path(narrator).stem}",
            uid=stable_uid(narrator),
            start="0s",
            duration=seconds_to_rational(narrator_info["duration"], fps_num, fps_den),
            hasVideo="0",
            hasAudio="1",
            audioSources="1",
            audioChannels="2",
            audioRate="48000")
        SubElement(asset, "media-rep",
            kind="original-media",
            src=f"file://{Path(narrator).resolve()}")

    if music_info:
        music_asset_id = f"a{next_asset_id}"
        next_asset_id += 1
        asset = SubElement(resources, "asset",
            id=music_asset_id,
            name=f"music_{Path(music).stem}",
            uid=stable_uid(music),
            start="0s",
            duration=seconds_to_rational(music_info["duration"], fps_num, fps_den),
            hasVideo="0",
            hasAudio="1",
            audioSources="1",
            audioChannels="2",
            audioRate="48000")
        SubElement(asset, "media-rep",
            kind="original-media",
            src=f"file://{Path(music).resolve()}")

    if stems:
        for i, (s, s_info) in enumerate(zip(stems, stems_info)):
            if not s_info:
                stem_asset_ids.append(None)
                continue
            sid = f"a{next_asset_id}"
            next_asset_id += 1
            stem_asset_ids.append(sid)
            asset = SubElement(resources, "asset",
                id=sid,
                name=f"stem_{Path(s).stem}",
                uid=stable_uid(s),
                start="0s",
                duration=seconds_to_rational(s_info["duration"], fps_num, fps_den),
                hasVideo="0",
                hasAudio="1",
                audioSources="1",
                audioChannels="2",
                audioRate="48000")
            SubElement(asset, "media-rep",
                kind="original-media",
                src=f"file://{Path(s).resolve()}")

    # FCPXML hierarchy is FLAT: <library> → <event> → <project>. No project-
    # grouping folders are allowed at either level.
    #   library DTD:  (event | smart-collection)*
    #   event DTD:    (clip | audition | mc-clip | ref-clip | sync-clip |
    #                  asset-clip | collection-folder | keyword-collection |
    #                  smart-collection | project)*
    # `<folder>` is NOT a valid element in FCPXML — only `collection-folder`
    # and `keyword-collection`, which group CLIPS not projects. The previous
    # patches tried `<folder>` in both spots and got rejected with explicit DTD
    # errors from FCP.
    #
    # Naming convention used in adgen (Option A):
    #   --event       = client name ("Acme Co", etc.)
    #   --project-name = concept timeline ("Sink Showdown", etc.)
    # For multiple timeline iterations of one concept, suffix the project name
    # (e.g., "Sink Showdown — v1", "Sink Showdown — 9x16").
    if folder_name:
        print(f"warning: --folder/{folder_name!r} is ignored — FCPXML doesn't "
              f"allow project-grouping folders inside events. Encode the "
              f"grouping into the project name instead.", file=sys.stderr)
    library = SubElement(fcpxml, "library")
    event = SubElement(library, "event", name=event_name or project_name)
    project = SubElement(event, "project", name=project_name)

    total_dur_sec = sum(p["duration"] for p in probed)
    sequence = SubElement(project, "sequence",
        format="r1",
        duration=seconds_to_rational(total_dur_sec, fps_num, fps_den),
        tcStart="0s",
        tcFormat="NDF",
        audioLayout="stereo",
        audioRate="48k")
    spine = SubElement(sequence, "spine")

    # Place clips on timeline (V1 spine).
    # Connected audio (narrator/music/stems) attaches as <asset-clip lane="-N">
    # children of the first V1 clip — convention per the HARD RULE.
    #
    # CRITICAL: accumulate offset in FRAMES, never seconds. Past mistake:
    # used `offset_sec += p["duration"]` and re-rounded to
    # frames per clip. The seconds-based accumulator drifts because
    # `round(5.06*24) + round(10.05*24) = 121 + 241 = 362 frames` but
    # `round((5.06+10.05)*24) = round(362.64) = 363 frames` — the operator saw
    # the resulting 1-frame black gap between shots 2 and 3 on the timeline.
    # Accumulating in frames eliminates the drift entirely; each clip starts
    # EXACTLY where the previous one ends.
    offset_frames = 0
    first_clip = None
    clip_offsets = []  # (offset_sec, duration_sec) per clip — used for stem placement
    for i, p in enumerate(probed):
        dur_frames = round(p["duration"] * fps_num / fps_den)
        # rational time strings, frame-exact (no seconds-rounding drift):
        offset_rational = f"{offset_frames * fps_den}/{fps_num}s"
        duration_rational = f"{dur_frames * fps_den}/{fps_num}s"
        clip_attrs = {
            "ref": f"a{i+1}",
            "offset": offset_rational,
            "name": p["name"],
            "duration": duration_rational,
        }
        if p["has_audio"]:
            clip_attrs["audioRole"] = "dialogue"
        clip_el = SubElement(spine, "asset-clip", **clip_attrs)
        if first_clip is None:
            first_clip = clip_el
        # clip_offsets kept in seconds for downstream stem-placement math
        # (sub-second stem offsets aren't expected; if stems start mid-clip
        # we'd need to repeat the frame-exact math there too).
        clip_offsets.append((offset_frames * fps_den / fps_num, p["duration"]))
        offset_frames += dur_frames

    total_timeline_sec = offset_frames * fps_den / fps_num
    total_timeline_frames = offset_frames

    # Place narrator as a connected clip on lane -1, spanning the whole timeline
    # (or its own duration if shorter). Attaches to the first V1 clip.
    if narrator_asset_id and first_clip is not None:
        narr_duration_sec = min(narrator_info["duration"], total_timeline_sec)
        SubElement(first_clip, "asset-clip",
            ref=narrator_asset_id,
            lane="-1",
            offset="0/24s" if fps == 24 else seconds_to_rational(0.0, fps_num, fps_den),
            name=f"narrator (lane -1)",
            duration=seconds_to_rational(narr_duration_sec, fps_num, fps_den),
            audioRole="narration")

    # Place music bed on lane -2, also attached to the first V1 clip.
    if music_asset_id and first_clip is not None:
        music_duration_sec = min(music_info["duration"], total_timeline_sec)
        SubElement(first_clip, "asset-clip",
            ref=music_asset_id,
            lane="-2",
            offset="0/24s" if fps == 24 else seconds_to_rational(0.0, fps_num, fps_den),
            name=f"music (lane -2)",
            duration=seconds_to_rational(music_duration_sec, fps_num, fps_den),
            audioRole="music")

    # Place per-clip stems on lane -3 under each corresponding V1 clip.
    if stem_asset_ids:
        spine_clips = list(spine.findall("asset-clip"))
        for i, sid in enumerate(stem_asset_ids):
            if not sid or i >= len(spine_clips):
                continue
            stem_dur = stems_info[i]["duration"]
            SubElement(spine_clips[i], "asset-clip",
                ref=sid,
                lane="-3",
                offset="0/24s" if fps == 24 else seconds_to_rational(0.0, fps_num, fps_den),
                name=f"stem {Path(stems[i]).stem}",
                duration=seconds_to_rational(stem_dur, fps_num, fps_den),
                audioRole="dialogue")

    return fcpxml


def serialize(fcpxml):
    """Pretty-print the XML and add the DOCTYPE."""
    rough = tostring(fcpxml, encoding="UTF-8").decode()
    pretty = minidom.parseString(rough).toprettyxml(indent="  ")
    # minidom adds an XML declaration — replace with our own that includes DOCTYPE
    lines = pretty.split("\n")
    # First line is the XML declaration; add DOCTYPE on next line
    output = '<?xml version="1.0" encoding="UTF-8"?>\n<!DOCTYPE fcpxml>\n' + "\n".join(
        l for l in lines[1:] if l.strip()
    )
    return output


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", required=True, help="Output .fcpxml path")
    ap.add_argument("--project-name", default="ad_v1", help="Project name shown in FCP")
    ap.add_argument("--event", help="FCP event the project goes under (per FCPXML DTD, events sit directly inside <library>). In adgen we use this for the CLIENT name. Match an EXISTING event name in your library to merge re-imports into one place. Defaults to project-name if omitted.")
    ap.add_argument("--folder", help="DEPRECATED — FCPXML doesn't support project-grouping folders. Anything passed here is warned-and-ignored; group via project naming instead (e.g., 'Sink Showdown — v1').")
    ap.add_argument("--manifest", help="Optional YAML manifest with clips list")
    ap.add_argument("--narrator", help="Path to narrator audio (placed on lane -1 spanning the full timeline). REQUIRED for any Strategy B spot with 11L VO.")
    ap.add_argument("--music", help="Path to music bed audio (placed on lane -2 spanning the full timeline).")
    ap.add_argument("--stems", help="Per-clip audio stem paths as a COMMA-SEPARATED list (placed on lane -3 under each clip). Pass one per clip in the same order; use empty entry to skip a clip. E.g. --stems 'a.mp3,b.mp3,,d.mp3'")
    ap.add_argument("--auto-audio", metavar="DIR", help="Auto-discover + place ALL audio in DIR (usually the concept's audio/ folder). Classifies by filename: narrator/vo → lane -1, music/bed/suno → lane -2, shot<NN>_audio → lane -3 stems. Explicit --narrator/--music/--stems override the auto-discovered ones. Anything unclassifiable is WARNED so nothing silently drops off the timeline. This is the PROACTIVE way to satisfy the 'every audio track on the spine' rule.")
    ap.add_argument("clips", nargs="*", help="Input clip paths (if not using --manifest)")
    args = ap.parse_args()

    manifest = None
    if args.manifest:
        try:
            import yaml
        except ImportError:
            sys.exit("yaml module required for --manifest. pip install pyyaml")
        with open(args.manifest) as f:
            manifest = yaml.safe_load(f)
        clips = manifest["clips"]
        project_name = manifest.get("project_name", args.project_name)
    else:
        if not args.clips:
            sys.exit("Provide either --manifest or positional clip arguments")
        clips = [
            {"path": str(Path(c).resolve()), "name": Path(c).stem}
            for c in args.clips
        ]
        project_name = args.project_name

    event_name = args.event or (manifest.get("event") if manifest else None)
    folder_name = args.folder or (manifest.get("folder") if manifest else None)
    narrator = args.narrator or (manifest.get("narrator") if manifest else None)
    music = args.music or (manifest.get("music") if manifest else None)
    stems = None
    if args.stems:
        stems = args.stems.split(",")
    elif manifest and manifest.get("stems"):
        stems = manifest["stems"]

    # Auto-discover audio from a directory (proactive placement). Explicit flags above win.
    auto_dir = args.auto_audio or (manifest.get("auto_audio") if manifest else None)
    if auto_dir:
        if not Path(auto_dir).is_dir():
            sys.exit(f"--auto-audio: {auto_dir} is not a directory")
        a_narr, a_music, a_stems, unclassified = discover_audio(auto_dir, len(clips))
        narrator = narrator or a_narr
        music = music or a_music
        if stems is None:
            stems = a_stems
        placed_auto = []
        if a_narr and not args.narrator:
            placed_auto.append(f"narrator={Path(a_narr).name}")
        if a_music and not args.music:
            placed_auto.append(f"music={Path(a_music).name}")
        if a_stems and not args.stems:
            placed_auto.append(f"stems={len([s for s in a_stems if s])}")
        if placed_auto:
            print(f"→ auto-audio from {auto_dir}: {' · '.join(placed_auto)}")
        if unclassified:
            print(f"⚠ auto-audio: {len(unclassified)} file(s) in {auto_dir} not placed on timeline "
                  f"(couldn't classify by filename) — wire them manually if needed:", file=sys.stderr)
            for u in unclassified:
                print(f"    {Path(u).name}", file=sys.stderr)
        if not (narrator or music or stems or any(
                probe(c["path"])["has_audio"] for c in clips[:1])):
            print("⚠ auto-audio: no audio classified AND first clip has no native audio — "
                  "the timeline may open silent. Check your audio/ filenames.", file=sys.stderr)
    # Resolve any "" / None entries in stems to None for clean skip
    if stems:
        stems = [str(Path(s).resolve()) if s and s.strip() else None for s in stems]
    fcpxml = build_fcpxml(clips, project_name, event_name=event_name, folder_name=folder_name,
                          narrator=narrator, music=music, stems=stems)
    output = serialize(fcpxml)

    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(output)

    # Validate XML well-formedness
    try:
        subprocess.run(["xmllint", "--noout", str(out_path)], check=True, capture_output=True)
        print(f"✓ {out_path} (valid XML)")
    except subprocess.CalledProcessError as e:
        print(f"⚠ {out_path} written, but xmllint reports issues:")
        print(e.stderr.decode())
    except FileNotFoundError:
        print(f"✓ {out_path} (xmllint not available, skipping XML validation)")

    # Sanity-check that all asset paths exist
    import re
    missing = []
    total_assets = len(clips) + (1 if narrator else 0) + (1 if music else 0) + (len([s for s in (stems or []) if s]))
    for path in re.findall(r'src="file://([^"]+)"', output):
        if not Path(path).exists():
            missing.append(path)
    if missing:
        print(f"⚠ {len(missing)} asset path(s) not found on disk:")
        for p in missing:
            print(f"  {p}")
    else:
        print(f"✓ all {total_assets} asset paths exist on disk")

    # Per the HARD RULE, surface what landed on the timeline so it's visible at gen time.
    placed = [f"V1: {len(clips)} clip(s)"]
    if narrator:
        placed.append(f"lane -1 (narration): {Path(narrator).name}")
    if music:
        placed.append(f"lane -2 (music): {Path(music).name}")
    if stems:
        nstems = len([s for s in stems if s])
        placed.append(f"lane -3 (stems): {nstems} per-clip track(s)")
    print(f"✓ timeline: {' · '.join(placed)}")


if __name__ == "__main__":
    main()
