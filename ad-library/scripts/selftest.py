#!/usr/bin/env python3
"""Offline self-test: runs every offline-testable script in a throwaway brand folder.

No Figma, no Gemini, no Meta calls, no cost. Proves the Python side works on this machine
before you spend a Figma or Gemini call. Prints PASS/FAIL per check; exits 1 on any FAIL.

Not covered (each needs a network call, a key or an optional package): gen_image.py and
ref_sheet.py generation, the print_gate.py vision call (its scorer IS tested), probe_gemini.py,
crawl_site.py, learn.py's Meta pull (--no-meta IS tested), figma_comments.py,
label_composite.py (needs OpenCV + SciPy), and everything that runs through the Figma MCP.

usage: python3 scripts/selftest.py [--keep]
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import _common  # noqa: E402,F401  (uses the package .venv when there is one)

results = []
NOT_COVERED = ("gen_image.py / ref_sheet.py generation, the print_gate.py vision call, probe_gemini.py, "
               "crawl_site.py, learn.py Meta pull, figma_comments.py, label_composite.py, the Figma MCP")


def check(label, ok, detail=""):
    results.append((label, bool(ok)))
    print(f"{'PASS' if ok else 'FAIL'}  {label}" + (f"\n      {detail}" if detail and not ok else ""))


def run(label, args, env, expect=0, record=True):
    r = subprocess.run([sys.executable, *args], capture_output=True, text=True, env=env, cwd=HERE.parent)
    ok = expect is None or r.returncode == expect
    if not record:
        return r
    results.append((label, ok))
    print(f"{'PASS' if ok else 'FAIL'}  {label}" + ("" if ok else f"\n      exit {r.returncode}\n      {(r.stdout + r.stderr)[-600:]}"))
    return r


def main() -> int:
    if any(x in ("-h", "--help") for x in sys.argv[1:]):
        print(__doc__)
        return 0
    import numpy as np
    from PIL import Image, ImageDraw

    tmp = Path(tempfile.mkdtemp(prefix="adlib-selftest-"))
    env = dict(os.environ, AD_LIBRARY_HOME=str(tmp))
    b = "selftest-brand"
    run("init_brand", [str(HERE / "init_brand.py"), b, "--name", "Selftest Brand"], env)
    lib = tmp / b
    run("learn --no-meta (tracker from angles.json)", [str(HERE / "learn.py"), b, "--no-meta"], env)
    r = run("sync_payload roadmap", [str(HERE / "sync_payload.py"), b], env)
    check("sync payload is JSON with subs", '"subs"' in r.stdout)
    run("sync_payload learnings", [str(HERE / "sync_payload.py"), b, "--learnings"], env)

    good = {"batch": "B00", "ads": [{"id": "A", "headline": "Granola like it used to be, minus the sugar",
                                    "disclaimer": "Terms apply.", "claims": ["C01"], "quotes": []}]}
    bad = {"batch": "B00", "ads": [{"id": "B", "headline": "A MIRACLE IN EVERY BOWL", "claims": ["C99"]}]}
    (lib / "copy/good.json").write_text(json.dumps(good))
    (lib / "copy/bad.json").write_text(json.dumps(bad))
    run("copy_gate passes clean copy", [str(HERE / "copy_gate.py"), b, str(lib / "copy/good.json")], env, 0)
    run("copy_gate fails bad copy", [str(HERE / "copy_gate.py"), b, str(lib / "copy/bad.json")], env, 1)

    # a flat-background 2x export with a headline and a pack-sized block
    rng = np.random.default_rng(0)
    im = Image.new("RGB", (2160, 2700), (240, 236, 228))
    d = ImageDraw.Draw(im)
    d.rectangle([300, 300, 1860, 560], fill=(30, 30, 34))
    d.rectangle([640, 900, 1520, 2300], fill=(180, 60, 40))
    noise = (rng.random((2700, 2160, 3)) * 6).astype("uint8")
    im = Image.fromarray(np.clip(np.array(im).astype(int) + noise, 0, 255).astype("uint8"))
    exp = lib / "runs/b00"
    exp.mkdir(parents=True, exist_ok=True)
    im.save(exp / "A-4x5.png")
    Image.new("RGB", (928, 1152), (120, 120, 120)).save(exp / "plate-1k.png")
    Image.new("RGB", (2400, 3000), (120, 120, 120)).save(exp / "plate-4k.png")
    r = run("qa_export on a 2x flat export", [str(HERE / "qa_export.py"), str(exp / "A-4x5.png"),
                                              "--plates", str(exp / "plate-4k.png")], env, None, record=False)
    verdict = json.loads(r.stdout).get("verdict") if r.stdout.strip().startswith("{") else None
    check(f"qa_export on a 2x flat export returns a verdict ({verdict})", verdict in ("PASS", "FAIL"))
    run("qa_export rejects a 1K plate", [str(HERE / "qa_export.py"), str(exp / "A-4x5.png"),
                                          "--plates", str(exp / "plate-1k.png")], env, 1)
    Image.new("RGB", (2160, 2700), (240, 236, 228)).save(exp / "blank-4x5.png")
    r = run("qa_export FAILs a flat export with no content", [str(HERE / "qa_export.py"), str(exp / "blank-4x5.png")], env, 1)
    check("qa_export names the missing content", "no content" in r.stdout, r.stdout[-300:] + r.stderr[-300:])
    run("qa_export with no args prints usage", [str(HERE / "qa_export.py")], env, 2)

    prod = Image.new("RGB", (1200, 1500), (255, 255, 255))
    ImageDraw.Draw(prod).rectangle([300, 200, 900, 1300], fill=(40, 90, 160))
    prod.save(tmp / "product.jpg")
    run("cutout from a white-background photo", [str(HERE / "cutout.py"), b, str(tmp / "product.jpg"), "--name", "main"], env)
    cut = lib / "brand/packs/pack-main.png"
    check("cutout is RGBA with transparent corners",
          cut.exists() and Image.open(cut).mode == "RGBA" and Image.open(cut).getpixel((0, 0))[3] < 10)

    run("asset_library register-packs", [str(HERE / "asset_library.py"), "register-packs", b], env)
    run("asset_library add plate", [str(HERE / "asset_library.py"), "add", b, "--type", "plate", "--id", "plate-test",
                                    "--name", "test plate", "--file", str(exp / "plate-4k.png"), "--status", "approved"], env)
    r = run("asset_library refs (approved only)", [str(HERE / "asset_library.py"), "refs", b, "pack-main", "plate-test"], env)
    check("refs returns two --ref paths", r.stdout.count("--ref") == 2)
    run("sheet.py contact sheet", [str(HERE / "sheet.py"), str(exp), str(tmp / "sheet.jpg"), "3"], env)

    from print_gate import score
    s_ok = score({"strings": [{"text": "No added sugar", "legibility": "crisp"},
                              {"text": "xx", "legibility": "unresolvable"}]}, ["No added sugar"])
    s_bad = score({"strings": [{"text": "No aded sugr", "legibility": "crisp"},
                               {"text": "Now with vitamins", "legibility": "crisp"}]}, ["No added sugar"])
    check("print_gate scorer passes letter-perfect", s_ok["pass_"])
    check("print_gate scorer fails garble + invented claim", s_bad["n_wrong"] == 2)

    if "--keep" in sys.argv:
        print(f"kept {tmp}")
    else:
        shutil.rmtree(tmp, ignore_errors=True)
    bad_steps = [l for l, ok in results if not ok]
    print(f"\nselftest: {len(results) - len(bad_steps)}/{len(results)} passed"
          + (f"; FAILED: {bad_steps}" if bad_steps else ""))
    print(f"not covered offline: {NOT_COVERED}")
    return 1 if bad_steps else 0


if __name__ == "__main__":
    sys.exit(main())
