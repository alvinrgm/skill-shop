#!/usr/bin/env python3
"""Per-second creative analysis of a video ad, via Gemini multimodal.

Uploads a video to the Gemini File API and asks for a structured second-by-
second timeline (script, on-screen text, shots, pacing, hook, product, CTA)
plus ad-level descriptors used by the cross-video analysis in compete.py.

This is the ONLY step that needs an API key. Harvesting and downloading work
with no credentials at all, so you can run the whole longevity pipeline first
and add creative analysis later.

Key resolution, in order:
  1. GEMINI_API_KEY in the environment
  2. GEMINI_API_KEY in a .env file (package root, or $ADLIB_ENV)
Get a key: https://aistudio.google.com/apikey

Usage:
  cv_analyze.py --video PATH --out OUT.json [--model gemini-2.5-pro] [--label NAME]
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parent.parent

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
  "descriptors": {   // ad-level features for the cross-video analysis
     "style": "<ugc | studio | animation | ai_generated | motion_graphics | mixed>",
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


def _load_key():
    if os.environ.get("GEMINI_API_KEY"):
        return os.environ["GEMINI_API_KEY"]
    env_path = Path(os.environ.get("ADLIB_ENV", PKG_ROOT / ".env"))
    if env_path.exists():
        try:
            from dotenv import load_dotenv
            load_dotenv(env_path)
        except ImportError:
            for line in env_path.read_text().splitlines():
                if line.strip().startswith("GEMINI_API_KEY="):
                    os.environ["GEMINI_API_KEY"] = line.split("=", 1)[1].strip()
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        sys.exit(
            "GEMINI_API_KEY not found.\n"
            f"  Set it in the environment, or add it to {env_path}\n"
            "  Get a key: https://aistudio.google.com/apikey\n"
            "  (Only the creative-analysis step needs this — harvest, download, "
            "and the longevity report all run without any key.)")
    return key


class AnalysisTimeout(RuntimeError):
    """One video exceeded its wall-clock budget."""


class _Watchdog:
    """Hard wall-clock cap on a single video.

    The SDK's own timeouts do not cover every stage (upload streaming, file-state
    polling), and a stalled request otherwise blocks forever with no output — a
    real hang observed in testing: one 11MB video sat for 90 minutes using 1.3s
    of CPU while the whole corpus run waited behind it. A run must never be
    hostage to one bad video.
    """

    def __init__(self, seconds):
        self.seconds = seconds

    def __enter__(self):
        try:
            import signal
            self._sig = signal
            self._old = signal.signal(signal.SIGALRM, self._fire)
            signal.alarm(int(self.seconds))
        except (ImportError, ValueError, AttributeError):
            self._sig = None  # not the main thread, or unsupported platform
        return self

    def _fire(self, *_):
        raise AnalysisTimeout(f"exceeded {self.seconds}s budget")

    def __exit__(self, *exc):
        if getattr(self, "_sig", None):
            self._sig.alarm(0)
            self._sig.signal(self._sig.SIGALRM, self._old)
        return False


TRANSIENT_MARKERS = ("504", "503", "502", "429", "deadline_exceeded",
                     "unavailable", "resource_exhausted", "internal error",
                     "timed out", "connection reset", "temporarily")


def _is_transient(err):
    """Server-side hiccups worth retrying, vs. real errors worth surfacing.

    A 504 from the API is NOT the same as our own watchdog firing: the request
    reached Google and Google gave up. Retrying that is usually enough, and not
    retrying it silently drops a video from the corpus — which quietly biases
    every percentage computed downstream.
    """
    s = str(err).lower()
    return any(m in s for m in TRANSIENT_MARKERS)


def analyze(video_path, model, label=None, timeout_sec=300, http_timeout_sec=120,
            retries=2, backoff_sec=20):
    try:
        from google import genai
    except ImportError:
        sys.exit("google-genai not installed. Run: pip install -r requirements.txt")
    try:  # per-request timeout where the SDK supports it (milliseconds)
        client = genai.Client(api_key=_load_key(),
                              http_options={"timeout": int(http_timeout_sec * 1000)})
    except Exception:  # noqa: BLE001 — older SDKs reject http_options
        client = genai.Client(api_key=_load_key())

    last_err = None
    for attempt in range(retries + 1):
        try:
            with _Watchdog(timeout_sec):
                f = client.files.upload(file=video_path)
                deadline = time.time() + min(timeout_sec, 180)
                while time.time() < deadline:
                    f = client.files.get(name=f.name)
                    if f.state == "ACTIVE":
                        break
                    if f.state == "FAILED":
                        raise RuntimeError("file processing FAILED")
                    time.sleep(2)
                else:
                    raise AnalysisTimeout("file never became ACTIVE")
                resp = client.models.generate_content(
                    model=model,
                    contents=[f, PROMPT],
                    config={"response_mime_type": "application/json",
                            "temperature": 0.2},
                )
            break
        except Exception as e:  # noqa: BLE001
            last_err = e
            if attempt < retries and _is_transient(e):
                wait = backoff_sec * (attempt + 1)
                print(f"      transient error ({str(e)[:80]}) — retrying in {wait}s "
                      f"[{attempt + 1}/{retries}]", flush=True)
                time.sleep(wait)
                continue
            raise
    else:  # pragma: no cover - loop always breaks or raises
        raise last_err

    data = json.loads(resp.text)
    if label:
        data["_label"] = label
    data["_video"] = str(video_path)
    data["_model"] = model
    return data


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--video", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", default="gemini-2.5-pro")
    ap.add_argument("--label", default=None)
    ap.add_argument("--timeout", type=int, default=300,
                    help="hard wall-clock budget for this video, seconds (default 300)")
    args = ap.parse_args()
    try:
        data = analyze(args.video, args.model, args.label, timeout_sec=args.timeout)
    except Exception as e:  # noqa: BLE001
        if args.model != "gemini-2.5-flash":
            print(f"{args.model} failed ({e}); retrying with gemini-2.5-flash")
            data = analyze(args.video, "gemini-2.5-flash", args.label,
                           timeout_sec=args.timeout)
        else:
            raise
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, indent=2))
    print(f"OK — {len(data.get('timeline', []))} timeline entries, "
          f"{data.get('duration_sec')}s, "
          f"hook={data.get('hook', {}).get('hook_archetype')}, "
          f"style={data.get('descriptors', {}).get('style')}")
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
