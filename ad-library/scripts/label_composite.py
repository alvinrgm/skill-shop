#!/usr/bin/env python3
"""Label composite repair: replace a generated pack's garbled label with the REAL label.

Image models garble fine print. This warps the real pack's label onto the plate with a thin-plate
spline fitted to SIFT matches on the print the model DID render right (it follows the pack's
curve, which one flat warp cannot), then relights it from the plate and keeps the plate's grain.

usage: label_composite.py <plate.png> <pack-rgba.png> <out.png> <fit.json>
fit.json (one per plate; read the corners off 4-5x zooms with a 10px grid):
  {"pack_region":[x0,y0,x1,y1], "plate_region":[x0,y0,x1,y1], "mask":"panel"|"face", "erode":18,
   "panel_hsv": {"sat_max":130, "val_min":150},   # "panel" mode: what counts as the label panel
   "anchors":[[[px,py],[qx,qy]], ...],            # pack point -> plate point, outline corners
   "cells":[[[4 pack pts TL,TR,BR,BL],[4 plate pts]], ...],   # small boxes the spline cannot resolve
   "occlusion":"auto"|"off", "occluders":[[[x,y],...], ...]}  # things in front of the pack
Modes: "panel" (default) replaces a light, low-saturation label panel (tune panel_hsv for your
pack); "face" replaces the whole printed front of a near-frontal pack (the cutout's alpha).
Needs opencv-python-headless + scipy + numpy (requirements-repair.txt). Afterwards the print gate
(print_gate.py) must pass with wrong=0 before the plate is used in an ad."""
import sys, json
from pathlib import Path
if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
    print(__doc__); sys.exit(0)
if len(sys.argv) < 5:
    print(__doc__, file=sys.stderr); sys.exit(2)
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common  # noqa: E402,F401  (uses the package .venv when there is one)
try:
    import cv2, numpy as np
    from scipy.interpolate import RBFInterpolator
except ImportError as e:
    sys.exit(f"{e}: label_composite.py needs OpenCV + SciPy: .venv/bin/pip install -r requirements-repair.txt")
