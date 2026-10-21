#!/usr/bin/env python3
"""DEATH-MODE ABLATION BATTERY — mutilate the ad the way the medium does.

    ablate.py <ad.png> [--surface feed|reels] [--out DIR]
              [--modes chrome,phone,desat] [--model M] [--workers N] [--no-cache]

Statics only (PNG/JPG). Mechanism: the feed does not show your ad the way you
exported it. It covers it with chrome or the fold, shows it at thumbnail size in
a viewer's peripheral vision. So we apply those exact mutilations with ffmpeg, ask Gemini
what meaning it can still extract from each mutant, and measure the DELTA
against the original. A field that goes from known to unknown is meaning the
medium destroyed.

    mode        what it simulates                  failing when
    ----------  ---------------------------------  ---------------------------
    chrome      IG chrome over / fold under the ad  meaning LOST -> layout fix
    phone       true ~180px visual size             meaning LOST -> legibility
    desat       peripheral vision (chroma dropped)  meaning LOST -> advisory

=============================== HONESTY RAIL ===============================
This battery measures whether the MEDIUM CAN KILL THE AD. It never measures
whether anyone would stop scrolling for it. A clean sweep grants exactly one
thing: "not killed by the medium." It does NOT grant "ship."

An ad can pass every mode here and still be completely boring, and boring is
the far more common way an ad fails. Boring detection belongs to the corpus
gate and the persona panel, not to this file. Do not let a green battery
launder a weak concept.
============================================================================
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

# Re-run under the package's own .venv when one exists (config.py does that at import).
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import config as _pkg_config  # noqa: E402,F401

sys.path.insert(0, str(Path(__file__).resolve().parent))
import geometry as G  # noqa: E402
from lib.gemini import extract  # noqa: E402

ROOT = Path(__file__).resolve().parent
STATIC_EXT = {".png", ".jpg", ".jpeg", ".webp"}

PHONE_W = 180          # true rendered width of an ad in peripheral awareness

ALL_FIELDS = ("product", "offer", "cta", "hook")

# mode -> (baseline, scored_fields). Losing meaning is bad in every mode.
MODES = {
    "chrome":    ("orig",     ALL_FIELDS),
    "phone":     ("orig",     ALL_FIELDS),
    "desat":     ("orig",     ALL_FIELDS),
}
ADVISORY = {"desat"}          # never a hard FAIL on its own
STATIC_MODES = ["chrome", "phone", "desat"]

LOSS_FAIL = 0.34              # >= 1 of 3 fields fully lost
TEXT_RECALL_FAIL = 0.60       # < 60% of legible strings survived
DRIFT_JACCARD = 0.34          # below this, a retained field counts as drifted

# Chrome on the FEED surface is the fold, and the fold is a property of the
# FORMAT, not the ad: a 4:5 feed asset shows ~23% of itself at the first-
# encounter moment, so every elite 4:5 static also "loses" whatever lives
# below that line (calibrated in a prior run: every elite 4:5 static in the
# reference corpus failed the absolute LOSS_FAIL bar under the identical
# mutation). Fold-dominated
# chrome is therefore scored RELATIVE to the elite reference distribution in
# calibration/chrome-feed-ref.json (rebuild: calibrate.py --build-chrome-ref).
# An ad fails only when it loses meaningfully more than elite ads do under
# the same occlusion.
CHROME_REF_PATH = ROOT / "calibration" / "chrome-feed-ref.json"
CHROME_EXCESS_FAIL = 0.25     # one full field-flip beyond the elite p75


def sh(cmd: list[str]) -> str:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd[:4])}... failed:\n{r.stderr[-1200:]}")
    return r.stdout


def probe(p: Path) -> dict:
    st = json.loads(sh(["ffprobe", "-v", "error", "-select_streams", "v:0",
                        "-show_entries", "stream=width,height",
                        "-of", "json", str(p)]))["streams"][0]
    return {"w": int(st["width"]), "h": int(st["height"])}


# ------------------------------------------------------- chrome rects ----
def chrome_boxes(w: int, h: int, surface: str) -> list[tuple[str, dict]]:
    """The exact regions the medium takes away, in asset px.

    reels -> IG chrome that OVERLAYS a 9:16 creative (bottom band + right rail +
             top bar) plus the cover-fill side crop.
    feed  -> IG chrome never overlays a feed post, so the honest analogue is
             the FOLD: everything the viewer has not seen yet at the moment
             the scroll decision gets made.
    """
    box = G.fit(w, h, surface)
    out: list[tuple[str, dict]] = []
    for r in G.CHROME[surface]:
        if not r.overlays_creative:
            continue
        a = G.to_asset_space(r, box)
        if a:
            out.append((r.name, {"x": a[0], "y": a[1], "w": a[2], "h": a[3],
                                 "opacity": r.opacity}))
    if box["x"] < 0:  # cover-fill crops the sides off - genuinely gone
        cw = -box["x"] / box["scale"]
        out.append(("crop_left", {"x": 0, "y": 0, "w": cw, "h": h,
                                  "opacity": 1.0}))
        out.append(("crop_right", {"x": w - cw, "y": 0, "w": cw, "h": h,
                                   "opacity": 1.0}))
    fold = G.fold_crop(w, h, surface)
    if fold:  # not yet scrolled into view - also genuinely unseen
        out.append(("below_fold", dict({k: fold[k] for k in "xywh"},
                                       opacity=1.0)))
    return out


def load_chrome_ref(w: int, h: int, surface: str) -> dict | None:
    """The elite reference distribution for fold-dominated chrome, if one
    matches this asset's shape. None when chrome is overlay-dominated (reels),
    when the whole creative is visible at first encounter, or when no
    reference covers this aspect ratio."""
    if surface != "feed" or not CHROME_REF_PATH.exists():
        return None
    if G.fold_crop(w, h, surface) is None:
        return None
    ref = json.loads(CHROME_REF_PATH.read_text())
    lo, hi = ref["aspect_hw_range"]
    return ref if lo <= h / w <= hi else None


def drawbox_filter(w: int, h: int, surface: str) -> str:
    parts = []
    for _, b in chrome_boxes(w, h, surface):
        parts.append(f"drawbox=x={int(b['x'])}:y={int(b['y'])}:"
                     f"w={int(b['w'])}:h={int(b['h'])}:"
                     f"color=black@{b.get('opacity', 1.0):.2f}:t=fill")
    return ",".join(parts)


# ---------------------------------------------------------- saboteurs ----
def make_mutant(src: Path, mode: str, out: Path, meta: dict, surface: str) -> Path:
    w, h = meta["w"], meta["h"]
    vf = {"chrome": drawbox_filter(w, h, surface),
          "phone": f"scale={PHONE_W}:-2,scale={w}:{h}:flags=bicubic",
          "desat": "hue=s=0"}[mode]
    sh(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-vf", vf,
        "-frames:v", "1", str(out)])
    return out


# ------------------------------------------------------------- delta ----
_word = re.compile(r"[a-z0-9]+")


def _toks(s: str) -> set[str]:
    return set(_word.findall((s or "").lower()))


def _jaccard(a: str, b: str) -> float:
    ta, tb = _toks(a), _toks(b)
    if not ta and not tb:
        return 1.0
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def _norm(s: str) -> str:
    return " ".join(_word.findall((s or "").lower()))


def text_recall(orig: dict, mut: dict) -> tuple[float, list[str]]:
    """Which legible strings from the original survived the mutation."""
    o = [t for t in (orig.get("onscreen_text") or []) if _norm(t)]
    m = [_norm(t) for t in (mut.get("onscreen_text") or [])]
    if not o:
        return 1.0, []
    blob = " || ".join(m)
    missing = []
    for t in o:
        n = _norm(t)
        hit = n in blob or any(_jaccard(t, x) >= 0.6 for x in m)
        if not hit:
            missing.append(t)
    return (len(o) - len(missing)) / len(o), missing


def score(mode: str, base: dict, mut: dict,
          chrome_ref: dict | None = None,
          fold_frac: float | None = None) -> dict:
    _, fields = MODES[mode]
    lost, drifted, kept = [], [], []
    for f in fields:
        b, m = base.get(f) or {}, mut.get(f) or {}
        bk, mk = bool(b.get("known")), bool(m.get("known"))
        if bk and not mk:
            lost.append({"field": f, "was": b.get("value", "")})
        elif bk and mk:
            j = _jaccard(b.get("value", ""), m.get("value", ""))
            entry = {"field": f, "was": b.get("value", ""),
                     "became": m.get("value", ""), "jaccard": round(j, 2)}
            (kept if j >= DRIFT_JACCARD else drifted).append(entry)
    n = max(1, len(fields))
    loss = (len(lost) + 0.5 * len(drifted)) / n
    recall, missing = text_recall(base, mut)
    gate_recall = recall < TEXT_RECALL_FAIL

    if mode == "chrome" and fold_frac is not None and chrome_ref is not None:
        # Fold-dominated chrome, scored RELATIVE to the elite reference
        # distribution. The fold hides the same fraction of every ad of this
        # shape, so absolute loss measures the format; only losing MORE than
        # elite ads do under the identical occlusion is a defect. Text recall
        # is not gated here for the same reason: where text sits relative to
        # the fold is composition, and the elite refs themselves span
        # 0-100% recall under this mutation.
        # Fail bar: a full field-flip beyond the elite p75, and never a score
        # an elite ad actually achieved (reference: two elite ads can sit at the
        # same loss as the worst killed static — a reference ad must not fail
        # its own reference). Strictly greater.
        st = chrome_ref["stats"]["meaning_loss"]
        bar = max(st["p75"] + CHROME_EXCESS_FAIL, st["max"])
        bad = loss > bar
        verdict = "fail" if bad else "pass"
        vis = (f"{fold_frac:.0%} of the creative is on screen at first "
               f"encounter")
        if bad:
            reason = (f"loses {loss:.0%} where NO elite "
                      f"{chrome_ref['aspect_class']} ad exceeds {bar:.0%} "
                      f"under the identical fold (median {st['median']:.0%}, "
                      f"p75 {st['p75']:.0%}) ({vis})")
        else:
            reason = (f"loss {loss:.0%} is within the elite band (median "
                      f"{st['median']:.0%}, p75 {st['p75']:.0%}, max "
                      f"{st['max']:.0%}, fail bar >{bar:.0%}); {vis} — fold "
                      f"visibility is a composition input, not a gate failure")
    else:
        bad = loss >= LOSS_FAIL or gate_recall
        verdict = ("advisory" if (bad and mode in ADVISORY)
                   else "fail" if bad else "pass")
        if not bad:
            reason = "meaning survived"
        else:
            bits = []
            if lost:
                bits.append("lost " + ", ".join(x["field"] for x in lost))
            if drifted:
                bits.append("drifted " + ", ".join(x["field"] for x in drifted))
            if gate_recall:
                bits.append(f"only {recall:.0%} of on-screen text still legible")
            reason = "; ".join(bits)
        if mode == "chrome" and fold_frac is not None and bad:
            # Fold-dominated chrome with NO matching reference distribution:
            # the absolute bar is known to measure the format constant (see
            # the 4:5 calibration note above), so a hard fail would repeat
            # that bug for this aspect. Downgrade to advisory and say why.
            verdict = "advisory"
            reason += (f"; NO reference distribution covers this aspect "
                       f"({fold_frac:.0%} visible at first encounter) — "
                       f"absolute fold loss measures the format, not the ad; "
                       f"build one via calibrate.py --build-chrome-ref")

    return {"mode": mode, "verdict": verdict, "reason": reason,
            "fold_visible_frac": fold_frac,
            "chrome_ref": (chrome_ref or {}).get("built"),
            "meaning_loss": round(loss, 3), "text_recall": round(recall, 3),
            "lost": lost, "drifted": drifted, "kept": kept,
            "missing_text": missing[:12],
            "legibility_notes": mut.get("legibility_notes", "")}


FIX = {
    "chrome": "move the element out of the chrome band / into the Meta safe zone",
    "phone": "the element is too small or too low-contrast at true phone size",
    "desat": "the element relies on colour alone — add contrast or weight",
}


# -------------------------------------------------------------- main ----
def run(ad: Path, surface: str, out: Path, modes: list[str], model: str,
        workers: int, cache: bool) -> dict:
    meta = probe(ad)
    w, h = meta["w"], meta["h"]
    mdir = out / "mutants"
    edir = out / "extractions"
    for d in (mdir, edir):
        d.mkdir(parents=True, exist_ok=True)
    avail = list(modes)

    print(f"[{ad.name}] {w}x{h} surface={surface} static")
    print(f"  modes: {', '.join(avail)}")

    # 1. build every mutant
    files: dict[str, Path] = {"orig": ad}
    for m in avail:
        p = mdir / f"{m}.png"
        if not (cache and p.exists()):
            make_mutant(ad, m, p, meta, surface)
        files[m] = p
    print(f"  built {len(files)-1} mutants")

    # 2. extract meaning from each, in parallel
    def _one(item):
        k, p = item
        cp = edir / f"{k}.json"
        if cache and cp.exists():
            return k, json.loads(cp.read_text())
        d = extract(p, model=model)
        cp.write_text(json.dumps(d, indent=2))
        return k, d

    with ThreadPoolExecutor(max_workers=workers) as ex:
        res = dict(ex.map(_one, files.items()))
    print(f"  extracted meaning from {len(res)} files")

    # 3. score the deltas
    fold = G.fold_crop(w, h, surface)
    fold_frac = fold["visible_frac"] if fold else None
    chrome_ref = load_chrome_ref(w, h, surface)
    if fold_frac is not None:
        print(f"  first-encounter visibility: {fold_frac:.0%} of the creative"
              + (f"  (chrome scored vs elite {chrome_ref['aspect_class']} "
                 f"reference, built {chrome_ref['built']})" if chrome_ref
                 else "  (no matching chrome reference)"))
    rows = []
    for m in avail:
        base_key = MODES[m][0]
        base = res.get(base_key, res["orig"])
        rows.append(score(m, base, res[m],
                          chrome_ref=chrome_ref if m == "chrome" else None,
                          fold_frac=fold_frac if m == "chrome" else None))

    hard = [r for r in rows if r["verdict"] == "fail"]
    rep = {
        "ad": str(ad), "surface": surface, "asset_px": [w, h],
        "fold_visible_frac": fold_frac,
        "model": model,
        "original": {k: (res["orig"].get(k) or {}) for k in ALL_FIELDS},
        "original_onscreen_text": res["orig"].get("onscreen_text", []),
        "modes": rows,
        "verdict": "NOT KILLED BY THE MEDIUM" if not hard else "KILLED",
        "failed_modes": [r["mode"] for r in hard],
        "honesty": ("This measures only whether the medium can kill the ad. "
                    "It never says anyone would stop for it."),
    }
    (out / "ablation.json").write_text(json.dumps(rep, indent=2))
    (out / "ablation.md").write_text(report_md(rep))
    return rep


def report_md(r: dict) -> str:
    ico = {"pass": "PASS", "fail": "FAIL", "advisory": "ADV "}
    L = [f"# Death-mode ablation — {Path(r['ad']).name}", "",
         f"surface **{r['surface']}** · {r['asset_px'][0]}x{r['asset_px'][1]}"
         + (f" · fold shows {r['fold_visible_frac']:.0%} at first encounter"
            if r.get("fold_visible_frac") else "")
         + f" · **{r['verdict']}**", "",
         "| mode | verdict | meaning loss | text recall | what happened |",
         "|---|---|---|---|---|"]
    for m in r["modes"]:
        L.append(f"| `{m['mode']}` | {ico.get(m['verdict'],m['verdict'])} | "
                 f"{m['meaning_loss']:.0%} | {m['text_recall']:.0%} | "
                 f"{m['reason']} |")

    fixes = [m for m in r["modes"] if m["verdict"] in ("fail", "advisory")]
    if fixes:
        L += ["", "## What died, and where", ""]
        for m in fixes:
            L.append(f"**`{m['mode']}`** — {FIX[m['mode']]}")
            for x in m["lost"]:
                L.append(f"  - lost **{x['field']}** "
                         f"(original: \"{str(x['was'])[:110]}\")")
            for x in m["drifted"]:
                L.append(f"  - **{x['field']}** drifted: "
                         f"\"{str(x['was'])[:60]}\" -> "
                         f"\"{str(x['became'])[:60]}\"")
            for t in m["missing_text"]:
                L.append(f"  - text no longer legible: \"{str(t)[:90]}\"")
            if m.get("legibility_notes"):
                L.append(f"  - judge noted: {str(m['legibility_notes'])[:220]}")
            L.append("")
    else:
        L += ["", "No mode destroyed the ad's meaning.", ""]

    L += ["---", "",
          "### What this verdict is worth", "",
          "This battery measures **whether the medium can kill the ad** — "
          "covered by chrome or the fold, shrunk to thumbnail size, desaturated. "
          "A clean sweep grants exactly one thing: **not killed by the medium.** "
          "It does **not** grant *ship*.", "",
          "Nothing here can tell you whether a person would stop scrolling. An "
          "ad can pass every mode and still be boring, and boring is the more "
          "common way ads fail. That judgment belongs to the corpus gate and "
          "the persona panel."]
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ad")
    ap.add_argument("--surface", choices=["feed", "reels"], default=None)
    ap.add_argument("--out", default=None)
    ap.add_argument("--modes", default=None,
                    help="comma list; default = all applicable")
    ap.add_argument("--model", default="gemini-2.5-flash")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--no-cache", action="store_true")
    a = ap.parse_args()

    ad = Path(a.ad).expanduser().resolve()
    if not ad.exists():
        sys.exit(f"no such ad: {ad}")
    if ad.suffix.lower() not in STATIC_EXT:
        sys.exit(f"statics only: expected one of {sorted(STATIC_EXT)}, got {ad.name}")
    meta = probe(ad)
    surface = a.surface or ("reels" if meta["h"] / meta["w"] > 1.6 else "feed")
    modes = ([m.strip() for m in a.modes.split(",") if m.strip()] if a.modes
             else STATIC_MODES)
    bad = [m for m in modes if m not in MODES]
    if bad:
        sys.exit(f"unknown mode(s): {bad}. known: {list(MODES)}")
    out = Path(a.out).expanduser() if a.out else ROOT / "out" / ad.stem
    out.mkdir(parents=True, exist_ok=True)

    rep = run(ad, surface, out, modes, a.model, a.workers, not a.no_cache)
    print(f"  VERDICT: {rep['verdict']}"
          + (f"  (failed: {', '.join(rep['failed_modes'])})"
             if rep["failed_modes"] else ""))
    print(f"  -> {out}/ablation.md")


if __name__ == "__main__":
    main()
