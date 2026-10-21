#!/usr/bin/env python3
"""The four Gemini vision passes, with their prompts verbatim.

  localise  — object box, printed-band box and the CONTACT LINE, as fractions. Feeds
              physics.locate_bag. Localisation is a PERCEPTION problem; measurement is
              not, so this pass only ever supplies the search region.

  inspect   — the 4x forensics pass: surface texture, label on curvature, displacement,
              duplication/warp, single-light consistency, "does it read as a photograph".

  print     — the LETTER-PERFECT filter. Every visible printed word
              must be letter-perfect, or genuinely unresolvable by scale/shadow/occlusion.
              "Not extractable" is NOT a passing grade; crisp-and-wrong is an instant kill.
              THE MODEL TRANSCRIBES; `score_print` DECIDES. Run at the scale a JUDGE
              actually uses (`judge_view`), never at native plate scale, or the transcript
              describes a file nobody will ever see.

  gi        — the GLOBAL-ILLUMINATION filter. The physics cascade probes ONE
              COLUMN under the object; it is structurally blind to two contradictory keys
              or a frame with no cast shadows at all.

CLIENT LAYER (the only client-welded thing in the original): the TRUTH list — the pack's
real printed strings — is loaded from a file, not hardcoded. `load_truth` resolves
<brand>/pack-strings.json for a client slug, falls back to this package's fixtures/, and
finally returns [] WITH A LOUD WARNING, because an empty truth list makes score_print
call every transcribed string a fabrication.

usage:
  python3 vision.py localise --plates 'PLATES/*.png' --out QA/boxes.json \
                             [--subject "a glass jar of honey with a gold lid label"]
  python3 vision.py print    --plates 'PLATES/G0*.png' --client <slug> --out QA/
  python3 vision.py gi       --plates 'PLATES/G0*.png' --out QA/
  python3 vision.py inspect  --plates 'PLATES/G0*.png' --out QA/
"""
from __future__ import annotations

import argparse
import base64
import concurrent.futures as cf
import difflib
import glob as globmod
import io
import json
import re
import sys
import time
import unicodedata
import urllib.request
from pathlib import Path

from PIL import Image

