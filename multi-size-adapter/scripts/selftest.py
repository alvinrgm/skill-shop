#!/usr/bin/env python3
"""selftest.py: prove the whole thing actually works, end to end, for about $0.13.

WHO RUNS THIS
  - The team lead, right after setting up the Gemini key and billing, to confirm the key is
    live BEFORE handing it to designers. (A key with no billing does not make worse images;
    it makes an error. This is how you find out in 30 seconds instead of during someone's
    first real job.)
  - Anyone who thinks something is broken and wants a yes/no answer.
  - The clean-room certifier, as the one entry command that cold-runs the pipeline.

WHAT IT DOES
  Takes the sample creative that ships in samples/ and asks the model for a square version of
  it using the same prompt template the real workflow uses, then checks a real image came
  back. One generation, roughly $0.134 on your team's Google account.

  With --full it also does a 9:16 story version and measures it, which is the format with the
  stacked safe-zone and legal-blank constraints and therefore the one most likely to break.
  Two generations, roughly $0.27. Worth it once, after setting up billing.

  It does NOT test the part that makes this tool good -- Claude looking at your creative and
  writing a bespoke prompt for it. It tests the plumbing: key, billing, network, engine, file
  writing. Passing means "the pipeline runs"; it does not mean "your ads will look right."

USAGE
  python3 scripts/selftest.py              # run it
  python3 scripts/selftest.py --dry-run    # check setup only, spend nothing
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = ROOT / "samples" / "base_creative.png"

PROMPT = """TASK: Adapt this ad into a square 1:1 version of itself, as the same brand designer would.

INSTRUCTIONS:
- Same background, same typography style, same visual motifs.
- Keep the same text the ad already has: the wordmark 'QUILLFORD · COFFEE', the headline 'Your
  first bag is on us', the subline 'Fresh-roasted. Shipped the same week.', and the pill
  button 'Claim your bag'. Do not add or invent any new text.
- Re-compose natively for a square canvas so it reads as designed for this shape, not cropped.

THE BOTTOM QUARTER OF THIS IMAGE MUST CONTAIN NO TEXT AT ALL.
The bottom 25% of the canvas has NO text. No words. No letters. No small print. No disclaimer.
No legal copy. Do NOT reproduce the small legal paragraph from the source image. That area is
reserved for a human to add text later. Any text there is a failure.
IMPORTANT: fill that area by CONTINUING the existing background exactly as it appears
elsewhere in the image, including the same colour gradient and the same motifs. It must blend
seamlessly, with no visible horizontal edge, seam, band, or change in tone."""


def fail(msg: str) -> None:
    print(f"\n  FAILED: {msg}\n")
    sys.exit(1)


def main() -> None:
    ap = argparse.ArgumentParser(description="Prove the pipeline works end to end.")
    ap.add_argument("--dry-run", action="store_true",
                    help="Check the setup without generating anything (spends nothing).")
    ap.add_argument("--out", default=None,
                    help="Where to write the test output (default: a temporary folder).")
    ap.add_argument("--full", action="store_true",
                    help="Also generate and measure a 9:16 story (2 generations, ~$0.27). "
                         "Exercises the format with the stacked constraints.")
    a = ap.parse_args()

    print("Multi-Size Creative Adapter: self-test")
    print("-" * 43)

    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        import gemini_native
    except Exception as e:                                   # pragma: no cover - import guard
        fail(f"could not load the engine: {e}")

    if not SAMPLE.exists():
        fail(f"the sample creative is missing ({SAMPLE}). Re-download the package.")
    print(f"  sample creative      found ({SAMPLE.stat().st_size // 1024} KB)")

    key = gemini_native.resolve_api_key(ROOT)
    if not key:
        fail("no Gemini API key. Ask your team lead for the shared key, then either paste it "
             "into config.yml or set GEMINI_API_KEY. See SETUP.md.")
    if not key.startswith("AIza") or len(key) < 30:
        fail(f"the configured key does not look like a Google API key (got {len(key)} "
             f"characters). Placeholder text left in by mistake?")
    print(f"  Gemini key           configured ({len(key)} chars)")

    if a.dry_run:
        print("\n  Setup looks right. Run without --dry-run to make one real image "
              "(about $0.134).\n")
        return

    out_dir = Path(a.out) if a.out else Path(tempfile.mkdtemp(prefix="msa-selftest-"))
    campaign = out_dir / "selftest"
    plan = {"campaign": "selftest",
            "sizes": [{"name": "1080x1080", "width": 1080, "height": 1080,
                       "strategy": "generate", "gen_prompt": PROMPT,
                       "copy": {"headline": "Your first bag is on us",
                                "body": "Fresh-roasted. Shipped the same week.",
                                "cta": "Claim your bag"}}]}
    plan_path = out_dir / "selftest-plan.json"
    out_dir.mkdir(parents=True, exist_ok=True)
    plan_path.write_text(json.dumps(plan, indent=2))

    print("  generating one square test image (about $0.134, usually under a minute)...")
    proc = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "adapt.py"),
         "--plan", str(plan_path), "--base", str(SAMPLE),
         "--out", str(campaign), "--images", "1", "--overwrite"],
        capture_output=True, text=True)
    if proc.returncode != 0:
        print(proc.stdout)
        print(proc.stderr, file=sys.stderr)
        fail("the engine returned an error. The message above says why.")

    made = sorted(p for p in (campaign / "1080x1080").glob("base*")) if (campaign / "1080x1080").is_dir() else []
    if not made:
        print(proc.stdout)
        print(proc.stderr, file=sys.stderr)
        fail("no image was produced. If the message above mentions billing, the key's Google "
             "project still needs billing enabled -- see SETUP.md 'For the team lead'.")

    img = made[0]
    data = img.read_bytes()
    kind, w, h = gemini_native.sniff_image(data)
    if kind == "bin" or len(data) < 10_000:
        fail(f"the file that came back is not a usable image ({len(data)} bytes).")
    if w and h and abs((w / h) - 1.0) > 0.02:
        fail(f"the returned image is {w}x{h}, which is not square. Something is wrong with the "
             f"model request.")

    sheet = campaign / "review-sheet.md"
    print(f"  image written        {img.name} ({kind.upper()}, {w}x{h}, {len(data) // 1024} KB)")
    print(f"  review sheet         {'written' if sheet.exists() else 'MISSING'}")
    if not sheet.exists():
        fail("no review sheet was written.")

    if a.full:
        story_prompt = PROMPT.replace("a square 1:1 version", "a vertical 9:16 story version") \
                             .replace("for a square canvas", "for a tall 9:16 canvas") + """

