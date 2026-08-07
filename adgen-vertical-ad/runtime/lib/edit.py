"""ffmpeg helpers: caption overlays, concat, Ken Burns, basic edit ops.

We keep this simple: drawtext for captions, concat for stitching, scale/pad for sizing,
zoompan for Ken Burns b-roll from still images.
"""
from __future__ import annotations
import subprocess, tempfile
from pathlib import Path

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ftf"
# Fallback if the above doesn't exist
import os
if not os.path.exists(FONT):
    FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"


def _run(cmd: list[str], label: str = "ffmpeg"):
    """Run a command, raise on failure."""
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"{label} failed: {r.stderr[-1500:]}")
    return r


def get_duration(video: Path) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(video)],
        capture_output=True, text=True,
    )
    return float(r.stdout.strip())


def add_captions(
    video_in: Path,
    video_out: Path,
    captions: list[dict],
) -> Path:
    """Burn-in caption overlays.

    captions: list of {start: float, end: float, text: str, y: int (optional)}
              y defaults to 60% of frame height.
    """
    filters = []
    for c in captions:
        text = c["text"].replace("'", "").replace(":", " ").upper()
        start, end = c["start"], c["end"]
        y = c.get("y", "h*0.55")
        f = (
            f"drawtext=fontfile='{FONT}'"
            f":text='{text}'"
            f":fontsize=52:fontcolor=black"
            f":box=1:boxcolor=yellow@0.95:boxborderw=16"
            f":x=(w-text_w)/2:y={y}"
            f":enable='between(t,{start},{end})'"
        )
        filters.append(f)
    vf = ",".join(filters) if filters else "null"

    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_in),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "copy",
        str(video_out),
    ]
    print(f"  ffmpeg: caption overlay → {video_out.name}")
    _run(cmd)
    return video_out


def ken_burns(
    image_in: Path,
    video_out: Path,
    duration: float = 3.0,
    width: int = 720,
    height: int = 1260,
    fps: int = 24,
    direction: str = "zoom_in",
) -> Path:
    """Create a Ken Burns (slow zoom/pan) video from a still image.

    Directions: zoom_in, zoom_out, pan_left, pan_right
    """
    frames = int(duration * fps)

    if direction == "zoom_in":
        # Slow zoom from 100% to 115%
        zp = f"zoompan=z='min(1+0.0004*on,1.15)':d={frames}:s={width}x{height}:fps={fps}"
    elif direction == "zoom_out":
        zp = f"zoompan=z='if(eq(on,0),1.15,max(1.15-0.0004*on,1))':d={frames}:s={width}x{height}:fps={fps}"
    elif direction == "pan_left":
        zp = f"zoompan=z='1.1':x='iw*0.1-iw*0.1*on/{frames}':d={frames}:s={width}x{height}:fps={fps}"
    elif direction == "pan_right":
        zp = f"zoompan=z='1.1':x='iw*0.0+iw*0.1*on/{frames}':d={frames}:s={width}x{height}:fps={fps}"
    else:
        zp = f"zoompan=z='min(1+0.0004*on,1.15)':d={frames}:s={width}x{height}:fps={fps}"

    cmd = [
        "ffmpeg", "-y",
        "-loop", "1", "-i", str(image_in),
        "-vf", zp,
        "-t", str(duration),
        "-c:v", "libx264", "-preset", "fast", "-crf", "18",
        "-pix_fmt", "yuv420p",
        str(video_out),
    ]
    print(f"  ffmpeg: ken_burns ({direction}, {duration}s) → {video_out.name}")
    _run(cmd)
    return video_out


