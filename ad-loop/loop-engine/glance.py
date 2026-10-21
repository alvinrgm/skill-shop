#!/usr/bin/env python3
"""Glance simulations + the measured-box overlay.

An ad is not read at 1080px. These are the three viewing conditions the loop judges at,
plus the overlay that makes the instrument's own reading auditable by eye:

  glance_blur.png     the ~1.5-second glance: downsample to 216px, Gaussian blur 2.2,
                      then NEAREST back up to 540 so the blur is visible rather than
                      resampled away. What survives here is what the ad actually says.
  glance_thumb180.png 180px feed thumbnail.
  glance_phone378.png 378px phone render.
  measured_boxes.png  cyan = the MEASURED ink boxes, magenta = the fold line,
                      orange = the bottom safe line. The instrument showing its work.

and the CAP-HEIGHT ARITHMETIC at each scale, which is the number that decides whether a
declared type size is readable where it will be seen (authenticity and
legibility are re-earned at render scale, never inherited from the source file).
"""
from __future__ import annotations

import sys
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

_HERE = Path(__file__).resolve().parent
for _p in (str(_HERE), str(_HERE.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import config  # noqa: E402

# cap-height as a fraction of the declared point size. 0.72 was calibrated in a prior run
# for a typical display face; pass cap_ratio= for a face with a different cap height.
CAP_RATIO = 0.72

# SAMPLING NOTE: the phone sim for a 4:5 canvas is 378x472 by truncation (378x473 by
# rounding) — a one-pixel difference, no threshold. Heights here are truncated.


def _scaled(size, w):
    W, H = size
    return (w, int(H * w / W))


def build(render, out_dir, *, blocks=None, fold=None, safe=None, declared_type=None,
          thumb=180, phone=378, glance_px=216, glance_blur=2.2, glance_zoom=540,
          cap_ratio=CAP_RATIO, echo=True):
    """render: path / PIL Image of the delivered ad. Returns {name: path}.

    blocks/fold/safe are optional; pass zones.ZoneQA's measured values to get the
    overlay. `declared_type` is [(name, pt), ...] for the cap-height table.
    """
    im = render if isinstance(render, Image.Image) else Image.open(render)
    im = im.convert("RGB")
    W, H = im.size
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    written = {}

    p = out_dir / "glance_blur.png"
    im.resize(_scaled(im.size, glance_px), Image.LANCZOS).filter(
        ImageFilter.GaussianBlur(glance_blur)).resize(
        _scaled(im.size, glance_zoom), Image.NEAREST).save(p)
    written["glance_blur"] = p

    p = out_dir / "glance_thumb180.png"
    im.resize(_scaled(im.size, thumb), Image.LANCZOS).save(p)
    written["thumb"] = p

    p = out_dir / "glance_phone378.png"
    im.resize(_scaled(im.size, phone), Image.LANCZOS).save(p)
    written["phone"] = p

    if blocks is not None:
        ov = im.copy()
        d = ImageDraw.Draw(ov)
        for b in blocks:
            bbox = b["bbox"] if isinstance(b, dict) else b
            d.rectangle(tuple(bbox), outline=(0, 255, 255), width=2)
        if fold is not None:
            d.line([(0, fold), (W, fold)], fill=(255, 0, 255), width=2)
        if safe is not None:
            d.line([(0, safe), (W, safe)], fill=(255, 128, 0), width=2)
        p = out_dir / "measured_boxes.png"
        ov.save(p)
        written["measured_boxes"] = p

    if echo:
        print("\nGLANCE SIMS")
        for k, v in written.items():
            print(f"   {k:15s} {v.name}")
        if "measured_boxes" in written:
            print("   measured_boxes: cyan = measured ink boxes, magenta = fold, "
                  "orange = safe line")

    caps = {}
    if declared_type:
        if echo:
            print(f"\nCAP-HEIGHT ARITHMETIC (cap = pt x {cap_ratio} x scale)")
            head = "   %-22s %8s" % ("declared", "1:1")
            for w, label in ((phone, f"phone {phone}"), (thumb, f"thumb {thumb}")):
                head += " %12s" % label
            print(head)
        for name, pt in declared_type:
            row = {"pt": pt, "1:1": round(pt * cap_ratio, 2)}
            for w, label in ((phone, "phone"), (thumb, "thumb")):
                row[label] = round(pt * cap_ratio * (w / W), 2)
            caps[name] = row
            if echo:
                print("   %-22s %8.2f %12.2f %12.2f"
                      % (name, row["1:1"], row["phone"], row["thumb"]))
        if echo:
            print("   a declared size whose cap disappears at the scale it will be seen "
                  "is not small type, it is absent type.")
    return {"files": written, "caps": caps}


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("render")
    ap.add_argument("--out", required=True)
    ap.add_argument("--fold-frac", type=float, default=config.FOLD_FRAC)
    ap.add_argument("--bottom-safe", type=int, default=config.BOTTOM_SAFE)
    a = ap.parse_args()
    im = Image.open(a.render)
    build(im, a.out, fold=int(im.size[1] * a.fold_frac),
          safe=im.size[1] - a.bottom_safe, blocks=[])
