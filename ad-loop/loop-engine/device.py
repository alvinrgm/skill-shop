#!/usr/bin/env python3
"""Measuring a concept's DEVICE as the device.

THE GENERAL RULE: when the concept IS a visual mechanism, QA gets an
instrument for that mechanism specifically. A concept named for a device — a shared word
stacking into a single vertical column — can render with that word at nine sizes and nine
x-positions while every other check passes, if NO instrument checks whether the device
exists. Every generic check can pass on an ad whose
whole idea has been destroyed.

THE PROOF OBLIGATION: a sharpened instrument must re-fail the artifact it
was written for. `invariant_column` lives in its own module precisely so the identical
code can be pointed at the render that exposed the gap and shown failing there. If the
fixed ruler stops failing that file, the score was fixed, not the ruler.

The instrument is deliberately blind to intent. It finds the accent-coloured ink inside a
declared band, bands it into rows, and asks four questions of the rendered pixels:

    same size?      every token's ink height within +-1px, width within +-2px
    same x?         every token's ink LEFT edge within +-2px
    same pitch?     consecutive row tops equally spaced within +-2px
    right count?    exactly N tokens
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image

_HERE = Path(__file__).resolve().parent
for _p in (str(_HERE), str(_HERE.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from common import hex2rgb, row_bands  # noqa: E402


def attach_dots(bands):
    """Attach the dot of an `i` to the word it belongs to.

    If the invariant word carries a diacritic (the dot of the `i` in "every time" sits above the
    x-height with clear rows between), a naive row-band returns TWO components per token —
    the instrument would then report 12 tokens where there are 6, and a meaningless height
    spread.

    The rule is adaptive rather than a hard pixel gap, so it works at any type size and
    cannot be tuned to flatter one render: a band whose height is under 30% of the tallest
    band in the set, and which sits within one tall-band height of the band BELOW it, is a
    diacritic and is merged downward. Everything is then measured on the ORIGINAL mask
    inside the merged band, so no geometry is softened by the merge.
    """
    if not bands:
        return bands
    tall = max(e - s + 1 for s, e in bands)
    out = []
    i = 0
    while i < len(bands):
        s, e = bands[i]
        h = e - s + 1
        if (h < 0.30 * tall and i + 1 < len(bands)
                and (bands[i + 1][0] - e) <= tall):
            out.append((s, bands[i + 1][1]))
            i += 2
        else:
            out.append((s, e))
            i += 1
    return out


def invariant_column(png, field_hex, accent_hex, band_y0, band_y1, band_x1,
                     n_expected, tol_x=2.0, tol_h=1.0, tol_w=2.0, tol_pitch=2.0):
    """Measure the accent-coloured invariant tokens inside a band. Pure pixels.

    Returns (rows, fails, summary). `rows` is one dict per token found.
    """
    im = np.asarray(Image.open(png).convert("RGB")).astype(int)
    field = hex2rgb(field_hex)
    accent = hex2rgb(accent_hex)

    ink = np.abs(im - field).sum(2) > 26
    # accent core: near the accent hue AND clearly not the body ink. A generous radius, then
    # a percentile trim, so antialiased edge pixels do not widen the measured boxes.
    d_acc = np.abs(im - accent).sum(2)
    acc = ink & (d_acc < 90)

    band = np.zeros_like(acc)
    band[band_y0:band_y1 + 1, :band_x1] = acc[band_y0:band_y1 + 1, :band_x1]

    rows = []
    # min_h=2: single-row noise inside the accent band is not a token
    # (common.row_bands takes it explicitly).
    for (s, e) in attach_dots(row_bands(band.any(1), min_h=2)):
        seg = band[s:e + 1]
        xs = np.flatnonzero(seg.any(0))
        if len(xs) == 0:
            continue
        ys = np.flatnonzero(seg.any(1))
        rows.append({
            "y0": s + int(ys.min()), "y1": s + int(ys.max()),
            "x0": int(xs.min()), "x1": int(xs.max()),
            "h": int(ys.max() - ys.min() + 1), "w": int(xs.max() - xs.min() + 1),
            "px": int(seg.sum()),
        })

    fails = []
    if len(rows) != n_expected:
        fails.append(f"invariant column: {len(rows)} accent tokens in the band, expected {n_expected}")

    summary = {}
    if rows:
        x0s = [r["x0"] for r in rows]
        hs = [r["h"] for r in rows]
        ws = [r["w"] for r in rows]
        tops = [r["y0"] for r in rows]
        pitches = [tops[i + 1] - tops[i] for i in range(len(tops) - 1)]
        summary = {
            "left_spread": max(x0s) - min(x0s),
            "height_spread": max(hs) - min(hs),
            "width_spread": max(ws) - min(ws),
            "pitch_spread": (max(pitches) - min(pitches)) if pitches else 0,
            "pitches": pitches,
            "x0": x0s, "h": hs, "w": ws,
        }
        if summary["left_spread"] > tol_x:
            fails.append(f"invariant column: left edges spread {summary['left_spread']}px "
                         f"(tol {tol_x}) — the tokens are not in one column")
        if summary["height_spread"] > tol_h:
            fails.append(f"invariant column: token heights spread {summary['height_spread']}px "
                         f"(tol {tol_h}) — the tokens are not one size")
        if summary["width_spread"] > tol_w:
            fails.append(f"invariant column: token widths spread {summary['width_spread']}px "
                         f"(tol {tol_w}) — the tokens are not one size")
        if pitches and summary["pitch_spread"] > tol_pitch:
            fails.append(f"invariant column: pitch spread {summary['pitch_spread']}px "
                         f"(tol {tol_pitch}) — the rows are not on one baseline grid")
    return rows, fails, summary


def report_column(rows, fails, summary, n_expected, label):
    print(f"   {label}")
    print(f"   {'#':>3} {'ink y0':>7} {'y1':>6} {'h':>4} {'ink x0':>7} {'x1':>6} {'w':>5} {'px':>7}")
    for i, r in enumerate(rows, 1):
        print(f"   {i:>3} {r['y0']:>7} {r['y1']:>6} {r['h']:>4} {r['x0']:>7} {r['x1']:>6} "
              f"{r['w']:>5} {r['px']:>7}")
    if summary:
        print(f"   tokens {len(rows)} (expected {n_expected})")
        print(f"   LEFT-EDGE spread   {summary['left_spread']:>4}px   tol 2   -> "
              f"{'PASS' if summary['left_spread'] <= 2 else 'FAIL'}")
        print(f"   HEIGHT spread      {summary['height_spread']:>4}px   tol 1   -> "
              f"{'PASS' if summary['height_spread'] <= 1 else 'FAIL'}")
        print(f"   WIDTH spread       {summary['width_spread']:>4}px   tol 2   -> "
              f"{'PASS' if summary['width_spread'] <= 2 else 'FAIL'}")
        print(f"   PITCH {summary['pitches']} spread {summary['pitch_spread']}px  tol 2   -> "
              f"{'PASS' if summary['pitch_spread'] <= 2 else 'FAIL'}")
    return fails
