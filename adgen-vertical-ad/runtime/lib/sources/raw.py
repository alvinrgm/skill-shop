"""raw source — trim pre-existing footage to an externally-set target duration.

Audio is handled at the assembly layer (single whole-VO mux), so this source
produces VIDEO-ONLY scene clips. The pipeline sets ``scene["_target_duration"]``
before dispatch.

Scene schema:
  id:         required
  source:     "raw"
  script:     VO line (used by pipeline to build the whole-VO MP3; not read here)
  caption:    on-screen caption text (optional, applied by assembler)
  clip:       filename under ctx.raw_dir                          (single-clip mode)
  clip_start: seconds into source to begin trim (default 0)
  OR
  clips:      [{path, start}, ...]                                (montage mode)
              Target duration is split evenly across sub-clips.
  fit:        "fill" | "blur_pad" (default "fill" for vertical src,
              auto-"blur_pad" for landscape src in a vertical format)
  _target_duration: float, injected by pipeline (seconds this clip should occupy)
"""
from __future__ import annotations
from pathlib import Path

from .base import Source, BuildContext, BuiltScene
from .. import ffkit
from ..ffkit import ffrun, probe_duration

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp", ".heic"}


class RawSource(Source):
    name = "raw"

    @classmethod
    def build(cls, scene: dict, ctx: BuildContext) -> BuiltScene:
        sid = scene["id"]
        scenes_dir = ctx.run_dir / "scenes"
        scenes_dir.mkdir(exist_ok=True)

        target_dur = float(scene["_target_duration"])

        out = scenes_dir / f"{sid}.mp4"
        sub_captions = None
        if "clips" in scene:
            cls._build_montage(scene, target_dur, out, ctx)
            # Per-sub-clip captions: offsets come from per-sub durations (so
            # each product caption lines up with when its word is spoken in
            # the VO) or fall back to even split.
            subs = scene["clips"]
            sub_durs = cls._sub_durations(scene, target_dur)
            collected = []
            offset = 0.0
            for sc, d in zip(subs, sub_durs):
                cap = sc.get("caption")
                if cap:
                    collected.append((offset, d, cap))
                offset += d
            sub_captions = collected or None
        else:
            src_path = ctx.raw_dir / scene["clip"]
            if src_path.suffix.lower() in IMAGE_EXTS:
                cls._build_still(scene, target_dur, out, ctx)
            else:
                cls._build_single(scene, target_dur, out, ctx)

        return BuiltScene(
            id=sid, path=out, duration=probe_duration(out),
            caption=scene.get("caption"), kind="scene",
            sub_captions=sub_captions,
        )

    # --- internals ---

    @classmethod
    def _video_filter(cls, src: Path, ctx: BuildContext, fit: str | None) -> str:
        """Choose scale/crop strategy based on source shape + requested fit.

        Shape detection accounts for QuickTime rotation metadata (iPhone clips
        encode raw 1920×1080 landscape but tag rotate=90 for portrait display).
        Without this, portrait .MOV files get misclassified as landscape and
        picks up a blur_pad fit that creates visible side-bars in formats
        wider than the source (e.g. 4:5 wrapping a 9:16 source).
        """
        if fit is None:
            try:
                import subprocess, json as _json
                r = subprocess.run(
                    ["ffprobe", "-v", "error", "-select_streams", "v:0",
                     "-show_entries", "stream=width,height",
                     "-of", "json", str(src)],
                    capture_output=True, text=True,
                )
                d = _json.loads(r.stdout)["streams"][0]
                src_w, src_h = d["width"], d["height"]
                rot_r = subprocess.run(
                    ["ffprobe", "-v", "error", "-select_streams", "v:0",
                     "-show_entries", "stream_tags=rotate",
                     "-of", "default=nw=1:nk=1", str(src)],
                    capture_output=True, text=True,
                )
                rot = int((rot_r.stdout.strip() or "0"))
                if rot in (90, 270):
                    src_w, src_h = src_h, src_w
                src_is_landscape = src_w > src_h
                target_is_vertical = ctx.height > ctx.width
                fit = "blur_pad" if (src_is_landscape and target_is_vertical) else "fill"
            except Exception:
                fit = "fill"

        if fit == "blur_pad":
            return ffkit.scale_blur_pad_filter(ctx.width, ctx.height, ctx.fps)
        return ffkit.scale_fill_filter(ctx.width, ctx.height, ctx.fps)

    @classmethod
    def _build_still(cls, scene, target_dur, out, ctx):
        """Turn a still image into a video scene with a subtle Ken Burns zoom."""
        src = ctx.raw_dir / scene["clip"]
        W, H, FPS = ctx.width, ctx.height, ctx.fps
        frames = max(1, int(target_dur * FPS))
        # Fit the image into the target frame first (letterbox with blur pad if
        # source aspect doesn't match), then zoompan on the result.
        fit = scene.get("fit", "blur_pad")
        if fit == "blur_pad":
            fit_graph = ffkit.scale_blur_pad_filter(W, H, FPS)
            filt = (
                f"{fit_graph},"
                f"zoompan=z='min(1+0.0006*on,1.10)':d={frames}:s={W}x{H}:fps={FPS}"
            )
        else:
            filt = (
                f"{ffkit.scale_fill_filter(W, H, FPS)},"
                f"zoompan=z='min(1+0.0006*on,1.10)':d={frames}:s={W}x{H}:fps={FPS}"
            )
        is_complex = filt.count("[") > 0
        cmd = ["ffmpeg", "-y", "-loop", "1", "-i", str(src), "-t", f"{target_dur}"]
        if is_complex:
            cmd += ["-filter_complex", f"{filt}[v]", "-map", "[v]"]
        else:
            cmd += ["-vf", filt]
        cmd += ["-an", *ffkit.encode_video_args(), str(out)]
        ffrun(cmd, f"raw-still-{scene['id']}")

    @classmethod
    def _build_single(cls, scene, target_dur, out, ctx):
        src = ctx.raw_dir / scene["clip"]
        clip_start = float(scene.get("clip_start", 0.0))
        src_dur = probe_duration(src)
        available = src_dur - clip_start
        vf = cls._video_filter(src, ctx, scene.get("fit"))
        is_complex = vf.count("[") > 0  # blur_pad is a filter_complex graph

        if is_complex:
            fc = f"{vf}[v]"
            if available >= target_dur - 0.05:
                ffrun([
                    "ffmpeg", "-y",
                    "-ss", f"{clip_start}", "-i", str(src),
                    "-t", f"{target_dur}",
                    "-filter_complex", fc,
                    "-map", "[v]", "-an",
                    *ffkit.encode_video_args(),
                    str(out),
                ], f"raw-{scene['id']}")
                return
            vf = ffkit.scale_fill_filter(ctx.width, ctx.height, ctx.fps)
            is_complex = False

        if available >= target_dur - 0.05:
            ffrun([
                "ffmpeg", "-y",
                "-ss", f"{clip_start}", "-i", str(src),
                "-t", f"{target_dur}",
                "-vf", vf, "-an",
                *ffkit.encode_video_args(),
                str(out),
            ], f"raw-{scene['id']}")
            return

        ratio = target_dur / max(available, 0.1)
        if ratio <= 1.5:
            vf_slow = f"setpts={ratio}*PTS,{vf}"
            ffrun([
                "ffmpeg", "-y",
                "-ss", f"{clip_start}", "-i", str(src),
                "-t", f"{target_dur}",
                "-vf", vf_slow, "-an",
                *ffkit.encode_video_args(),
                str(out),
            ], f"raw-{scene['id']}-slow")
            return

        vf_pad = f"setpts=1.5*PTS,{vf},tpad=stop_mode=clone:stop_duration={target_dur}"
        ffrun([
            "ffmpeg", "-y",
            "-ss", f"{clip_start}", "-i", str(src),
            "-t", f"{target_dur}",
            "-vf", vf_pad, "-an",
            *ffkit.encode_video_args(),
            str(out),
        ], f"raw-{scene['id']}-freeze")

    @classmethod
    def _sub_durations(cls, scene: dict, target_dur: float) -> list[float]:
        """Per-sub durations for a montage.

        If any sub sets a `duration`, explicit values are honored; unspecified
        subs split the remainder evenly. Otherwise all subs get equal time.
        This lets per-product cuts snap to VO word beats.
        """
        subs = scene["clips"]
        explicit = [sc.get("duration") for sc in subs]
        if not any(d is not None for d in explicit):
            return [target_dur / len(subs)] * len(subs)
        assigned = sum(float(d) for d in explicit if d is not None)
        missing = [i for i, d in enumerate(explicit) if d is None]
        remain = max(0.0, target_dur - assigned)
        fill = (remain / len(missing)) if missing else 0.0
        return [float(d) if d is not None else fill for d in explicit]

    @classmethod
    def _build_montage(cls, scene, target_dur, out, ctx):
        subs = scene["clips"]
        sub_durs = cls._sub_durations(scene, target_dur)
        tmp_dir = ctx.run_dir / "scenes" / f"_{scene['id']}_subs"
        tmp_dir.mkdir(parents=True, exist_ok=True)

        sub_paths = []
        for i, (sc, sub_dur) in enumerate(zip(subs, sub_durs)):
            src = ctx.raw_dir / sc["path"]
            start = float(sc.get("start", 0.0))
            vf = cls._video_filter(src, ctx, sc.get("fit") or scene.get("fit"))
            is_complex = vf.count("[") > 0
            sub_out = tmp_dir / f"sub_{i}.mp4"
            if is_complex:
                fc = f"{vf}[v]"
                ffrun([
                    "ffmpeg", "-y",
                    "-ss", f"{start}", "-i", str(src),
                    "-t", f"{sub_dur}",
                    "-filter_complex", fc,
                    "-map", "[v]", "-an",
                    *ffkit.encode_video_args(),
                    str(sub_out),
                ], f"montage-{scene['id']}-{i}")
            else:
                ffrun([
                    "ffmpeg", "-y",
                    "-ss", f"{start}", "-i", str(src),
                    "-t", f"{sub_dur}",
                    "-vf", vf, "-an",
                    *ffkit.encode_video_args(),
                    str(sub_out),
                ], f"montage-{scene['id']}-{i}")
            sub_paths.append(sub_out)

        concat_list = tmp_dir / "concat.txt"
        concat_list.write_text("".join(f"file '{p.name}'\n" for p in sub_paths))
        ffrun([
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0", "-i", str(concat_list),
            "-c", "copy", str(out),
        ], f"montage-concat-{scene['id']}")
