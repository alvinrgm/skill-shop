#!/usr/bin/env python3
"""ref_sheet.py: one command for a locked reference sheet, registered in the Library.

Types:
  product    the pack from several views plus the product in use, from the REAL pack photo as --ref.
             Print-gated (print_gate.py --native, wrong must be 0) before it can be approved.
  location   one place, 6 panels (angles x light), PLUS the canonical 9:16 empty PLATE, which is
             the continuity lock: pass it as the first --ref for every later plate in that place.
  character  face + body turnaround sheet. Your own rules about generated people apply when
             anything SHIPS, not here.

Every output lands in $AD_LIBRARY_HOME/<brand>/library/<type>/ as a DRAFT entry with the locked
description stored on the entry, so every later prompt pastes the same words.

  ref_sheet.py --brand <slug> --type location --id loc-home --name "Home" \
      --brief-file brief.txt [--ref photo.jpg ...] [--ref-asset pack-main-sku] \
      [--size 2K] [--no-plate] [--dry-run]

Cost (printed before the call, rough): ~$0.13 per 1K-2K image, ~$0.24 at 4K on your Gemini key.
A location costs 2 images (sheet + plate).
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import asset_library as L  # noqa: E402

GEN = Path(__file__).resolve().parent / "gen_image.py"
COST = {"1K": 0.13, "2K": 0.13, "4K": 0.24}

PRODUCT = """Product reference sheet for {name}. A 6-panel grid (3 over 3) on a clean neutral
light-grey seamless background, soft even studio light from the upper left, a soft natural
contact shadow under the product, no reflections, no props.
Panels: 1 FRONT straight-on, full product centered · 2 BACK straight-on · 3 THREE-QUARTER LEFT ·
4 THREE-QUARTER RIGHT · 5 TOP-DOWN · 6 THE PRODUCT IN USE: {in_use}.
Every panel the same scale, the same light, the same colour temperature. Thin neutral grid lines.
No captions, no labels, no added text of any kind.
THE PRODUCT: {brief}
CRITICAL: this is the REAL product in the reference image. Copy its packaging exactly: colours,
logo, wordmark, layout. Do not invent, re-letter or add any printed text; where a line of print is
too small to copy exactly, leave it soft and unreadable rather than writing new words."""

LOCATION = """Environment reference sheet for {name}. A 6-panel grid (3 over 3), thin neutral grey
dividers, NO captions or labels. All six panels show the SAME place: identical geometry,
materials, fixtures and objects, varied only by camera angle and light.
Panels: 1 WIDE, the full space, {light_a} · 2 MEDIUM on the hero surface where the action happens,
same light · 3 REVERSE ANGLE, same light · 4 the WIDE again in {light_b} · 5 the MEDIUM again in
{light_c} · 6 DETAIL STUDY of the signature surface and its texture, neutral light.
THE PLACE: {brief}
Photographic, shot on a full-frame camera, natural light only, real materials with wear, matte
surfaces, no gloss, no perfect steam plume, no rim light. NO people, NO animals, NO products,
NO packaging, NO text anywhere. 16:9."""

PLATE = """Use this EXACT place from the reference sheet: identical geometry, materials, fixtures
and objects. One single photograph, vertical 9:16, the hero camera: {hero}. {light_a}.
The hero surface sits in the lower half with clear empty space on it where a product will be
placed later; the top third is calm (a wall, a window, soft background) for a headline.
Photographic, full-frame camera, natural light, matte, real wear. NO people, NO animals,
NO products, NO packaging, NO text."""

CHARACTER = """Character reference sheet for {name}. A 6-panel grid (3 over 3) on a plain light-grey
background, soft even light. Panels: 1 FACE front · 2 FACE three-quarter · 3 FACE profile ·
4 FULL BODY front · 5 FULL BODY three-quarter · 6 FULL BODY back. The same person in every panel:
identical face, hair, build, wardrobe. Neutral expression. No captions, no text, no props.
THE CHARACTER: {brief}"""


def gen(out: Path, prompt: str, aspect: str, size: str, refs: list[str], dry: bool):
    pf = out.with_suffix(".prompt.txt")
    pf.write_text(prompt)
    cmd = [sys.executable, str(GEN), "--out", str(out), "--prompt-file", str(pf),
           "--aspect", aspect, "--size", size, "--model", "pro"]
    for r in refs:
        cmd += ["--ref", r]
    print(f"$ gen {out.name} ({aspect}, {size}, refs={len(refs)}) ≈ ${COST[size]:.2f}")
    if dry:
        return
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0 or not out.exists():
        print(r.stdout[-800:], r.stderr[-1500:])
        sys.exit(f"generation failed for {out.name}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--brand", required=True)
    ap.add_argument("--type", required=True, choices=("product", "location", "character"))
    ap.add_argument("--id", required=True)
    ap.add_argument("--name", required=True)
    ap.add_argument("--brief"); ap.add_argument("--brief-file")
    ap.add_argument("--ref", action="append", default=[], help="real photo(s) as reference")
    ap.add_argument("--ref-asset", action="append", default=[], help="Library asset id(s) as reference")
    ap.add_argument("--in-use", default="the product opened, its contents shown beside it")
    ap.add_argument("--light", default="soft overcast morning window light|warm low late-afternoon sun"
                    "|evening, a single warm lamp and cool window light",
                    help="three lights a|b|c (locations)")
    ap.add_argument("--hero", default="eye level, 35mm, looking across the hero surface toward the window")
    ap.add_argument("--size", default="2K", choices=("1K", "2K", "4K"))
    ap.add_argument("--no-plate", action="store_true")
    ap.add_argument("--plate-only", action="store_true", help="re-make only the 9:16 plate (sheet must exist)")
    ap.add_argument("--plate-from", help="Library id of an approved PLATE to evolve: same camera and framing, "
                    "only what the brief changes (e.g. the same room in another season). Passed as the FIRST ref.")
    ap.add_argument("--replace", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)

    brief = Path(a.brief_file).read_text().strip() if a.brief_file else (a.brief or "")
    if not brief:
        sys.exit("--brief or --brief-file is required (the locked description of the thing)")
    reg = L.load(a.brand)
    refs = [str(Path(r).expanduser().resolve()) for r in a.ref]
    for aid in a.ref_asset:
        e = L.entry(reg, aid)
        if e["status"] != "approved":
            sys.exit(f"--ref-asset {aid} is {e['status']}; only approved assets can start a sheet")
        refs.append(str(L.abspath(a.brand, e)))
    if a.type == "product" and not refs:
        sys.exit("a product sheet needs the REAL pack as --ref or --ref-asset (never invent a pack)")

    work = L.lib_dir(a.brand) / a.type / "_work"
    work.mkdir(parents=True, exist_ok=True)
    la, lb, lc = (a.light.split("|") + ["", "", ""])[:3]
    sheet = work / f"{a.id}.png"
    if a.type == "product":
        prompt = PRODUCT.format(name=a.name, brief=brief, in_use=a.in_use)
    elif a.type == "location":
        prompt = LOCATION.format(name=a.name, brief=brief, light_a=la, light_b=lb, light_c=lc)
    else:
        prompt = CHARACTER.format(name=a.name, brief=brief)
    n_img = (0 if a.plate_only else 1) + (1 if (a.type == "location" and not a.no_plate) else 0)
    print(f"cost estimate: {n_img} image(s) × ${COST[a.size]:.2f} ≈ ${n_img * COST[a.size]:.2f} (Gemini, your key)")
    if a.plate_only:
        e = L.entry(reg, a.id)
    else:
        gen(sheet, prompt, "16:9", a.size, refs, a.dry_run)
        e = None
    if e is None and not a.dry_run:
        e = L.add_entry(a.brand, reg, type_=a.type, aid=a.id, name=a.name, file=sheet,
                    sources=refs, description=brief, tags=["sheet", "generated"],
                    status="draft", replace=a.replace,
                    notes=f"ref_sheet.py {a.type} sheet; prompt {sheet.with_suffix('.prompt.txt')}")
        L.save(a.brand, reg)
        print(f"registered {e['id']} (draft) → {L.abspath(a.brand, e)}")

    if a.type == "location" and not a.no_plate:
        plate = work / f"{a.id}-plate.png"
        sheet_ref = str(L.abspath(a.brand, e)) if e else str(sheet)
        prefs, ptxt = [sheet_ref], PLATE.format(hero=a.hero, light_a=la)
        if a.plate_from:
            pf = L.entry(reg, a.plate_from)
            if pf["status"] != "approved":
                sys.exit(f"--plate-from {a.plate_from} is {pf['status']}")
            prefs = [str(L.abspath(a.brand, pf))] + prefs
            ptxt = ("The FIRST reference image is the locked camera: keep its EXACT framing, lens, camera height, "
                    "and the positions of every fixed object, so the two images could be cross-dissolved. Change ONLY what "
                    "this brief changes: " + brief + "\n" + ptxt)
        gen(plate, ptxt, "9:16", a.size, prefs, a.dry_run)
        if not a.dry_run:
            reg = L.load(a.brand)
            p = L.add_entry(a.brand, reg, type_="location", aid=f"{a.id}-plate", name=f"{a.name} — canonical 9:16 plate",
                            file=plate, sources=[sheet_ref], description=brief,
                            tags=["plate", "continuity-lock", "generated"], status="draft", replace=a.replace,
                            notes="the continuity lock: pass as the FIRST --ref for every later plate in this place")
            L.save(a.brand, reg)
            print(f"registered {p['id']} (draft) → {L.abspath(a.brand, p)}")

    if a.dry_run:
        print("dry run: nothing generated or registered (prompt files written next to each output)")
        return

    if a.type == "product":
        print("next: asset_library.py gate", a.brand, a.id, "--print --native   (must be wrong=0 to approve)")
    else:
        print(f"next: look at it at full size, then asset_library.py set {a.brand} {a.id} status=approved")


if __name__ == "__main__":
    main()
