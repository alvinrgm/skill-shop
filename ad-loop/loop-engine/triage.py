#!/usr/bin/env python3
"""The cascade RUNNER — locate -> A -> B -> C -> D over a batch of plates.

This is the experiment's primary instrument. It prints
one row per plate with every raw number, writes triage.json, and ends on the SURVIVAL
CURVE, which is the actual output: a batch returning zero survivors is a
result when the filters that killed it are new and validated. Report the curve; do not
lower a filter that was written this morning to justify the plates generated this
afternoon.

Nothing is hardcoded to one client; these are arguments:
the plate glob, the vision boxes.json, the reference object and the delivery canvas.

usage:
  python3 triage.py --plates 'PLATES/[A-E][0-9][0-9].png' \
                    --boxes QA/boxes.json \
                    --ref  /path/to/real-pack-shot.png \
                    [--client <slug>] [--deliv 1080x1350] \
                    [--dark-side A=R,B=L,C=R,D=L,E=R] \
                    [--out QA/triage.json] [--debug <plate id>]
"""
from __future__ import annotations

import argparse
import glob as globmod
import json
import sys
from pathlib import Path

from PIL import Image, ImageDraw

_HERE = Path(__file__).resolve().parent
for _p in (str(_HERE), str(_HERE.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import config  # noqa: E402
import physics  # noqa: E402


def debug_overlay(path: Path, res: dict, out_dir: Path):
    """The --debug overlay: green = the printed band box, magenta = the measured contact
    seam, blue = the central column strip the seam and the falloff profile were read in."""
    im = Image.open(path).convert("RGB")
    d = ImageDraw.Draw(im)
    b = res["bag"]
    d.rectangle([b["bx0"], b["band_y0"], b["bx1"], b["band_y1"]], outline=(0, 255, 0), width=8)
    d.line([b["bx0"] - 200, b["floor"], b["bx1"] + 200, b["floor"]], fill=(255, 0, 255), width=8)
    d.line([b["cx0"], b["floor"] - 300, b["cx0"], b["floor"] + 300], fill=(0, 128, 255), width=6)
    d.line([b["cx1"], b["floor"] - 300, b["cx1"], b["floor"] + 300], fill=(0, 128, 255), width=6)
    p = out_dir / f"debug_{path.stem}.jpg"
    im.resize((640, 800), Image.LANCZOS).save(p, quality=90)
    return p


def run(plates, boxes, ref_pack, *, deliv=(config.CANVAS_W, config.CANVAS_H),
        dark_side=None, out_json=None, debug=None, echo=True):
    """Returns (results, curve). `plates` is a list of paths, `boxes` the parsed
    boxes.json dict, `ref_pack` the real reference object."""
    results = []
    for f in plates:
        f = Path(f)
        r = physics.analyse(f, boxes, ref_pack, deliv=deliv, dark_side=dark_side)
        results.append(r)
        b = r.get("B") or {}
        c = r.get("C") or {}
        dd = r.get("D") or {}
        if echo:
            print("%-5s %-16s A sd%6.2f | B r=%-6s mono=%-5s dep=%-6s thr%+8s dir=%-5s | "
                  "C ret=%-6s | D ds=%-5s hp=%-5s" % (
                      r["plate"], r["verdict"], r["A"]["sd_min"],
                      b.get("contact_ratio", "-"), b.get("monotonic", "-"),
                      b.get("seam_depth", "-"), b.get("throw", "-"),
                      b.get("direction_ok", "-"), c.get("retain", "-"),
                      dd.get("downsample", "-"), dd.get("hp_ratio", "-")), flush=True)
        if debug and r["plate"] == debug and r.get("bag"):
            p = debug_overlay(f, r, Path(out_json).parent if out_json else f.parent)
            if echo:
                print("   wrote", p)

    n = len(results)
    curve = {"generated": n}
    alive = [r for r in results if r["bag"]]
    curve["bag located"] = len(alive)
    for f in "ABCD":
        alive = [r for r in alive if r.get(f, {}).get("pass_")]
        curve[f"after {f}"] = len(alive)
    if out_json:
        Path(out_json).write_text(json.dumps(results, indent=1))
    if echo:
        print("\nSURVIVAL CURVE:", json.dumps(curve))
        print("survivors:", [r["plate"] for r in alive])
    return results, curve


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--plates", required=True, help="glob of plate PNGs")
    ap.add_argument("--boxes", required=True, help="vision boxes.json (vision.py localise)")
    ap.add_argument("--ref", help="the REAL photograph of the object filter D calibrates on")
    ap.add_argument("--client", help="resolve --ref from the client layer instead")
    ap.add_argument("--deliv", default=f"{config.CANVAS_W}x{config.CANVAS_H}")
    ap.add_argument("--dark-side", default="",
                    help="per-variant declared window side, e.g. A=R,B=L (RECORDED, never gated)")
    ap.add_argument("--out", help="where to write triage.json (default: beside --boxes)")
    ap.add_argument("--debug", help="write a geometry overlay for this plate")
    a = ap.parse_args(argv)

    ref = Path(a.ref).expanduser() if a.ref else physics.ref_pack_for(a.client)
    if not ref.exists():
        sys.exit(f"reference object not found: {ref}")
    boxes = json.loads(Path(a.boxes).read_text())
    plates = sorted(Path(p) for p in globmod.glob(str(Path(a.plates).expanduser())))
    if a.debug:
        plates = [p for p in plates if p.stem == a.debug]
    if not plates:
        sys.exit(f"no plates matched {a.plates}")
    w, h = (int(v) for v in a.deliv.lower().split("x"))
    ds = dict(kv.split("=") for kv in a.dark_side.split(",") if "=" in kv) or None
    out = a.out or str(Path(a.boxes).parent / "triage.json")
    print(f"reference object: {ref}")
    print(f"{len(plates)} plate(s), delivery canvas {w}x{h}\n")
    run(plates, boxes, ref, deliv=(w, h), dark_side=ds, out_json=out, debug=a.debug)


if __name__ == "__main__":
    main()
