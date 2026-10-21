#!/usr/bin/env python3
"""Prove the Gemini key works with a REAL API call (not just "is the variable set").

Checks, in order: the key is set; the models list call succeeds; the vision model used by the
print gate is visible; the image models used by gen_image.py are visible. Prints which thing is
wrong (invalid key, quota, region, model not available) and exits non-zero on a hard failure.
Costs nothing: listing models is free.

usage: python3 scripts/probe_gemini.py
"""
from __future__ import annotations

import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import gemini_key  # noqa: E402
from gen_image import model_id  # noqa: E402
from print_gate import VISION_MODEL  # noqa: E402


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        return 0
    key = gemini_key()
    url = "https://generativelanguage.googleapis.com/v1beta/models?pageSize=1000&key=" + key
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        body = e.read().decode()[:400]
        why = {400: "invalid key (or malformed)", 403: "key not allowed: API disabled, or unsupported region",
               429: "quota exhausted"}.get(e.code, "unexpected error")
        print(f"FAIL  Gemini API HTTP {e.code}: {why}\n      {body}")
        if e.code in (400, 401, 403):
            print("      Create or replace the key at https://aistudio.google.com/apikey and put it on the "
                  "GEMINI_API_KEY= line in .env")
        return 1
    except urllib.error.URLError as e:
        print(f"FAIL  could not reach the Gemini API: {e.reason}")
        return 1
    names = {m.get("name", "").split("/")[-1] for m in data.get("models", [])}
    print(f"OK    key accepted, {len(names)} models visible")
    hard = 0
    want = {"print gate (vision)": VISION_MODEL,
            "plates, nb2": model_id("nb2"),
            "plates, pro": model_id("pro")}
    for label, m in want.items():
        if m in names:
            print(f"OK    {label}: {m}")
        else:
            print(f"WARN  {label}: {m} not listed for this key. Google may have renamed it; "
                  f"pick a current id from the list and set it in .env "
                  f"(AD_LIBRARY_VISION_MODEL / AD_LIBRARY_IMAGE_MODEL_NB2 / AD_LIBRARY_IMAGE_MODEL_PRO).")
            if label.startswith("print"):
                hard = 1
    return hard


if __name__ == "__main__":
    sys.exit(main())
