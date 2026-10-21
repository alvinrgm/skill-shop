#!/usr/bin/env python3
"""Zone-binding QA — the type-layer instrument set.

THE GOVERNING RULE: every zone is COMPUTED from the render, never
hand-typed. Type zones declared as literal rectangles copied from batch.json are the
LAYOUT BOX (the CSS column), not the INK: a defect sitting just outside a hand-typed box
gets the ad certified clean. Here the script is handed images and finds the ink itself: if a glyph moves 1px,
every number moves with it.

Covers: per-element WCAG on exclusive ink, DOM collisions cross-checked against pixels,
law-4 headline scale, whole-canvas flatness, pack print cap-heights, render-minus-plate
ink derivation, ink-halo flatness cells, the lit-ground rule, and per-block WCAG against
the plate ground.

TWO INK-DERIVATION MODES:

  (a) render minus plate/scene   — the ad is type over a photograph. ink = |render - plate|
  (b) render vs a declared field — the ad is flat ink on a flat field. ink = |render - field|

plus, in either mode, optional subtraction of a photograph's own alpha silhouette, so the
type checks never swallow the photo and the flatness check never measures it.

Nothing returns a scalar average. Every method returns a dict and appends human-readable
strings to `.fails`; a caller that wants a verdict reads `len(qa.fails)`.
"""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
from PIL import Image

