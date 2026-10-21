#!/usr/bin/env python3
"""Ingest a harvest, download the creatives, keep a ledger, report longevity.

  ingest  — diff against the ledger, download NEW creatives (HD preferred, SD
            fallback), write metadata sidecars, update the ledger.
  status  — what the library holds, per page.
  report  — the longevity table (markdown), written to the outputs dir.

Storage (override with env vars):
  ADLIB_DATA    default <package>/data     — creatives + ledger
  ADLIB_OUTPUT  default <package>/outputs  — reports

  <ADLIB_DATA>/<page-slug>/<creative_key>.mp4    the creative
  <ADLIB_DATA>/<page-slug>/<creative_key>.json   harvested metadata
  <ADLIB_DATA>/ledger.jsonl                      one line per library ID

Re-running a page later only downloads what is new. That diff is the signal:
it is the answer to "what did they launch since last time."

THE HONESTY CONSTRAINT, which governs every number this file emits: the Ad
Library publishes NO impressions, spend, retention, or ROAS for commercial ads.
The only observable proxies are days_running, how many library IDs share a
creative, and platform spread. A long-running ad means the advertiser keeps
paying for it — which is confounded by their budget, always-on habits,
seasonality, and plain inertia. Treat it as a hypothesis about what THEY
believe, never as a measured result.

Usage:
  adlib_fetch.py ingest --in data/harvest.json --page-slug acme --label competitor
  adlib_fetch.py status [--page-slug X]
  adlib_fetch.py report [--page-slug X] [--out outputs/report.md]
"""
import argparse
import datetime as dt
import json
import os
import re
import sys
from pathlib import Path

import requests

PKG_ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get("ADLIB_DATA", PKG_ROOT / "data"))
OUTPUT = Path(os.environ.get("ADLIB_OUTPUT", PKG_ROOT / "outputs"))
LEDGER = DATA / "ledger.jsonl"
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
MIN_VIDEO_BYTES = 10_000


def _today():
    return dt.date.today().isoformat()


def _epoch_to_iso(v):
    if not v:
        return None
    try:
        return dt.datetime.fromtimestamp(int(v)).date().isoformat()
    except (ValueError, TypeError, OSError):
        return str(v)


def _days_since(iso):
    try:
        return (dt.date.today() - dt.date.fromisoformat(iso)).days
    except (ValueError, TypeError):
        return None


def slugify(name):
    return re.sub(r"[^a-z0-9]+", "-", (name or "").lower()).strip("-")


def load_ledger():
    out = {}
    if LEDGER.exists():
        for line in LEDGER.read_text().splitlines():
            if line.strip():
                e = json.loads(line)
                out[e["library_id"]] = e
    return out


def save_ledger(entries):
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    with LEDGER.open("w") as f:
        for e in sorted(entries.values(), key=lambda x: x["library_id"]):
            f.write(json.dumps(e) + "\n")


def download(url, dest):
    r = requests.get(url, headers={"User-Agent": UA}, timeout=90)
    r.raise_for_status()
    if len(r.content) < MIN_VIDEO_BYTES:
        raise RuntimeError(f"suspiciously small response ({len(r.content)} bytes)")
    dest.write_bytes(r.content)
    return len(r.content)


def cmd_ingest(args):
    creatives = json.loads(Path(args.infile).read_text())
    if isinstance(creatives, dict):
        creatives = creatives.get("creatives") or creatives.get("ads") or []
    ledger = load_ledger()
    slug = args.page_slug or slugify(
        (creatives[0].get("page_name") if creatives else None) or "unknown")
    page_dir = DATA / slug
    page_dir.mkdir(parents=True, exist_ok=True)

    new_files, new_ads, known_ads, failed = 0, [], 0, []
    for c in creatives:
        ads = c.get("ads") or []
        fresh = [a for a in ads if str(a.get("library_id")) not in ledger]
        known_ads += len(ads) - len(fresh)
        if not fresh:
            for a in ads:
                ledger[str(a["library_id"])]["active_last_seen"] = _today()
            continue

        key = c.get("creative_key") or str(fresh[0]["library_id"])
        dest = page_dir / f"{key}.mp4"
        url = c.get("hd") or c.get("sd")
        res = "hd" if c.get("hd") else "sd"
        if not url:
            failed.append((key, "no video url"))
            continue
        if not dest.exists():
            try:
                size = download(url, dest)
                new_files += 1
            except Exception as ex:  # noqa: BLE001
                failed.append((key, str(ex)))
                continue
        else:
            size = dest.stat().st_size
        (page_dir / f"{key}.json").write_text(json.dumps(c, indent=2))

        for a in fresh:
            lid = str(a["library_id"])
            ledger[lid] = {
                "library_id": lid,
                "creative_key": key,
                "page_slug": slug,
                "page_name": c.get("page_name"),
                "page_id": str(c.get("page_id") or ""),
                "label": args.label,
                "first_ingested": _today(),
                "start_date": _epoch_to_iso(a.get("start_date")),
                "active_last_seen": _today(),
                "is_active": a.get("is_active"),
                "collation_count": a.get("collation_count"),
                "platforms": a.get("publisher_platform"),
                "cta_type": c.get("cta_type"),
                "title": c.get("title"),
                "link_url": c.get("link_url"),
                "video_file": str(dest),
                "resolution": res,
                "video_bytes": size,
            }
            new_ads.append(lid)

    save_ledger(ledger)
    print(f"ingest {slug}: {new_files} new creatives downloaded, "
          f"{len(new_ads)} new library IDs, {known_ads} already known, "
          f"{len(failed)} failed")
    for key, err in failed:
        print(f"  FAIL {key}: {err}")
    if failed and new_files == 0:
        sys.exit(1)


