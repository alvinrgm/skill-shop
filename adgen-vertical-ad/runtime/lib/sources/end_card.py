"""end_card source — logo + caption card with a subtle zoom.

Treated as a regular scene at the tail of the ordered scene list so the
assembler doesn't need a special code path. Audio is handled at assembly
(single whole-VO mux), so this source produces a VIDEO-ONLY clip. The caption
itself is burned in by the assembler, not baked into the still frame here.

Scene schema (usually provided under brief["end_card"], copied into scenes[]
by the pipeline):
  id: "end_card"
  source: "end_card"
  logo_url:   URL to brand logo (optional)
  caption:    URL or tagline under logo (applied by assembler)
  script:     optional VO line (used by pipeline for whole-VO script; not read here)
  bg_color:   background color (default "#FFF5E6")
  duration:   fallback only; pipeline normally injects _target_duration
  _target_duration: float, injected by pipeline
"""
from __future__ import annotations
import requests
from pathlib import Path

from .base import Source, BuildContext, BuiltScene
from .. import ffkit
from ..ffkit import ffrun, probe_duration


class EndCardSource(Source):
    name = "end_card"

    @classmethod
    def build(cls, scene: dict, ctx: BuildContext) -> BuiltScene:
        ec_dir = ctx.run_dir / "end_card"
        ec_dir.mkdir(exist_ok=True)
        W, H, FPS = ctx.width, ctx.height, ctx.fps

        duration = float(scene.get("_target_duration", scene.get("duration", 2.5)))

        logo_url = scene.get("logo_url", "")
        logo_path = ec_dir / "logo.png"
        if logo_url and not logo_path.exists():
            r = requests.get(logo_url, stream=True); r.raise_for_status()
            with open(logo_path, "wb") as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk)

        bg = scene.get("bg_color", "#FFF5E6")

        # Still frame: solid bg + centered logo (caption burned in by assembler).
        frame = ec_dir / "frame.png"
        logo_w = int(W * 0.5)
        if logo_path.exists():
            ffrun([
                "ffmpeg", "-y",
                "-f", "lavfi", "-i", f"color=c={bg}:s={W}x{H}:d=1",
                "-i", str(logo_path),
                "-filter_complex",
                f"[1:v]scale={logo_w}:-1[logo];"
                f"[0:v][logo]overlay=(W-w)/2:(H-h)/2-{int(H*0.05)}",
                "-frames:v", "1", str(frame),
            ], "endcard-frame")
        else:
            ffrun([
                "ffmpeg", "-y",
                "-f", "lavfi", "-i", f"color=c={bg}:s={W}x{H}:d=1",
                "-frames:v", "1", str(frame),
            ], "endcard-frame-nologo")

        # Static still: no motion on the logo — motion looked weird with the
        # embossed wheat-stalk mark. Loop the single frame for the target duration.
        scenes_dir = ctx.run_dir / "scenes"
        scenes_dir.mkdir(exist_ok=True)
        out = scenes_dir / "end_card.mp4"
        ffrun([
            "ffmpeg", "-y", "-loop", "1", "-i", str(frame),
            "-t", str(duration),
            "-vf", f"fps={FPS}",
            *ffkit.encode_video_args(crf=20),
            "-an", str(out),
        ], "endcard-still")

        return BuiltScene(
            id="end_card", path=out, duration=probe_duration(out),
            caption=scene.get("caption"), kind="endcard",
        )
