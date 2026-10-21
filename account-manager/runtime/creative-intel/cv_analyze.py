#!/usr/bin/env python3
"""Per-second creative CV analysis of a video ad via Gemini multimodal.

Uploads a video to the Gemini File API, then asks for a structured second-by-
second timeline (script/transcript, on-screen text, shots, pace, hook, product,
CTA) PLUS ad-level creative descriptors used by the cross-video regression.

Usage:
  cv_analyze.py --video PATH --out OUT.json [--model gemini-2.5-pro] [--label NAME]

Key: GEMINI_API_KEY, loaded from the package .env (override the path with the
AM_ENV env var if your key lives elsewhere).
"""
import argparse
import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai

# Load the package .env (runtime/.env, one level up from creative-intel/), or AM_ENV if set.
load_dotenv(os.environ.get("AM_ENV", Path(__file__).resolve().parents[1] / ".env"))

PROMPT = """You are a senior performance-creative analyst. Analyze this video AD
second by second. Be precise and literal — describe what is actually on screen
and said, not what you imagine. Return STRICT JSON matching this schema:

{
  "duration_sec": <number>,
  "timeline": [   // one entry per ~1s (merge only identical adjacent seconds)
    {"t": <sec int>,
     "shot": "<what is visually on screen>",
     "on_screen_text": "<exact text overlay, or ''>",
     "spoken": "<verbatim words spoken/VO this second, or ''>",
     "is_cut": <true if a new shot starts this second>,
     "people": <int faces/people on screen>,
     "product_visible": <true/false>}
  ],
  "hook": {"first_3s_summary": "<what happens 0-3s>",
           "hook_archetype": "<one of: question, bold_claim, problem, pattern_interrupt, demo, testimonial, offer, story, other>",
           "hook_has_text": <bool>, "hook_has_face": <bool>, "hook_has_product": <bool>},
  "descriptors": {   // ad-level features for cross-video regression
     "style": "<ugc | studio | claymation | ai_generated | motion_graphics | mixed>",
     "time_to_first_product_sec": <number or null>,
     "time_to_first_text_sec": <number or null>,
     "cuts_total": <int>,
     "cuts_per_10s": <number>,
     "on_screen_text_density": "<low|medium|high>",
     "talent_present": <bool>,
     "voiceover": <bool>,
     "music_energy": "<none|low|medium|high>",
     "claim_type": "<offer|benefit|social_proof|education|humor|none>",
     "cta_type": "<shop|learn|signup|none|other>",
     "cta_time_sec": <number or null>,
     "emotional_tone": "<comma-separated, e.g. playful, urgent, warm>",
     "pacing": "<slow|moderate|fast>"},
  "scenes": [ {"start": <sec>, "end": <sec>, "label": "<scene purpose>"} ]
}

Return ONLY the JSON, no prose."""


def analyze(video_path, model, label=None):
    client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    print(f"uploading {video_path} ...")
    f = client.files.upload(file=video_path)
    # wait for ACTIVE
    for _ in range(60):
        f = client.files.get(name=f.name)
        if f.state == "ACTIVE":
            break
        if f.state == "FAILED":
            raise RuntimeError("file processing FAILED")
        time.sleep(2)
    print(f"file active: {f.name}")
    resp = client.models.generate_content(
        model=model,
        contents=[f, PROMPT],
        config={"response_mime_type": "application/json", "temperature": 0.2},
    )
    data = json.loads(resp.text)
    if label:
        data["_label"] = label
    data["_video"] = str(video_path)
    data["_model"] = model
    return data


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", default="gemini-2.5-pro")
    ap.add_argument("--label", default=None)
    args = ap.parse_args()
    try:
        data = analyze(args.video, args.model, args.label)
    except Exception as e:  # noqa: BLE001
        if args.model != "gemini-2.5-flash":
            print(f"{args.model} failed ({e}); retrying with gemini-2.5-flash")
            data = analyze(args.video, "gemini-2.5-flash", args.label)
        else:
            raise
    Path(args.out).write_text(json.dumps(data, indent=2))
    tl = data.get("timeline", [])
    print(f"OK — {len(tl)} timeline entries, {data.get('duration_sec')}s, "
          f"hook={data.get('hook',{}).get('hook_archetype')}, "
          f"style={data.get('descriptors',{}).get('style')}")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
