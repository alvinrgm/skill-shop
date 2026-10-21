#!/usr/bin/env python3
"""Run every loop-engine module against SYNTHETIC artifacts and print PASS/FAIL per module.

This is the file that makes "the instruments run on this machine" a measurement instead
of a claim. Every test builds its own input in a temp directory (a flat-field ad with
known ink geometry, a token column with a known pitch, a plate with and without ground
texture, a review export, a transcription), so it runs on a fresh install with no client
data and no API key.

Each instrument is tested in BOTH directions (in miniature): it must pass the
clean artifact AND fail a deliberately broken copy of it. A ruler that cannot fail is not
a ruler.

What this does NOT prove: that the calibrated thresholds suit YOUR category. They were
calibrated on real loop runs; a plate that keeps failing one filter for a reason the
human eye disagrees with is a signal to report, never to move the threshold mid-run
(SKILL.md invariant 10).

Nothing is written outside a temp directory.

usage:
  python3 selftest.py            # no API calls
  python3 selftest.py --live     # additionally makes ONE real Gemini vision call (~$0.01)
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
import traceback
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

_HERE = Path(__file__).resolve().parent
for _p in (str(_HERE), str(_HERE.parent)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import config          # noqa: E402
import common          # noqa: E402
import zones           # noqa: E402
import physics         # noqa: E402
import triage as triage_mod   # noqa: E402
import vision          # noqa: E402
import device          # noqa: E402
import claims          # noqa: E402
import glance          # noqa: E402

TMP = None   # set in main(): importing this module never creates a temp dir
W, H = config.CANVAS_W, config.CANVAS_H
FIELD, INK, ACCENT = "#F2EDE4", "#1E1B24", "#B23A2A"


class Result:
    def __init__(self, name):
        self.name = name
        self.notes: list[str] = []
        self.bad: list[str] = []
        self.skipped = None

    def check(self, label, got, want, tol=0):
        okv = (abs(got - want) <= tol) if isinstance(want, (int, float)) and \
              isinstance(got, (int, float)) and not isinstance(want, bool) else (got == want)
        self.notes.append(f"    {'ok ' if okv else 'BAD'} {label}: {got!r} "
                          f"(expected {want!r})")
        if not okv:
            self.bad.append(f"{label}: got {got!r}, expected {want!r}")
        return okv

    def note(self, s):
        self.notes.append(f"        {s}")

    def skip(self, why):
        self.skipped = why

    @property
    def status(self):
        if self.skipped:
            return "SKIP"
        return "FAIL" if self.bad else "PASS"


# ---------------------------------------------------------------- synthetic fixtures
def _rgb(h):
    return tuple(int(x) for x in common.hex2rgb(h))


def synthetic_ad(path, *, left=110, headline_top=110, accent_tokens=None):
    """A flat-field 4:5 ad with KNOWN ink: a 3-line headline block, a 2-line body block,
    optional accent tokens. Returns the path."""
    im = Image.new("RGB", (W, H), _rgb(FIELD))
    d = ImageDraw.Draw(im)
    # headline: three bars, 46px tall, 14px leading -> one merged block
    for i in range(3):
        y = headline_top + i * 60
        d.rectangle([left, y, 960, y + 45], fill=_rgb(INK))
    # body: two thinner bars well below (gap > merge kernel)
    for i in range(2):
        y = 760 + i * 40
        d.rectangle([110, y, 700, y + 21], fill=_rgb(INK))
    for (x0, y0, x1, y1) in (accent_tokens or []):
        d.rectangle([x0, y0, x1, y1], fill=_rgb(ACCENT))
    im.save(path)
    return path


def synthetic_plate(path, *, textured=True, seed=7):
    """A 4:5 plate with a package standing on a lit surface, light from the left.
    textured=False is the mathematically flat field that filter A exists to kill."""
    rng = np.random.default_rng(seed)
    h, w = H, W
    xs = np.linspace(1.0, 0.0, w)[None, :]
    if textured:
        ground = 150 + 50 * xs + np.zeros((h, 1))        # left brighter (one window)
        ground = ground + rng.normal(0, 6, (h, w))
    else:
        ground = np.full((h, w), 180.0)                  # mathematically flat, no key
    rgb = np.stack([ground * 1.02, ground * 0.96, ground * 0.88], axis=2)
    # the package
    bx0, bx1, by0, floor = 380, 700, 420, 1000
    rgb[by0:floor, bx0:bx1] = [235, 228, 215]
    rgb[620:700, bx0:bx1] = [200, 40, 40]                 # printed label band
    rgb[633:687, bx0 + 25:bx1 - 25] = np.where(           # ...with legible "print" on it
        rng.random((54, bx1 - bx0 - 50, 1)) > 0.5, [235, 70, 70], [120, 20, 20])
    # a contact shadow that recovers with distance, thrown to the right (away from light)
    rgb[floor - 6:floor, bx0:bx1] *= 0.55                # the pack's own base in its shadow
    for dy in range(0, 140):
        k = 0.40 if dy < 6 else 0.40 + 0.60 * min(1.0, (dy - 6) / 110.0)
        rgb[floor + dy, bx0 - 20:bx1 + 60] *= k
    Image.fromarray(np.clip(rgb, 0, 255).astype(np.uint8)).save(path)
    boxes = {Path(path).stem: {
        "bag": {"x0": bx0 / w, "y0": by0 / h, "x1": bx1 / w, "y1": floor / h},
        "red_band": {"x0": bx0 / w, "y0": 620 / h, "x1": bx1 / w, "y1": 700 / h},
        "base_y": floor / h, "base_x0": bx0 / w, "base_x1": bx1 / w,
        "base_occluded": False, "light_from": "left", "bag_fully_in_frame": True}}
    return path, boxes


def synthetic_ref_pack(path):
    """An alpha-matted 'real photograph' of the package, with the same red band."""
    a = np.zeros((900, 500, 4), np.uint8)
    a[:, :, :3] = [235, 228, 215]
    a[:, :, 3] = 255
    a[300:420, :, :3] = [200, 40, 40]
    rng = np.random.default_rng(3)
    a[320:400, 40:460, :3] = np.where(rng.random((80, 420, 1)) > 0.5,
                                      [235, 70, 70], [120, 20, 20])                # "print"
    Image.fromarray(a, "RGBA").save(path)
    return path


# ---------------------------------------------------------------- common
def test_common():
    r = Result("common")
    m = np.zeros((7, 7), bool)
    m[3, 3] = True
    r.check("dilate(1px, 1, 1) area", int(common.dilate(m, 1, 1).sum()), 9)
    r.check("dilate(1px, 2, 0) area", int(common.dilate(m, 2, 0).sum()), 5)
    cc = np.zeros((5, 9), bool)
    cc[1, 1:3] = True
    cc[2, 2] = True
    cc[1, 6:8] = True
    labels, ids = common.components(cc)
    r.check("components count", len(ids), 2)
    r.check("component sizes", sorted(int((labels == i).sum()) for i in ids), [2, 3])
    r.check("row_bands min_h=1", common.row_bands([0, 1, 1, 0, 1, 0, 0], 1), [(1, 2), (4, 4)])
    r.check("row_bands min_h=2", common.row_bands([0, 1, 1, 0, 1, 0, 0], 2), [(1, 2)])
    r.check("contrast(white, black)", round(common.contrast([255, 255, 255], [0, 0, 0]), 2), 21.0)
    r.check("contrast(x, x)", round(common.contrast([128, 64, 32], [128, 64, 32]), 2), 1.0)
    r.check("hex2rgb", list(common.hex2rgb("#EFE7DA")), [239, 231, 218])
    a = np.ones((9, 9)) * 5.0
    r.check("boxblur constant field", round(float(common.boxblur(a, 2).std()), 6), 0.0)
    px = np.zeros((1, 3, 3), float)
    px[0, 0] = [200, 40, 40]
    px[0, 1] = [150, 115, 70]
    px[0, 2] = [240, 240, 240]
    r.check("red_mask separates band from warm-brown surface", common.red_mask(px)[0].tolist(),
            [True, False, False])
    return r


# ---------------------------------------------------------------- zones
def test_zones():
    r = Result("zones")
    good = synthetic_ad(TMP / "ad_good.png")
    q = zones.ZoneQA(good, field=FIELD, verbose=False)
    blocks = q.find_blocks()
    r.check("type blocks found", len(blocks), 2)
    r.check("headline block bbox (measured, not typed)", list(blocks[0]["bbox"]),
            [110, 110, 960, 275])
    m = q.margins()
    r.check("global ink bbox", m["bbox"], [110, 110, 960, 821])
    r.check("bottom safe ok", m["safe_ok"], True)
    lines = q.wcag_lines()
    r.check("WCAG lines measured (>0)", len(lines) > 0, True)
    r.check("WCAG line failures", sum(1 for x in lines if not x["ok"]), 0)
    r.check("clean ad: zero zone fails", q.fails, [])

    # the instrument must be able to FAIL: push the headline into the margin
    bad = synthetic_ad(TMP / "ad_bad.png", left=40)
    qb = zones.ZoneQA(bad, field=FIELD, verbose=False)
    qb.find_blocks()
    qb.margins()
    r.check("a 40px left margin is caught", any("margin left" in f for f in qb.fails), True)
    return r


# ---------------------------------------------------------------- device
def test_device():
    r = Result("device")
    toks = [(700, 380 + i * 52, 795, 380 + i * 52 + 37) for i in range(6)]
    p = synthetic_ad(TMP / "ad_tokens.png", accent_tokens=toks)
    rows, fails, summary = device.invariant_column(p, FIELD, ACCENT, 360, 700, 860,
                                                   n_expected=6)
    r.check("accent tokens in the band", len(rows), 6)
    r.check("pitches", summary["pitches"], [52, 52, 52, 52, 52])
    r.check("left-edge spread", summary["left_spread"], 0)
    r.check("clean column: no fails", fails, [])
    toks[3] = (706, toks[3][1], 801, toks[3][3])           # one token 6px off the column
    pb = synthetic_ad(TMP / "ad_tokens_bad.png", accent_tokens=toks)
    _rows, fails_b, _s = device.invariant_column(pb, FIELD, ACCENT, 360, 700, 860,
                                                 n_expected=6)
    r.check("a 6px column break is caught", any("left edges" in f for f in fails_b), True)
    return r


# ---------------------------------------------------------------- physics + triage
def test_physics():
    r = Result("physics + triage")
    ref = synthetic_ref_pack(TMP / "ref_pack.png")
    tex, boxes = synthetic_plate(TMP / "T01.png", textured=True)
    flat, boxes_f = synthetic_plate(TMP / "F01.png", textured=False)
    boxes.update(boxes_f)
    res_t = physics.analyse(tex, boxes, ref)
    res_f = physics.analyse(flat, boxes, ref)
    r.check("textured ground clears filter A (row-SD floor)", res_t["A"]["pass_"], True)
    r.check("flat field is killed at A", res_f["verdict"], "FAIL@A")
    r.check("a physically plausible plate SURVIVES all four filters", res_t["verdict"],
            "SURVIVE")
    r.check("measured light: left brighter", res_t["A"]["lateral_LR"] > 0, True)
    r.note(f"textured plate verdict: {res_t['verdict']} "
           f"(B contact {res_t.get('B', {}).get('contact_ratio')}, "
           f"D downsample {res_t.get('D', {}).get('downsample')})")
    miss = physics.analyse(tex, {}, ref, name="NOPE")
    r.check("no vision box -> FAIL@bag-not-found", miss["verdict"], "FAIL@bag-not-found")
    results, curve = triage_mod.run([tex, flat], boxes, ref,
                                    out_json=str(TMP / "triage.json"), echo=False)
    r.check("triage ran both plates", len(results), 2)
    r.check("triage.json written", (TMP / "triage.json").exists(), True)
    r.note(f"survival curve: {json.dumps(curve)}")
    b = physics.renormalise_box(boxes["T01"], 4000.0, 3600.0)
    r.check("renormalise_box scales x by src/crop",
            round(b["bag"]["x1"], 6), round(boxes["T01"]["bag"]["x1"] * 4000.0 / 3600.0, 6))
    r.check("renormalise_box leaves y untouched", b["bag"]["y1"], boxes["T01"]["bag"]["y1"])
    r.check("constants unmoved: SD_FLOOR", physics.SD_FLOOR, 3.02)
    r.check("constants unmoved: contact gate", [physics.CONTACT_LO, physics.CONTACT_HI],
            [0.25, 0.75])
    r.check("constants unmoved: MAX_DOWNSAMPLE", physics.MAX_DOWNSAMPLE, 2.18)
    return r


# ---------------------------------------------------------------- vision (offline half)
def test_vision(live=False):
    r = Result("vision")
    r.check("jparse extracts the JSON object from prose",
            vision.jparse('here you go:\n{"a": 1, "b": [2, 3]}\nthanks'), {"a": 1, "b": [2, 3]})
    r.check("jparse on prose with no object", vision.jparse("no json here"), None)
    fx = vision.FIXTURES / "example-pack-strings.json"
    truth = vision.load_truth(source=fx)
    r.check("example truth list loaded", len(truth) > 0, True)
    transcript = {"strings": [
        {"text": "ORIGINAL SEA SALT", "legibility": "crisp"},      # on the pack
        {"text": "ORIGNAL SAE SALT", "legibility": "crisp"},       # fluent garble
        {"text": "CLINICALLY PROVEN", "legibility": "crisp"},      # invented claim
        {"text": "", "legibility": "unresolvable"},
    ]}
    s = vision.score_print(transcript, truth)
    r.check("letter-perfect string accepted", s["letter_perfect"], ["ORIGINAL SEA SALT"])
    r.check("garble + invented claim both flagged", s["n_wrong"], 2)
    r.check("an invented claim is marked not-on-pack",
            any(w.get("note") == "not on pack" for w in s["wrong"]), True)
    r.check("crisp-and-wrong fails the filter", s["pass_"], False)
    src, _ = synthetic_plate(TMP / "V01.png")
    jv = vision.judge_view(src, zoom=2)
    r.check("judge_view = delivery canvas x zoom", list(jv.size), [W * 2, H * 2])
    if live:
        try:
            d = vision.jparse(vision.ask(vision.GI_PROMPT, Image.open(src), maxpx=1200))
            r.check("live gi call returns a verdict", bool(d and "verdict" in d), True)
        except Exception as e:
            r.bad.append(f"live vision call failed: {type(e).__name__}: {e}")
    else:
        r.note("live API pass NOT run (use --live). localise/inspect/print/gi network "
               "paths are UNVERIFIED by this run; only their pure-python halves are.")
    return r


# ---------------------------------------------------------------- claims
def test_claims():
    r = Result("claims")
    recs = {"data": [
        {"id": 1, "reviewTitle": "Best snack in the pantry", "reviewMessage":
         "We go through a box a week. My kids ask for these every time!", "reviewVerifiedType": 2,
         "reviewRating": 5, "author": "Sam P.", "reviewDate": "03/02/2026",
         "productName": "Original Sea Salt Crackers"},
        {"id": 2, "reviewTitle": "Finally, a cracker I trust", "reviewMessage":
         "I reach for these every time!", "reviewVerifiedType": 2,
         "reviewRating": 5, "author": "Jo K.", "reviewDate": "04/11/2026",
         "productName": "Variety Pack"},
    ]}
    (TMP / "reviews-p1.json").write_text(json.dumps(recs))
    records = claims.load_records([str(TMP / "reviews-p*.json")])
    r.check("review records loaded", len(records), 2)
    ship = [{"id": 1, "field": "reviewMessage", "text": "My kids ask for these every time!",
             "author": "Sam P.", "year": "2026"},
            {"id": 2, "field": "reviewTitle", "text": "Finally, a cracker I trust",
             "author": "Jo K.", "year": "2026"}]
    ok, rows = claims.verify(ship, records, product_line_re="cracker|pack",
                             word_cap=10, require_rating=5, require_verified=2, echo=False)
    r.check("clean fragments verify", ok, True)
    tampered = [dict(ship[0], text="My kids ask for these every tmie!")]
    bad_ok, bad_rows = claims.verify(tampered, records, echo=False)
    r.check("a one-letter tamper is caught", bad_ok, False)
    r.check("...as NOT-A-WHOLE-UNIT", "NOT-A-WHOLE-UNIT" in bad_rows[0]["flags"], True)
    sliced = [dict(ship[0], text="My kids ask for these")]
    sl_ok, _ = claims.verify(sliced, records, echo=False)
    r.check("a trailing elision is caught", sl_ok, False)
    off = claims.verify([ship[1]], records, product_line_re="^cracker", echo=False)[1]
    r.check("off-category product line is flagged",
            any(f.startswith("OFF-CATEGORY-SKU") for f in off[0]["flags"]), True)
    return r


# ---------------------------------------------------------------- glance
def test_glance():
    r = Result("glance")
    fin = synthetic_ad(TMP / "ad_glance.png")
    res = glance.build(fin, TMP / "glance", blocks=[{"bbox": (100, 100, 500, 300)}],
                       fold=int(H * config.FOLD_FRAC), safe=H - config.BOTTOM_SAFE,
                       declared_type=[("headline", 52), ("microtype", 13)], echo=False)
    for k in ("glance_blur", "thumb", "phone", "measured_boxes"):
        r.check(f"{k} written", res["files"][k].exists(), True)
    r.check("thumb size", list(Image.open(res["files"]["thumb"]).size), [180, 225])
    r.check("phone size", list(Image.open(res["files"]["phone"]).size), [378, 472])
    r.check("headline cap at 180px thumb", res["caps"]["headline"]["thumb"],
            round(52 * glance.CAP_RATIO * 180 / W, 2))
    return r


# ---------------------------------------------------------------- config
def test_config():
    """CONSTANTS ONLY. A PASS here says nothing about whether the loop can run; key and
    path readiness is reported separately in the ENVIRONMENT block."""
    r = Result("config wiring (constants only, NOT an env readiness check)")
    r.check("delivery canvas", [config.CANVAS_W, config.CANVAS_H], [1080, 1350])
    r.check("fold fraction", config.FOLD_FRAC, 0.23)
    kw = zones.ZoneQA.__init__.__kwdefaults__ or {}
    r.check("zones margin default from config", kw.get("margin"), config.MARGIN)
    r.check("physics delivery canvas from config",
            [physics.DELIV_W, physics.DELIV_H], [config.CANVAS_W, config.CANVAS_H])
    try:
        config.plate_spend(config.VOLUME_BATCH_CAP + 1)
        r.bad.append("plate_spend did not refuse a batch above the cap")
    except ValueError:
        r.check("spend guard refuses a batch above the cap", True, True)
    return r


def env_report() -> tuple[bool, list[str]]:
    present, where = config.gemini_key_present()
    lines = [f"GEMINI_API_KEY : {'PRESENT' if present else 'ABSENT'} ({where})"]
    if not present:
        lines.append("                 -> image generation and EVERY vision pass will fail. "
                     "Get a key: https://aistudio.google.com/apikey")
    probs = [p for p in config.check() if p.startswith("MISSING")]
    lines += [f"config.check   : {p}" for p in probs] or ["config.check   : required paths present"]
    return (present and not probs), lines


# ---------------------------------------------------------------- driver
def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--live", action="store_true", help="also make one real Gemini vision call")
    ap.add_argument("--keep", action="store_true", help="keep the temp output directory")
    ap.add_argument("--verbose", action="store_true", help="print every assertion")
    a = ap.parse_args(argv)

    global TMP
    TMP = Path(tempfile.mkdtemp(prefix="ad-loop-selftest-"))

    tests = [
        ("common", test_common),
        ("zones", test_zones),
        ("device", test_device),
        ("physics + triage", test_physics),
        ("vision", lambda: test_vision(a.live)),
        ("claims", test_claims),
        ("glance", test_glance),
        ("config wiring", test_config),
    ]
    print("=" * 78)
    print("ad-loop loop-engine selftest (synthetic fixtures, no client data needed)")
    print(f"work root  : {config.WORK_ROOT}")
    print(f"temp output: {TMP}")
    print("=" * 78)
    results = []
    for name, fn in tests:
        try:
            r = fn()
        except Exception:
            r = Result(name)
            r.bad.append("EXCEPTION")
            r.notes.append(traceback.format_exc())
        results.append(r)
        print(f"\n[{r.status}] {r.name}")
        if r.skipped:
            print(f"    -- {r.skipped}")
        elif a.verbose or r.bad:
            for n in r.notes:
                print(n)
        else:
            for n in r.notes:
                if not n.strip().startswith(("ok ", "BAD")):
                    print(n)
            print(f"    {sum(1 for n in r.notes if n.strip().startswith(('ok ', 'BAD')))} "
                  f"assertions, 0 failed")
        for b in r.bad:
            print(f"    !! {b}")

    print("\n" + "=" * 78)
    n_pass = sum(1 for r in results if r.status == "PASS")
    n_fail = sum(1 for r in results if r.status == "FAIL")
    for r in results:
        print(f"  {r.status:4s}  {r.name}")
    print(f"\n{n_pass}/{len(results)} pass, {n_fail} fail")
    print("\nENVIRONMENT (not a test: a PASS above never means the loop can run)")
    ready, lines = env_report()
    for ln in lines:
        print("  " + ln)
    print(f"  VERDICT        : {'loop is runnable' if ready else 'LOOP IS NOT RUNNABLE AS CONFIGURED'}")
    print("=" * 78)
    if not a.keep:
        shutil.rmtree(TMP, ignore_errors=True)
    else:
        print("temp output kept at", TMP)
    return 1 if n_fail else 0


if __name__ == "__main__":
    sys.exit(main())