def _filtered(ledger, page_slug):
    return [e for e in ledger.values() if not page_slug or e["page_slug"] == page_slug]


def cmd_status(args):
    entries = _filtered(load_ledger(), args.page_slug)
    if not entries:
        print("ledger empty" + (f" for {args.page_slug}" if args.page_slug else ""))
        return
    by_page = {}
    for e in entries:
        by_page.setdefault(e["page_slug"], []).append(e)
    for slug, es in sorted(by_page.items()):
        keys = {e["creative_key"] for e in es}
        print(f"{slug}: {len(es)} library IDs / {len(keys)} unique creatives  "
              f"(page: {es[0].get('page_name')}, label: {es[0].get('label')})")


def build_report(page_slug=None):
    entries = _filtered(load_ledger(), page_slug)
    by_key = {}
    for e in entries:
        g = by_key.setdefault(e["creative_key"], {
            "key": e["creative_key"], "page_name": e.get("page_name"),
            "ads": [], "res": e.get("resolution"),
            "file": Path(e["video_file"]).name, "cta": e.get("cta_type"),
            "title": e.get("title")})
        g["ads"].append(e)
    rows = []
    for g in by_key.values():
        starts = [a["start_date"] for a in g["ads"] if a.get("start_date")]
        first = min(starts) if starts else None
        rows.append({**g, "first_start": first,
                     "days": _days_since(first) if first else None,
                     "n_ads": len(g["ads"])})
    rows.sort(key=lambda r: -(r["days"] if r["days"] is not None else -1))

    L = ["# Ad Library longevity report", ""]
    L.append(f"Generated {_today()}"
             + (f" · page filter: `{page_slug}`" if page_slug else ""))
    L.append("")
    L.append("| creative | advertiser | first seen running | days running "
             "| # library IDs | CTA | res |")
    L.append("|---|---|---|---|---|---|---|")
    for r in rows:
        L.append(f"| `{r['key']}` | {r['page_name']} | {r['first_start'] or '?'} "
                 f"| {r['days'] if r['days'] is not None else '?'} | {r['n_ads']} "
                 f"| {r.get('cta') or '?'} | {r['res']} |")
    L += ["", f"**{len(rows)} unique creatives across {len(entries)} library IDs.**", "",
          "Longevity and library-ID count are PROXIES, not metrics. The Ad Library "
          "publishes no impressions, spend, retention, or ROAS for commercial ads. "
          "A long-running ad means the advertiser keeps paying for it — confounded "
          "by budget, always-on strategy, seasonality, and inertia. Read every row "
          "as a hypothesis about what they believe, to be tested on your own "
          "account, never as evidence it will work for you.", ""]
    return "\n".join(L), rows


def cmd_report(args):
    md, rows = build_report(args.page_slug)
    print(md)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    dest = Path(args.out) if args.out else OUTPUT / (
        f"longevity-{args.page_slug or 'all'}-{_today()}.md")
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(md)
    print(f"\nwrote {dest}")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("ingest")
    p.add_argument("--in", dest="infile", required=True)
    p.add_argument("--page-slug", default=None)
    p.add_argument("--label", default=None,
                   help="free-text tag, e.g. competitor / us / category")
    p.set_defaults(fn=cmd_ingest)
    p = sub.add_parser("status")
    p.add_argument("--page-slug", default=None)
    p.set_defaults(fn=cmd_status)
    p = sub.add_parser("report")
    p.add_argument("--page-slug", default=None)
    p.add_argument("--out", default=None)
    p.set_defaults(fn=cmd_report)
    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
