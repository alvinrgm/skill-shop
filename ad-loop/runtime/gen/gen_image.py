#!/usr/bin/env python3
"""The ad-loop image generator: Google Gemini image model ("Nano Banana Pro").

RULE: ALL ad-loop image generation goes through this Gemini path, on YOUR
GEMINI_API_KEY. Never a credit-billing image service.

RESOLUTION RULE: CORE REFERENCE SHOTS (product/location/character reference sheets,
any locked master reference, the locked winner plate) are generated at 4K. VOLUME
plates for triage are drafts: pass --size 1K (config.VOLUME_PLATE_SIZE). The default
here is 4K, so a volume batch MUST pass --size explicitly; config.plate_spend(n)
prints the cost first.

Why REST instead of the google-genai SDK: as of google-genai 1.47 (latest), the
typed ImageConfig only exposes `aspect_ratio` and REJECTS `image_size`
(extra_forbidden). The REST API DOES support imageConfig.imageSize
("1K" | "2K" | "4K") for gemini-3-pro-image-preview, so we call REST directly.
Revisit if/when the SDK exposes image_size.

Usage:
  python3 gen_image.py --out PATH --prompt "..."                 # 4K, 9:16 (defaults)
  python3 gen_image.py --out PATH --prompt-file FILE --aspect 16:9   # contact sheet
  python3 gen_image.py --out PATH --prompt "..." --size 2K       # only if NOT a core ref
  python3 gen_image.py ... --ref IMG1 --ref IMG2                  # reference images (paths)
  python3 gen_image.py ... --model nb2                            # Nano Banana 2 instead of Pro
"""
from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import sys
import urllib.request
from pathlib import Path

# Re-run under the package's own .venv when one exists (config.py does that at import).
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import config as _pkg_config  # noqa: E402,F401

# The key lives in the ad-loop package .env (two levels up), or in the environment.
PACKAGE = Path(__file__).resolve().parents[2]
try:
    from dotenv import load_dotenv
    load_dotenv(PACKAGE / ".env")
except ImportError:          # python-dotenv is optional; fall back to a tiny parser
    _env = PACKAGE / ".env"
    if _env.is_file():
        for _l in _env.read_text().splitlines():
            if "=" in _l and not _l.lstrip().startswith("#"):
                _k, _v = _l.split("=", 1)
                if _v.strip():
                    os.environ.setdefault(_k.strip(), _v.strip().strip("'\""))

MODEL = "gemini-3-pro-image-preview"  # Nano Banana Pro (default)
MODELS = {"pro": "gemini-3-pro-image-preview", "nb2": "gemini-3.1-flash-image"}
ENDPOINT_TMPL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"


def _ref_part(ref: str) -> dict:
    """Build an inline_data part from a local image path (for reference images)."""
    data = Path(ref).read_bytes()
    mime = mimetypes.guess_type(ref)[0] or "image/png"
    return {"inlineData": {"mimeType": mime, "data": base64.b64encode(data).decode()}}


def generate(prompt: str, out: str, size: str = "4K", aspect: str = "9:16",
             refs: list[str] | None = None, model: str = MODEL) -> str:
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        sys.exit("GEMINI_API_KEY not set. Add it to the ad-loop .env "
                 "(get one at https://aistudio.google.com/apikey).")
    parts = [{"text": prompt}]
    for r in refs or []:
        parts.append(_ref_part(r))
    body = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "responseModalities": ["IMAGE"],
            "imageConfig": {"aspectRatio": aspect, "imageSize": size},
        },
    }
    req = urllib.request.Request(
        f"{ENDPOINT_TMPL.format(model=model)}?key={key}",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            resp = json.load(r)
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code}: {e.read().decode()[:1000]}")

    for cand in resp.get("candidates", []):
        for part in cand.get("content", {}).get("parts", []):
            inline = part.get("inlineData") or part.get("inline_data")
            if inline and inline.get("data"):
                Path(out).parent.mkdir(parents=True, exist_ok=True)
                Path(out).write_bytes(base64.b64decode(inline["data"]))
                return out
    raise RuntimeError(f"No image part in response: {json.dumps(resp)[:1000]}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--prompt")
    ap.add_argument("--prompt-file")
    ap.add_argument("--size", default="4K", choices=["1K", "2K", "4K"])
    ap.add_argument("--aspect", default="9:16")
    ap.add_argument("--ref", action="append", default=[])
    ap.add_argument("--model", default="pro", choices=sorted(MODELS),
                    help="pro = Nano Banana Pro (default), nb2 = Nano Banana 2")
    a = ap.parse_args()
    prompt = a.prompt or Path(a.prompt_file).read_text()
    # Reference-image visibility — the #1 cause of "the product looks wrong" is generating
    # WITHOUT a real reference, so the model invents the package. Make that loud, not silent.
    for r in a.ref:
        if not Path(r).exists():
            sys.exit(f"--ref not found on disk: {r}\n"
                     f"   A pasted/attached chat image is NOT a file. Save it to disk first "
                     f"(e.g. brand/refs/scraped/product.png), then pass THAT path as --ref.")
    if a.ref:
        print(f"REFS: {len(a.ref)} reference image(s) → {', '.join(a.ref)}", file=sys.stderr)
    else:
        print("⚠️  NO --ref PASSED — generating from the PROMPT ONLY. Any real product/character "
              "will be INVENTED, not matched to a photo. For a product or locked asset, this is "
              "almost certainly wrong: pass the real image via --ref.", file=sys.stderr)
    out = generate(prompt, a.out, a.size, a.aspect, a.ref, MODELS[a.model])
    print(f"SAVED {out} (model={MODELS[a.model]}, size={a.size}, aspect={a.aspect}, refs={len(a.ref)})")