THE TOP 15% OF THIS IMAGE MUST CONTAIN NO TEXT AT ALL.
The wordmark, the headline, the subline and the button ALL sit below the top 15% of the
canvas. The top 15% is background only. Any text in the top 15% is a failure. Likewise the
bottom 21% holds no text."""
        plan2 = {"campaign": "selftest",
                 "sizes": [{"name": "1080x1920", "width": 1080, "height": 1920,
                            "strategy": "generate", "gen_prompt": story_prompt,
                            "copy": plan["sizes"][0]["copy"]}]}
        plan2_path = out_dir / "selftest-plan-story.json"
        plan2_path.write_text(json.dumps(plan2, indent=2))
        print("  generating a 9:16 story too (the format with the stacked constraints)...")
        p2 = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "adapt.py"),
             "--plan", str(plan2_path), "--base", str(SAMPLE),
             "--out", str(campaign), "--images", "1", "--overwrite"],
            capture_output=True, text=True)
        story = sorted((campaign / "1080x1920").glob("base*")) if (campaign / "1080x1920").is_dir() else []
        if p2.returncode != 0 or not story:
            print(p2.stdout)
            print(p2.stderr, file=sys.stderr)
            fail("the 9:16 story did not generate.")
        print(f"  story written        {story[0].name}")
        m = subprocess.run([sys.executable, str(ROOT / "scripts" / "measure.py"),
                            str(story[0]), "--format", "9x16"], capture_output=True, text=True)
        print("  --- measured ---")
        for line in (m.stdout or "").rstrip().splitlines():
            print(f"  {line}")
        if m.returncode == 1:
            fail("the 9:16 story failed its measured checks (see above). The pipeline runs, "
                 "but this creative or prompt needs attention before trusting a real batch.")

    print("\n  PASSED: the plumbing works -- key, billing, network, engine and file writing.")
    print("  This does NOT tell you your ads will look right. The part that makes output good")
    print("  is Claude reading YOUR creative and checking each result, which no self-test can")
    print("  stand in for. Treat this as 'connected', not 'validated'.")
    print(f"\n  Test files are in: {campaign}  (delete the folder, it was only a test)\n")


if __name__ == "__main__":
    main()
