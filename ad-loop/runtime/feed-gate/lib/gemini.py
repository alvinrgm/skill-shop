#!/usr/bin/env python3
"""Gemini access for the feed-survival gate.

Key: GEMINI_API_KEY from the environment or the ad-loop package .env. Never a
credit-billing generation service: this module only reads.

Two capabilities:
  extract()  - "what is this ad for / offer / CTA / hook", used by ablate.py
               on the original and on every mutant.
  localize() - bounding boxes of text + critical elements, used by the
               harness's chrome-collision report. Gemini returns boxes as
               [ymin, xmin, ymax, xmax] normalized to 0-1000; we convert to
               asset pixels here so no caller has to know that.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai

ENV_PATH = Path(__file__).resolve().parents[3] / ".env"   # <package>/.env
DEFAULT_MODEL = "gemini-2.5-flash"

_client = None


def client():
    global _client
    if _client is None:
        load_dotenv(ENV_PATH)
        key = os.environ.get("GEMINI_API_KEY")
        if not key:
            raise RuntimeError(f"GEMINI_API_KEY not found in {ENV_PATH}")
        _client = genai.Client(api_key=key)
    return _client


def _upload(path: Path, timeout_s: int = 240):
    c = client()
    f = c.files.upload(file=str(path))
    waited = 0
    while f.state != "ACTIVE":
        if f.state == "FAILED":
            raise RuntimeError(f"gemini file processing FAILED for {path.name}")
        if waited > timeout_s:
            raise RuntimeError(f"gemini file never became ACTIVE: {path.name}")
        time.sleep(2)
        waited += 2
        f = c.files.get(name=f.name)
    return f


def _call(path: Path, prompt: str, model: str, temperature: float = 0.0) -> dict:
    f = _upload(path)
    resp = client().models.generate_content(
        model=model,
        contents=[f, prompt],
        config={"response_mime_type": "application/json",
                "temperature": temperature},
    )
    return json.loads(resp.text)


# ------------------------------------------------------------ extract ----
EXTRACT_PROMPT = """You are a person who just encountered this ad while
scrolling a phone. You get exactly what the file gives you and nothing else -
no outside knowledge of the brand, no assumptions about what was "probably"
there. If something is genuinely unreadable, blacked out, too small,
or absent, you MUST report it as not known rather than guessing.

Answer four questions and be strict about the `known` flags.

Return STRICT JSON:
{
  "product":  {"known": <bool>, "value": "<what is this ad for? the product or
                service category and brand if legible>",
               "evidence": "<what in the file told you - e.g. 'pack shot centre',
                'headline names it', 'logo bottom-left'>"},
  "offer":    {"known": <bool>, "value": "<the specific offer/claim/promise>",
               "evidence": "<...>"},
  "cta":      {"known": <bool>, "value": "<what you are being asked to do>",
               "evidence": "<...>"},
  "hook":     {"known": <bool>, "value": "<what grabs you first - the first
                thing you notice>",
               "evidence": "<...>"},
  "onscreen_text": ["<every legible text string, verbatim, in order>"],
  "legibility_notes": "<anything unreadable, cropped, obscured, or too small,
                        and WHERE it was>"
}

Set "known": false and value "" when you cannot determine it FROM THIS FILE.
Do not infer the brand from partial letters. Do not describe what you assume a
covered region contained. Return ONLY the JSON."""


def extract(path: Path, model: str = DEFAULT_MODEL) -> dict:
    """What meaning survives in this file? Used on original + every mutant."""
    return _call(path, EXTRACT_PROMPT, model)


# ----------------------------------------------------------- localize ----
LOCALIZE_PROMPT = """Locate every element in this ad creative that carries
meaning a viewer needs. Include: each block of on-screen text (headline,
subhead, price, disclaimer, badge), the logo/wordmark, the product itself, and
any CTA button.

For EACH element return a 2D bounding box as [ymin, xmin, ymax, xmax]
normalized to 0-1000.

Return STRICT JSON:
{"elements": [
  {"label": "<short name, e.g. 'headline: STONE MILLED'>",
   "kind": "<text | logo | product | cta | badge | other>",
   "criticality": "<critical | supporting | decorative>",
   "text": "<verbatim text if it is text, else ''>",
   "box_2d": [ymin, xmin, ymax, xmax]}
]}

"critical" = the ad stops working if the viewer never sees it.
Return ONLY the JSON."""


def localize(path: Path, asset_w: int, asset_h: int,
             model: str = DEFAULT_MODEL) -> list[dict]:
    """Bounding boxes of meaning-carrying elements, in ASSET pixel coords."""
    data = _call(path, LOCALIZE_PROMPT, model)
    out = []
    for el in data.get("elements", []):
        b = el.get("box_2d") or []
        if len(b) != 4:
            continue
        ymin, xmin, ymax, xmax = b
        out.append({
            "label": el.get("label", "?"),
            "kind": el.get("kind", "other"),
            "criticality": el.get("criticality", "supporting"),
            "text": el.get("text", ""),
            "x": xmin / 1000.0 * asset_w,
            "y": ymin / 1000.0 * asset_h,
            "w": max(0.0, (xmax - xmin) / 1000.0 * asset_w),
            "h": max(0.0, (ymax - ymin) / 1000.0 * asset_h),
        })
    return out