plate_f, pack_f, out_f, fit_f = sys.argv[1:5]
FIT = json.load(open(fit_f))
plate = cv2.imread(plate_f, cv2.IMREAD_COLOR)
pk = cv2.imread(pack_f, cv2.IMREAD_UNCHANGED)
a = pk[:, :, 3:4] / 255.0; pack = (pk[:, :, :3] * a + 255 * (1 - a)).astype(np.uint8)
px0, py0, px1, py1 = FIT["pack_region"]            # the label panel area on the real pack cutout
sx0, sy0, sx1, sy1 = FIT["plate_region"]           # where the pack's panel sits in the generated plate
P = pack[py0:py1, px0:px1]; S = plate[sy0:sy1, sx0:sx1]
sift = cv2.SIFT_create(nfeatures=6000, contrastThreshold=0.02)
k1, d1 = sift.detectAndCompute(cv2.cvtColor(P, cv2.COLOR_BGR2GRAY), None)
k2, d2 = sift.detectAndCompute(cv2.cvtColor(S, cv2.COLOR_BGR2GRAY), None)
good = [x for x, y in cv2.BFMatcher().knnMatch(d1, d2, k=2) if x.distance < 0.8 * y.distance]
src = np.float32([k1[g.queryIdx].pt for g in good]) + [px0, py0]   # pack
dst = np.float32([k2[g.trainIdx].pt for g in good]) + [sx0, sy0]   # plate
H, inl = cv2.findHomography(src, dst, cv2.RANSAC, 14.0)              # loose: only drops wrong matches
src, dst = src[inl.ravel() == 1], dst[inl.ravel() == 1]
# second pass: keep points a smooth spline agrees with (drops the last outliers)
f0 = RBFInterpolator(dst, src, kernel="thin_plate_spline", smoothing=50.0)
err = np.linalg.norm(f0(dst) - src, axis=1); keep = err < 6
src, dst = src[keep], dst[keep]
print(f"matches {len(good)}, kept {len(src)}")
if len(src) < 40: sys.exit("too few good points: do not trust this fit")
# panel-outline anchors pin the curved side and any area where the model's print was too garbled for SIFT
ANCH = [tuple(map(tuple, a)) for a in FIT.get("anchors", [])]
if ANCH: src = np.vstack([src, [a for a, b in ANCH]]); dst = np.vstack([dst, [b for a, b in ANCH]])
sm = np.r_[np.full(len(src) - len(ANCH), 8.0), np.full(len(ANCH), 0.2)]
f = RBFInterpolator(dst, src, kernel="thin_plate_spline", smoothing=sm)  # plate -> pack
# mask on the pack. "panel" (default): the light label panel (every row, closed, filled, grown over the outline).
# "face": the whole printed front of the pack = the cutout's alpha, eroded so the plate keeps its own pack edges
# and silhouette (use for a near-frontal pack; the spline then carries every printed line from the real pack).
MODE = FIT.get("mask", "panel")
hsv = cv2.cvtColor(pack, cv2.COLOR_BGR2HSV)
PH = FIT.get("panel_hsv", {})
panel = ((hsv[:, :, 1] < PH.get("sat_max", 130)) & (hsv[:, :, 2] > PH.get("val_min", 150))).astype(np.uint8)
reg = np.zeros_like(panel); reg[py0 + 10:py1 - 15, px0 + 15:px1 - 10] = 1; panel &= reg
n, lab, st, _ = cv2.connectedComponentsWithStats(panel)
blob = np.isin(lab, [i for i in range(1, n) if st[i, cv2.CC_STAT_AREA] > 1500]).astype(np.uint8)
blob = cv2.morphologyEx(blob, cv2.MORPH_CLOSE, np.ones((31, 31), np.uint8))
cnts, _ = cv2.findContours(blob, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
mask = np.zeros_like(blob, np.float32); cv2.drawContours(mask, cnts, -1, 1.0, -1)
mask = cv2.dilate(mask, np.ones((13, 13), np.uint8))
if MODE == "face":
    al = (pk[:, :, 3] > 200).astype(np.uint8); reg2 = np.zeros_like(al); reg2[py0:py1, px0:px1] = 1
    mask = cv2.erode(al & reg2, np.ones((2 * FIT.get("erode", 18) + 1,) * 2, np.uint8)).astype(np.float32)
# backward warp over the plate search box
ys, xs = np.mgrid[sy0:sy1, sx0:sx1]; pts = np.stack([xs.ravel(), ys.ravel()], 1).astype(np.float64)
m = f(pts).astype(np.float32); mx = m[:, 0].reshape(xs.shape); my = m[:, 1].reshape(xs.shape)
wp = cv2.remap(pack, mx, my, cv2.INTER_CUBIC, borderValue=(255, 255, 255)).astype(np.float32)
wm = cv2.remap(mask, mx, my, cv2.INTER_LINEAR, borderValue=0)
wm = np.clip(cv2.GaussianBlur(wm, (0, 0), 1.2), 0, 1)
Sf = S.astype(np.float32); hard = (wm > 0.5).astype(np.float32)
def mblur(img, mm, s):
    return cv2.GaussianBlur(img * mm[..., None], (0, 0), s) / np.maximum(cv2.GaussianBlur(mm, (0, 0), s)[..., None], 1e-3)
RS = FIT.get("relight_sigma", 16)
L = mblur(Sf, hard, RS) / np.maximum(mblur(wp, hard, RS), 1)
fix = np.clip(wp * L, 0, 255)
# grain = the plate's high-pass CLIPPED to sensor-noise strength: unclipped, it carried the edges of the
# garbled letters underneath and ghosted them back in
fix = np.clip(fix + np.clip(0.35 * (Sf - cv2.GaussianBlur(Sf, (0, 0), 1.0)), -4, 4), 0, 255)
# OCCLUSION: things in front of the pack (food, a utensil, a towel) must stay in front. Where the plate differs
# from the relit real pack in a SOLID patch (not thin text strokes), keep the plate. "occlusion": "auto" (default
# in face mode), plus optional manual "occluders": [[x,y],...] polygons in plate coordinates.
if FIT.get("occlusion", "auto" if MODE == "face" else "off") == "auto":
    D = np.abs(cv2.GaussianBlur(Sf, (0, 0), 2.0) - cv2.GaussianBlur(fix, (0, 0), 2.0)).mean(axis=2)
    occ = ((D > FIT.get("occlusion_threshold", 38)) & (hard > 0)).astype(np.uint8)
    occ = cv2.morphologyEx(occ, cv2.MORPH_OPEN, np.ones((11, 11), np.uint8))      # drop text-stroke differences
    n_o, lab_o, st_o, _ = cv2.connectedComponentsWithStats(occ)
    occ = np.isin(lab_o, [i for i in range(1, n_o) if st_o[i, cv2.CC_STAT_AREA] > 400]).astype(np.uint8)
    occ = cv2.dilate(occ, np.ones((7, 7), np.uint8)).astype(np.float32)
    print("occlusion px:", int(occ.sum()))
    wm = wm * (1 - np.clip(cv2.GaussianBlur(occ, (0, 0), 1.5), 0, 1))
for poly in FIT.get("occluders", []):
    om = np.zeros_like(wm); cv2.fillPoly(om, [np.int32(poly) - np.int32([sx0, sy0])], 1.0)
    wm = wm * (1 - np.clip(cv2.GaussianBlur(om, (0, 0), 1.5), 0, 1))
out = plate.copy().astype(np.float32)
out[sy0:sy1, sx0:sx1] = Sf * (1 - wm[..., None]) + fix * wm[..., None]
cv2.imwrite(out_f.replace(".png", "-mask.png"), (wm * 255).astype(np.uint8)) if FIT.get("debug") else None
# per-cell patches: small boxes the spline cannot resolve get their own 4-corner perspective warp
h, w = plate.shape[:2]
CELLS = FIT.get("cells", [])  # (pack quad TL,TR,BR,BL) -> (plate quad TL,TR,BR,BL)
for sq, dq in CELLS:
    Hc = cv2.getPerspectiveTransform(np.float32(sq), np.float32(dq))
    cw = cv2.warpPerspective(pack, Hc, (w, h), flags=cv2.INTER_CUBIC).astype(np.float32)
    cm = np.zeros((h, w), np.float32); cv2.fillPoly(cm, [np.int32(dq)], 1.0)
    cm = cv2.erode(cm, np.ones((5, 5), np.uint8))           # stay inside the cell outline
    cm = np.clip(cv2.GaussianBlur(cm, (0, 0), 1.0), 0, 1)
    Lc = mblur(out, (cm > 0.5).astype(np.float32), 10) / np.maximum(mblur(cw, (cm > 0.5).astype(np.float32), 10), 1)
    pf = plate.astype(np.float32)
    fixc = np.clip(cw * Lc, 0, 255)  # no grain in small cells: any high-pass of the plate carries the old letters
    out = out * (1 - cm[..., None]) + fixc * cm[..., None]
cv2.imwrite(out_f, out.astype(np.uint8))
yy, xx = np.where(wm > 0.5); print("panel bbox in plate", xx.min() + sx0, yy.min() + sy0, xx.max() + sx0, yy.max() + sy0)
