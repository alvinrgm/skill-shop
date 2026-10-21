#!/usr/bin/env python3
"""Make a transparent pack cutout from a product photo shot on a plain background.

Most store product photos are on white or a flat colour. This keys that background out by a
flood fill from the image border (so a white label INSIDE the pack is kept), feathers the edge,
crops to the pack, and writes an RGBA PNG to <brand>/brand/packs/pack-<name>.png, ready for
asset_library.py register-packs and the Assets page.

It is a plain-background tool. For a pack photographed in a scene, use Figma's own
"Remove background" image action on the Assets page, or any background-removal tool, and save
the PNG into brand/packs/ yourself. Always look at the result at full size: the cutout is the
truth the print gate compares against.

usage: cutout.py <brand> <photo> --name main-sku [--tol 18] [--feather 1.2] [--pad 12]
"""
from __future__ import annotations

import argparse
import sys
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import brand_dir  # noqa: E402

import numpy as np  # noqa: E402
from PIL import Image, ImageFilter  # noqa: E402


def key_background(rgb: np.ndarray, tol: float) -> np.ndarray:
    """True where the pixel is background reachable from the border."""
    h, w, _ = rgb.shape
    border = np.concatenate([rgb[0], rgb[-1], rgb[:, 0], rgb[:, -1]])
    bg = np.median(border, axis=0)
    close = np.abs(rgb.astype(int) - bg).max(axis=2) <= tol
    seen = np.zeros((h, w), bool)
    q = deque()
    for x in range(w):
        for y in (0, h - 1):
            if close[y, x] and not seen[y, x]:
                seen[y, x] = True
                q.append((y, x))
    for y in range(h):
        for x in (0, w - 1):
            if close[y, x] and not seen[y, x]:
                seen[y, x] = True
                q.append((y, x))
    while q:
        y, x = q.popleft()
        for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
            if 0 <= ny < h and 0 <= nx < w and close[ny, nx] and not seen[ny, nx]:
                seen[ny, nx] = True
                q.append((ny, nx))
    return seen


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("brand")
    ap.add_argument("photo")
    ap.add_argument("--name", required=True)
    ap.add_argument("--tol", type=float, default=18, help="max channel distance from the background colour")
    ap.add_argument("--feather", type=float, default=1.2)
    ap.add_argument("--pad", type=int, default=12)
    a = ap.parse_args()
    im = Image.open(a.photo).convert("RGB")
    rgb = np.array(im)
    bg = key_background(rgb, a.tol)
    alpha = Image.fromarray(((~bg) * 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(a.feather))
    rgba = im.copy()
    rgba.putalpha(alpha)
    ys, xs = np.where(~bg)
    if len(xs) == 0:
        sys.exit("nothing left after keying: the photo is not on a plain background (use --tol, or another tool)")
    box = (max(0, xs.min() - a.pad), max(0, ys.min() - a.pad),
           min(im.width, xs.max() + a.pad + 1), min(im.height, ys.max() + a.pad + 1))
    out_dir = brand_dir(a.brand) / "brand" / "packs"
    out_dir.mkdir(parents=True, exist_ok=True)
    name = a.name if a.name.startswith("pack-") else f"pack-{a.name}"
    out = out_dir / f"{name}.png"
    rgba.crop(box).save(out)
    kept = (~bg).mean() * 100
    print(f"wrote {out} ({box[2] - box[0]}x{box[3] - box[1]}, {kept:.0f}% of the photo kept). Look at it at full size.")


if __name__ == "__main__":
    main()
