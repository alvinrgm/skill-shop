#!/usr/bin/env python3
"""measure.py: turn the verification checks that can be measured into actual measurements.

WHY THIS EXISTS. SKILL.md tells Claude to check safe zones "by measurement, not by eye,"
because a top-anchored wordmark looks normal while sitting inside the excluded band -- that
mistake shipped once. But an instruction to measure is worthless without an instrument, and
"look at the image and estimate a percentage" is eyeballing with a decimal point on it. This
is the instrument.

WHAT IT MEASURES (deterministic, no model judgment):
  - where content actually starts and ends vertically, as a percentage of height
  - how much of the canvas is dead background (the "is this composed, or just padded?" number)
  - whether the reserved legal band is genuinely empty
  - the worst horizontal tonal step, which is how a blanked band shows up as a visible seam

WHAT IT CANNOT DO. It cannot read text, so it cannot check copy. It cannot judge brand
fidelity or whether a layout is any good. Those stay human/model judgment -- this just stops
three of the five checks from being guesses.

NEEDS PILLOW. Generation does not, but decoding a JPEG to look at pixels does. If Pillow is
missing this prints exactly that, so the run records "not measured" rather than a guess.

USAGE
  python3 scripts/measure.py <image> [--format 9x16]
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# "Content" means text and graphic elements, NOT background. A fixed variance floor does not
# work: a background with soft circular motifs has real row-to-row variance, so a low fixed
# floor marks the whole canvas as content and the tool fails images that are fine. A detector
# that cries wolf gets ignored, which is worse than no detector. So the floor is derived per
# image: quiet rows set the baseline, and content has to stand well clear of it.
def content_threshold(variances):
    ordered = sorted(variances)
    quiet = ordered[len(ordered) // 5]                 # 20th percentile row = background
    loudest = ordered[-1]
    return quiet + max(8.0, 0.10 * (loudest - quiet))


def main() -> None:
    ap = argparse.ArgumentParser(description="Measure an output image for the verify step.")
    ap.add_argument("image")
    ap.add_argument("--format", default="", help="e.g. 9x16 to apply story safe-zone rules")
    ap.add_argument("--legal-band", type=float, default=0.75,
                    help="fraction of height where the reserved legal area starts (default 0.75)")
    a = ap.parse_args()

    try:
        from PIL import Image
    except ImportError:
        print("NOT MEASURED: Pillow is not installed, so the pixels cannot be read.\n"
              "  Install it with: python3 -m pip install --user Pillow\n"
              "  Until then, record safe zones and dead space as 'not measured' in the review\n"
              "  sheet. Do NOT write a number you estimated by eye.")
        sys.exit(2)

    path = Path(a.image)
    if not path.exists():
        sys.exit(f"No such image: {path}")
    img = Image.open(path).convert("L")
    w, h = img.size
    px = img.load()

    # Per-row spread of brightness. A row of flat background has almost none.
    rows = []
    step = max(1, w // 256)          # sample columns; exact enough and fast on 2K images
    for y in range(h):
        vals = [px[x, y] for x in range(0, w, step)]
        mean = sum(vals) / len(vals)
        var = sum((v - mean) ** 2 for v in vals) / len(vals)
        rows.append((mean, var))

    threshold = content_threshold([var for _, var in rows])
    content = [y for y, (_, var) in enumerate(rows) if var > threshold]
    print(f"image            {path.name}  {w}x{h}")
    if not content:
        print("content          NONE FOUND -- the image looks entirely blank. This is a FAIL.")
        sys.exit(1)

    top, bot = content[0] / h * 100, content[-1] / h * 100
    covered = len(content) / h * 100
    print(f"content starts   {top:.1f}% of height")
    print(f"content ends     {bot:.1f}% of height")
    # The honest emptiness signal is NOT what fraction of rows have ink -- text has gaps
    # between lines, so a well-set layout scores low. It is the unexplained gap: the run of
    # dead canvas between where content stops and where the legal band is deliberately blank.
    gap = max(0.0, a.legal_band * 100 - bot)
    print(f"content span     {top:.1f}% to {bot:.1f}%  ({bot - top:.1f}% of height)")
    print(f"unexplained gap  {gap:.1f}% dead canvas between content end and the legal band")

    band_start = int(h * a.legal_band)
    band_rows = [y for y in content if y >= band_start]
    band_clear_from = (min(band_rows) / h * 100) if band_rows else None
    print(f"legal band       {'empty as intended' if not band_rows else f'OCCUPIED from {band_clear_from:.1f}%'}"
          f" (reserved from {a.legal_band * 100:.0f}% down)")

    means = [m for m, _ in rows]
    steps = [(abs(means[i + 1] - means[i]), i) for i in range(h // 3, h - 1)]
    worst, at = max(steps) if steps else (0.0, 0)
    print(f"worst tonal step {worst:.1f} brightness levels at {at / h * 100:.1f}%"
          f"{'  <- look here for a seam' if worst >= 25 else ''}")

    verdicts = []
    fmt = a.format.replace(":", "x")
    if fmt and fmt != "9x16":
        print(f"note             {fmt} has no platform chrome zone, so the top/bottom safe-zone "
              f"rules do not apply -- only the reserved legal band below.")
    elif not fmt:
        print("note             no --format given, so safe-zone rules are not applied. Pass "
              "--format 9x16 for a story/reel.")
    if fmt == "9x16":
        # IMPORTANT: this tool reads pixels, not words. It cannot tell a photograph from a
        # headline. On a photo-led ad the image legitimately runs to the very top, so a
        # content-in-the-top-band reading is NOT a failure by itself -- only TEXT up there is.
        # Reporting it as FAIL would fail correct work on most real ads, and a checker that
        # cries wolf gets ignored. So: state the fact, and hand the judgement to a human/model
        # that can actually read.
        if top < 15.0:
            verdicts.append(f"LOOK: content reaches {top:.1f}% from the top, inside the 15% "
                            f"safe zone. That is FINE if it is photography or background, and a "
                            f"FAIL only if TEXT, the logo or the button sit up there. Open the "
                            f"image and check which it is -- I read pixels, not words.")
        elif bot > 75.0:
            verdicts.append(f"LOOK: content reaches {bot:.1f}%, inside the reserved bottom 25%. "
                            f"Fine if photography, a FAIL if text/logo/button. Open and check.")
        else:
            verdicts.append(f"PASS safe zones (all content between {top:.1f}% and {bot:.1f}%, "
                            f"clear of the 15% and 75% lines -- nothing to check by eye)")

    # Composition. A generative re-composition that leaves a big unexplained hole is not
    # better than a mechanical pad, which is the whole premise the user is paying for. The
    # legal band is excluded because that emptiness is intentional.
    if gap >= 20.0:
        verdicts.append(f"FAIL composition: {gap:.0f}% of the canvas is dead space between the "
                        f"end of the content and the legal band. That reads as padded rather "
                        f"than designed for this shape, which is the thing being paid for. "
                        f"Regenerate asking the layout to fill the canvas.")
    elif gap >= 12.0:
        verdicts.append(f"WEAK composition: {gap:.0f}% dead canvas above the legal band. Look "
                        f"at it before accepting.")

    # This one the tool CAN decide, and it is the property that actually matters: the reserved
    # band exists so a person has blank space to paste the legal text into. Anything occupying
    # it -- regenerated text, a CTA button, or photography -- defeats that, regardless of what
    # it is. This is the gate that catches "looks great, nowhere to put the disclosure."
    if band_rows and a.legal_band < 1.0:
        verdicts.append(f"FAIL legal band: the reserved area below {a.legal_band * 100:.0f}% is "
                        f"occupied from {band_clear_from:.1f}% down, so there is nowhere to "
                        f"paste the legal text. Whether that is regenerated legal copy, a CTA "
                        f"button or photography, this size cannot be finished as-is. "
                        f"Regenerate keeping the bottom clear, or hand it to a designer.")

    if worst >= 25:
        verdicts.append(f"CHECK for a seam at {at / h * 100:.0f}% of height: there is a "
                        f"{worst:.0f}-level tonal step there. It is often just the edge of a "
                        f"background shape, so look before judging. If it IS a hard horizontal "
                        f"line, regenerate with the 'continue the background' wording.")

    print()
    for v in verdicts or ["No automatic failures. Copy and brand still need your eyes."]:
        print(f"  {v}")
    sys.exit(1 if any(v.startswith("FAIL") for v in verdicts) else 0)


if __name__ == "__main__":
    main()
