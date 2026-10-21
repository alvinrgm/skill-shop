#!/usr/bin/env python3
"""Contact sheet: tile a directory of exported ad PNGs into one labeled JPEG for review.

Usage:
  python3 sheet.py <dir-of-pngs> <out.jpg> [cols=4]
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common  # noqa: E402,F401  (uses the package .venv when there is one)

from PIL import Image, ImageDraw, ImageFont  # noqa: E402

THUMB_W = 340
GUTTER = 16
LABEL_H = 30
PAPER = (246, 244, 240)
INK = (30, 30, 34)


def _load_label_font() -> ImageFont.ImageFont:
    try:
        return ImageFont.load_default(size=18)
    except TypeError:
        # Older Pillow: load_default() has no size param.
        return ImageFont.load_default()


def build_sheet(in_dir: Path, out_path: Path, cols: int = 4) -> None:
    paths = sorted(in_dir.glob("*.png"), key=lambda p: p.name)
    if not paths:
        raise SystemExit(f"no PNGs found in {in_dir}")

    thumbs = []
    for p in paths:
        img = Image.open(p)
        w, h = img.size
        thumb_h = round(THUMB_W * h / w)
        img = img.resize((THUMB_W, thumb_h), Image.LANCZOS)
        thumbs.append((p.name, img))

    max_thumb_h = max(img.height for _, img in thumbs)
    rows = -(-len(thumbs) // cols)  # ceil div

    cell_w = THUMB_W + GUTTER
    cell_h = max_thumb_h + LABEL_H + GUTTER
    sheet_w = GUTTER + cols * cell_w
    sheet_h = GUTTER + rows * cell_h

    sheet = Image.new("RGB", (sheet_w, sheet_h), PAPER)
    draw = ImageDraw.Draw(sheet)
    font = _load_label_font()

    for i, (name, thumb) in enumerate(thumbs):
        col, row = i % cols, i // cols
        x = GUTTER + col * cell_w
        y = GUTTER + row * cell_h
        thumb_y = y + (max_thumb_h - thumb.height)  # bottom-align thumbs, labels line up

        if thumb.mode in ("RGBA", "LA") or (thumb.mode == "P" and "transparency" in thumb.info):
            thumb = thumb.convert("RGBA")
            sheet.paste(thumb, (x, thumb_y), thumb)
        else:
            sheet.paste(thumb.convert("RGB"), (x, thumb_y))

        label_y = y + max_thumb_h + 6
        draw.text((x + THUMB_W // 2, label_y), name, font=font, fill=INK, anchor="ma")

    sheet.save(out_path, quality=90)
    print(f"sheet: {len(thumbs)} images, {cols} cols -> {out_path}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Tile PNGs into a labeled contact sheet.")
    parser.add_argument("in_dir", type=Path, help="directory of PNGs")
    parser.add_argument("out_path", type=Path, help="output .jpg path")
    parser.add_argument("cols", type=int, nargs="?", default=4, help="columns (default 4)")
    args = parser.parse_args()
    build_sheet(args.in_dir, args.out_path, args.cols)


if __name__ == "__main__":
    main()
