#!/usr/bin/env python3
"""No-credential intelligence: what you can learn WITHOUT watching the videos.

The per-second creative analysis (cv_analyze.py) needs an API key. This module
needs nothing. It reads what the harvest already captured plus what the video
files themselves declare, and turns it into a real report — so the no-key path
produces intelligence, not just a table of hashes and dates.

What it extracts, all credential-free:
  offers        promo/discount codes in the ad copy. A spread of person-shaped
                codes is a creator/affiliate program in plain sight, and the
                roster is the list of partners they are actively paying.
  destinations  landing paths. One path across every ad is a focused funnel;
                many paths is a catalog strategy.
  campaign tags utm_campaign values where present. NOT always present — many
                advertisers use non-utm params (promo_code, etc.) or none.
  cta mix       call-to-action buttons, and how they shift by launch date.
  placements    which platforms each creative is booked on.
  cadence       launches grouped by date — their testing tempo.
  format        duration, resolution, aspect ratio, file weight. Requires
                ffprobe; skipped cleanly when it is absent.
  copy          the ad body text, deduped.
  qa            unresolved template placeholders ({{product.name}}) that made it
                to a live ad — worth noticing, in their ads or your own.

Usage as a lib:  from describe import describe, render
CLI:             describe.py --page-slug seed [--out outputs/profile-seed.md]
"""
import argparse
import collections
import json
import os
import re
import shutil
import subprocess
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get("ADLIB_DATA", PKG_ROOT / "data"))
OUTPUT = Path(os.environ.get("ADLIB_OUTPUT", PKG_ROOT / "outputs"))

CODE_RE = re.compile(r"\b(?:code|promo_code=|coupon)\s*:?\s*([A-Z0-9]{4,14})\b", re.I)
PLACEHOLDER_RE = re.compile(r"\{\{[^}]+\}\}")


def _ffprobe(path):
    if not shutil.which("ffprobe"):
        return None
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0",
             "-show_entries", "stream=width,height:format=duration",
             "-of", "json", str(path)],
            capture_output=True, text=True, timeout=30)
        j = json.loads(out.stdout or "{}")
        st = (j.get("streams") or [{}])[0]
        w, h = st.get("width"), st.get("height")
        dur = float((j.get("format") or {}).get("duration") or 0) or None
        ratio = None
        if w and h:
            r = w / h
            ratio = ("9:16 vertical" if r < 0.62 else
                     "4:5 portrait" if r < 0.9 else
                     "1:1 square" if r < 1.1 else
                     "16:9 landscape")
        return {"width": w, "height": h, "duration_sec": dur, "aspect": ratio}
    except Exception:  # noqa: BLE001
        return None


def _load(page_slug):
    """Prefer per-creative sidecars; they carry the full harvested record."""
    page_dir = DATA / page_slug
    recs = []
    for j in sorted(page_dir.glob("*.json")):
        if j.name.startswith("cv_"):
            continue
        try:
            recs.append(json.loads(j.read_text()))
        except Exception:  # noqa: BLE001
            continue
    return recs, page_dir


def describe(page_slug):
    recs, page_dir = _load(page_slug)
    codes, paths, campaigns, ctas, platforms = (collections.Counter() for _ in range(5))
    bodies, launches, fmts, placeholders = set(), collections.Counter(), [], []

    for c in recs:
        text = " ".join(filter(None, [c.get("title"), c.get("body")]))
        url = c.get("link_url") or ""
        for m in CODE_RE.findall(text + " " + url):
            codes[m.upper()] += 1
        if url:
            paths[re.sub(r"https?://[^/]+", "", url).split("?")[0] or "/"] += 1
            if "utm_campaign=" in url:
                campaigns[url.split("utm_campaign=")[1].split("&")[0]] += 1
        if c.get("cta_type"):
            ctas[c["cta_type"]] += 1
        if c.get("body"):
            bodies.add(c["body"].strip())
        if PLACEHOLDER_RE.search(text):
            placeholders.append(c.get("creative_key"))
        for a in (c.get("ads") or []):
            for p in (a.get("publisher_platform") or []):
                platforms[p] += 1
            if a.get("start_date"):
                import datetime as dt
                try:
                    launches[dt.datetime.fromtimestamp(
                        int(a["start_date"])).date().isoformat()] += 1
                except Exception:  # noqa: BLE001
                    pass
        mp4 = page_dir / f"{c.get('creative_key')}.mp4"
        if mp4.exists():
            info = _ffprobe(mp4)
            if info:
                info["creative_key"] = c.get("creative_key")
                info["mb"] = round(mp4.stat().st_size / 1e6, 1)
                fmts.append(info)

    return {
        "page_slug": page_slug,
        "n_creatives": len(recs),
        "page_name": recs[0].get("page_name") if recs else None,
        "offer_codes": codes, "landing_paths": paths, "campaigns": campaigns,
        "ctas": ctas, "platforms": platforms, "launches": launches,
        "bodies": sorted(bodies), "formats": fmts,
        "placeholder_creatives": placeholders,
        "ffprobe_available": bool(shutil.which("ffprobe")),
    }


