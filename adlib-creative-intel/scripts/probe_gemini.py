#!/usr/bin/env python3
"""Prove the Gemini key actually WORKS — not just that a variable is set.

An "is the env var non-empty" check is a false green: a typo'd key, a revoked
key, a project without model access, or a blown quota all pass it and then fail
at the moment you try to analyze a video. This makes a real API call instead and
translates the failure into the specific thing you need to fix.

  --deep   also upload a real video file through the File API, which is the
           exact path video analysis uses. Slower, and the most honest check.

Usage:
  probe_gemini.py            # key validity + model access (fast)
  probe_gemini.py --deep     # the above, plus a real video upload
"""
import argparse
import os
import sys
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parent.parent

HELP = """
How to fix this:
  1. Go to  https://aistudio.google.com/apikey
  2. Sign in with any Google account
  3. Click "Create API key"  (free tier is enough to get started)
  4. Copy the key, then either:
       echo 'GEMINI_API_KEY=your-key-here' >> .env
     or paste it to your agent and ask it to write .env for you
  5. Re-run:  python3 scripts/probe_gemini.py
"""


def _load_key():
    if not os.environ.get("GEMINI_API_KEY"):
        env_path = Path(os.environ.get("ADLIB_ENV", PKG_ROOT / ".env"))
        if env_path.exists():
            for line in env_path.read_text().splitlines():
                line = line.strip()
                if line.startswith("GEMINI_API_KEY=") and not line.startswith("#"):
                    val = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if val:
                        os.environ["GEMINI_API_KEY"] = val
    return os.environ.get("GEMINI_API_KEY")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--deep", action="store_true",
                    help="also test a real video upload (the actual analysis path)")
    ap.add_argument("--model", default="gemini-2.5-flash")
    args = ap.parse_args()

    key = _load_key()
    if not key:
        print("❌ GEMINI_API_KEY is not set.")
        print(HELP)
        sys.exit(1)
    if len(key) < 20:
        print(f"❌ GEMINI_API_KEY looks too short ({len(key)} chars) — probably truncated.")
        print(HELP)
        sys.exit(1)

    try:
        from google import genai
    except ImportError:
        print("❌ google-genai not installed → pip install -r requirements.txt")
        sys.exit(1)

    client = genai.Client(api_key=key)

    # 1. real call: key validity + model access
    try:
        r = client.models.generate_content(
            model=args.model, contents="Reply with the single word: ok")
        txt = (r.text or "").strip().lower()
        print(f"✅ Key works — {args.model} responded ({txt[:20]!r})")
    except Exception as e:  # noqa: BLE001
        msg = str(e)
        print("❌ The key is set but the API call FAILED.")
        low = msg.lower()
        if "api_key_invalid" in low or "api key not valid" in low or "400" in low:
            print("   Cause: the key is not valid. Re-copy it — no quotes, no spaces.")
        elif "permission" in low or "403" in low:
            print("   Cause: the key lacks access to this model, or the API is not")
            print("   enabled for that Google project.")
        elif "quota" in low or "429" in low or "resource_exhausted" in low:
            print("   Cause: quota exceeded. Wait for the window to reset, or enable")
            print("   billing. This is not a setup error — the key is fine.")
        elif "location" in low or "user location" in low:
            print("   Cause: the Gemini API is not available in your region.")
        else:
            print(f"   Raw error: {msg[:300]}")
        print(HELP)
        sys.exit(1)

    # 2. optional: the actual video path
    if args.deep:
        mp4 = next((p for p in sorted(
            (Path(os.environ.get("ADLIB_DATA", PKG_ROOT / "data"))).rglob("*.mp4"),
            key=lambda p: p.stat().st_size)), None)
        if not mp4:
            print("⚠️  --deep skipped: no harvested .mp4 yet. Run a harvest first, "
                  "then re-run with --deep.")
            return
        print(f"   uploading {mp4.name} ({mp4.stat().st_size / 1e6:.1f}MB) via the File API ...")
        try:
            import time
            f = client.files.upload(file=str(mp4))
            for _ in range(60):
                f = client.files.get(name=f.name)
                if f.state == "ACTIVE":
                    break
                if f.state == "FAILED":
                    raise RuntimeError("file processing FAILED")
                time.sleep(2)
            r = client.models.generate_content(
                model=args.model,
                contents=[f, "In one short sentence, what happens in this video?"])
            print(f"✅ Video analysis path works — model saw the file and replied:")
            print(f"   {(r.text or '').strip()[:160]}")
        except Exception as e:  # noqa: BLE001
            print(f"❌ Video upload/analysis failed: {str(e)[:300]}")
            print("   The key is valid (step 1 passed), so this is a File API or")
            print("   quota issue rather than a bad key.")
            sys.exit(1)

    print("\nYou're set up for creative analysis. Run:")
    print("  python3 scripts/full_run.py --page-id <ID> --slug <name> --cv-limit 0")


if __name__ == "__main__":
    main()
