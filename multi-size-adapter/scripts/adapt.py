#!/usr/bin/env python3
"""
adapt.py: mechanical resize/recompose engine for the Multi-Size Creative Adapter.

This script does NOT make creative decisions. Claude looks at the base image first and writes
the adaptation plan (per-size strategy and prompt); this script just executes that plan. The
four built-in formats need no image library at all; see the note on Pillow below.

Usage:
    python3 adapt.py --plan plan.json --base base_creative.png --out outputs/<campaign>/

Plan JSON shape (one file covers the whole run):
{
  "campaign": "example-campaign",
  "focal_point": {"x": 0.5, "y": 0.35},   # fraction of image width/height, 0-1
  "safe_area_guide": false,                # true = stamp a translucent safe-area guide on each output
  "sizes": [
    {
      "name": "1080x1350",
      "width": 1080,
      "height": 1350,
      "strategy": "generate",              # "generate" (native re-composition via Gemini; what Claude
                                           # plans by default in v2), "crop" (scale+crop to fill) or
                                           # "extend" (scale to fit, pad). A size with no strategy
                                           # field falls back to "crop".
      "gen_prompt": "TASK: Adapt ...",     # required when strategy == "generate"; Claude writes it
                                           # (preserve-verbatim + safe zones + the legal-blank
                                           # block, see SKILL.md)
      "allow_extra": false,                # true = permit a shape outside the four built-ins.
                                           # Needs Pillow (a crop step). Default false.
      "extend_fill": "blur",               # "blur" or "solid" (only used when strategy == "extend")
      "solid_color": [20, 24, 40],         # only used when extend_fill == "solid"
      "copy": {
        "headline": "Get paid up to 2 days early",
        "body": "No fees. No minimum balance.",
        "cta": "Get started"
      }
    }
  ]
}

"generate" needs a Gemini API key (config.yml gemini_api_key or GEMINI_API_KEY env; see
SETUP.md). A generate size that fails (bad key, network, refusal) is logged and the run
continues. If Pillow is installed the size falls back to a mechanical resize and is marked
FALLBACK; if it is not, that size is marked FAILED and nothing is written for it. Either way
the rest of the batch completes and the review sheet records what happened.

Output per size: <out>/<name>/base.<jpg|png> (the extension follows the bytes the model
actually returned) + <out>/<name>/copy.md
Also writes <out>/review-sheet.md indexing every size.

Convention: write the plan to <out>/plan.json so each run's inputs sit beside its outputs and
a rerun is self-documenting. Campaign and size names are used as folder names, so keep them
free of slashes; spaces are fine but hyphens travel better.
"""

from __future__ import annotations   # keeps type annotations lazy so this module imports
                                      # cleanly when Pillow is absent (the normal case for the
                                      # four built-in formats). Without it, `Image.Image` in a
                                      # signature is evaluated at def-time and raises.

import argparse
import json
import sys
from pathlib import Path

# Pillow is OPTIONAL. The four built-in formats (1:1, 4:5, 9:16, 16:9) are generated at their
# native shape and written straight to disk, so a normal run never touches an image library.
# Pillow is needed only for the opt-in extra formats and the mechanical fallback paths.
try:
    from PIL import Image, ImageFilter, ImageDraw
    HAVE_PILLOW = True
except ImportError:
    Image = ImageFilter = ImageDraw = None
    HAVE_PILLOW = False


# Google's published price for Gemini 3 Pro Image output up to 2K, which is what this tool
# generates. Planning figure only -- the Google billing console is the authority.
USD_PER_IMAGE = 0.134