def concat_videos(
    clips: list[Path],
    output: Path,
    crossfade: float = 0.0,
) -> Path:
    """Concatenate video clips. If crossfade > 0, applies xfade between clips.

    All clips must have the same resolution and codec.
    For crossfade, clips need to be at least crossfade duration long.
    """
    if not clips:
        raise ValueError("no clips to concat")
    if len(clips) == 1:
        import shutil
        shutil.copy(clips[0], output)
        return output

    if crossfade <= 0:
        # Simple concat demuxer (fast, no re-encode for video)
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
            for c in clips:
                f.write(f"file '{c.resolve()}'\n")
            concat_file = f.name

        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", concat_file,
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-c:a", "aac", "-b:a", "128k",
            str(output),
        ]
        print(f"  ffmpeg: concat {len(clips)} clips → {output.name}")
        _run(cmd)
        os.unlink(concat_file)
    else:
        # xfade between each pair of clips
        # Build a complex filtergraph
        inputs = []
        for c in clips:
            inputs.extend(["-i", str(c)])

        n = len(clips)
        # Build video xfade chain
        vfilter_parts = []
        afilter_parts = []

        # First pair
        offset = get_duration(clips[0]) - crossfade
        vfilter_parts.append(f"[0:v][1:v]xfade=transition=fade:duration={crossfade}:offset={offset}[v01]")
        afilter_parts.append(f"[0:a][1:a]acrossfade=d={crossfade}[a01]")

        for i in range(2, n):
            prev_v = f"v{i-2:0d}{i-1:0d}"
            prev_a = f"a{i-2:0d}{i-1:0d}"
            cur_v = f"v{i-1:0d}{i:0d}"
            cur_a = f"a{i-1:0d}{i:0d}"
            # Approximate offset: sum of all previous durations minus crossfades applied so far
            offset += get_duration(clips[i]) - crossfade
            vfilter_parts.append(f"[{prev_v}][{i}:v]xfade=transition=fade:duration={crossfade}:offset={offset}[{cur_v}]")
            afilter_parts.append(f"[{prev_a}][{i}:a]acrossfade=d={crossfade}[{cur_a}]")

        last_v = f"v{n-2:0d}{n-1:0d}"
        last_a = f"a{n-2:0d}{n-1:0d}"
        filtergraph = ";".join(vfilter_parts + afilter_parts)

        cmd = ["ffmpeg", "-y"] + inputs + [
            "-filter_complex", filtergraph,
            "-map", f"[{last_v}]", "-map", f"[{last_a}]",
            "-c:v", "libx264", "-preset", "fast", "-crf", "20",
            "-c:a", "aac", "-b:a", "128k",
            str(output),
        ]
        print(f"  ffmpeg: concat {n} clips with {crossfade}s crossfade → {output.name}")
        _run(cmd)

    return output


def add_audio_to_video(video_in: Path, audio_in: Path, video_out: Path) -> Path:
    """Replace or add audio track to a video (useful for b-roll with VO underneath)."""
    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_in),
        "-i", str(audio_in),
        "-c:v", "copy", "-c:a", "aac", "-b:a", "128k",
        "-map", "0:v:0", "-map", "1:a:0",
        "-shortest",
        str(video_out),
    ]
    print(f"  ffmpeg: add audio → {video_out.name}")
    _run(cmd)
    return video_out


def make_silent_video(video_in: Path, video_out: Path) -> Path:
    """Strip audio from a video (for b-roll clips that will be overlaid)."""
    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_in),
        "-c:v", "copy", "-an",
        str(video_out),
    ]
    _run(cmd, "ffmpeg-silent")
    return video_out


def normalize_clip(video_in: Path, video_out: Path, width: int = 720, height: int = 1260,
                   fps: int = 24) -> Path:
    """Normalize a clip to target resolution, fps, and codec for safe concat."""
    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_in),
        "-vf", f"scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2",
        "-r", str(fps),
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "aac", "-b:a", "128k", "-ar", "44100", "-ac", "2",
        str(video_out),
    ]
    _run(cmd, "ffmpeg-normalize")
    return video_out


def generate_silence(duration: float, out_path: Path, sample_rate: int = 44100) -> Path:
    """Generate a silent audio file."""
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi", "-i", f"anullsrc=r={sample_rate}:cl=stereo",
        "-t", str(duration),
        "-c:a", "aac", "-b:a", "128k",
        str(out_path),
    ]
    _run(cmd, "ffmpeg-silence")
    return out_path
