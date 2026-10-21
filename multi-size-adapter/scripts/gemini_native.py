#!/usr/bin/env python3
"""
gemini_native.py: generative native re-composition backend for the Multi-Size Creative Adapter.

Called by adapt.py when a size uses "strategy": "generate". Takes the base creative + a
per-size prompt (written by Claude in the plan) and produces a natively re-composed canvas
at the exact target pixel size.

No image library needed for the shipped formats. This tool ships four formats (1:1, 4:5,
9:16, 16:9), all of which the model generates natively at the correct shape -- so the bytes
Google returns are written straight to disk at roughly 2K on the long edge. Nothing to crop,
nothing to resize, no Pillow, no pip install. A designer scales the file in their design tool
as part of finishing it anyway.

Pillow is only touched if someone opts into a format outside those four (see "Adding a
format" in SKILL.md), where a crop to the requested shape IS required. If Pillow is missing
in that case the size fails with a plain-English message instead of crashing the batch.

Key resolution order: config.yml `gemini_api_key` (next to the skill), then the
GEMINI_API_KEY environment variable. The key belongs to YOUR team (one shared key created
by your team lead is fine). Nothing else is sent anywhere: one HTTPS call to Google's
Gemini API per generated size, carrying the base image + the instruction prompt.

Standalone use (adapt.py normally drives this):
    python3 gemini_native.py --base creative.png --out out.png --width 1080 --height 1920 \
        --prompt-file prompt.txt
"""

import argparse
import base64
import json
import mimetypes
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

MODEL = "gemini-3-pro-image-preview"
ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"

# The four formats this tool ships with. All are generated NATIVELY by the model at the
# right shape, so no cropping or resizing is needed and no image library is required.
# More formats can be added -- see "Adding a format" in SKILL.md. Anything outside this
# set needs a crop step (and therefore Pillow), which is why it is opt-in, not default.
SUPPORTED_RATIOS = {
    "1:1": (1, 1), "4:5": (4, 5), "9:16": (9, 16), "16:9": (16, 9),
}

# Ratios the model can also produce, available if someone explicitly asks for them later.
EXTRA_RATIOS = {
    "2:3": (2, 3), "3:2": (3, 2), "3:4": (3, 4), "4:3": (4, 3), "5:4": (5, 4), "21:9": (21, 9),
}


def sniff_image(data: bytes):
    """Return (extension, width, height) by reading the file header directly. Stdlib only, so
    this works on a machine with no image library. Google returns JPEG or PNG depending on the
    request; writing JPEG bytes under a .png name would be wrong, and asserting the size we
    ASKED for rather than the size we GOT would be worse."""
    if data[:3] == b"\xff\xd8\xff":                                   # JPEG
        i, n = 2, len(data)
        while i < n - 9:
            if data[i] != 0xFF:
                i += 1
                continue
            marker = data[i + 1]
            if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
                i += 2
                continue
            seglen = int.from_bytes(data[i + 2:i + 4], "big")
            if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                          0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):          # SOFn carries the size
                h = int.from_bytes(data[i + 5:i + 7], "big")
                w = int.from_bytes(data[i + 7:i + 9], "big")
                return "jpg", w, h
            i += 2 + seglen
        return "jpg", None, None
    if data[:8] == b"\x89PNG\r\n\x1a\n":                             # PNG
        w = int.from_bytes(data[16:20], "big")
        h = int.from_bytes(data[20:24], "big")
        return "png", w, h
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "webp", None, None
    return "bin", None, None


def _one_line(text: str, limit: int = 160) -> str:
    """Collapse an API error body to a single short line. It ends up inside a markdown table
    cell in the review sheet, so embedded newlines would shatter the table."""
    flat = " ".join(str(text).split())
    return flat[:limit] + ("..." if len(flat) > limit else "")


def _explain_http_error(e) -> str:
    """Turn a Google HTTP error into something a designer can act on.

    Note the important case: an invalid OR unbilled key comes back as HTTP 400 with
    API_KEY_INVALID / billing language, NOT 401/403. Handling only 401/403 would leave the
    single most likely first-run failure falling through to a raw JSON dump."""
    try:
        body = e.read().decode()
    except Exception:
        body = ""
    low = body.lower()
    if e.code == 400 and ("api key not valid" in low or "api_key_invalid" in low):
        return ("The Gemini API key was rejected as invalid. Ask your team lead for the current "
                "key. (Google said: " + _one_line(body, 90) + ")")
    if e.code == 400 and ("billing" in low or "billed" in low):
        return ("The Gemini key works but its Google project has no billing enabled. Image "
                "generation is not available on the free tier -- see SETUP.md 'For the team "
                "lead'. (Google said: " + _one_line(body, 90) + ")")
    if e.code in (401, 403):
        return ("The Gemini API key was refused (not authorised). Ask your team lead for the "
                "current key. (Google said: " + _one_line(body, 90) + ")")
    if e.code == 429:
        return ("Hit Google's rate limit. The tool waits and retries automatically; if you see "
                "this, the retries were also rate-limited. Wait a few minutes and re-run.")
    if e.code >= 500:
        return f"Google's service returned an error (HTTP {e.code}). This is usually temporary; try again."
    return f"Gemini API error HTTP {e.code}: {_one_line(body, 120)}"


