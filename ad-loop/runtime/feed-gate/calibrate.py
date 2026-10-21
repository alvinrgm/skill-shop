"""Run the full gate over a known set and print the calibration table.

    calibrate.py [--set calibration/set.json] [--only NAME,...] [--model M]
                 [--no-cache] [--skip-harness]

The calibration contract for this instrument is a set YOU declare, in
calibration/set.json (copy calibration/set.example.json):

  ELITE  (should largely SURVIVE: ads that demonstrably work in the wild,
          e.g. long-running actives from the Ad Library)
  KILLED (should localise CONCRETE failures: ads a human already killed)

If the elite ads fail modes broadly, the thresholds are wrong. Tune
LOSS_FAIL / TEXT_RECALL_FAIL in ablate.py, do not rationalise the result.

--build-chrome-ref rebuilds calibration/chrome-feed-ref.json: the elite
reference distribution that fold-dominated chrome (feed statics) is scored
against. Chrome on feed = the fold, and the fold hides the same ~77% of every
4:5 asset, so an absolute loss bar measures the format. The reference answers
"how much do elite ads of this shape lose under the identical occlusion" and
ablate.py fails an ad only when it loses meaningfully more than that. It uses
every 4:5 static in your inspo corpus ($AD_LOOP_HOME/inspo). A reference built
from 12 anonymised elite statics ships with the package, so this is optional.
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import subprocess
import sys
from datetime import date
from pathlib import Path

# Re-run under the package's own .venv when one exists (config.py does that at import).
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import config as _pkg_config  # noqa: E402,F401

ROOT = Path(__file__).resolve().parent
WORK = Path(os.path.expanduser(os.environ.get("AD_LOOP_HOME") or str(Path.home() / "ad-loop-work")))
INSPO = WORK / "inspo"
ALL_MODES = ["chrome", "phone", "desat"]


def load_set(path: Path):
    """[(name, path, class, brand)] from a user-declared calibration set."""
    if not path.exists():
        sys.exit(f"no calibration set at {path}. Copy calibration/set.example.json, "
                 "point it at 3+ elite ads and 2+ ads a human killed, then re-run.")
    rows = json.loads(path.read_text())
    return [(r["name"], Path(os.path.expanduser(r["path"])), r["class"], r.get("brand", "yourbrand"))
            for r in rows]


def chrome_ref_set():
    """Every 4:5-ish static in the inspo corpus (h/w within the reference's range)."""
    from PIL import Image
    out = []
    for p in sorted(INSPO.rglob("*")):
        if p.suffix.lower() not in (".jpg", ".jpeg", ".png", ".webp"):
            continue
        try:
            w, h = Image.open(p).size
        except Exception:
            continue
        if 1.15 <= h / w <= 1.40:
            out.append((f"elite_{len(out) + 1:02d}", p))
    return out


def build_chrome_ref(model: str, no_cache: bool) -> None:
    """Run chrome-mode ablation over the elite 4:5 set and write the
    reference distribution ablate.py scores fold-dominated chrome against."""
    rows = []
    for name, path in chrome_ref_set():
        if not path.exists():
            print(f"!! missing {path}")
            continue
        out = ROOT / "out" / name
        out.mkdir(parents=True, exist_ok=True)
        cmd = [sys.executable, str(ROOT / "ablate.py"), str(path),
               "--surface", "feed", "--modes", "chrome",
               "--out", str(out), "--model", model]
        if no_cache:
            cmd.append("--no-cache")
        run(cmd)
        rep = json.loads((out / "ablation.json").read_text())
        ch = next(m for m in rep["modes"] if m["mode"] == "chrome")
        rows.append({"name": name, "meaning_loss": ch["meaning_loss"],
                     "text_recall": ch["text_recall"],
                     "lost": [x["field"] for x in ch["lost"]],
                     "drifted": [x["field"] for x in ch["drifted"]]})
    if len(rows) < 8:
        sys.exit(f"only {len(rows)} reference ads ran — refusing to write a "
                 "distribution that thin")
    losses = sorted(r["meaning_loss"] for r in rows)
    recalls = sorted(r["text_recall"] for r in rows)
    q_loss = statistics.quantiles(losses, n=4)
    ref = {
        "built": str(date.today()),
        "model": model,
        "surface": "feed",
        "aspect_class": "4:5",
        # h/w of every ad in the set falls in here; ablate.py only applies
        # the reference to assets whose shape it actually describes
        "aspect_hw_range": [1.15, 1.40],
        "what_this_is": (
            "meaning-loss distribution of elite 4:5 corpus statics under the "
            "identical fold occlusion (chrome mode, feed surface). Fail bar "
            "in ablate.py = strictly above max(p75 + CHROME_EXCESS_FAIL, "
            "elite max). Built from the corpus, never from a candidate "
            "batch — see README calibration section."),
        "ads": rows,
        "stats": {
            "n": len(rows),
            "meaning_loss": {
                "min": losses[0], "median": statistics.median(losses),
                "p75": q_loss[2], "max": losses[-1]},
            "text_recall": {
                "min": recalls[0], "median": statistics.median(recalls),
                "max": recalls[-1]},
        },
    }
    dest = ROOT / "calibration" / "chrome-feed-ref.json"
    dest.parent.mkdir(exist_ok=True)
    dest.write_text(json.dumps(ref, indent=2))
    st = ref["stats"]["meaning_loss"]
    print(f"\nwrote {dest}")
    print(f"  n={ref['stats']['n']}  loss min {st['min']:.0%} / median "
          f"{st['median']:.0%} / p75 {st['p75']:.0%} / max {st['max']:.0%}")
    bar = max(st["p75"] + 0.25, st["max"])
    print(f"  fail bar = max(p75 + 0.25, elite max) = fails only ABOVE "
          f"{bar:.0%}")


def run(cmd: list[str]) -> int:
    print("  $ " + " ".join(c.replace(str(Path.home()), "~") for c in cmd[:6])
          + " ...")
    r = subprocess.run(cmd, capture_output=True, text=True)
    for ln in (r.stdout or "").splitlines():
        print("    " + ln)
    if r.returncode != 0:
        print("    !! " + (r.stderr or "")[-900:])
    return r.returncode


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default=str(ROOT / "calibration" / "set.json"))
    ap.add_argument("--only", default=None)
    ap.add_argument("--model", default="gemini-2.5-flash")
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--skip-harness", action="store_true")
    ap.add_argument("--build-chrome-ref", action="store_true",
                    help="rebuild calibration/chrome-feed-ref.json from the "
                         "elite 4:5 reference set, then exit")
    a = ap.parse_args()

    if a.build_chrome_ref:
        build_chrome_ref(a.model, a.no_cache)
        return

    want = set(s.strip() for s in a.only.split(",")) if a.only else None
    outroot = ROOT / "out"
    rows = []
    for name, path, klass, brand in load_set(Path(a.set)):
        if want and name not in want:
            continue
        if not path.exists():
            print(f"!! missing {path}")
            continue
        out = outroot / name
        out.mkdir(parents=True, exist_ok=True)
        print(f"\n=== {name}  [{klass}] ===")
        if not a.skip_harness:
            run([sys.executable, str(ROOT / "feedmock" / "render_infeed.py"),
                 str(path), "--out", str(out), "--brand", brand,
                 "--scales", "1,3", "--model", a.model])
        cmd = [sys.executable, str(ROOT / "ablate.py"), str(path),
               "--out", str(out), "--model", a.model]
        if a.no_cache:
            cmd.append("--no-cache")
        run(cmd)
        jf = out / "ablation.json"
        if jf.exists():
            rows.append((name, klass, json.loads(jf.read_text()),
                         out / "collision.json"))

    # ---- calibration table ----
    print("\n\n" + "=" * 78)
    print("CALIBRATION TABLE")
    print("=" * 78)
    hdr = f"{'ad':<22}{'class':<8}" + "".join(f"{m[:9]:<10}" for m in ALL_MODES)
    print(hdr)
    print("-" * 78)
    ico = {"pass": "pass", "fail": "FAIL", "advisory": "adv"}
    for name, klass, rep, _ in rows:
        by = {m["mode"]: m for m in rep["modes"]}
        line = f"{name:<22}{klass:<8}"
        for m in ALL_MODES:
            line += f"{ico.get(by[m]['verdict'],'-') if m in by else 'n/a':<10}"
        print(line)
    print("-" * 78)
    for name, klass, rep, cj in rows:
        extra = ""
        if cj.exists():
            c = json.loads(cj.read_text())
            extra = (f" | collision {c.get('verdict','?')}"
                     f" ({len(c.get('critical_hits',[]))} critical)")
            if "fold_visible_frac" in c:
                extra += f" | fold shows {c['fold_visible_frac']:.0%}"
        print(f"{name:<22} {rep['verdict']}"
              + (f"  failed: {','.join(rep['failed_modes'])}"
                 if rep["failed_modes"] else "") + extra)

    elite_fails = sum(len(r["failed_modes"]) for _, k, r, _ in rows
                      if k == "elite")
    killed_fails = sum(len(r["failed_modes"]) for _, k, r, _ in rows
                       if k == "killed")
    print("\nelite failed-mode count :", elite_fails,
          "(broadly >0 means thresholds are too strict)")
    print("killed failed-mode count:", killed_fails,
          "(0 means the battery is blind)")
    print("\nReminder: passing this battery means NOT KILLED BY THE MEDIUM. "
          "It never means ship.")


if __name__ == "__main__":
    main()