def render(d):
    L = [f"# Advertiser profile — {d.get('page_name') or d['page_slug']}", "",
         f"Built from {d['n_creatives']} harvested creatives. **No API key was used "
         f"for anything on this page** — every line below comes from the ad metadata "
         f"and the video files themselves.", ""]

    if d["offer_codes"]:
        L += ["## Offers and codes", "",
              "Discount codes appearing in the live ad copy. Person-shaped codes "
              "usually mean an active creator/affiliate roster — the partners they "
              "are paying right now, visible without any access to their account.", ""]
        for code, n in d["offer_codes"].most_common():
            L.append(f"- `{code}` — in {n} creative(s)")
        L.append("")

    L += ["## Where the traffic goes", ""]
    for p, n in d["landing_paths"].most_common(10):
        L.append(f"- `{p}` — {n} creative(s)")
    if len(d["landing_paths"]) == 1:
        L += ["", "> Every ad points at a single page. That is a deliberately "
                  "narrow funnel, not a catalog strategy."]
    L.append("")

    if d["campaigns"]:
        L += ["## Campaign tags (utm_campaign)", ""]
        for c, n in d["campaigns"].most_common():
            L.append(f"- `{c}` — {n}")
        L.append("")
    else:
        L += ["## Campaign tags", "",
              "None of these ads carry a `utm_campaign` parameter, so their internal "
              "campaign naming is not exposed here. This varies by advertiser — some "
              "leak their whole taxonomy in the link, others use non-utm parameters "
              "or none at all. Absence tells you nothing about their sophistication.", ""]

    L += ["## Call-to-action mix", ""]
    for c, n in d["ctas"].most_common():
        L.append(f"- {c} — {n}")
    L += ["", "## Placements", ""]
    for p, n in d["platforms"].most_common():
        L.append(f"- {p} — {n} ad(s)")

    L += ["", "## Launch cadence", "",
          "How many ads went live on each date — their testing tempo.", ""]
    for day, n in sorted(d["launches"].items()):
        L.append(f"- {day}: {n} ad(s) {'▪' * min(n, 30)}")

    L += ["", "## Format", ""]
    if not d["ffprobe_available"]:
        L += ["_ffprobe not installed — duration, resolution, and aspect ratio "
              "skipped. Install ffmpeg to enable (`brew install ffmpeg`)._", ""]
    elif d["formats"]:
        durs = [f["duration_sec"] for f in d["formats"] if f.get("duration_sec")]
        if durs:
            L.append(f"- {len(durs)} videos · shortest {min(durs):.0f}s · "
                     f"longest {max(durs):.0f}s · median "
                     f"{sorted(durs)[len(durs) // 2]:.0f}s")
        for a, n in collections.Counter(
                f.get("aspect") for f in d["formats"] if f.get("aspect")).most_common():
            L.append(f"- {a} — {n}")
        L.append("")
        L += ["| creative | duration | resolution | aspect | size |", "|---|---|---|---|---|"]
        for f in sorted(d["formats"], key=lambda x: -(x.get("duration_sec") or 0)):
            L.append(f"| `{f['creative_key']}` | "
                     f"{(str(round(f['duration_sec'])) + 's') if f.get('duration_sec') else '?'} | "
                     f"{f.get('width')}x{f.get('height')} | {f.get('aspect') or '?'} | "
                     f"{f.get('mb')}MB |")
    L.append("")

    if d["placeholder_creatives"]:
        L += ["## QA flag — unresolved placeholders", "",
              f"{len(d['placeholder_creatives'])} creative(s) carry an unrendered "
              "template placeholder (e.g. `{{product.name}}`) in the live ad text. "
              "In catalog/dynamic ads the field is filled at render time, so this is "
              "often cosmetic — but it is worth a look, and worth checking you are "
              "not doing the same.", ""]
        L.append("Affected: " + ", ".join(f"`{k}`" for k in d["placeholder_creatives"]))
        L.append("")

    if d["bodies"]:
        L += ["## Ad copy", "",
              f"{len(d['bodies'])} distinct body text(s) across the set.", ""]
        for b in d["bodies"][:25]:
            L.append(f"- {b}")
        L.append("")

    L += ["---", "",
          "**What this does and does not tell you.** Everything above is *observed "
          "fact* — codes, links, buttons, dates, file properties. None of it is "
          "performance. The Ad Library publishes no impressions, spend, or ROAS, so "
          "nothing here says an ad worked. Pair it with the longevity report for the "
          "only available performance proxy, and treat even that as a hypothesis.", ""]
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--page-slug", required=True)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    d = describe(args.page_slug)
    if not d["n_creatives"]:
        raise SystemExit(f"no harvested creatives found for '{args.page_slug}' in {DATA}")
    md = render(d)
    print(md)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    dest = Path(args.out) if args.out else OUTPUT / f"profile-{args.page_slug}.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(md)
    print(f"\nwrote {dest}")


if __name__ == "__main__":
    main()
