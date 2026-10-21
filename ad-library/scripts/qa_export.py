#!/usr/bin/env python3
"""Zero-call QA for a Figma-exported static ad.
usage: qa_export.py <png> [--ratio 4x5|9x16] [--plates plate.png ...] [--allow-1x] [--contrast x0,y0,x1,y1[:dark] ...]

Checks:
  - exact size at 2x export scale (2160x2700 / 2160x3840). A 1080-wide 1x export FAILS unless
    --allow-1x: Meta renders ads at phone width (about 1179 px on a current iPhone), so a 1080
    upload is upscaled on every phone.
  - file size: a tiny file means an image fill had not loaded when Figma exported. Re-export.
  - --plates: every generated plate the ad uses must meet the resolution floor, 2x the frame it
    fills (>=2160 wide for 4:5, >=3840 tall for 9:16). A 1K plate under vector type looks fine
    on the canvas and grainy on a phone; the floor is the guard, not the eye.
  - flat-colour backgrounds: headline cap band, side margins and safe zones, from pixels.
    Photo backgrounds cannot be measured from pixels: the script says so, and the geometry check
    lives in the Figma build call (check() in the kit) plus an eyes-on look. It never passes a
    photo ad on its own (verdict NEEDS EYES).

Safe zones: 9:16 = top 250 / bottom 240 (Reels/Stories UI), in 1x units. 4:5 feed has no UI
overlay, so its bottom floor is a 24 px edge margin.

--contrast x0,y0,x1,y1 (repeatable, 1x / 1080-frame units, scaled to the export): WCAG contrast of
light text over whatever is behind it in that box (text = 99th-percentile luminance, ground =
75th, the conservative pick). Floor 4.5. Use it on every small line over a photo, the disclaimer
above all. Dark text on a light ground: add ":dark" (text = 1st percentile, ground = 25th).
Exit code 1 on any FAIL."""
import sys, json, os
from pathlib import Path
if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
    print(__doc__); sys.exit(0)
if len(sys.argv) < 2 or sys.argv[1].startswith("--"):
    print(__doc__, file=sys.stderr); sys.exit(2)
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _common  # noqa: E402,F401  (uses the package .venv when there is one)
from PIL import Image
import numpy as np
f = sys.argv[1]; ratio = sys.argv[sys.argv.index("--ratio")+1] if "--ratio" in sys.argv else None
im = Image.open(f); rgb = np.array(im.convert("RGB")).astype(int); H, W, _ = rgb.shape
if ratio is None: ratio = "9x16" if H / W > 1.6 else "4x5"
fails, notes = [], []
allow_1x = "--allow-1x" in sys.argv
if (W, H) in ((2160, 2700), (2160, 3840)): S = 2
elif (W, H) in ((1080, 1350), (1080, 1920)):
    S = 1
    if not allow_1x: fails.append(f"size {W}x{H} is a 1x export: export at scale 2 (2160 wide); --allow-1x only for legacy reads")
else: S = 1; fails.append(f"size {W}x{H}: expected 2160x2700 or 2160x3840")
kb = os.path.getsize(f) / 1024
kb_floor = 800 if S == 2 else 200
if kb < kb_floor: fails.append(f"file {kb:.0f} KB < {kb_floor} KB: image fill probably missing, re-export once")
# plate resolution floor: 2x the frame the plate fills
PLATE_FLOOR = {"4x5": (2160, 2700), "9x16": (2160, 3840)}
plates = []
if "--plates" in sys.argv:
    i = sys.argv.index("--plates") + 1
    while i < len(sys.argv) and not sys.argv[i].startswith("--"): plates.append(sys.argv[i]); i += 1
plate_out = []
for pth in plates:
    pw, ph = Image.open(pth).size; fw, fh = PLATE_FLOOR[ratio]
    ok = pw >= fw and ph >= fh
    plate_out.append({"plate": pth, "size": [pw, ph], "floor": [fw, fh], "ok": ok})
    if not ok: fails.append(f"plate {os.path.basename(pth)} is {pw}x{ph}, under the {fw}x{fh} floor for {ratio}: regenerate at 4K")