def resolve_api_key(skill_root: Path):
    """config.yml gemini_api_key first, then GEMINI_API_KEY env var."""
    cfg = skill_root / "config.yml"
    found = None
    if cfg.exists():
        # utf-8-sig strips a byte-order mark. Notepad and PowerShell's Out-File write one by
        # default, and Python's .strip() does not treat it as whitespace -- so without this a
        # Windows user gets a green health check and then "no API key" on every single size.
        for line in cfg.read_text(encoding="utf-8-sig").splitlines():
            stripped = line.split("#", 1)[0].strip()
            if stripped.startswith("gemini_api_key:"):
                val = stripped.split(":", 1)[1].strip().strip("'\"")
                if val:
                    found = val          # last match wins, matching doctor.sh / doctor.ps1
    return found or os.environ.get("GEMINI_API_KEY") or None


def nearest_ratio(width, height, allow_extra=False):
    """Return (ratio_name, coverage) where coverage is the fraction of the generated
    canvas the final crop keeps (1.0 = exact ratio match, meaning no crop needed)."""
    target = width / height
    pool = dict(SUPPORTED_RATIOS)
    if allow_extra:
        pool.update(EXTRA_RATIOS)
    best_name, best_dist = None, None
    for name, (rw, rh) in pool.items():
        r = rw / rh
        # log distance treats 2x-too-wide and 2x-too-tall symmetrically
        import math
        dist = abs(math.log(target / r))
        if best_dist is None or dist < best_dist:
            best_name, best_dist = name, dist
    rw, rh = pool[best_name]
    gen_ratio = rw / rh
    coverage = min(target / gen_ratio, gen_ratio / target)
    return best_name, coverage


def _post_with_backoff(req, attempts: int = 3):
    """Send the request, backing off on rate limits. Without this, one 429 mid-batch cascades:
    every remaining size fires immediately, is also rate-limited, and the whole rest of the run
    degrades in a single pass."""
    import time
    delay = 20
    for attempt in range(attempts):
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            transient = e.code == 429 or e.code >= 500
            if not transient or attempt == attempts - 1:
                raise
            retry_after = e.headers.get("Retry-After") if e.headers else None
            wait = int(retry_after) if (retry_after or "").isdigit() else delay
            # Google can ask for a very long wait. Honour it up to a point -- an unattended
            # hour-long sleep per size is worse than failing the size and letting the batch
            # move on, especially when the user was quoted "about 35 seconds each".
            wait = min(wait, 90)
            print(f"    rate limited, waiting {wait}s before retry "
                  f"({attempt + 1}/{attempts - 1})...", file=sys.stderr)
            time.sleep(wait)
            delay *= 2


# Gemini rejects inline payloads over ~20MB; base64 inflates by ~4/3.
MAX_INLINE_BYTES = 14 * 1024 * 1024


