#!/usr/bin/env python3
"""Shared primitives used by every instrument in this package. One implementation each.

numpy + Pillow ONLY. No scipy is required, deliberately: `dilate` is a cumulative-sum box dilation and `components` is a
two-pass run-length labeller. Both workarounds are kept.
"""
from __future__ import annotations

import numpy as np


# ---------------------------------------------------------------- luminance / WCAG
def lum(a):
    """Rec.709 luminance of an HxWx3 array, in 0-255 levels."""
    a = a.astype(float)
    return 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]


def srgb_lin(c):
    c = np.asarray(c, dtype=float) / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def rel_lum(rgb):
    """WCAG relative luminance. Accepts a single rgb triple or an Nx3 array."""
    a = srgb_lin(rgb)
    if a.ndim == 1:
        r, g, b = a
        return 0.2126 * r + 0.7152 * g + 0.0722 * b
    return 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]


def contrast(fg, bg):
    """WCAG contrast ratio between two rgb triples."""
    a, b = float(rel_lum(fg)), float(rel_lum(bg))
    hi, lo = max(a, b), min(a, b)
    return (hi + 0.05) / (lo + 0.05)


def hex2rgb(h):
    h = str(h).lstrip("#")
    return np.array([int(h[i:i + 2], 16) for i in (0, 2, 4)], dtype=int)


# ---------------------------------------------------------------- morphology
def dilate(mask, kx, ky):
    """Box dilation via cumulative sums — no scipy on this machine."""
    m = mask.astype(np.uint8)
    pad = np.pad(m, ((ky, ky), (kx, kx)))
    cs = pad.cumsum(0).cumsum(1)
    cs = np.pad(cs, ((1, 0), (1, 0)))
    h, w = mask.shape
    y0 = np.arange(h)[:, None]
    x0 = np.arange(w)[None, :]
    y1 = y0 + 2 * ky + 1
    x1 = x0 + 2 * kx + 1
    tot = cs[y1, x1] - cs[y0, x1] - cs[y1, x0] + cs[y0, x0]
    return tot > 0


def components(mask):
    """Two-pass run-length connected components (8-connected), pure numpy/python.

    Returns (labels, ids) where labels is an int32 HxW array of 1-based component ids.
    """
    h, w = mask.shape
    parent = {}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    labels = np.zeros((h, w), dtype=np.int32)
    nxt = 1
    for y in range(h):
        row = mask[y]
        if not row.any():
            continue
        xs = np.flatnonzero(row)
        # split into runs
        splits = np.flatnonzero(np.diff(xs) > 1)
        starts = np.concatenate(([0], splits + 1))
        ends = np.concatenate((splits, [len(xs) - 1]))
        for s, e in zip(starts, ends):
            x0, x1 = xs[s], xs[e]
            above = labels[y - 1, max(0, x0 - 1):x1 + 2] if y else np.zeros(0, dtype=np.int32)
            neigh = np.unique(above[above > 0])
            if len(neigh) == 0:
                lab = nxt
                parent[lab] = lab
                nxt += 1
            else:
                lab = int(neigh[0])
                for n in neigh[1:]:
                    union(lab, int(n))
            labels[y, x0:x1 + 1] = lab
    if nxt == 1:
        return labels, []
    remap, out_ids = {}, []
    for lab in range(1, nxt):
        r = find(lab)
        if r not in remap:
            remap[r] = len(remap) + 1
            out_ids.append(remap[r])
        remap[lab] = remap[r]
    lut = np.zeros(nxt, dtype=np.int32)
    for lab, r in remap.items():
        lut[lab] = r
    return lut[labels], out_ids


def row_bands(rows_any, min_h=1):
    """Row-profile segmentation: runs of True in a 1-D boolean row profile.

    SAMPLING NOTE: the zone QA keeps every run (min_h=1), while the device instrument
    uses min_h=2 to drop single-row noise inside the accent band. The parameter is
    explicit; callers pass the value they need. No threshold moved.
    """
    out, s = [], None
    for i, v in enumerate(rows_any):
        if v and s is None:
            s = i
        elif not v and s is not None:
            if i - s >= min_h:
                out.append((s, i - 1))
            s = None
    if s is not None and len(rows_any) - s >= min_h:
        out.append((s, len(rows_any) - 1))
    return out


def bands(rows_any):
    """min_h=1 alias — the form the zone QA uses for line bands inside a block."""
    return row_bands(rows_any, min_h=1)


# ---------------------------------------------------------------- filtering
def boxblur(a, r):
    """Separable box blur by cumulative sums, edge-padded."""
    if r < 1:
        return a
    k = 2 * r + 1
    c = np.cumsum(np.pad(a, ((r + 1, r), (0, 0)), mode="edge"), axis=0)
    a = (c[k:] - c[:-k]) / k
    c = np.cumsum(np.pad(a, ((0, 0), (r + 1, r)), mode="edge"), axis=1)
    return (c[:, k:] - c[:, :-k]) / k


def red_mask(rgb, loose=False):
    """Saturated-red mask used to find a printed brand band on a pack shot.

    R-G is the channel that separates a saturated red band from warm-brown surfaces at
    equal saturation. A saturation-only mask cannot tell them apart.
    """
    R, G, B = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    mx, mn = rgb.max(2), rgb.min(2)
    sat = (mx - mn) / np.maximum(mx, 1)
    if loose:   # extent-measuring mask: includes the band's lighter, sunlit half
        return (R == mx) & (sat > 0.22) & (R > 120) & (R - G > 34) & (G >= B - 20)
    return (R == mx) & (sat > 0.35) & (R > 130) & (R - G > 70) & (G >= B - 20)