_HERE = Path(__file__).resolve().parent
for _p in (str(_HERE), str(_HERE.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import config  # noqa: E402

FIXTURES = _HERE / "fixtures"
DELIV_W, DELIV_H = config.CANVAS_W, config.CANVAS_H


def _endpoint() -> str:
    # config.gemini_key() reads the key at call time out of the environment or the package
    # .env; it is never stored in this module and never printed.
    return (f"https://generativelanguage.googleapis.com/v1beta/models/"
            f"{config.VISION_MODEL}:generateContent?key={config.gemini_key()}")


def ask(prompt: str, img: Image.Image, maxpx: int = 1600, quality: int = 95) -> str:
    im = img.copy()
    im.thumbnail((maxpx, maxpx), Image.LANCZOS)
    buf = io.BytesIO()
    im.convert("RGB").save(buf, "JPEG", quality=quality)
    body = {"contents": [{"parts": [
        {"text": prompt},
        {"inlineData": {"mimeType": "image/jpeg",
                        "data": base64.b64encode(buf.getvalue()).decode()}},
    ]}], "generationConfig": {"temperature": 0.0}}
    # TRANSPORT-LEVEL retry only: the provider returns 503 "model is experiencing high
    # demand" in bursts, and a caller probing a PAID generation with no try/except of its
    # own can throw away output that was already charged. This retries the HTTP call and changes nothing a judge sees: same
    # prompt, same temperature, same parsing, same thresholds. A non-transient status
    # (400/403/404) still raises immediately.
    payload = json.dumps(body).encode()
    TRANSIENT = {408, 429, 500, 502, 503, 504}
    last = None
    for attempt in range(6):
        req = urllib.request.Request(_endpoint(), data=payload,
                                     headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=300) as r:
                resp = json.load(r)
            break
        except urllib.error.HTTPError as e:
            last = e
            if e.code not in TRANSIENT:
                raise
        except (urllib.error.URLError, TimeoutError) as e:
            last = e
        time.sleep(min(45, 4 * (2 ** attempt)))
    else:
        raise last
    out = []
    for c in resp.get("candidates", []):
        for p in c.get("content", {}).get("parts", []):
            if "text" in p:
                out.append(p["text"])
    return "\n".join(out)


def jparse(t: str):
    m = re.search(r"\{.*\}", t, re.S)
    return json.loads(m.group(0)) if m else None


# ------------------------------------------------------------------ localise
LOCALISE = """You are measuring a photograph for an automated instrument. Answer with JSON only.

In this image there is one product package: {subject}.
Its most prominent printed label band is the "red_band" below (the name is historical:
it is whichever saturated, printed band carries the product name).

Report, in FRACTIONS of the image width/height (0.0 to 1.0, four decimals):

{
 "bag":        {"x0":, "y0":, "x1":, "y1":},   // tight box around the WHOLE package
 "red_band":   {"x0":, "y0":, "x1":, "y1":},   // just the saturated printed label band
 "base_y":     ,   // y of the CONTACT LINE where the package's bottom meets the surface it stands on
 "base_x0":,  "base_x1":,   // the x span of that contact line (the footprint)
 "base_occluded": true|false,  // is the contact line hidden behind ANOTHER OBJECT (a bowl, a cloth,
                               // a prop) or cropped by the frame edge? Loose product dusted or banked
                               // against the package is NOT occlusion -- that is the surface itself.
 "clear_ground_side": "left"|"right"|"none",  // which side of the package has open, unobstructed surface next to it
 "light_from": "left"|"right"|"front"|"back-left"|"back-right",  // where the dominant light enters from
 "bag_fully_in_frame": true|false
}

Be precise about base_y: it is where the package STOPS, not where its shadow ends.
JSON only, no prose."""
# NOTE: the prompt names the SUBJECT because a vision model localises better when told
# what to find. Pass --subject (or localise(..., subject=...)) with a short visual
# description of YOUR pack. The JSON contract is what physics.locate_bag depends on.
DEFAULT_SUBJECT = "a retail product package (pouch, box, bag, bottle or jar) with a printed label"


def localise(plates, out_json, prompt=None, workers=6, echo=True, subject=None):
    out = {}
    if prompt is None:
        prompt = LOCALISE.replace("{subject}", subject or DEFAULT_SUBJECT)

    def one(f):
        for _ in range(3):
            try:
                d = jparse(ask(prompt, Image.open(f)))
                if d and "bag" in d and "base_y" in d:
                    return f.stem, d
            except Exception:
                pass
        return f.stem, {"error": "unparsed"}

    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        for name, d in ex.map(one, plates):
            out[name] = d
            if echo:
                print(name, json.dumps(d)[:170], flush=True)
    Path(out_json).write_text(json.dumps(out, indent=1))
    if echo:
        print("wrote", out_json)
    return out


# ------------------------------------------------------------- the print filter
PRINT_PROMPT = """You are a print-quality examiner. You are looking at ONE photograph that
contains a product package with printing on it. You have no context and you are not comparing
it to anything.

Read the package's printing at maximum magnification and answer in JSON.

For EVERY separate line or block of printing you can see anywhere on the package, add an
entry to "strings". Transcribe EXACTLY what the letters on the image say -- character for
character, including any misspelling, invented word, or nonsense. Do NOT correct anything,
do NOT guess at what it was probably meant to say, and do NOT fill in a word you cannot
actually read. Transcribing what a real package would say instead of what THIS image says
is the single worst thing you can do here.

Classify each entry's "legibility":
  "crisp"        - the letterforms are sharp and individually distinguishable; you are
                   reading actual letters, not guessing
  "soft"         - you can mostly make it out but some characters are ambiguous
  "unresolvable" - you can see that there is printing there but you cannot make out any
                   letters at all; it is a texture, a smudge, or a grey bar

{
 "strings": [ {"text":"<exactly what the letters say>", "where":"<=8 words",
               "legibility":"crisp"|"soft"|"unresolvable",
               "is_real_word_or_phrase": true|false} ],
 "any_garbled_or_misspelled": true|false,
 "garbled_examples": ["..."],
 "worst_print_defect": "<=25 words"
}
JSON only."""


def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.replace("·", " ").replace("•", " ").replace("’", "'")
    s = re.sub(r"[^A-Za-z0-9%()\.\- ]+", " ", s)
    return re.sub(r"\s+", " ", s).strip().lower()


def load_truth(source=None, slug=None) -> list[str]:
    """The real printed strings on the client's pack — the ground truth score_print
    compares a transcription against.

    Resolution order:
      1. `source`   an explicit path (JSON list, or newline-delimited text)
      2. `slug`     <brand>/pack-strings.json in the client layer
      3. `slug`     this package's fixtures/<slug>-pack-strings.json
      4. []         with a LOUD warning — an empty truth list makes every transcribed
                    string score as a fabrication, so a silent [] would turn the filter
                    into a machine that fails everything.
    """
    cands = []
    if source:
        cands.append(Path(source).expanduser())
    if slug:
        cands.append(config.brand_dir(slug) / "pack-strings.json")
        cands.append(FIXTURES / f"{slug}-pack-strings.json")
    for p in cands:
        if p.exists():
            txt = p.read_text()
            try:
                data = json.loads(txt)
            except json.JSONDecodeError:
                return [ln.strip() for ln in txt.splitlines() if ln.strip()]
            if isinstance(data, dict):
                data = data.get("strings", [])
            return [str(s) for s in data]
    print("!! WARNING: no pack-strings file found "
          f"(looked at: {[str(c) for c in cands] or 'nothing — no source or slug given'}).\n"
          "!! score_print will treat EVERY transcribed string as not-on-pack. Write the "
          "pack's real printed lines to <brand>/pack-strings.json before trusting a "
          "print verdict.", file=sys.stderr)
    return []


def score_print(d: dict, truth: list[str]) -> dict:
    """Deterministic scoring of the model's transcription against the real pack's
    strings. The MODEL transcribes; this function decides."""
    truth_n = [_norm(t) for t in truth]
    bad, ok, unres = [], [], []
    for s in d.get("strings", []):
        txt = (s.get("text") or "").strip()
        leg = (s.get("legibility") or "").lower()
        n = _norm(txt)
        if leg == "unresolvable" or not n:
            unres.append(txt)
            continue
        # exact / containment against any truth string
        hit = any(n == t or (len(n) >= 4 and (n in t or t in n)) for t in truth_n)
        if not hit:
            # near-miss to a truth string = the fluent-garble signature
            best, ratio = "", 0.0
            for t in truth_n:
                r = difflib.SequenceMatcher(None, n, t).ratio()
                if r > ratio:
                    best, ratio = t, r
            if ratio >= 0.55:
                bad.append({"read": txt, "nearest_truth": best, "ratio": round(ratio, 2),
                            "legibility": leg, "where": s.get("where", "")})
                continue
            # not close to anything on the pack at all -> also a fabricated string
            # (a generated pack does not merely garble its label, it INVENTS
            #  claims on it, and invented copy reads as fact)
            bad.append({"read": txt, "nearest_truth": best, "ratio": round(ratio, 2),
                        "legibility": leg, "where": s.get("where", ""), "note": "not on pack"})
            continue
        ok.append(txt)
    return {"letter_perfect": ok, "unresolvable": unres, "wrong": bad,
            "n_wrong": len(bad),
            "pass_": bool(len(bad) == 0),
            "model_said_garbled": bool(d.get("any_garbled_or_misspelled")),
            "model_garbled_examples": d.get("garbled_examples", []),
            "worst_print_defect": d.get("worst_print_defect", "")}


def judge_view(f, zoom: int = 3, deliv=(DELIV_W, DELIV_H)) -> Image.Image:
    """Exactly what a judge does to the DELIVERED file: the plate is resampled to
    the 1080x1350 delivery canvas (centre 4:5 crop, full width -- the framing that
    maximises s), then magnified. Magnifying a delivered PNG cannot recover detail
    the downsample destroyed, so this is the honest test of what ships, and it is
    the operation that exposes 'crisp wrong letters' a full-size view hides."""
    im = Image.open(f).convert("RGB")
    W, H = im.size
    w = min(W, int(round(H * deliv[0] / deliv[1])))
    x0 = (W - w) // 2
    im = im.crop((x0, 0, x0 + w, H)).resize(deliv, Image.LANCZOS)
    return im.resize((deliv[0] * zoom, deliv[1] * zoom), Image.BICUBIC)


def print_filter(plates, out_dir, truth, scale="judge", workers=4, echo=True):
    out_dir = Path(out_dir)

    def one(f):
        im = judge_view(f) if scale == "judge" else Image.open(f)
        for _ in range(3):
            try:
                d = jparse(ask(PRINT_PROMPT, im, maxpx=2600))
                if d and "strings" in d:
                    return f.stem, d
            except Exception:
                pass
        return f.stem, {"error": "unparsed"}

    recs = {}
    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        for n, d in ex.map(one, plates):
            rec = {"raw": d, "scored": score_print(d, truth) if "strings" in d else None,
                   "scale": scale}
            (out_dir / f"print-{scale}-{n}.json").write_text(json.dumps(rec, indent=1))
            recs[n] = rec
            s = rec["scored"] or {}
            if echo:
                print(f"{n} {scale:6s} pass={s.get('pass_')} wrong={s.get('n_wrong')} "
                      f"{[w['read'] for w in s.get('wrong', [])][:4]}", flush=True)
    return recs


# ---------------------------------------------------- global illumination
GI_PROMPT = """You are a lighting supervisor examining ONE photograph. You have no context
about how it was made and you are not comparing it to anything. Answer in JSON.

Look at every shadow in the frame and reason about the light.

{
 "n_light_sources": <integer>,          // how many distinct light sources do the shadows imply
 "single_key": true|false,              // is there exactly ONE dominant key light
 "key_direction": "<=8 words",
 "objects": [ {"object":"<=5 words",
               "casts_a_shadow_on_the_surface": true|false,
               "shadow_direction":"<=6 words",
               "shadow_edge":"hard"|"soft"|"none"} ],
                                        // list EVERY major object standing on the surface
 "all_shadows_agree": true|false,       // do all cast shadows point consistently from one key
 "objects_with_no_cast_shadow": ["..."],// anything sitting on the surface casting nothing
 "orphan_shadows": {"found": true|false, "what":"<=30 words"},
                                        // a shadow, dark patch, arc or smudge with no object
                                        // that could have cast it
 "ghost_arcs_or_inpaint_signatures": {"found": true|false, "what":"<=30 words"},
                                        // smooth bald arcs, clean swept rings, a region
                                        // suspiciously smoother or cleaner than around it
 "contradictory_highlights": {"found": true|false, "what":"<=30 words"},
                                        // specular highlights or lit faces implying a
                                        // second light from a different direction
 "verdict": "coherent"|"incoherent",
 "why": "<=30 words"
}
JSON only."""


def gi_filter(plates, out_dir, workers=4, echo=True):
    out_dir = Path(out_dir)

    def one(f):
        for _ in range(3):
            try:
                d = jparse(ask(GI_PROMPT, Image.open(f), maxpx=2000))
                if d and "verdict" in d:
                    return f.stem, d
            except Exception:
                pass
        return f.stem, {"error": "unparsed"}

    recs = {}
    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        for n, d in ex.map(one, plates):
            (out_dir / f"gi-{n}.json").write_text(json.dumps(d, indent=1))
            recs[n] = d
            if echo:
                nocast = d.get("objects_with_no_cast_shadow") or []
                print(f"{n} verdict={d.get('verdict')} single_key={d.get('single_key')} "
                      f"agree={d.get('all_shadows_agree')} nocast={len(nocast)} "
                      f"orphan={(d.get('orphan_shadows') or {}).get('found')} "
                      f"ghost={(d.get('ghost_arcs_or_inpaint_signatures') or {}).get('found')} "
                      f"contra={(d.get('contradictory_highlights') or {}).get('found')}",
                      flush=True)
    return recs


# ------------------------------------------------------------------ inspect
INSPECT = """You are a photo forensics examiner looking at ONE photograph for the first time.
You have no context about how it was made and you are not comparing it to anything.

Examine it at high magnification and answer ONLY about what is visibly in this frame.
Answer in JSON.

{
 "surface_texture": {"verdict":"real"|"suspect"|"fake", "why":"<=25 words"},
 "label_on_curvature": {"verdict":"real"|"suspect"|"fake", "why":"<=25 words"},
 "material_displacement": {"verdict":"real"|"suspect"|"fake"|"absent", "why":"<=25 words"},
 "loose_material_on_the_package": {"verdict":"present"|"absent", "why":"<=20 words"},
 "duplication_or_warp": {"found": true|false, "what":"<=30 words"},
 "single_light_consistency": {"verdict":"consistent"|"inconsistent", "why":"<=25 words"},
 "reads_as_a_real_photograph": {"verdict":"yes"|"borderline"|"no", "why":"<=30 words"},
 "worst_defect": "<=30 words, the single thing you would fix first"
}
JSON only."""
# The keys name generic surface/material checks (texture of the food or material in
# frame, displaced loose material, dust on the pack). If your category has a more
# specific tell, pass prompt= to swap the nouns per client.


def inspect(plates, out_dir, prompt=INSPECT, workers=4, echo=True):
    out_dir = Path(out_dir)

    def one(f):
        for _ in range(3):
            try:
                d = jparse(ask(prompt, Image.open(f), maxpx=2400))
                if d:
                    return f.stem, d
            except Exception:
                pass
        return f.stem, {"error": "unparsed"}

    recs = {}
    with cf.ThreadPoolExecutor(max_workers=workers) as ex:
        for n, d in ex.map(one, plates):
            (out_dir / f"vision-{n}.json").write_text(json.dumps(d, indent=1))
            recs[n] = d
            if echo:
                print(n, json.dumps(d)[:360], flush=True)
    return recs


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=["localise", "inspect", "print", "print-native", "gi"])
    ap.add_argument("--plates", required=True, help="glob of plate PNGs")
    ap.add_argument("--out", required=True, help="boxes.json path (localise) or a directory")
    ap.add_argument("--client", help="client slug, used to resolve the pack-strings truth list")
    ap.add_argument("--truth", help="explicit path to the pack-strings file")
    ap.add_argument("--subject", help="localise: short visual description of the product package")
    a = ap.parse_args(argv)

    plates = sorted(Path(p) for p in globmod.glob(str(Path(a.plates).expanduser())))
    if not plates:
        sys.exit(f"no plates matched {a.plates}")
    if a.mode == "localise":
        localise(plates, a.out, subject=a.subject)
    elif a.mode == "inspect":
        inspect(plates, a.out)
    elif a.mode == "gi":
        gi_filter(plates, a.out)
    else:
        truth = load_truth(a.truth, a.client)
        print_filter(plates, a.out, truth,
                     scale="native" if a.mode == "print-native" else "judge")


if __name__ == "__main__":
    main()
