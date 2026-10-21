#!/usr/bin/env python3
"""The letter-perfect print gate for generated plates that show the product.

Image models garble fine print, and worse, they print fluent words that are not on your pack
(invented claims read as fact). This gate makes a fresh vision model TRANSCRIBE every line of
printing it can see, character for character, then a deterministic scorer DECIDES by comparing
each line with the real printed strings of your pack (brand/pack-strings.json).

  wrong = 0  -> the plate may be used
  wrong > 0  -> repair it (label_composite.py) and gate again, or regenerate. Never blur to pass.

A line the model cannot read at all ("unresolvable") does not fail: print that is too small to
read at phone scale is fine. A crisp line that is close to, but not, a real string is the worst
case (fluent garble) and fails. A crisp line that matches nothing on the pack also fails.

Scale: by default the plate is first resampled to the 1080x1350 delivery frame and magnified 3x,
which is what a person zooming into the shipped ad can see. --native reads the file at its own
resolution (use it for wide contact sheets).

usage:
  python3 scripts/print_gate.py --brand <slug> --plates 'plates/*.png' --out qa/
  python3 scripts/print_gate.py --truth my-pack-strings.json --plates p.png --out qa/ [--native]
Exit code: 0 when every plate has wrong=0, 1 otherwise.
"""
from __future__ import annotations

import argparse
import base64
import concurrent.futures as cf
import difflib
import glob
import io
import json
import os
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import brand_dir, gemini_key  # noqa: E402

from PIL import Image  # noqa: E402

VISION_MODEL = os.environ.get("AD_LIBRARY_VISION_MODEL", "gemini-3.1-pro-preview")
DELIV = (1080, 1350)

PROMPT = """You are a print-quality examiner. You are looking at ONE photograph that contains a
product package with printing on it. You have no context and you are not comparing it to anything.

Read the package's printing at maximum magnification and answer in JSON.

For EVERY separate line or block of printing you can see anywhere on the package, add an entry to
"strings". Transcribe EXACTLY what the letters on the image say, character for character,
including any misspelling, invented word, or nonsense. Do NOT correct anything, do NOT guess at
what it was probably meant to say, and do NOT fill in a word you cannot actually read.
Transcribing what a real package would say instead of what THIS image says is the single worst
thing you can do here.

Classify each entry's "legibility":
  "crisp"        - letterforms are sharp and individually distinguishable
  "soft"         - you can mostly make it out but some characters are ambiguous
  "unresolvable" - you can see printing there but cannot make out any letters at all

{
 "strings": [ {"text":"<exactly what the letters say>", "where":"<=8 words",
               "legibility":"crisp"|"soft"|"unresolvable",
               "is_real_word_or_phrase": true|false} ],
 "any_garbled_or_misspelled": true|false,
 "garbled_examples": ["..."],
 "worst_print_defect": "<=25 words"
}
JSON only."""


def ask(prompt: str, img: Image.Image, maxpx: int = 2600) -> str:
    im = img.copy()
    im.thumbnail((maxpx, maxpx), Image.LANCZOS)
    buf = io.BytesIO()
    im.convert("RGB").save(buf, "JPEG", quality=95)
    body = json.dumps({"contents": [{"parts": [
        {"text": prompt},
        {"inlineData": {"mimeType": "image/jpeg", "data": base64.b64encode(buf.getvalue()).decode()}}]}],
        "generationConfig": {"temperature": 0.0}}).encode()
    url = (f"https://generativelanguage.googleapis.com/v1beta/models/{VISION_MODEL}:generateContent"
           f"?key={gemini_key()}")
    last = None
    for attempt in range(6):  # transport retry only; a 400/403/404 raises at once
        try:
            req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=300) as r:
                resp = json.load(r)
            break
        except urllib.error.HTTPError as e:
            last = e
            if e.code not in (408, 429, 500, 502, 503, 504):
                raise RuntimeError(f"Gemini HTTP {e.code}: {e.read().decode()[:300]}") from None
        except (urllib.error.URLError, TimeoutError) as e:
            last = e
        time.sleep(min(45, 4 * 2 ** attempt))
    else:
        raise RuntimeError(f"Gemini unreachable after retries: {last}")
    return "\n".join(p["text"] for c in resp.get("candidates", [])
                     for p in c.get("content", {}).get("parts", []) if "text" in p)


