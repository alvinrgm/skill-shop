"""assembler — concat silent scene videos, mux the whole-ad VO, burn captions.

The assembler is format-agnostic. Every source plugin produces a VIDEO-ONLY
clip at the target width/height/fps; the pipeline generates ONE whole-ad VO
MP3 and passes it to the assembler, which mixes it onto the concatenated
picture and burns safe-zone-aware captions in the same pass.

Caption placement rules:
  - Default y comes from FormatSpec.caption_y_frac (always above the bottom
    danger zone by design).
  - Captions for endcard scenes get the format's endcard defaults.
"""
from __future__ import annotations
from pathlib import Path

from .ffkit import ffrun, probe_duration, FONT, CAPTION_FONT, ff_escape, encode_audio_args, encode_video_args
from .style import FormatSpec, caption_y_pixels


def _wrap_caption(text: str, max_chars: int = 22) -> str:
    """Break a caption into up to two lines at a word boundary near the middle.

    drawtext renders embedded newlines natively; the background box grows to
    fit the widest line. Keeping it to two lines keeps the block compact.
    """
    if len(text) <= max_chars:
        return text
    words = text.split()
    if len(words) <= 1:
        return text
    # Pick the split that minimizes the longer line.
    best_i, best_max = 1, 10**9
    for i in range(1, len(words)):
        top = " ".join(words[:i])
        bot = " ".join(words[i:])
        m = max(len(top), len(bot))
        if m < best_max:
            best_max, best_i = m, i
    return " ".join(words[:best_i]) + "\n" + " ".join(words[best_i:])


def assemble(
    scenes: list,                   # list[BuiltScene] — all video-only
    fmt: FormatSpec,
    run_dir: Path,
    vo_path: Path,                  # single whole-ad voiceover MP3
    out_name: str = "final.mp4",
) -> Path:
    asm_dir = run_dir / "assembly"
    asm_dir.mkdir(exist_ok=True)

    n = len(scenes)
    if n == 0:
        raise ValueError("assembler: no scenes")

    # --- 1. Concat video via demuxer (stream copy). All scenes are video-only
    # with matching codec/fps, so -c copy finishes in seconds. ---
    concat_list = asm_dir / "concat.txt"
    concat_list.write_text("".join(f"file '{s.path.resolve()}'\n" for s in scenes))

    silent_concat = asm_dir / "concat.mp4"
    ffrun([
        "ffmpeg", "-y",
        "-f", "concat", "-safe", "0", "-i", str(concat_list),
        "-c", "copy",
        "-movflags", "+faststart",
        str(silent_concat),
    ], "assembler-concat")

    total_video = probe_duration(silent_concat)

    # --- 2. Build caption filter chain (one drawtext per scene with a caption) ---
    starts = [0.0]
    for i in range(n - 1):
        starts.append(starts[-1] + scenes[i].duration)

    def _drawtext(caption: str, start: float, end: float, is_endcard: bool) -> str:
        y_frac = fmt.caption_endcard_y_frac if is_endcard else fmt.caption_y_frac
        fontsize = fmt.caption_endcard_fontsize_px if is_endcard else fmt.caption_fontsize_px
        y_px = caption_y_pixels(fmt, y_frac)
        # Scene captions: IG-Story-default block — HEAVY sans-serif (Arial Black)
        # white on a solid black box, wrapped to 2 lines if needed. Serifs and
        # stroke-only styles were rejected twice as too weak. The block +
        # heavy typeface is the legibility floor.
        if is_endcard:
            text = ff_escape(caption)
            return (
                f"drawtext=fontfile='{FONT}'"
                f":text='{text}'"
                f":fontsize={fontsize}:fontcolor=#111111"
                f":x=(w-text_w)/2:y={y_px}"
                f":enable='between(t,{start:.3f},{end:.3f})'"
            )
        wrapped = _wrap_caption(caption, max_chars=22)
        text = ff_escape(wrapped)
        return (
            f"drawtext=fontfile='{CAPTION_FONT}'"
            f":text='{text}'"
            f":fontsize={fontsize}:fontcolor=white"
            f":box=1:boxcolor=black@0.85:boxborderw=18"
            f":line_spacing=8"
            f":x=(w-text_w)/2:y={y_px}-(text_h-{fontsize})/2"
            f":enable='between(t,{start:.3f},{end:.3f})'"
        )

    filters = []
    for i, s in enumerate(scenes):
        is_endcard = (s.kind == "endcard")
        # Per-sub-clip captions override the scene-level caption (for montages).
        if s.sub_captions:
            for (off, dur, text) in s.sub_captions:
                start = starts[i] + off + 0.05
                end = min(starts[i] + off + dur - 0.05, total_video - 0.05)
                if start >= end:
                    continue
                filters.append(_drawtext(text, start, end, is_endcard))
            continue

        if not s.caption:
            continue
        start = starts[i] + 0.15
        end = min(starts[i] + s.duration - 0.1, total_video - 0.05)
        if start >= end:
            continue
        filters.append(_drawtext(s.caption, start, end, is_endcard))

    # --- 3. Mux VO + burn captions in a single encode pass ---
    final_path = asm_dir / out_name
    cmd = [
        "ffmpeg", "-y",
        "-i", str(silent_concat),
        "-i", str(vo_path),
    ]
    if filters:
        cmd += ["-vf", ",".join(filters)]
    cmd += [
        "-map", "0:v:0", "-map", "1:a:0",
        *encode_video_args(crf=20),
        *encode_audio_args(),
        "-shortest",
        "-movflags", "+faststart",
        str(final_path),
    ]
    ffrun(cmd, "assembler-mux-captions")
    return final_path
