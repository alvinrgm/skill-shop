"""ffkit — shared ffmpeg primitives used by every source plugin and the assembler.

Keep this dumb: no business logic, no brief knowledge. Just wrappers that turn
common ffmpeg recipes into one-line Python calls.
"""
from __future__ import annotations
import os, subprocess
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
BRAND_FONT = os.path.normpath(os.path.join(_HERE, "..", "assets", "fonts", "BitterBold.ttf"))
MAC_FONT = "/System/Library/Fonts/Supplemental/Arial Bold.ttf"
LINUX_FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
# Optional display font (Bitter Bold serif, free on Google Fonts) — used for the
# end-card URL/logo region if you drop the .ttf at runtime/assets/fonts/. Scene captions need a HEAVY sans-serif for IG-Story
# legibility; BitterBold's serif reads as delicate against busy backgrounds.
FONT = BRAND_FONT if os.path.exists(BRAND_FONT) else (MAC_FONT if os.path.exists(MAC_FONT) else LINUX_FONT)

# Scene-caption font: heavy sans-serif, IG-Story style. Arial Black is the
# thickest universally-available option on macOS; falls back to BitterBold
# only if Arial Black is missing (linux CI, etc.).
_ARIAL_BLACK = "/System/Library/Fonts/Supplemental/Arial Black.ttf"
CAPTION_FONT = _ARIAL_BLACK if os.path.exists(_ARIAL_BLACK) else FONT


def ffrun(cmd, label="ffmpeg"):
    """Run an ffmpeg/ffprobe command; raise with tail-of-stderr on failure."""
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(f"ERROR [{label}]:\n{r.stderr[-2500:]}")
        raise RuntimeError(f"{label} failed")
    return r


def probe_duration(path: Path | str) -> float:
    r = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    return float(r.stdout.strip())


def ff_escape(text: str) -> str:
    """Escape text for ffmpeg drawtext filter."""
    return (
        text.replace("\\", "\\\\")
            .replace("'", "\u2019")
            .replace(":", "\\:")
            .replace(",", "\\,")
    )


def scale_fill_filter(w: int, h: int, fps: int) -> str:
    """Scale+center-crop so input fills wxh without letterboxing. Source may be cropped."""
    return (f"scale={w}:{h}:force_original_aspect_ratio=increase,"
            f"crop={w}:{h},fps={fps}")


def scale_pad_filter(w: int, h: int, fps: int, bg: str = "black") -> str:
    """Scale so the full input fits wxh, pad the remainder with `bg`."""
    return (f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
            f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:{bg},fps={fps}")


def scale_blur_pad_filter(w: int, h: int, fps: int, blur_sigma: int = 40) -> str:
    """Landscape-to-vertical classic: full shot centered over a blurred background of itself.

    The trailing fps= is critical: without it the overlay output inherits the
    background branch's framerate (= source fps), which breaks the concat
    demuxer downstream when scenes have heterogeneous source rates.
    """
    return (
        f"[0:v]split=2[bg][fg];"
        f"[bg]scale={w}:{h}:force_original_aspect_ratio=increase,"
        f"crop={w}:{h},boxblur={blur_sigma},fps={fps}[bg2];"
        f"[fg]scale={w}:{h}:force_original_aspect_ratio=decrease,fps={fps}[fg2];"
        f"[bg2][fg2]overlay=(W-w)/2:(H-h)/2,fps={fps}"
    )


def encode_video_args(crf: int = 20, preset: str = "fast") -> list[str]:
    return ["-c:v", "libx264", "-preset", preset, "-crf", str(crf), "-pix_fmt", "yuv420p"]


def encode_audio_args(bitrate: str = "192k", rate: int = 44100) -> list[str]:
    return ["-c:a", "aac", "-b:a", bitrate, "-ar", str(rate)]


def make_silence(duration: float, out: Path, rate: int = 44100):
    ffrun([
        "ffmpeg", "-y", "-f", "lavfi", "-i", f"anullsrc=r={rate}:cl=mono",
        "-t", f"{duration}", "-c:a", "aac", "-b:a", "128k", str(out),
    ], "silence")