if not plates: notes.append("no --plates given: plate resolution floor not checked (pass every generated plate the ad uses)")
corner = rgb[5*S:45*S, 5*S:45*S].reshape(-1, 3); field = np.median(corner, axis=0)
ink = np.abs(rgb - field).sum(axis=2) > 60
photo = corner.std(axis=0).mean() > 10 or ink.mean() > 0.6
out = {"file": f, "ratio": ratio, "size": [W, H], "export_scale": S, "kb": round(kb), "background": "photo" if photo else "flat"}
if plate_out: out["plates"] = plate_out
if photo:
    notes.append("photo background: pixel geometry skipped. Pass needs (1) the Figma check() result and (2) an eyes-on look at text vs the product.")
elif not ((ink.sum(axis=1) > 3).any() and (ink.sum(axis=0) > 3).any()):
    fails.append("no content / image fill missing: the export is one flat colour. Wait a minute, export again")
    out["verdict_reason"] = "no content"
else:
    safe_bottom = (240 if ratio == "9x16" else 24) * S; safe_top = (250 if ratio == "9x16" else 0) * S
    rows = np.where(ink.sum(axis=1) > 3)[0]; cols = np.where(ink.sum(axis=0) > 3)[0]
    r = ink.sum(axis=1) > 3; blocks = []; s = None
    for y, v in enumerate(r):
        if v and s is None: s = y
        if not v and s is not None: blocks.append((s, y)); s = None
    if s is not None: blocks.append((s, H))
    if rows.max() >= H - safe_bottom: fails.append(f"ink enters bottom zone (ends {rows.max()}, limit {H-safe_bottom})")
    big = 300 * S
    if rows.min() < safe_top: fails.append(f"ink enters top safe zone (starts {rows.min()}, limit {safe_top})")
    margin = int(min(cols.min(), W - 1 - cols.max()))
    if margin < 90 * S: fails.append(f"side margin {margin}px < {90*S}")
    top = [b for b in blocks if b[0] < H * 0.45 and b[1] - b[0] < big]  # text rows in the top 45%, not the pack
    cap = max(((b[1] - b[0]) / H * 100 for b in top), default=0)
    if ratio == "4x5" and cap < 8: fails.append(f"tallest headline line {cap:.1f}% of height < 8%")
    if not [b for b in blocks if b[1] - b[0] > big]: fails.append(f"no pack-sized block (>{big}px): image fill missing?")
    out.update({"tallest_headline_line_pct": round(cap, 1), "side_margin": margin, "ink_y": [int(rows.min()), int(rows.max())]})
def _lum(a):
    a = a / 255.0; a = np.where(a <= 0.03928, a / 12.92, ((a + 0.055) / 1.055) ** 2.4)
    return 0.2126 * a[..., 0] + 0.7152 * a[..., 1] + 0.0722 * a[..., 2]
boxes = [sys.argv[i + 1] for i, a in enumerate(sys.argv) if a == "--contrast"]
cr = []
for b in boxes:
    box, _, pol = b.partition(":"); dark = pol == "dark"
    x0, y0, x1, y1 = (int(v) * S for v in box.split(",")); L = _lum(rgb[y0:y1, x0:x1].astype(float))
    # light text: text = 99th pct, ground = 75th. dark text (":dark"): the mirror, text = 1st, ground = 25th
    c = ((np.percentile(L, 25) + 0.05) / (np.percentile(L, 1) + 0.05) if dark
         else (np.percentile(L, 99) + 0.05) / (np.percentile(L, 75) + 0.05))
    cr.append({"box": b, "text": "dark" if dark else "light", "contrast": round(float(c), 2)})
    if c < 4.5: fails.append(f"text contrast {c:.2f} < 4.5 in box {b}")
if cr: out["contrast"] = cr
if photo and cr and not fails: notes.append("contrast boxes pass; still look at text vs the product by eye.")
out.update({"fails": fails, "notes": notes, "verdict": "FAIL" if fails else ("NEEDS EYES" if photo else "PASS")})
print(json.dumps(out, indent=1))
sys.exit(1 if fails else 0)
