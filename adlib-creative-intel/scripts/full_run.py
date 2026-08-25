#!/usr/bin/env python3
"""ONE command, whole pipeline: harvest -> download -> analyze -> report.

This is the entry point. From an empty package it produces every input it
needs by itself — nothing to export, download, or drop in by hand.

  python3 scripts/full_run.py --page-id 178024832922517 --slug seed

Stages:
  1. harvest   headless browser -> the page's active video ads (no credentials)
  2. ingest    dedupe by creative, download the mp4s, update the ledger
  3. analyze   per-second creative analysis (ONLY stage needing an API key;
               skipped automatically when no key is set, or with --no-cv)
  4. report    longevity table + creative findings -> outputs/

Find a page ID: open the advertiser in the Ad Library and copy the
`view_all_page_id=` value out of the URL.
"""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = PKG_ROOT / "scripts"
DATA = Path(os.environ.get("ADLIB_DATA", PKG_ROOT / "data"))
OUTPUT = Path(os.environ.get("ADLIB_OUTPUT", PKG_ROOT / "outputs"))
sys.path.insert(0, str(SCRIPTS))


def _run(cmd):
    print(f"\n$ {' '.join(str(c) for c in cmd)}")
    r = subprocess.run([str(c) for c in cmd])
    if r.returncode != 0:
        sys.exit(f"step failed ({r.returncode}): {' '.join(str(c) for c in cmd)}")


