#!/usr/bin/env python3
"""Generate one photo plate with Google Gemini image models ("Nano Banana"), on YOUR key.

Plates are the ONLY generated layer in an ad. Type, labels, badges and the pack cutout are
Figma layers. Always pass the real pack photo as --ref when the product is in the scene,
or the model invents a pack (and invents claims printed on it).

Models:
  --model nb2  Nano Banana 2  (gemini-3.1-flash-image)       cheaper, good for 1K exploration
  --model pro  Nano Banana Pro (gemini-3-pro-image-preview)   default; use for the 4K winner
Override an id if Google renames it: AD_LIBRARY_IMAGE_MODEL_NB2 / AD_LIBRARY_IMAGE_MODEL_PRO.

Sizes: 1K for exploration (cap ~15 per shot), 4K for the plate that ships. A plate that goes
into an ad must be at least 2x the Figma frame (>=2160 wide for 4:5, >=3840 tall for 9:16);
qa_export.py --plates enforces that.

Why REST and not the google-genai SDK: the REST API takes imageConfig.imageSize (1K/2K/4K);
some SDK versions reject that field.

usage:
  python3 gen_image.py --out plate.png --prompt "..." --aspect 4:5 --size 1K --model nb2 --ref pack.png
  python3 gen_image.py --out plate-4k.png --prompt-file p.txt --aspect 4:5 --size 4K --ref pack.png --ref pick-1k.png
"""
from __future__ import annotations

import argparse
import base64
import json
import mimetypes
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import gemini_key  # noqa: E402

MODELS = {"pro": "gemini-3-pro-image-preview", "nb2": "gemini-3.1-flash-image"}
ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
OVERRIDES = {"pro": "AD_LIBRARY_IMAGE_MODEL_PRO", "nb2": "AD_LIBRARY_IMAGE_MODEL_NB2"}
COST_HINT = {"1K": 0.13, "2K": 0.13, "4K": 0.24}  # USD per image, rough, check Google's pricing page


def model_id(name: str) -> str:
    """The model id for --model <name>, honouring its .env override."""
    return os.environ.get(OVERRIDES[name], "").strip() or MODELS[name]


def _ref_part(ref: str) -> dict:
    data = Path(ref).read_bytes()
    mime = mimetypes.guess_type(ref)[0] or "image/png"
    return {"inlineData": {"mimeType": mime, "data": base64.b64encode(data).decode()}}


def generate(prompt: str, out: str, size: str = "4K", aspect: str = "4:5",
             refs: list[str] | None = None, model: str = MODELS["pro"]) -> str:
    parts = [{"text": prompt}] + [_ref_part(r) for r in (refs or [])]
    body = {"contents": [{"parts": parts}],
            "generationConfig": {"responseModalities": ["IMAGE"],
                                 "imageConfig": {"aspectRatio": aspect, "imageSize": size}}}
    req = urllib.request.Request(ENDPOINT.format(model=model) + "?key=" + gemini_key(),
                                 data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=300) as r:
            resp = json.load(r)
    except urllib.error.HTTPError as e:  # never print the URL: it carries the key
        sys.exit(f"Gemini HTTP {e.code}: {e.read().decode()[:800]}")
    for cand in resp.get("candidates", []):
        for part in cand.get("content", {}).get("parts", []):
            inline = part.get("inlineData") or part.get("inline_data")
            if inline and inline.get("data"):
                Path(out).parent.mkdir(parents=True, exist_ok=True)
                Path(out).write_bytes(base64.b64decode(inline["data"]))
                return out
    sys.exit(f"no image in the response: {json.dumps(resp)[:800]}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("--prompt")
    ap.add_argument("--prompt-file")
    ap.add_argument("--size", default="4K", choices=["1K", "2K", "4K"])
    ap.add_argument("--aspect", default="4:5")
    ap.add_argument("--model", default="pro", choices=sorted(MODELS))
    ap.add_argument("--ref", action="append", default=[])
    a = ap.parse_args()
    prompt = a.prompt or (Path(a.prompt_file).read_text() if a.prompt_file else "")
    if not prompt:
        sys.exit("--prompt or --prompt-file is required")
    for r in a.ref:
        if not Path(r).exists():
            sys.exit(f"--ref not found on disk: {r} (a chat attachment is not a file: save it first)")
    if not a.ref:
        print("WARNING: no --ref passed. Any real product in this scene will be INVENTED. "
              "Pass the real pack photo as --ref.", file=sys.stderr)
    gemini_key()  # fail on a missing key before quoting a cost
    model = model_id(a.model)
    print(f"generating {a.out} model={model} size={a.size} aspect={a.aspect} refs={len(a.ref)} "
          f"(about ${COST_HINT[a.size]:.2f})", file=sys.stderr)
    out = generate(prompt, a.out, a.size, a.aspect, a.ref, model)
    print(f"SAVED {out}")


if __name__ == "__main__":
    main()