def generate_native(base_path: Path, out_path: Path, width: int, height: int,
                    prompt: str, api_key: str, image_size: str = "2K",
                    allow_extra: bool = False) -> dict:
    """One generation call + exact-size finishing crop. Returns metadata for the review sheet.

    Raises RuntimeError with a plain-English message on API failure so adapt.py can log it
    per size without killing the whole run.
    """
    ratio_name, coverage = nearest_ratio(width, height, allow_extra=allow_extra)

    data = base_path.read_bytes()
    if not data:
        raise RuntimeError(f"The source image {base_path.name} is empty (0 bytes).")
    kind, _, _ = sniff_image(data)
    if kind == "bin":
        raise RuntimeError(f"{base_path.name} does not look like an image file (its contents "
                           f"are not JPEG, PNG or WEBP). Check you handed over the right file.")
    if len(prompt) > 8000:
        raise RuntimeError(
            f"The generation prompt is {len(prompt)} characters, which is far longer than a "
            f"real adaptation prompt needs (limit 8000). This usually means text from the "
            f"source creative was pulled in wholesale. Shorten it and check the creative for "
            f"unexpected embedded text.")
    if len(data) > MAX_INLINE_BYTES:
        raise RuntimeError(f"The source image {base_path.name} is "
                           f"{len(data) / 1024 / 1024:.1f}MB, which is too large to send "
                           f"(limit is about {MAX_INLINE_BYTES // 1024 // 1024}MB). Export it "
                           f"smaller and try again -- no money was spent.")
    mime = mimetypes.guess_type(str(base_path))[0] or "image/png"
    body = {
        "contents": [{"parts": [
            {"text": prompt},
            {"inlineData": {"mimeType": mime, "data": base64.b64encode(data).decode()}},
        ]}],
        "generationConfig": {
            "responseModalities": ["IMAGE"],
            "imageConfig": {"aspectRatio": ratio_name, "imageSize": image_size},
        },
    }
    req = urllib.request.Request(
        f"{ENDPOINT}?key={api_key}",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        resp = _post_with_backoff(req)
    except urllib.error.HTTPError as e:
        raise RuntimeError(_explain_http_error(e))
    except urllib.error.URLError as e:
        raise RuntimeError(f"Could not reach the Gemini API. Check the internet connection. ({e.reason})")

    img_bytes = None
    for cand in resp.get("candidates", []):
        for part in cand.get("content", {}).get("parts", []):
            inline = part.get("inlineData") or part.get("inline_data")
            if inline and inline.get("data"):
                img_bytes = base64.b64decode(inline["data"])
                break
    if img_bytes is None:
        raise RuntimeError(f"Gemini returned no image (possibly refused). "
                           f"Response head: {json.dumps(resp)[:300]}")

    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Native path (all four shipped formats): the model already returned the right shape.
    # Write the bytes as-is. No image library, no pip install, no quality loss from resampling.
    if coverage > 0.995:
        ext, gw, gh = sniff_image(img_bytes)
        real_path = out_path.with_suffix("." + ext)
        real_path.write_bytes(img_bytes)
        meta = {"ratio_used": ratio_name, "coverage": round(coverage, 3),
                "crop": "none (native shape)", "path": str(real_path),
                "requested_px": f"{width}x{height}"}
        if gw and gh:
            meta["actual_px"] = f"{gw}x{gh}"
            # The model's canvas is not always an exact multiple of the requested shape.
            # Report the real drift instead of asserting the ratio we asked for.
            drift = abs((gw / gh) / (width / height) - 1) * 100
            meta["ratio_drift_pct"] = round(drift, 2)
        return meta

    # Opt-in path only: a requested shape the model cannot make directly, so it must be
    # cropped. This is the ONLY case that needs Pillow.
    try:
        from PIL import Image
    except ImportError:
        raise RuntimeError(
            f"{width}x{height} is not one of the four built-in formats, so it needs a crop "
            f"step, and the Pillow image library is not installed. Either stick to the "
            f"built-in formats (square, 4:5, 9:16, 16:9) or install Pillow: "
            f"python3 -m pip install --user Pillow")

    tmp = out_path.with_suffix(".gen.png")
    tmp.write_bytes(img_bytes)
    img = Image.open(tmp).convert("RGB")
    gw, gh = img.size
    target = width / height
    if gw / gh > target:
        crop_w = round(gh * target)
        left = (gw - crop_w) // 2
        img = img.crop((left, 0, left + crop_w, gh))
    elif gw / gh < target:
        crop_h = round(gw / target)
        top = (gh - crop_h) // 2
        img = img.crop((0, top, gw, top + crop_h))
    img = img.resize((width, height), Image.LANCZOS)
    img.save(out_path)
    tmp.unlink(missing_ok=True)

    return {"ratio_used": ratio_name, "coverage": round(coverage, 3),
            "crop": f"cropped from {gw}x{gh}", "path": str(out_path),
            "requested_px": f"{width}x{height}", "actual_px": f"{width}x{height}",
            "ratio_drift_pct": 0.0}


def main():
    ap = argparse.ArgumentParser(description="Generate one natively re-composed size.")
    ap.add_argument("--base", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--width", type=int, required=True)
    ap.add_argument("--height", type=int, required=True)
    ap.add_argument("--prompt-file", required=True)
    a = ap.parse_args()

    key = resolve_api_key(Path(__file__).resolve().parent.parent)
    if not key:
        sys.exit("No Gemini API key found. Put it in config.yml (gemini_api_key: ...) or set "
                 "GEMINI_API_KEY. Your team lead has the shared key -- see SETUP.md.")
    meta = generate_native(Path(a.base), Path(a.out), a.width, a.height,
                           Path(a.prompt_file).read_text(), key)
    print(f"OK {a.out} {meta}")


if __name__ == "__main__":
    main()