def jparse(t: str):
    m = re.search(r"\{.*\}", t, re.S)
    return json.loads(m.group(0)) if m else None


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.replace("·", " ").replace("•", " ").replace("’", "'")
    s = re.sub(r"[^A-Za-z0-9%()\.\- ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip().lower()


def load_truth(path: Path) -> list[str]:
    if not path.exists():
        sys.exit(f"no pack-strings file at {path}. Write every line printed on the real pack "
                 "(front and any side the plate shows) into it first: an empty truth list would "
                 "fail every plate.")
    txt = path.read_text()
    try:
        data = json.loads(txt)
    except json.JSONDecodeError:
        return [ln.strip() for ln in txt.splitlines() if ln.strip()]
    if isinstance(data, dict):
        data = data.get("strings", [])
    return [str(s) for s in data]


def score(d: dict, truth: list[str]) -> dict:
    """The model transcribes; this decides."""
    tn = [_norm(t) for t in truth]
    bad, ok, unres = [], [], []
    for s in d.get("strings", []):
        txt = (s.get("text") or "").strip()
        leg = (s.get("legibility") or "").lower()
        n = _norm(txt)
        if leg == "unresolvable" or not n:
            unres.append(txt)
            continue
        if any(n == t or (len(n) >= 4 and (n in t or t in n)) for t in tn):
            ok.append(txt)
            continue
        best, ratio = "", 0.0
        for t in tn:
            r = difflib.SequenceMatcher(None, n, t).ratio()
            if r > ratio:
                best, ratio = t, r
        bad.append({"read": txt, "nearest_truth": best, "ratio": round(ratio, 2), "legibility": leg,
                    "where": s.get("where", ""),
                    "note": "near-miss garble" if ratio >= 0.55 else "not on pack (invented)"})
    return {"letter_perfect": ok, "unresolvable": unres, "wrong": bad, "n_wrong": len(bad),
            "pass_": not bad, "model_said_garbled": bool(d.get("any_garbled_or_misspelled")),
            "worst_print_defect": d.get("worst_print_defect", "")}


def judge_view(f: Path, zoom: int = 3) -> Image.Image:
    im = Image.open(f).convert("RGB")
    W, H = im.size
    w = min(W, int(round(H * DELIV[0] / DELIV[1])))
    x0 = (W - w) // 2
    im = im.crop((x0, 0, x0 + w, H)).resize(DELIV, Image.LANCZOS)
    return im.resize((DELIV[0] * zoom, DELIV[1] * zoom), Image.BICUBIC)


def run(plates: list[Path], out: Path, truth: list[str], native: bool) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    mode = "native" if native else "judge"

    def one(f: Path):
        im = Image.open(f) if native else judge_view(f)
        for _ in range(3):
            try:
                d = jparse(ask(PROMPT, im))
                if d and "strings" in d:
                    return f, d
            except RuntimeError as e:
                return f, {"error": str(e)}
            except Exception:
                pass
        return f, {"error": "unparsed"}

    recs = {}
    with cf.ThreadPoolExecutor(max_workers=4) as ex:
        for f, d in ex.map(one, plates):
            rec = {"plate": str(f), "mode": mode, "model": VISION_MODEL, "raw": d,
                   "scored": score(d, truth) if "strings" in d else None}
            (out / f"print-{mode}-{f.stem}.json").write_text(json.dumps(rec, indent=1))
            recs[f.stem] = rec
            s = rec["scored"] or {}
            print(f"{f.name}: pass={s.get('pass_')} wrong={s.get('n_wrong', d.get('error'))} "
                  f"{[w['read'] for w in s.get('wrong', [])][:4]}", flush=True)
    return recs


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--plates", required=True, help="a file or a glob")
    ap.add_argument("--out", required=True, help="directory for the per-plate JSON reports")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--brand", help="brand slug: reads <brand>/brand/pack-strings.json")
    g.add_argument("--truth", help="explicit pack-strings file (JSON list or one line per string)")
    ap.add_argument("--native", action="store_true", help="read at file resolution (contact sheets)")
    a = ap.parse_args()
    plates = sorted(Path(p) for p in glob.glob(str(Path(a.plates).expanduser())))
    if not plates:
        sys.exit(f"no plates matched {a.plates}")
    tp = Path(a.truth).expanduser() if a.truth else brand_dir(a.brand) / "brand" / "pack-strings.json"
    recs = run(plates, Path(a.out).expanduser(), load_truth(tp), a.native)
    bad = [k for k, r in recs.items() if not (r["scored"] or {}).get("pass_")]
    print(f"print gate: {len(recs) - len(bad)}/{len(recs)} plates wrong=0")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