def _have_key():
    if os.environ.get("GEMINI_API_KEY"):
        return True
    env = Path(os.environ.get("ADLIB_ENV", PKG_ROOT / ".env"))
    return env.exists() and "GEMINI_API_KEY=" in env.read_text() and not any(
        line.strip().endswith("=") or "your-key-here" in line
        for line in env.read_text().splitlines()
        if line.strip().startswith("GEMINI_API_KEY="))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--page-id", required=True)
    ap.add_argument("--slug", required=True, help="short name for this advertiser")
    ap.add_argument("--country", default="US")
    ap.add_argument("--label", default="competitor")
    ap.add_argument("--no-cv", action="store_true",
                    help="skip creative analysis (no API key needed)")
    ap.add_argument("--cv-limit", type=int, default=0,
                    help="analyze the N longest-running creatives. "
                         "0 = ALL of them (the default — a content-strategy "
                         "breakdown needs the whole corpus, not a sample)")
    ap.add_argument("--max-scrolls", type=int, default=40)
    ap.add_argument("--model", default="gemini-2.5-pro",
                    help="analysis model. gemini-2.5-flash is faster and cheaper "
                         "on a large corpus; pro is more precise (default pro)")
    ap.add_argument("--skip-harvest", action="store_true",
                    help="work from already-downloaded creatives; do not hit the "
                         "Ad Library at all. Use when resuming after a rate-limit.")
    ap.add_argument("--cv-timeout", type=int, default=300,
                    help="hard wall-clock budget per video in seconds (default 300). "
                         "A video that blows it is retried once on flash, then "
                         "skipped — one bad video never stalls the run.")
    args = ap.parse_args()

    DATA.mkdir(parents=True, exist_ok=True)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    harvest_file = DATA / f"harvest_{args.slug}.json"

    # Is there already work on disk for this slug? If so, a failed harvest must
    # never discard it — analysis and reporting can proceed from what we have.
    have_local = bool(list((DATA / args.slug).glob("*.mp4"))) if (DATA / args.slug).exists() else False

    # 1. harvest (skippable; failure is survivable when local data exists)
    creatives = []
    if args.skip_harvest:
        print("--skip-harvest: working from already-downloaded creatives.")
    else:
        rc = subprocess.run(
            [str(c) for c in [sys.executable, SCRIPTS / "harvest.py",
                              "--page-id", args.page_id, "--out", harvest_file,
                              "--country", args.country,
                              "--max-scrolls", args.max_scrolls]]).returncode
        if rc != 0:
            if not have_local:
                sys.exit("\nHarvest failed and there is no local data to fall back "
                         "on. Nothing was written. Wait a few minutes and retry — "
                         "repeated requests can get rate-limited.")
            print("\n[warn] Harvest failed (blocked, rate-limited, or the page "
                  "changed). Continuing with the creatives already downloaded — "
                  "results may be missing anything launched since the last "
                  "successful harvest.")
        else:
            try:
                creatives = json.loads(harvest_file.read_text())
            except Exception:  # noqa: BLE001
                creatives = []

    if not creatives and not have_local:
        print("\nNo active video ads found for that page/country, and nothing "
              "downloaded previously. That is a real answer, not an error.")
        report_path = OUTPUT / f"longevity-{args.slug}.md"
        if report_path.exists() and report_path.stat().st_size > 500:
            print(f"(keeping the existing {report_path.name} rather than "
                  f"overwriting it with an empty result)")
        else:
            report_path.write_text(
                f"# Ad Library longevity report\n\nNo active video ads found for "
                f"page {args.page_id} in {args.country}.\n")
        return

    # 2. ingest + download (only when we have a fresh harvest)
    if creatives:
        _run([sys.executable, SCRIPTS / "adlib_fetch.py", "ingest",
              "--in", harvest_file, "--page-slug", args.slug, "--label", args.label])

    # 3a. no-credential profile — always runs, needs no key
    import describe as desc
    prof = desc.describe(args.slug)
    prof_dest = OUTPUT / f"profile-{args.slug}.md"
    prof_dest.write_text(desc.render(prof))
    print(f"\nwrote {prof_dest}  (offers, destinations, CTA mix, cadence, format "
          f"— no API key used)")

    # 3b. creative analysis (optional, needs a key)
    import adlib_fetch as fetch
    _, rows = fetch.build_report(args.slug)
    cv_results = []
    do_cv = not args.no_cv and _have_key()
    if not args.no_cv and not do_cv:
        print("\n[skip] creative analysis — no GEMINI_API_KEY set. "
              "The longevity report below still works. Add a key "
              "(https://aistudio.google.com/apikey) to enable it.")
    if do_cv:
        import cv_analyze
        import time
        targets = rows if args.cv_limit == 0 else rows[:args.cv_limit]
        cached = sum(1 for r in targets
                     if (DATA / args.slug / f"cv_{r['key']}.json").exists())
        todo = len(targets) - cached
        print(f"\nanalyzing {len(targets)} creative(s) second by second"
              f"{' — the full corpus' if args.cv_limit == 0 else ''}", flush=True)
        print(f"  {cached} already analyzed (cached), {todo} to go"
              f"{f' — roughly {todo} min' if todo else ''}", flush=True)
        t0, done_now = time.time(), 0
        for i, r in enumerate(targets, 1):
            mp4 = DATA / args.slug / f"{r['key']}.mp4"
            if not mp4.exists():
                continue
            out = DATA / args.slug / f"cv_{r['key']}.json"
            try:
                if out.exists():
                    data = json.loads(out.read_text())
                    print(f"  [{i}/{len(targets)}] {r['key']} — cached", flush=True)
                else:
                    print(f"  [{i}/{len(targets)}] {r['key']} — analyzing "
                          f"({mp4.stat().st_size / 1e6:.0f}MB) ...", flush=True)
                    try:
                        data = cv_analyze.analyze(str(mp4), args.model,
                                                  label=r["key"],
                                                  timeout_sec=args.cv_timeout)
                    except Exception as first_err:  # noqa: BLE001
                        # Any failure — our watchdog OR an API-side 504/503/429 —
                        # gets one fallback attempt on flash. A dropped video is
                        # not neutral: it silently biases every percentage the
                        # strategy report computes.
                        print(f"      {str(first_err)[:90]} — falling back to "
                              f"gemini-2.5-flash", flush=True)
                        data = cv_analyze.analyze(str(mp4), "gemini-2.5-flash",
                                                  label=r["key"],
                                                  timeout_sec=args.cv_timeout)
                    out.write_text(json.dumps(data, indent=2))
                    done_now += 1
                    el = time.time() - t0
                    rate = el / done_now
                    left = todo - done_now
                    print(f"      done in {rate:.0f}s avg"
                          + (f" · ~{rate * left / 60:.0f} min left" if left > 0 else ""),
                          flush=True)
                cv_results.append({
                    "creative_key": r["key"], "days_running": r["days"],
                    "n_library_ids": r["n_ads"],
                    "features": {**(data.get("descriptors") or {}),
                                 "hook_archetype": (data.get("hook") or {}).get("hook_archetype"),
                                 "duration_sec": data.get("duration_sec")},
                    "hook": (data.get("hook") or {}).get("first_3s_summary"),
                })
            except Exception as e:  # noqa: BLE001
                print(f"      FAILED {r['key']}: {str(e)[:200]}", flush=True)
                if "quota" in str(e).lower() or "429" in str(e):
                    print("      (quota hit — already-analyzed videos are cached, "
                          "so re-running later picks up where this stopped)",
                          flush=True)

    # 4. report
    md, _ = fetch.build_report(args.slug)
    if cv_results:
        from compete import analyze_competitors
        res = analyze_competitors(cv_results)
        md += "\n## Creative findings (longevity-associated)\n\n"
        md += f"Analyzed the {len(cv_results)} longest-running creatives.\n\n"
        md += "### Hooks\n\n"
        for c in sorted(cv_results, key=lambda x: -(x["days_running"] or 0)):
            md += (f"- `{c['creative_key']}` ({c['days_running']}d): "
                   f"**{c['features'].get('hook_archetype')}** — {c['hook']}\n")
        md += "\n### Features associated with longer runs\n\n"
        md += "| feature | longest-running | vs shortest | n | confidence |\n"
        md += "|---|---|---|---|---|\n"
        for f in res["findings"][:12]:
            if f["kind"] == "numeric":
                md += (f"| {f['feature']} | r={f['pearson_r_vs_days_running']} "
                       f"({f['direction']}) | — | {f['n']} | {f['confidence']} |\n")
            else:
                md += (f"| {f['feature']} | {f['longest_running_level']} "
                       f"({f['mean_days_at_that_level']}d) | "
                       f"{f['shortest_running_level']} "
                       f"({f['mean_days_at_shortest']}d) | {f['n']} "
                       f"| {f['confidence']} |\n")
        md += f"\n> {res['caveat']}\n"

    dest = OUTPUT / f"longevity-{args.slug}.md"
    dest.write_text(md)

    # 5. content-strategy synthesis — the payoff, needs the analyzed corpus
    strat_dest = None
    if cv_results:
        import strategy as strat
        S = strat.synthesize(args.slug)
        strat_dest = OUTPUT / f"strategy-{args.slug}.md"
        strat_dest.write_text(strat.render(S))

    print(f"\n{'=' * 60}")
    print(f"wrote {prof_dest}")
    print(f"wrote {dest}")
    if strat_dest:
        print(f"wrote {strat_dest}   <-- the content-strategy breakdown")
    print(f"creatives: {len(creatives)} · analyzed second-by-second: {len(cv_results)}")
    if not cv_results:
        print("\nNo videos were watched. You have metadata only. To get the "
              "content-strategy breakdown — what the ads actually DO — set up a "
              "Gemini key:\n  python3 scripts/probe_gemini.py   (it walks you "
              "through it)")


if __name__ == "__main__":
    main()