def estimate_batch(n_images: int, n_sizes: int) -> str:
    """Volume + cost estimate shown BEFORE any generation happens. Retries are billed too,
    so the worst case is stated alongside the expected case rather than hidden."""
    gens = n_images * n_sizes
    expected = gens * USD_PER_IMAGE
    # Two independent retry paths exist per size (an API refusal retry and a verify-FAIL
    # retry), so the honest ceiling is 3 generations per size, not 2.
    worst = gens * 3 * USD_PER_IMAGE
    minutes = max(1, round(gens * 35 / 60))
    return (
        "\n"
        "  BATCH ESTIMATE\n"
        f"    Source creatives   {n_images}\n"
        f"    Formats each       {n_sizes}\n"
        f"    Images to generate {gens}\n"
        f"    Estimated cost     ${expected:,.2f}  (${USD_PER_IMAGE} per image)\n"
        f"    Worst case ${worst:,.2f} if every size needs both retries (refusal + quality)\n"
        f"    Claude's own usage is billed separately by Anthropic and is NOT in this figure.\n"
        f"    Rough time         ~{minutes} min (calls run one at a time)\n"
        "    Billed to your team's Google account. Charges appear in the Google billing console.\n"
    )


def validate_plan(plan: dict) -> list:
    """Check the plan before spending anything. Returns a list of plain-English problems.
    Every one of these was previously a raw traceback in front of a non-technical user."""
    problems = []
    if not isinstance(plan, dict):
        return ["The plan file must be a JSON object (starting with '{'), not a list or a "
                "bare value."]
    sizes = plan.get("sizes")
    if not isinstance(sizes, list) or not sizes:
        return ["The plan has no 'sizes' listed, so there is nothing to make."]
    seen = {}
    for i, sz in enumerate(sizes):
        where = f"size #{i + 1}"
        if not isinstance(sz, dict):
            problems.append(f"{where} is not a valid entry.")
            continue

        # 'name' becomes a directory name. Everything downstream indexes it, and an unchecked
        # value can write outside the output folder entirely (an absolute path makes pathlib
        # discard --out) or collide with another size and silently deliver one image for two
        # billed generations.
        raw = sz.get("name")
        if raw is None or not isinstance(raw, str) or not raw.strip():
            problems.append(f"{where}: missing a 'name' (it becomes the output folder name).")
            continue
        name = raw.strip()
        if ("/" in name or "\\" in name or "\x00" in name or name in (".", "..")
                or name.startswith("~") or len(name) > 64):
            problems.append(f"{where}: the name {raw!r} is not usable as a folder name. Use a "
                            f"plain name like '1080x1920' (no slashes, no '..', 64 characters "
                            f"or fewer).")
            continue
        key = name.casefold()   # macOS and Windows are case-insensitive, so "Feed" and "feed"
                                #  are the same folder -- one would overwrite the other.
        if key in seen:
            problems.append(f"{where}: the name {name!r} clashes with size #{seen[key]} (names "
                            f"that differ only in capitalisation land in the same folder on Mac "
                            f"and Windows). You would pay for both and keep one.")
            continue
        seen[key] = i + 1
        for field in ("width", "height"):
            val = sz.get(field)
            if val is None:
                problems.append(f"{name}: missing '{field}'.")
            elif not isinstance(val, int) or isinstance(val, bool):
                problems.append(f"{name}: '{field}' must be a whole number, got {val!r}.")
            elif val < 16:
                problems.append(f"{name}: '{field}' is {val}; must be at least 16 pixels.")
            elif val > 8192:
                problems.append(f"{name}: '{field}' is {val}; the maximum is 8192 pixels.")
        if sz.get("strategy") == "generate" and not str(sz.get("gen_prompt", "")).strip():
            problems.append(f"{name}: uses 'generate' but has no 'gen_prompt'.")
    return problems


def existing_outputs(out_root: Path, sizes: list) -> list:
    """Any file we are about to replace. Overwriting a size a designer already finished in
    place would destroy their work silently, so the caller must opt in."""
    hits = []
    for sz in sizes:
        d = out_root / str(sz.get("name", ""))
        if d.is_dir():
            hits += [f for f in sorted(d.iterdir()) if f.is_file() and f.name.startswith("base")]
    return hits


def load_plan(plan_path: Path) -> dict:
    with open(plan_path, "r") as f:
        return json.load(f)