_HERE = Path(__file__).resolve().parent
# the folder is kebab-case (`loop-engine`), so it is not importable as a package; these
# modules are script-style and put their own directory and the skill root on sys.path.
for _p in (str(_HERE), str(_HERE.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import config  # noqa: E402
from common import bands, contrast, components, dilate, hex2rgb, lum  # noqa: E402


# ---- calibrated constants, carried over verbatim ----------------------------
INK_DELTA = 26        # per-pixel channel-SUM difference that counts as ink
CLOSE_X, CLOSE_Y = 44, 26   # block-merge kernel: merges glyphs+lines, keeps blocks apart
MIN_INK_PX = 60       # components smaller than this are render noise
LIT = 110             # plate luminance above which ground counts as "lit"
HALO = 12             # px dilation of the ink footprint = the ground a reader sees
GUTTER = 8            # minimum gutter between two logical elements
FLAT_CELL_GATE = 16.0  # law 21: max luminance range inside one ink-halo cell
FLAT_FIELD_GATE = 1.0  # law 21: max background range on a declared flat field
LAW4_LO, LAW4_HI = 10.0, 14.0   # headline x-height as % of canvas height
PACK_CAP_FLOOR = 8.5  # rendered cap-height floor for print inside a photographed pack

# SAMPLING NOTE: a looser band-differencing variant uses `|render - scene|.mean(2) > 22`,
# i.e. a channel-SUM threshold of 66, against the 26 used here. That value is available
# as ink_delta=66 for anyone re-running that band-differencing exactly. No threshold
# was moved.


def _as_rgb_array(x):
    if isinstance(x, np.ndarray):
        return x.astype(int)
    im = x if isinstance(x, Image.Image) else Image.open(x)
    return np.asarray(im.convert("RGB")).astype(int)


class ZoneQA:
    """Bind every zone to the measured ink of one render.

    final       path / PIL Image / HxWx3 array of the DELIVERED ad
    plate       the untouched plate or scene the type was laid over (mode a)
    field       declared flat field colour, "#RRGGBB" or an rgb triple (mode b)
    photo       an RGBA image (path/Image) or a bool mask: a photograph living IN the ad
                whose own pixels must not be counted as type ink
    photo_at    (x, y) placement of that photograph on the canvas
    """

    def __init__(self, final, *, plate=None, field=None, photo=None, photo_at=(0, 0),
                 margin=config.MARGIN, bottom_safe=config.BOTTOM_SAFE,
                 fold_frac=config.FOLD_FRAC, ink_delta=INK_DELTA, verbose=True):
        if (plate is None) == (field is None):
            raise ValueError("give exactly one of plate= (mode a) or field= (mode b)")
        self.fa = _as_rgb_array(final)
        self.H, self.W = self.fa.shape[:2]
        self.margin = margin
        self.bottom_safe = bottom_safe
        self.fold = int(self.H * fold_frac)
        self.verbose = verbose
        self.fails: list[str] = []
        self.result: dict = {"canvas": [self.W, self.H], "fold": self.fold}

        if plate is not None:
            self.pa = _as_rgb_array(plate)
            if self.pa.shape != self.fa.shape:
                raise ValueError(f"plate {self.pa.shape} != render {self.fa.shape}")
            self.field = None
            self.mode = "render-minus-plate"
            self.diff_all = np.abs(self.fa - self.pa).sum(2)
        else:
            self.pa = None
            self.field = hex2rgb(field) if isinstance(field, str) else np.asarray(field, int)
            self.mode = "render-vs-field"
            self.diff_all = np.abs(self.fa - self.field).sum(2)

        self.all_ink = self.diff_all > ink_delta

        # the photograph's own silhouette, grown 3px so its antialiased matte does not
        # leak into the type mask
        self.photo = np.zeros((self.H, self.W), dtype=bool)
        self.photo_soft_frac = None
        if photo is not None:
            self._set_photo(photo, photo_at)
        self.ink = self.all_ink & ~dilate(self.photo, 3, 3)

        self.result["mode"] = self.mode
        self.result["ink_px"] = int(self.ink.sum())
        self.result["all_ink_px"] = int(self.all_ink.sum())
        self._blocks = None

        if verbose:
            print(f"ink derivation: {self.mode}  (delta {ink_delta}, channel sum)")
            print(f"   all non-field pixels {int(self.all_ink.sum())}  ->  type ink "
                  f"{int(self.ink.sum())} after removing the photograph's silhouette")

    # ------------------------------------------------------------------ setup
    def _set_photo(self, photo, at):
        if isinstance(photo, np.ndarray) and photo.dtype == bool:
            self.photo = photo
            return
        im = photo if isinstance(photo, Image.Image) else Image.open(photo)
        a = np.array(im.convert("RGBA"))[..., 3]
        x, y = int(at[0]), int(at[1])
        ph, pw = a.shape
        y1, x1 = min(self.H, y + ph), min(self.W, x + pw)
        self.photo[y:y1, x:x1] = a[:y1 - y, :x1 - x] > 8
        # a real photographic matte carries soft alpha; a hard 0% is the cutout tell
        soft = ((a > 8) & (a < 247)).mean()
        self.photo_soft_frac = float(soft)
        self.result["photo"] = {"at": [x, y], "plate_size": [pw, ph],
                                "canvas_px": int(self.photo.sum()),
                                "soft_edge_alpha_frac": round(float(soft), 4)}
        if self.verbose:
            print(f"   photo placed at x{x} y{y}, plate {pw}x{ph}; canvas crops "
                  f"{max(0, x + pw - self.W)}px off the right and "
                  f"{max(0, y + ph - self.H)}px off the bottom")
            print(f"   matte: {100 * soft:.2f}% soft-edge alpha "
                  f"(a hard 0% is the cutout tell)")

    # ------------------------------------------------------------ ink geometry
    @property
    def blocks(self):
        if self._blocks is None:
            self.find_blocks()
        return self._blocks

    def find_blocks(self, close_x=CLOSE_X, close_y=CLOSE_Y, min_px=MIN_INK_PX):
        """Merge glyphs and lines into type BLOCKS, then band each block into lines.

        Every bbox below is measured, none is hand-typed.
        """
        closed = dilate(self.ink, close_x, close_y)
        labels, ids = components(closed)
        blocks = []
        for cid in ids:
            sel = (labels == cid) & self.ink
            n = int(sel.sum())
            if n < min_px:
                continue
            ys, xs = np.where(sel)
            blocks.append({"bbox": (int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())),
                           "px": n, "mask": sel})
        blocks.sort(key=lambda b: (b["bbox"][1], b["bbox"][0]))
        for i, b in enumerate(blocks, 1):
            b["name"] = f"block{i}"
            x0, y0, x1, y1 = b["bbox"]
            b["lines"] = bands(b["mask"][y0:y1 + 1, x0:x1 + 1].any(1))
            b["cap"] = int(np.median([e - s + 1 for s, e in b["lines"]])) if b["lines"] else 0
        self._blocks = blocks
        self.result["blocks"] = [{"name": b["name"], "bbox": list(b["bbox"]), "px": b["px"],
                                  "lines": len(b["lines"]), "cap": b["cap"]} for b in blocks]
        if self.verbose:
            print("\nTYPE BLOCKS — every zone MEASURED, none hand-typed")
            print(f"   merge kernel +-{close_x}x{close_y}  ->  {len(blocks)} block(s)")
            for b in blocks:
                x0, y0, x1, y1 = b["bbox"]
                print(f"   {b['name']:8s} x{x0:4d}..{x1:4d}  y{y0:4d}..{y1:4d}  "
                      f"({x1-x0+1:4d}x{y1-y0+1:4d})  ink {b['px']:6d}px  "
                      f"lines {len(b['lines']):2d}  median line-height {b['cap']}px")
        return blocks

    # -------------------------------------------------------- margins + safe
    def margins(self):
        """Measured on TYPE ink only; a photograph may bleed by design."""
        ys, xs = np.where(self.ink)
        gx0, gy0, gx1, gy1 = int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())
        m = {"left": gx0, "right": self.W - 1 - gx1, "top": gy0, "bottom": self.H - 1 - gy1}
        safe = self.H - self.bottom_safe
        out = {"bbox": [gx0, gy0, gx1, gy1], "margins": m, "safe_line": safe,
               "lowest_ink": gy1, "safe_ok": bool(gy1 <= safe)}
        for k in ("left", "right", "top"):
            if m[k] < self.margin - 2:
                self.fails.append(f"margin {k} = {m[k]}px < {self.margin}px")
        if gy1 > safe:
            self.fails.append("bottom safe zone")
        if self.verbose:
            print("\nMARGINS + BOTTOM SAFE ZONE")
            print(f"   type ink bbox x{gx0}..{gx1}  y{gy0}..{gy1}")
            print(f"   left {m['left']}  right {m['right']}  top {m['top']}  "
                  f"bottom {m['bottom']}   (target >= {self.margin}, law 4)")
            print(f"   lowest TYPE ink y={gy1}  safe line y={safe} -> "
                  f"{'PASS' if out['safe_ok'] else 'FAIL'} ({safe - gy1:+d}px)")
        self.result["margins"] = out
        return out

    # ---------------------------------------------- fold + law-4 headline scale
    def fold_and_headline(self, anchor=None, lead_px=110, law4=(LAW4_LO, LAW4_HI)):
        """Fold band + headline scale as a HARD GATE.

        `anchor` selects the headline's ink. Pass a dict to find it by colour and
        position — {"accent": "<accent hex>", "max_y": 360, "max_x": 700} — and the
        reason why:

            the topmost merged block is NOT necessarily the headline. At the merge
            kernel a quote wall, the brand mark and the attributions can fuse into one
            component, so blocks[0] is not the headline; measuring it can report ~6%
            and fail a law the design actually meets.

        Pass None to fall back to the topmost block, which is correct
        only when the headline is its own component — the caveat is printed, not hidden.
        """
        if anchor:
            acc = hex2rgb(anchor["accent"])
            tol = anchor.get("tol", 90)
            mask = self.ink & (np.abs(self.fa - acc).sum(2) < tol)
            if "max_y" in anchor:
                mask[anchor["max_y"]:, :] = False
            if "min_y" in anchor:
                mask[:anchor["min_y"], :] = False
            if "max_x" in anchor:
                mask[:, anchor["max_x"]:] = False
            if "min_x" in anchor:
                mask[:, :anchor["min_x"]] = False
            how = "accent colour inside a declared search window"
        else:
            b = self.blocks[0]
            mask = b["mask"]
            how = ("topmost merged block — CAVEAT: this is the headline only when the "
                   "headline is its own component")
        ay, ax = np.where(mask)
        if ay.size == 0:
            self.fails.append("headline anchor: no ink matched the anchor spec")
            return {"error": "no anchor ink"}
        hx0, hy0, hx1, hy1 = int(ax.min()), int(ay.min()), int(ax.max()), int(ay.max())
        col = mask[:, hx0:hx0 + lead_px]
        rr = np.flatnonzero(col.any(1))
        xh = int(rr.max() - rr.min() + 1)
        pct = xh / self.H * 100
        law4_ok = law4[0] <= pct <= law4[1]
        fold_ok = hy0 <= self.fold
        above = int(self.ink[:self.fold].sum())
        out = {"how": how, "bbox": [hx0, hy0, hx1, hy1],
               "block_h_pct": round((hy1 - hy0 + 1) / self.H * 100, 2),
               "x_height_px": xh, "x_height_pct": round(pct, 2),
               "law4_range": list(law4), "law4_ok": bool(law4_ok),
               "fold": self.fold, "fold_ok": bool(fold_ok),
               "ink_above_fold_px": above,
               "ink_above_fold_frac": round(above / max(1, int(self.ink.sum())), 4)}
        if not law4_ok:
            self.fails.append(f"law 4: headline scale {pct:.2f}% outside "
                              f"{law4[0]}-{law4[1]}%")
        if not fold_ok:
            self.fails.append("fold: headline starts below the first-encounter band")
        if self.verbose:
            print(f"\nLAW 4 HEADLINE SCALE (a hard gate) + FOLD BAND")
            print(f"   anchor found by: {how}")
            print(f"   anchor ink block {hx1-hx0+1}x{hy1-hy0+1}px "
                  f"= {out['block_h_pct']:.2f}% of canvas height (with descenders/dots)")
            print(f"   anchor x-height band (leading glyph) {xh}px = {pct:.2f}%   "
                  f"law 4 target {law4[0]}-{law4[1]}% -> "
                  f"{'PASS' if law4_ok else 'OUT OF RANGE'}")
            print(f"   fold band = top {self.fold}px. anchor occupies y{hy0}..{hy1} -> "
                  f"{'PASS' if fold_ok else 'FAIL'}")
            print(f"   type ink above the fold: {above}px "
                  f"({out['ink_above_fold_frac']*100:.1f}% of type ink)")
        self.result["headline"] = out
        return out

    # ------------------------------------------------------------- collisions
    def block_collisions(self, gutter=GUTTER):
        """Pairwise on the MERGED blocks, kept HONEST about its
        blind spot: two elements that genuinely touch are merged into one
        component and have no pair to compare, so this test goes quiet exactly when it
        should shout. Use `element_collisions` as well whenever a DOM probe exists.
        """
        hits = []
        for i in range(len(self.blocks)):
            for j in range(i + 1, len(self.blocks)):
                a, c = self.blocks[i]["bbox"], self.blocks[j]["bbox"]
                ox = min(a[2], c[2]) - max(a[0], c[0]) + 1 + 2 * gutter
                oy = min(a[3], c[3]) - max(a[1], c[1]) + 1 + 2 * gutter
                if ox > 0 and oy > 0:
                    hits.append({"a": self.blocks[i]["name"], "b": self.blocks[j]["name"],
                                 "overlap": [int(ox), int(oy)]})
                    self.fails.append(f"collision {self.blocks[i]['name']}/"
                                      f"{self.blocks[j]['name']}")
        if self.verbose:
            print(f"\nCOLLISIONS — merged blocks at a {gutter}px gutter: {len(hits)} hit(s)")
            for h in hits:
                print(f"   ! {h['a']} x {h['b']} overlap {h['overlap'][0]}x{h['overlap'][1]}px")
            if not hits:
                print("   (a pixel-only test cannot see two elements that "
                      "MERGED — run element_collisions too)")
        self.result["block_collisions"] = hits
        return hits

    def element_collisions(self, elements, gutter=GUTTER, pad=3):
        """DOM-element collisions, cross-checked against the pixels.

        Boxes are compared at the LOGICAL-ELEMENT level (the probe tags each span with
        its group). The spans inside one quote line, and the successive lines of one
        paragraph, are kerning and leading — an instrument that reports those as
        collisions has no way left to report a real one.

        Every declared box is also checked to CARRY INK, so the DOM cannot lie either:
        a box with no ink under it is reported as a fail, not silently skipped.
        """
        els = [e for e in elements
               if e.get("cls") != "SCRIPT" and e["w"] > 2 and e["h"] > 2]
        groups: dict[str, dict] = {}
        checked = 0
        for e in els:
            x0, y0 = int(e["x"]), int(e["y"])
            x1b, y1b = int(e["x"] + e["w"]), int(e["y"] + e["h"])
            # PAD of 3px, not 6: the wall's leading is ~11px, so a 6px search pad reaches
            # into the NEXT line's ink and every adjacent pair then reports a negative
            # gutter. The pad exists to catch antialiasing, nothing more.
            sub = self.ink[max(0, y0 - pad):y1b + pad, max(0, x0 - pad):x1b + pad]
            if sub.sum() == 0:
                self.fails.append(f"declared element {e.get('cls')} has no ink under it")
                if self.verbose:
                    print(f"   ! DOM says {e.get('cls')} at ({x0},{y0}) but there is no "
                          f"type ink there")
                continue
            checked += 1
            xs5 = np.flatnonzero(sub.any(0))
            ys5 = np.flatnonzero(sub.any(1))
            box = (max(0, x0 - pad) + int(xs5.min()), max(0, y0 - pad) + int(ys5.min()),
                   max(0, x0 - pad) + int(xs5.max()), max(0, y0 - pad) + int(ys5.max()))
            key = e.get("group", e.get("cls"))
            g = groups.setdefault(key, {"g": key, "text": "", "ix0": box[0], "iy0": box[1],
                                        "ix1": box[2], "iy1": box[3]})
            g["ix0"] = min(g["ix0"], box[0]); g["iy0"] = min(g["iy0"], box[1])
            g["ix1"] = max(g["ix1"], box[2]); g["iy1"] = max(g["iy1"], box[3])
            if len(e.get("text", "")) > len(g["text"]):
                g["text"] = e.get("text", "")
        real = list(groups.values())
        worst, wpair, hits = 10 ** 6, None, []
        for i in range(len(real)):
            for j in range(i + 1, len(real)):
                a, b = real[i], real[j]
                gx = max(a["ix0"] - b["ix1"], b["ix0"] - a["ix1"]) - 1
                gy = max(a["iy0"] - b["iy1"], b["iy0"] - a["iy1"]) - 1
                g = max(gx, gy)
                if g < worst:
                    worst, wpair = g, (a, b)
                if g < gutter:
                    hits.append({"a": a["g"], "b": b["g"], "gutter": int(g)})
                    self.fails.append(f"element gutter {a['g']}/{b['g']} = {g}px < {gutter}px")
        out = {"spans": len(els), "spans_with_ink": checked, "logical_elements": len(real),
               "tightest": int(worst) if wpair else None, "gutter_min": gutter, "hits": hits}
        if self.verbose:
            print(f"\nCOLLISIONS — DOM element boxes, cross-checked against the pixels")
            print(f"   {checked}/{len(els)} declared spans carry measured ink, forming "
                  f"{len(real)} logical elements")
            for h in hits:
                print(f"   ! {h['a']} x {h['b']} -> {h['gutter']}px gutter")
            if wpair:
                a, b = wpair
                print(f"   tightest element pair: {a['g']} {a['text'][:22]!r} / {b['g']} "
                      f"{b['text'][:22]!r} = {worst}px (min {gutter}) -> "
                      f"{'PASS' if worst >= gutter else 'FAIL'}")
        self.result["element_collisions"] = out
        return out

    def photo_collisions(self, gutter=GUTTER):
        """Type vs the photograph — the collision the DOM cannot see, because the photo
        is an image whose real edge is its alpha, not its box."""
        over = int((self.ink & self.photo).sum())
        if over:
            self.fails.append(f"{over}px of type ink overlaps the photograph")
        gaps = []
        for y in range(self.H):
            r_ink = np.flatnonzero(self.ink[y])
            r_pa = np.flatnonzero(self.photo[y])
            if len(r_ink) and len(r_pa):
                g = int(r_pa.min() - r_ink.max() - 1)
                if g >= 0:
                    gaps.append((g, y))
        tight = min(gaps) if gaps else None
        if tight and tight[0] < gutter:
            self.fails.append(f"type-to-photo gutter {tight[0]}px at y{tight[1]}")
        out = {"overlap_px": over, "tightest_gutter": tight[0] if tight else None,
               "at_y": tight[1] if tight else None}
        if self.verbose:
            print(f"   type ink INSIDE the photo silhouette: {over}px -> "
                  f"{'PASS' if over == 0 else 'FAIL'}")
            if tight:
                print(f"   tightest type-to-photo gutter: {tight[0]}px at y{tight[1]} "
                      f"(min {gutter}) -> {'PASS' if tight[0] >= gutter else 'FAIL'}")
        self.result["photo_collisions"] = out
        return out

    # ------------------------------------------------------------------ WCAG
    def wcag_lines(self):
        """PER LINE, not per merged block.

        A merge kernel grouping sixteen lines returns one number dominated by whichever
        line carries the most ink: an eyebrow, attributions and a compliance microtype
        all sat at 3.6:1 inside a block certified at 11.98:1.

        LIMIT of this test, found by trying to trust it: attributions sit on the SAME
        horizontal band as their quote, so a row-band average is dominated by the
        quote's ink and certifies a 10px attribution it never measured — per-BLOCK
        laundering became per-LINE laundering. `wcag_elements` is the instrument the
        line test needed.
        """
        if self.field is None:
            raise ValueError("wcag_lines measures against a declared flat field; "
                             "in plate mode use wcag_blocks_vs_plate()")
        rows = []
        for b in self.blocks:
            x0, y0, x1b, y1b = b["bbox"]
            for (s, e) in b["lines"]:
                ly0, ly1 = y0 + s, y0 + e
                sel = b["mask"].copy()
                sel[:ly0] = False
                sel[ly1 + 1:] = False
                if sel.sum() < 30:
                    continue
                d = self.diff_all[sel]
                core = sel.copy()
                core[sel] = d >= np.percentile(d, 75)
                rgb = self.fa[core].mean(0)
                c = contrast(rgb, self.field)
                hgt = ly1 - ly0 + 1
                xs3 = np.flatnonzero(sel.any(0))
                need = 3.0 if hgt >= 24 else 4.5
                ok = c >= need
                if not ok:
                    self.fails.append(f"WCAG {b['name']} line y{ly0}..{ly1} "
                                      f"{c:.2f}:1 < {need}:1")
                rows.append({"block": b["name"], "y0": ly0, "y1": ly1, "h": hgt,
                             "x0": int(xs3.min()), "x1": int(xs3.max()),
                             "rgb": [round(float(v)) for v in rgb],
                             "ratio": round(c, 2), "need": need, "ok": bool(ok)})
                if self.verbose:
                    print(f"   {b['name']:7s} y{ly0:4d}..{ly1:4d} h{hgt:3d}  "
                          f"x{xs3.min():4d}..{xs3.max():4d}  "
                          f"core {str(np.round(rgb,0)):>20s}  {c:6.2f}:1  need {need} -> "
                          f"{'PASS' if ok else 'FAIL'}")
        if self.verbose:
            print(f"   {len(rows)} lines measured individually")
        self.result["wcag_lines"] = rows
        return rows

    def wcag_elements(self, elements):
        """PER DECLARED ELEMENT, on its OWN EXCLUSIVE INK — the instrument the line test
        needed. An element's exclusive ink is its own box minus the boxes of any elements
        nested inside it, so a parent never inherits its children's contrast.
        """
        if self.field is None:
            raise ValueError("wcag_elements measures against a declared flat field")
        els = [e for e in elements
               if e.get("cls") != "SCRIPT" and e["w"] > 2 and e["h"] > 2]

        def boxof(e):
            return (int(e["x"]) - 2, int(e["y"]) - 2,
                    int(e["x"] + e["w"]) + 2, int(e["y"] + e["h"]) + 2)

        def inside(a, b):   # a strictly inside b, and a is not b
            ax0, ay0, ax1, ay1 = boxof(a); bx0, by0, bx1, by1 = boxof(b)
            return (a is not b and ax0 >= bx0 and ay0 >= by0 and ax1 <= bx1 and ay1 <= by1
                    and (ax1 - ax0) * (ay1 - ay0) < (bx1 - bx0) * (by1 - by0))

        rows = []
        if self.verbose:
            print(f"\nWCAG — PER DECLARED ELEMENT (on its own exclusive ink)")
            print(f"   {'element':10s} {'text':34s} {'px':>5} {'core rgb':>18} "
                  f"{'ratio':>8} {'need':>5}  verdict")
        for e in els:
            x0, y0, x1b, y1b = boxof(e)
            sel = np.zeros_like(self.ink)
            sel[max(0, y0):y1b, max(0, x0):x1b] = self.ink[max(0, y0):y1b, max(0, x0):x1b]
            for o in els:
                if inside(o, e):
                    ox0, oy0, ox1, oy1 = boxof(o)
                    sel[max(0, oy0):oy1, max(0, ox0):ox1] = False
            if sel.sum() < 25:
                continue
            d = self.diff_all[sel]
            core = sel.copy()
            core[sel] = d >= np.percentile(d, 75)
            rgb = self.fa[core].mean(0)
            c = contrast(rgb, self.field)
            size = float(str(e["size"]).replace("px", ""))
            bold = int(e["weight"]) >= 700
            need = 3.0 if (size >= 24 or (bold and size >= 18.66)) else 4.5
            ok = c >= need
            if not ok:
                self.fails.append(f"WCAG element {e.get('cls')} {e.get('text','')[:24]!r} "
                                  f"{c:.2f}:1 < {need}:1")
            rows.append({"cls": e.get("cls"), "text": e.get("text", ""),
                         "px": int(sel.sum()), "rgb": [round(float(v)) for v in rgb],
                         "ratio": round(c, 2), "need": need, "ok": bool(ok)})
            if self.verbose:
                print(f"   {str(e.get('cls'))[:10]:10s} {e.get('text','')[:34]:34s} "
                      f"{int(sel.sum()):5d} {str(np.round(rgb,0)):>18} {c:8.2f} "
                      f"{need:5.1f}  {'PASS' if ok else 'FAIL'}")
        if self.verbose:
            print(f"   {len(rows)} declared elements measured on their own exclusive ink")
        self.result["wcag_elements"] = rows
        return rows

    def wcag_blocks_vs_plate(self):
        """Plate mode: measured ink colour vs the ground under the MEASURED footprint.

        Both sides are measured. The gate is the WORST ground the glyphs actually cover
        (its brightest percentile), not the mean — a mean launders a bright patch.
        """
        if self.pa is None:
            raise ValueError("wcag_blocks_vs_plate needs plate mode")
        rows = []
        if self.verbose:
            print("\nWCAG — measured ink colour vs the ground under the MEASURED footprint")
        for b in self.blocks:
            sel = b["mask"]
            ink_rgb = self.fa[sel].mean(0)
            ground = self.pa[sel]
            gl = lum(ground)
            bright = ground[gl >= np.percentile(gl, 99)].mean(0)
            mean_g = ground.mean(0)
            cw = contrast(ink_rgb, bright)
            cm = contrast(ink_rgb, mean_g)
            need = 3.0 if b["cap"] >= 24 else 4.5
            ok = cw >= need
            if not ok:
                self.fails.append(f"WCAG: {b['name']} {cw:.2f}:1 < {need}:1")
            rows.append({"block": b["name"], "ink_rgb": [round(float(v)) for v in ink_rgb],
                         "worst_ground": round(cw, 2), "mean_ground": round(cm, 2),
                         "need": need, "ok": bool(ok)})
            if self.verbose:
                print(f"   {b['name']:8s} ink rgb {ink_rgb.round(0)}  "
                      f"worst-ground {cw:5.2f}:1  mean-ground {cm:5.2f}:1  "
                      f"need {need}:1 -> {'PASS' if ok else 'FAIL'}")
        self.result["wcag_blocks"] = rows
        return rows

    # -------------------------------------------------------- law 21 flatness
    def flatness_halo(self, cell_h=67, cell_w=88, gate=FLAT_CELL_GATE, halo=HALO):
        """Law 21, ink-halo form. Flat ink needs flat ground — INCLUDING
        under the chrome.

        The gating measure is cells over the ink footprint dilated `halo`px: the ground
        a reader actually sees behind the glyphs. Whole-bbox range is ALSO printed and
        is NOT the gate — a merged block's bbox contains empty gaps whose gradient no
        glyph ever sits on.
        """
        if self.pa is None:
            raise ValueError("flatness_halo measures the plate's ground; needs plate mode")
        pl = lum(self.pa)
        n = over = 0
        worst = 0.0
        rows = []
        if self.verbose:
            print("\nLAW 21 — ground flatness under and around the MEASURED INK ITSELF")
        for b in self.blocks:
            x0, y0, x1, y1 = b["bbox"]
            h = dilate(b["mask"], halo, halo)
            cells = []
            for yy in range(y0, y1 + 1, cell_h):
                for xx in range(x0, x1 + 1, cell_w):
                    m = h[yy:min(yy + cell_h, y1 + 1), xx:min(xx + cell_w, x1 + 1)]
                    c = pl[yy:min(yy + cell_h, y1 + 1), xx:min(xx + cell_w, x1 + 1)]
                    if m.sum() >= 0.25 * m.size:
                        v = c[m]
                        cells.append(v.max() - v.min())
            cells = np.array(cells) if cells else np.array([0.0])
            n += len(cells)
            over += int((cells > gate).sum())
            worst = max(worst, float(cells.max()))
            box = pl[y0:y1 + 1, x0:x1 + 1]
            rows.append({"block": b["name"], "whole_box_range": round(float(box.max() - box.min()), 1),
                         "cells": len(cells), "max": round(float(cells.max()), 1),
                         "mean": round(float(cells.mean()), 1),
                         "over_gate": int((cells > gate).sum())})
            if self.verbose:
                print(f"   {b['name']:8s} whole-box range {box.max()-box.min():6.1f} "
                      f"(not the gate) | ink-halo cells n={len(cells):2d} "
                      f"max={cells.max():5.1f} mean={cells.mean():5.1f} "
                      f"over-{int(gate)}={(cells > gate).sum()}")
        if over:
            self.fails.append(f"law 21: {over} ink-halo cell(s) over {int(gate)} levels")
        out = {"cells": n, "over": over, "worst": round(worst, 1), "gate": gate,
               "per_block": rows}
        if self.verbose:
            print(f"   VERDICT: {n-over}/{n} ink-halo cells under {int(gate)}; "
                  f"worst {worst:.1f}")
        self.result["flatness_halo"] = out
        return out

    def flatness_field(self, gate=FLAT_FIELD_GATE, ink_grow=14, photo_grow=20):
        """Law 21, whole-canvas form. On a declared flat field the honest
        number is the background luminance RANGE outside the type and outside any
        photograph: 0.00 levels = one flat field, and that measurement is what makes the
        whole composite-physics failure family
        structurally unreachable — proof rather than claim.
        """
        bg_mask = ~dilate(self.ink, ink_grow, ink_grow) & ~dilate(self.photo, photo_grow, photo_grow)
        bg = lum(self.fa)[bg_mask]
        rng = float(bg.max() - bg.min())
        ok = rng <= gate
        if not ok:
            self.fails.append(f"law 21: ground is not flat ({rng:.2f} levels)")
        out = {"range": round(rng, 2), "gate": gate, "ok": bool(ok),
               "sampled_px": int(bg_mask.sum())}
        if self.verbose:
            print(f"\nLAW 21 — background luminance range across the whole canvas, "
                  f"outside the type and outside the photograph:")
            print(f"   {rng:.2f} levels (0.00 = one flat field)  -> "
                  f"{'PASS' if ok else 'FAIL'}")
        self.result["flatness_field"] = out
        return out

    # -------------------------------------------------------- lit-ground rule
    def lit_ground(self, lit=LIT):
        """No ink over anything lit (e.g. a letter over a lit fingertip, mechanised). Requires plate mode."""
        if self.pa is None:
            raise ValueError("lit_ground measures the plate's ground; needs plate mode")
        pl = lum(self.pa)
        rows = []
        if self.verbose:
            print(f"\nNO INK OVER ANYTHING LIT (plate luminance > {lit})")
        for b in self.blocks:
            g = pl[b["mask"]]
            pct = float((g > lit).mean() * 100)
            ok = pct == 0.0
            if not ok:
                self.fails.append(f"lit ground: {b['name']} {pct:.2f}% of ink over lum>{lit}")
            rows.append({"block": b["name"], "max": round(float(g.max()), 1),
                         "mean": round(float(g.mean()), 1),
                         "p99": round(float(np.percentile(g, 99)), 1),
                         "over_lit_pct": round(pct, 2), "ok": bool(ok)})
            if self.verbose:
                print(f"   {b['name']:8s} ground under ink: max {g.max():5.1f}  "
                      f"mean {g.mean():5.1f}  p99 {np.percentile(g,99):5.1f}  "
                      f"over-{lit} {pct:5.2f}% -> {'PASS' if ok else 'FAIL'}")
        self.result["lit_ground"] = rows
        return rows

    # ------------------------------------------------------------- law 29
    def never_enlarge(self, items):
        """Law 29: an asset may be downsampled, never enlarged past its native pixels.

        items: [(name, native_w, rendered_w), ...]

        PRESENTATION CHANGE: this can be expressed two ways — the mark as
        rendered/native (fail > 1.0) and the pack as native/rendered (fail < 1.0). Both
        are the same test inverted; it is normalised here to enlargement = rendered/native
        and the downsample factor is reported alongside. The gate value did not move.
        """
        rows = []
        if self.verbose:
            print("\nLAW 29 — never enlarge")
        for name, native_w, rendered_w in items:
            enlargement = rendered_w / float(native_w)
            ok = enlargement <= 1.0
            if not ok:
                self.fails.append(f"law 29: {name} enlarged past its native resolution "
                                  f"({enlargement:.3f}x)")
            rows.append({"name": name, "native_w": native_w, "rendered_w": rendered_w,
                         "enlargement": round(enlargement, 4),
                         "downsample": round(1.0 / enlargement, 4) if enlargement else None,
                         "ok": bool(ok)})
            if self.verbose:
                print(f"   {name:28s} native {native_w} -> rendered {rendered_w}px = "
                      f"{enlargement:.4f}x  (downsample {1.0/enlargement:.4f}x)  "
                      f"{'OK' if ok else 'ENLARGED — LAW 29 FAIL'}")
        self.result["never_enlarge"] = rows
        return rows

    # ------------------------------------------------- accent / type families
    def accent_discipline(self, accent_hex, ink_hex=None, families=None,
                          expect_families=None, tol=40):
        """Law 14: one accent, used as one system.

        Counts core accent pixels and core body-ink pixels inside the TYPE ink only, and
        reports where the accent lives. A brand mark's own identity colour and a
        photographed pack's own printed band are inside reproduced brand assets (law 8,
        label fidelity) — they are not palette additions, which is why this measures the
        type layer and not the canvas.
        """
        accent = hex2rgb(accent_hex)
        pxs = self.fa[self.ink]
        n_acc = int((np.abs(pxs - accent).sum(1) < tol).sum())
        n_ink = None
        if ink_hex:
            n_ink = int((np.abs(pxs - hex2rgb(ink_hex)).sum(1) < tol).sum())
        sel = self.ink & (np.abs(self.fa - accent).sum(2) < tol)
        ys, xs = np.where(sel)
        out = {"accent": accent_hex, "accent_core_px": n_acc, "ink_core_px": n_ink,
               "accent_bbox": [int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]
               if xs.size else None}
        if families is not None:
            out["families"] = families
            out["n_families"] = len(families)
            if expect_families is not None and len(families) != expect_families:
                self.fails.append(f"type families = {len(families)}, "
                                  f"declared {expect_families}")
        if self.verbose:
            print("\nLAW 14 — one accent, used as one system")
            print(f"   accent {accent_hex}: {n_acc:6d} core px" +
                  (f"   ink {ink_hex}: {n_ink:6d} core px" if n_ink is not None else ""))
            if out["accent_bbox"]:
                b = out["accent_bbox"]
                print(f"   accent type ink lives at x{b[0]}..{b[2]}  y{b[1]}..{b[3]}")
            if families is not None:
                print(f"   type families, counted by resolved metrics: {families}  -> "
                      f"DISTINCT = {len(families)}")
        self.result["accent"] = out
        return out

    # ---------------------------------------------------------- pack print
    def pack_print(self, spec, ratio, at, plate_size, floor=PACK_CAP_FLOOR):
        """Cap-height of the print ON a photographed package, measured on the SHIPPED
        pixels.

        spec        [(name, native_cap_px, native_y0, native_y1), ...] — the native
                    cap-heights measured on the source pack shot, with the plate-space
                    y band each one lands in
        ratio       native / rendered width, i.e. the downsample `s` the pack is at
        at          (x, y) placement on the canvas
        plate_size  (w, h) of the placed plate

        Anything whose rendered cap falls below `floor` is a FAIL — the kill:
        downsampling real detail past legibility reads as AI garble, and authenticity is
        re-earned at render scale, never inherited from the source file. The honest fix
        is a crop that removes the small print, never a shrink that keeps it.
        """
        px, py = int(at[0]), int(at[1])
        pw, ph = int(plate_size[0]), int(plate_size[1])
        rows = []
        if self.verbose:
            print("\nTHE PACK — real photograph, print measured on the shipped pixels")
            print(f"   {'element':32s} {'native cap':>10} {'predicted':>10} "
                  f"{'MEASURED':>9}  verdict")
        for name, cap_native, ny0, ny1 in spec:
            pred = cap_native / ratio
            cy0 = py + int(ny0 / ratio)
            cy1 = py + int(ny1 / ratio)
            strip = self.fa[max(0, cy0 - 2):cy1 + 2, px:min(self.W, px + pw)]
            msk = self.photo[max(0, cy0 - 2):cy1 + 2, px:min(self.W, px + pw)]
            L = strip.sum(2)
            if msk.sum() < 50:
                rows.append({"name": name, "native_cap": cap_native,
                             "predicted": round(pred, 2), "measured": None,
                             "ok": True, "note": "out of frame"})
                if self.verbose:
                    print(f"   {name:32s} {cap_native:10d} {pred:10.2f}   (out of frame)")
                continue
            med = np.median(L[msk])
            dark = (L < med - 72) & msk
            caps = []
            win = max(12, int(60 / ratio))
            for xw in range(0, strip.shape[1] - win, win):
                wsel = dark[:, xw:xw + win]
                rr2 = np.flatnonzero(wsel.sum(1) > 1)
                if len(rr2) > 2:
                    caps.append(rr2.max() - rr2.min() + 1)
            meas = float(np.median(caps)) if caps else 0.0
            ok = meas >= floor - 0.6
            if not ok:
                self.fails.append(f"pack print '{name.strip()}' renders at {meas:.1f}px cap "
                                  f"(floor {floor})")
            rows.append({"name": name, "native_cap": cap_native, "predicted": round(pred, 2),
                         "measured": round(meas, 1), "ok": bool(ok)})
            if self.verbose:
                print(f"   {name:32s} {cap_native:10d} {pred:10.2f} {meas:9.1f}  "
                      f"{'PASS' if ok else 'FAIL'}")
        if self.verbose:
            print(f"   floor {floor}px rendered cap. Anything below it must be CROPPED OUT "
                  f"by the frame, not shrunk.")
        self.result["pack_print"] = {"ratio": ratio, "floor": floor, "rows": rows}
        return rows

    # ---------------------------------------------------------------- verdict
    def verdict(self):
        if self.verbose:
            print("\n" + "=" * 78)
            if self.fails:
                print(f"FAILS ({len(self.fails)}):")
                for f in self.fails:
                    print("  -", f)
            else:
                print("NO FAILS.")
            print("=" * 78)
        return self.result, self.fails
