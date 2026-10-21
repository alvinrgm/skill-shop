"""hedra_broll source — Nano Banana T2I still, animated with Kling I2V.

Ported from legacy/pipeline_v4.py step 7. Produces a silent b-roll cutaway clip.

Scene schema:
  id, source: "hedra_broll"
  prompt:        T2I prompt for the still
  motion_prompt: Kling I2V motion prompt (falls back to prompt)
  duration_ms:   requested clip duration in ms (default 3000)
  caption:       optional
"""
from __future__ import annotations
import requests
from pathlib import Path

from .base import Source, BuildContext, BuiltScene
from ..ffkit import ffrun, probe_duration, encode_audio_args, make_silence


class HedraBRollSource(Source):
    name = "hedra_broll"

    @classmethod
    def build(cls, scene: dict, ctx: BuildContext) -> BuiltScene:
        # Lazy import to avoid pulling Hedra config when it isn't used
        from lib.hedra import MODELS

        sid = scene["id"]
        broll_dir = ctx.run_dir / "broll"
        broll_dir.mkdir(exist_ok=True)

        still_path = broll_dir / f"{sid}.png"
        if not still_path.exists():
            ctx.hedra.make_image(scene["prompt"], still_path, aspect_ratio=ctx.aspect_ratio)
        still_asset_id_path = broll_dir / f"{sid}.still.asset_id"
        if not still_asset_id_path.exists():
            asset_id = ctx.hedra.upload_image(still_path)
            still_asset_id_path.write_text(asset_id)
        still_asset_id = still_asset_id_path.read_text().strip()

        raw_vid = broll_dir / f"{sid}_raw.mp4"
        if not raw_vid.exists():
            body = {
                "type": "video",
                "ai_model_id": MODELS["video_kling_2_6_pro_i2v"],
                "start_keyframe_id": still_asset_id,
                "generated_video_inputs": {
                    "text_prompt": scene.get("motion_prompt", scene["prompt"]),
                    "aspect_ratio": ctx.aspect_ratio,
                    "resolution": ctx.resolution,
                    "duration_ms": int(scene.get("duration_ms", 3000)),
                },
            }
            gen = ctx.hedra._post("/generations", json=body)
            ctx.hedra.poll(gen["id"], every=5, max_wait=300)
            url = ctx.hedra.get_asset_url(gen["asset_id"], "video")
            if not url:
                s = ctx.hedra._get(f"/generations/{gen['id']}/status")
                url = s.get("url") or s.get("download_url")
            if not url:
                raise RuntimeError(f"no download URL for hedra_broll {sid}")
            r = requests.get(url, stream=True); r.raise_for_status()
            with open(raw_vid, "wb") as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk)

        # Normalize to target size/fps + attach silent audio track
        scenes_dir = ctx.run_dir / "scenes"
        scenes_dir.mkdir(exist_ok=True)
        out = scenes_dir / f"{sid}.mp4"
        silence = broll_dir / f"{sid}_silence.m4a"
        dur = probe_duration(raw_vid)
        make_silence(dur, silence)
        ffrun([
            "ffmpeg", "-y", "-i", str(raw_vid), "-i", str(silence),
            "-vf", f"scale={ctx.width}:{ctx.height}:force_original_aspect_ratio=increase,"
                   f"crop={ctx.width}:{ctx.height},fps={ctx.fps}",
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "libx264", "-preset", "fast", "-crf", "20", "-pix_fmt", "yuv420p",
            *encode_audio_args(),
            "-shortest", str(out),
        ], f"broll-{sid}-norm")

        return BuiltScene(
            id=sid, path=out, duration=probe_duration(out),
            caption=scene.get("caption"), kind="broll",
        )