def crop_to_fill(img: Image.Image, target_w: int, target_h: int, focal: tuple) -> Image.Image:
    """Scale the image up to fully cover the target box, then crop around the focal point."""
    src_w, src_h = img.size
    target_ratio = target_w / target_h
    src_ratio = src_w / src_h

    if src_ratio > target_ratio:
        # source is relatively wider than target -> scale to target height, crop width
        scale = target_h / src_h
    else:
        # source is relatively taller than target -> scale to target width, crop height
        scale = target_w / src_w

    new_w = max(1, round(src_w * scale))
    new_h = max(1, round(src_h * scale))
    scaled = img.resize((new_w, new_h), Image.LANCZOS)

    fx, fy = focal
    focal_x_px = new_w * fx
    focal_y_px = new_h * fy

    left = focal_x_px - target_w / 2
    top = focal_y_px - target_h / 2
    left = max(0, min(left, new_w - target_w))
    top = max(0, min(top, new_h - target_h))
    left, top = round(left), round(top)

    return scaled.crop((left, top, left + target_w, top + target_h))


def extend_to_fit(img: Image.Image, target_w: int, target_h: int, fill_mode: str,
                   solid_color: tuple) -> Image.Image:
    """Scale the image to fit entirely within the target box, then pad the rest."""
    src_w, src_h = img.size
    scale = min(target_w / src_w, target_h / src_h)
    new_w = max(1, round(src_w * scale))
    new_h = max(1, round(src_h * scale))
    scaled = img.resize((new_w, new_h), Image.LANCZOS)

    if fill_mode == "blur":
        # Cover-crop a blurred version of the source as the backdrop, then paste the scaled
        # full image centered on top.
        backdrop = crop_to_fill(img, target_w, target_h, (0.5, 0.5))
        backdrop = backdrop.filter(ImageFilter.GaussianBlur(radius=max(target_w, target_h) // 40 + 8))
    else:
        backdrop = Image.new(img.mode if img.mode in ("RGB", "RGBA") else "RGB",
                              (target_w, target_h), tuple(solid_color))

    paste_x = (target_w - new_w) // 2
    paste_y = (target_h - new_h) // 2
    if scaled.mode == "RGBA":
        backdrop = backdrop.convert("RGBA")
        backdrop.paste(scaled, (paste_x, paste_y), scaled)
    else:
        backdrop.paste(scaled, (paste_x, paste_y))
    return backdrop


def stamp_safe_area(img: Image.Image, margin_frac: float = 0.08) -> Image.Image:
    """Draw a translucent safe-area guide rectangle so the designer can see the crop-safe zone."""
    img = img.convert("RGBA")
    overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    w, h = img.size
    mx, my = round(w * margin_frac), round(h * margin_frac)
    draw.rectangle([mx, my, w - mx, h - my], outline=(255, 0, 128, 180), width=max(2, w // 300))
    return Image.alpha_composite(img, overlay)


def run_generate(base_path: Path, out_file: Path, size: dict) -> dict:
    """Native generative re-composition via scripts/gemini_native.py. Returns metadata.
    Raises RuntimeError (with a per-size message) on any failure; caller decides fallback."""
    import gemini_native
    key = gemini_native.resolve_api_key(Path(__file__).resolve().parent.parent)
    if not key:
        raise RuntimeError("no Gemini API key (config.yml gemini_api_key or GEMINI_API_KEY env; see SETUP.md)")
    prompt = size.get("gen_prompt", "")
    if not prompt.strip():
        raise RuntimeError("size has strategy 'generate' but no gen_prompt in the plan")
    return gemini_native.generate_native(base_path, out_file, size["width"], size["height"],
                                        prompt, key,
                                        allow_extra=bool(size.get("allow_extra", False)))


import re as _re

_KEY_RE = _re.compile(r"AIza[0-9A-Za-z_\-]{10,}")


def _cell(text) -> str:
    """Make a value safe to put in a markdown table cell: single line, no pipes, and never
    carrying an API key that an upstream error body echoed back at us."""
    flat = " ".join(str(text).split()).replace("|", "/")
    flat = _KEY_RE.sub("[key redacted]", flat)
    return flat[:200] + ("..." if len(flat) > 200 else "")


def write_copy_md(out_dir: Path, size_name: str, copy: dict, strategy: str) -> None:
    lines = [
        f"# Copy: {size_name}",
        "",
        f"**Strategy used:** {strategy}",
        "",
        f"**Headline:** {copy.get('headline', '')}",
        f"**Body:** {copy.get('body', '')}",
        f"**CTA:** {copy.get('cta', '')}",
        "",
    ]
    (out_dir / "copy.md").write_text("\n".join(lines))


def write_review_sheet(out_root: Path, campaign: str, sizes: list, filename: str = "review-sheet.md") -> None:
    any_marked = any(sz.get("strategy", "crop") == "generate"
                     and sz.get("legal_blanked", True) for sz in sizes)
    lines = [
        f"# Review sheet: {campaign}",
        "",
        "Designer-ready starting points, not finished ads.",
        "",
    ]
    if any_marked:
        lines += [
            "**The generated images below are named `.NEEDS-LEGAL.` on purpose.** The",
            "legal/disclaimer text from your source creative was deliberately not generated, so",
            "those files are missing a required element. Paste the legal text back in during",
            "finishing and rename the file. Do not hand one of these to an ad platform or a",
            "client with the marker still on it.",
            "",
            "**Before any of these ship, a person must paste the legal/disclaimer text back into",
            "the blank area.** Legal copy is left out on purpose: AI-rendered legal text comes out",
            "subtly wrong, and wrong legal text on an ad is a compliance problem.",
            "",
        ]
    lines += [
        "Every size also still needs a design pass (brand QA, kerning/typesetting, final touch-up).",
        "",
        "| Size | Strategy | Headline | Body | CTA | Verify (copy / brand / safe-zone / artifacts) |",
        "|---|---|---|---|---|---|",
    ]
    for s in sizes:
        c = s.get("copy", {}) if isinstance(s.get("copy"), dict) else {}
        strat = s.get("strategy", "crop")
        if "FALLBACK" in strat:
            verify_cell = f"FALLBACK: needs rework ({_cell(s.get('gen_error', ''))})"
        elif "FAILED" in strat:
            verify_cell = f"FAILED: nothing written ({_cell(s.get('gen_error', ''))})"
        else:
            verify_cell = "PENDING"
        lines.append(
            f"| {_cell(s.get('name', '?'))} | {_cell(strat)} | {_cell(c.get('headline', ''))} "
            f"| {_cell(c.get('body', ''))} | {_cell(c.get('cta', ''))} | {verify_cell} |"
        )
    lines.append("")
    lines.append("Each size's folder also has its own `copy.md` with the full text.")
    lines.append("")
    lines.append(
        "Each Verify cell is filled in after that output has been opened and checked "
        "(copy word-for-word, brand fidelity, safe zones, legal area clear, artifacts). "
        "A cell still reading the placeholder means that size has not been checked yet."
    )
    (out_root / filename).write_text("\n".join(lines))


def main():
    ap = argparse.ArgumentParser(description="Adapt a base creative into multiple target sizes.")
    ap.add_argument("--plan", required=True, help="Path to the adaptation plan JSON.")
    ap.add_argument("--base", required=True, help="Path to the base creative image (PNG/JPG).")
    ap.add_argument("--out", required=True, help="Output root folder (e.g. outputs/<campaign>/).")
    ap.add_argument("--images", type=int, default=1,
                    help="How many source creatives this batch covers (for the estimate).")
    ap.add_argument("--estimate-only", action="store_true",
                    help="Print the volume/cost estimate for this plan and exit without generating.")
    ap.add_argument("--overwrite", action="store_true",
                    help="Replace existing output files. Without this the run stops rather than "
                         "destroying work a designer may have finished in place.")
    ap.add_argument("--skip-existing", action="store_true",
                    help="Leave sizes that already have output alone (useful to resume a batch "
                         "without paying again for sizes that already succeeded).")
    args = ap.parse_args()

    if args.overwrite and args.skip_existing:
        print("ERROR: --overwrite and --skip-existing are opposite instructions (one replaces "
              "existing output, the other keeps it). Pass only one.", file=sys.stderr)
        sys.exit(2)

    plan_path = Path(args.plan)
    base_path = Path(args.base)
    out_root = Path(args.out)

    if not plan_path.exists():
        print(f"ERROR: plan file not found: {plan_path}", file=sys.stderr)
        sys.exit(1)
    if not base_path.exists():
        print(f"ERROR: base image not found: {base_path}", file=sys.stderr)
        sys.exit(1)

    try:
        plan = load_plan(plan_path)
    except json.JSONDecodeError as e:
        print(f"ERROR: the plan file is not valid JSON (line {e.lineno}, column {e.colno}): "
              f"{e.msg}", file=sys.stderr)
        sys.exit(1)

    problems = validate_plan(plan)
    if problems:
        print("ERROR: the plan has problems, so nothing was generated and nothing was billed:",
              file=sys.stderr)
        for pr in problems:
            print(f"  - {pr}", file=sys.stderr)
        sys.exit(1)
    campaign = plan.get("campaign", "campaign")
    focal = plan.get("focal_point", {"x": 0.5, "y": 0.5})
    focal_tuple = (focal.get("x", 0.5), focal.get("y", 0.5))
    safe_area_guide = plan.get("safe_area_guide", False)
    sizes = plan.get("sizes", [])

    if not sizes:
        print("ERROR: plan has no sizes listed.", file=sys.stderr)
        sys.exit(1)

    # Never destroy work in place. A designer may have finished a size by hand.
    clashes = existing_outputs(out_root, sizes)
    # A price quote writes nothing, so it must never be blocked by the guard that protects
    # existing files -- otherwise the mandatory cost gate is unrunnable exactly when someone
    # is resuming, which is when they most want to know the price.
    if clashes and args.estimate_only:
        print(f"  NOTE: {len(clashes)} output file(s) already exist here. This quote covers "
              f"every size in the plan; to actually run, add --skip-existing (only makes the "
              f"missing ones, cheaper) or --overwrite (replaces them).\n")
    elif clashes and not (args.overwrite or args.skip_existing):
        print(f"ERROR: {len(clashes)} output file(s) already exist under {out_root}:",
              file=sys.stderr)
        for f in clashes[:8]:
            print(f"  - {f}", file=sys.stderr)
        if len(clashes) > 8:
            print(f"  ...and {len(clashes) - 8} more", file=sys.stderr)
        print("\nNothing was changed and nothing was billed. If a designer has finished any of "
              "these by hand, re-running would destroy that work.\n"
              "  --skip-existing   keep them and only make the missing sizes (also avoids "
              "paying twice)\n"
              "  --overwrite       replace them on purpose", file=sys.stderr)
        sys.exit(1)

    # Volume + cost estimate ALWAYS prints before any generation happens.
    if args.images < 1:
        print("ERROR: --images must be at least 1.", file=sys.stderr)
        sys.exit(1)
    # Look at the source before quoting a price on it. Two things a designer would want to be
    # told BEFORE paying: the file is too small to upscale from, and they just asked for a
    # format the source already is.
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import gemini_native as _gn
        _kind, _sw, _sh = _gn.sniff_image(base_path.read_bytes())
        if _sw and _sh:
            print(f"  source: {base_path.name}  {_sw}x{_sh}")
            if max(_sw, _sh) < 800:
                print(f"  WARNING: that is small for an ad source. Outputs are generated at "
                      f"about 2K, so this is being upscaled roughly {2048 / max(_sw, _sh):.1f}x "
                      f"and detail will be soft. If you have the original at full size, use "
                      f"that instead.\n")
            src_ratio = _sw / _sh
            same = [sz["name"] for sz in sizes
                    if abs((sz["width"] / sz["height"]) / src_ratio - 1) < 0.03]
            if same:
                print(f"  NOTE: the source is already this shape, so {', '.join(same)} would be "
                      f"close to a copy. Worth skipping unless you want it re-composed.\n")
    except Exception:
        pass   # a source check must never block the run

    print(estimate_batch(args.images, len(sizes)))
    if args.images == 1:
        print("  NOTE: this estimate covers ONE source creative. For a batch, pass --images <N>\n"
              "        with the real count so the figure above is not understated.\n")
    if args.estimate_only:
        print("  (estimate only -- nothing generated)")
        return

    out_root.mkdir(parents=True, exist_ok=True)

    # The base image is only opened for the mechanical (Pillow) paths. Generate-only plans
    # never need it, which is what keeps a normal run dependency-free.
    needs_pillow = any(sz.get("strategy", "crop") != "generate" for sz in sizes)
    base_img = None
    if needs_pillow:
        if not HAVE_PILLOW:
            print("ERROR: this plan uses a mechanical strategy (crop/extend), which needs the "
                  "Pillow image library. Either use only the four built-in formats with "
                  "strategy 'generate', or install Pillow: python3 -m pip install --user Pillow",
                  file=sys.stderr)
            sys.exit(1)
        base_img = Image.open(base_path)
        if base_img.mode not in ("RGB", "RGBA"):
            base_img = base_img.convert("RGB")

    produced = []
    written_sheet = "review-sheet.md"
    try:
      for size in sizes:
          name = size["name"]
          w, h = size["width"], size["height"]
          strategy = size.get("strategy", "crop")

          size_dir = out_root / name
          size_dir.mkdir(parents=True, exist_ok=True)
          out_file = size_dir / "base.png"
          result = None
          gen_note = ""

          if args.skip_existing:
              already = [f for f in size_dir.iterdir() if f.is_file() and f.name.startswith("base")]
              if already:
                  size["strategy"] = "skipped (output already present)"
                  produced.append(size)
                  print(f"SKIP    {name:>10}  already has {already[0].name}, not regenerating")
                  continue

          if strategy == "generate":
              try:
                  meta = run_generate(base_path, out_file, size)
                  # The engine names the file after the bytes the model actually returned
                  # (JPEG or PNG), so take the real path back from it.
                  out_file = Path(meta.get("path", out_file))
                  size["actual_px"] = meta.get("actual_px", "")
                  gen_note = f"{meta['ratio_used']}, {meta.get('actual_px','?')} px"
                  if meta.get("ratio_drift_pct", 0) >= 1.0:
                      gen_note += f", ratio off by {meta['ratio_drift_pct']}%"
              except Exception as e:  # any failure (API, decode, PIL) is contained; batch survives
                  size["gen_error"] = str(e)
                  if HAVE_PILLOW:
                      # Fall back to a mechanical pad so the batch completes, marked for rework.
                      print(f"FALLBACK  {name}: generate failed ({e}); using extend", file=sys.stderr)
                      if base_img is None:
                          base_img = Image.open(base_path)
                          if base_img.mode not in ("RGB", "RGBA"):
                              base_img = base_img.convert("RGB")
                      strategy = "extend"
                      size["strategy"] = "extend (FALLBACK from generate)"
                  else:
                      # No Pillow: produce nothing for this size rather than a misleading image.
                      print(f"FAILED    {name}: {e}", file=sys.stderr)
                      strategy = "failed"
                      size["strategy"] = "FAILED (nothing written)"

          if strategy == "crop":
              result = crop_to_fill(base_img, w, h, focal_tuple)
          elif strategy == "extend":
              fill_mode = size.get("extend_fill", "blur")
              solid = tuple(size.get("solid_color", [20, 24, 40]))
              result = extend_to_fit(base_img, w, h, fill_mode, solid)
          elif strategy == "failed":
              result = None   # nothing written on purpose; recorded as FAILED in the review sheet
          elif strategy != "generate":
              print(f"WARNING: unknown strategy '{strategy}' for {name}, defaulting to crop", file=sys.stderr)
              if base_img is None:
                  base_img = Image.open(base_path)
                  if base_img.mode not in ("RGB", "RGBA"):
                      base_img = base_img.convert("RGB")
              result = crop_to_fill(base_img, w, h, focal_tuple)

          if result is not None:
              if safe_area_guide:
                  result = stamp_safe_area(result)
              result.convert("RGB" if result.mode != "RGBA" else "RGBA").save(out_file)

          # The legal area was deliberately left blank. That fact has to travel WITH the file:
          # a review sheet stays behind the moment someone drags the image into Slack or an ad
          # platform, and a blank lower band reads as intentional negative space, not as a
          # missing disclosure. Encode it in the filename so every downstream human sees it.
          # Only the generate path omits legal. A mechanical crop/extend keeps the whole source
          # (legal included), so it must NOT be marked NEEDS-LEGAL.
          strat_now = size.get("strategy", "crop")
          legal_omitted = strat_now == "generate" and size.get("legal_blanked", True)
          if out_file.exists() and legal_omitted:
              marked = out_file.with_name(out_file.stem + ".NEEDS-LEGAL" + out_file.suffix)
              out_file.replace(marked)
              out_file = marked
          wrote_image = out_file.exists()
          if wrote_image:
              # Clear a stale prior file (different extension) only AFTER a real success, and
              # NOT when this size fell back to a mechanical downgrade. Two safeguards in one:
              #   - after the write, so a failed generate never destroys the prior good output;
              #   - not on a FALLBACK, so re-running --overwrite and hitting a transient failure
              #     doesn't replace last run's good generate with this run's worse pad.
              downgraded = "FALLBACK" in size.get("strategy", "") or "FAILED" in size.get("strategy", "")
              if args.overwrite and not downgraded:
                  for old in size_dir.glob("base*"):
                      if old.is_file() and old.resolve() != out_file.resolve():
                          old.unlink()
              write_copy_md(size_dir, name, size.get("copy", {}), size.get("strategy", strategy))
          produced.append(size)

          if wrote_image:
              note = f"  [{gen_note}]" if gen_note else ""
              print(f"OK      {name:>10}  ({w}x{h}, {size.get('strategy', strategy)})  -> {out_file}{note}")
          else:
              print(f"FAILED  {name:>10}  ({w}x{h})  nothing written: {size.get('gen_error', 'unknown error')}",
                    file=sys.stderr)

    finally:
        # Always leave an index behind, even if the run died partway. A paid-for batch with no
        # review sheet is the worst outcome: files on disk and no record of what happened.
        #
        # The rule is deliberately dumb, because every clever version of it grew an edge case
        # that silently ate a designer's notes: NEVER overwrite an existing review sheet. If
        # review-sheet.md does not exist, write it. If it does (any state -- fully annotated,
        # half-annotated, empty), leave it exactly as-is and write this run's index to the next
        # free review-sheet-runN.md. Nothing a person may have touched is ever replaced.
        if produced:
            target, note = out_root / "review-sheet.md", ""
            if target.exists():
                n = 2
                while (out_root / f"review-sheet-run{n}.md").exists():
                    n += 1
                target = out_root / f"review-sheet-run{n}.md"
                note = (f"Left the existing review-sheet.md untouched (it may hold your notes); "
                        f"this run's index is in {target.name}.")
            written_sheet = target.name
            write_review_sheet(out_root, campaign, produced, filename=target.name)
            if note:
                print(note)
    failed = [s2 for s2 in produced if "FAILED" in s2.get("strategy", "")]
    fell_back = [s2 for s2 in produced if "FALLBACK" in s2.get("strategy", "")]
    skipped = [s2 for s2 in produced if "skipped" in s2.get("strategy", "")]
    ok = len(produced) - len(failed) - len(fell_back) - len(skipped)
    print(f"\n{ok} of {len(produced)} size(s) generated cleanly -> {out_root}")
    if skipped:
        print(f"{len(skipped)} already existed and were left alone: "
              f"{', '.join(s2['name'] for s2 in skipped)}")
    if fell_back:
        print(f"{len(fell_back)} fell back to a mechanical resize and NEED REWORK: "
              f"{', '.join(s2['name'] for s2 in fell_back)}")
    if failed:
        print(f"{len(failed)} FAILED with nothing written: "
              f"{', '.join(s2.get('name', '?') for s2 in failed)}")
    if produced and ok == 0 and not skipped:
        print("\nNothing was generated successfully. Exiting non-zero so this is not mistaken "
              "for a successful run.", file=sys.stderr)
        sys.exit(1)
    sheet_name = written_sheet if 'written_sheet' in dir() else 'review-sheet.md'
    print(f"Review sheet: {out_root / sheet_name}")


if __name__ == "__main__":
    main()
