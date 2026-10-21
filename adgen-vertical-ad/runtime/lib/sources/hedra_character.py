"""hedra_character source — Pixar-style talking character.

Ported from legacy/pipeline_v4.py steps 1-6. Flow:
  1. Generate base character image (cached at pipeline level — the base image
     is shared across all character scenes in the same run)
  2. I2I expression variant for this scene
  3. Upload expression as keyframe
  4. ElevenLabs v3 TTS
  5. Upload TTS as audio asset
  6. Character-3 lipsync → clip with VO already baked in

Scene schema:
  id, source: "hedra_character"
  script, caption
  expression_prompt:  I2I prompt for this emotion
  lipsync_prompt:     prompt passed to Character-3 during lipsync
  base_ref:           path to an already-generated base character (optional —
                      first character scene in a run generates one and stashes
                      it under run_dir/character/base.png for later scenes)
  character_prompt:   T2I prompt if base_ref is missing (falls back to
                      brief-level "character_prompt" if not on scene)
"""
from __future__ import annotations
import shutil
from pathlib import Path

from .base import Source, BuildContext, BuiltScene
from ..ffkit import probe_duration


class HedraCharacterSource(Source):
    name = "hedra_character"

    @classmethod
    def build(cls, scene: dict, ctx: BuildContext) -> BuiltScene:
        sid = scene["id"]
        char_dir = ctx.run_dir / "character"
        char_dir.mkdir(exist_ok=True)

        # 1. Base character (generated once per run, stashed under character/base.png)
        base_path = char_dir / "base.png"
        base_ref_id_path = char_dir / "base_ref_id.txt"
        if not base_path.exists():
            prompt = scene.get("character_prompt") or ctx.__dict__.get("character_prompt")
            if not prompt:
                raise ValueError("hedra_character scene needs character_prompt on "
                                 "the scene or at brief level on the first character scene")
            ctx.hedra.make_image(prompt, base_path, aspect_ratio=ctx.aspect_ratio)
        if not base_ref_id_path.exists():
            ref_id = ctx.hedra.upload_image(base_path)
            base_ref_id_path.write_text(ref_id)
        ref_id = base_ref_id_path.read_text().strip()

        # 2. I2I expression
        expr_dir = char_dir / "expressions"
        expr_dir.mkdir(exist_ok=True)
        expr_path = expr_dir / f"{sid}.png"
        if not expr_path.exists():
            try:
                ctx.hedra.make_i2i(ref_id, scene["expression_prompt"], expr_path,
                                   aspect_ratio=ctx.aspect_ratio)
            except Exception as e:
                print(f"  ⚠ I2I failed for {sid}, reusing base: {e}")
                shutil.copy(base_path, expr_path)

        # 3. Upload expression as keyframe
        keyframe_id_path = expr_dir / f"{sid}.asset_id"
        if not keyframe_id_path.exists():
            asset_id = ctx.hedra.upload_image(expr_path)
            keyframe_id_path.write_text(asset_id)
        keyframe_id = keyframe_id_path.read_text().strip()

        # 4. TTS
        tts_dir = ctx.run_dir / "tts"
        tts_dir.mkdir(exist_ok=True)
        vo_path = tts_dir / f"{sid}.mp3"
        if not vo_path.exists():
            ctx.tts.tts(ctx.tts_voice, scene["script"], vo_path)

        # 5. Upload audio
        audio_id_path = tts_dir / f"{sid}.asset_id"
        if not audio_id_path.exists():
            audio_asset_id = ctx.hedra.upload_audio(vo_path)
            audio_id_path.write_text(audio_asset_id)
        audio_asset_id = audio_id_path.read_text().strip()

        # 6. Lipsync
        clips_dir = ctx.run_dir / "scenes"
        clips_dir.mkdir(exist_ok=True)
        out = clips_dir / f"{sid}.mp4"
        if not out.exists():
            ctx.hedra.make_lipsync(
                image_asset_id=keyframe_id,
                audio_asset_id=audio_asset_id,
                out_path=out,
                text_prompt=scene.get("lipsync_prompt", "character speaking expressively"),
                aspect_ratio=ctx.aspect_ratio,
                resolution=ctx.resolution,
            )

        return BuiltScene(
            id=sid, path=out, duration=probe_duration(out),
            caption=scene.get("caption"), kind="scene",
        )
