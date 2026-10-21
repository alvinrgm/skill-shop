#!/usr/bin/env python3
"""Harvest a page's STATIC image ads from the public Meta Ad Library into your
inspo library ($AD_LOOP_HOME/inspo).

Headless, anonymous, public pages only (no login, no cookies). It extracts
snapshot.images[].original_image_url (+ card images) and each image's
destination (snapshot.link_url; a carousel card's own link_url), dedupes by CDN filename
AND by content at download time (md5 + 16x16 dhash — a re-uploaded creative
gets a fresh CDN filename, so filename identity alone inflates the corpus; an audit
found most advertisers carried 1-3 such duplicate pairs), downloads the files
immediately (signed URLs expire ~5 days).

Default filter is media_type=all: Meta's media_type=image filter is unreliable
server-side (it has returned "No ads" for a page demonstrably running ~990
statics under media_type=all). --media all still yields only
real statics because the extractor reads snapshot.images[]/cards[] and never
video_preview_image_url.

Ads past the first ~30 arrive as /api/graphql XHRs while scrolling. They are read
with Playwright's page.on("response") listener: the window.fetch wrapper this
tool used before never saw them (0 captures, 30 of ~410 ads on one advertiser).

Usage:
  harvest_inspo.py --page-id <AD_LIBRARY_PAGE_ID> --slug <advertiser> [--top 12] [--country US] [--media all]

Find a page id: open https://www.facebook.com/ads/library/, search the advertiser, click
into their page, and copy view_all_page_id=<ID> from the browser URL.

Automated access to the Ad Library is contrary to Meta's Terms of Service; keep it to
occasional, low-volume research. Harvested creatives are someone else's copyrighted work:
study them as a taste bar, never republish them.

Output: $AD_LOOP_HOME/inspo/<slug>/<slug>_NN.jpg + <slug>/manifest.json
"""
import argparse
import hashlib
import io
import json
import os
import sys
import time
import urllib.request
from pathlib import Path

# Re-run under the package's own .venv when one exists (config.py does that at import).
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
import config as _pkg_config  # noqa: E402,F401

INSPO = Path(os.path.expanduser(os.environ.get("AD_LOOP_HOME") or str(Path.home() / "ad-loop-work"))) / "inspo"

AD_LIBRARY_URL = (
    "https://www.facebook.com/ads/library/"
    "?active_status=active&ad_type=all&country={country}"
    "&view_all_page_id={page_id}&media_type={media}"
)

EXTRACT_JS = r"""
(extra) => {
  const found = {};
  const pick = (o) => {
    const snap = o.snapshot || {};
    const imgs = [];
    for (const im of (snap.images || []))
      imgs.push({url: im.original_image_url || im.resized_image_url || null,
                 link_url: snap.link_url || null});
    for (const c of (snap.cards || []))
      if (c.original_image_url || c.resized_image_url)
        imgs.push({url: c.original_image_url || c.resized_image_url,
                   link_url: c.link_url || snap.link_url || null});
    return {
      library_id: String(o.ad_archive_id),
      start_date: o.start_date || null,
      is_active: o.is_active !== undefined ? o.is_active : null,
      collation_count: o.collation_count || null,
      page_name: o.page_name || snap.page_name || null,
      cta_type: snap.cta_type || null,
      title: (snap.title || "").slice(0, 200) || null,
      body: ((snap.body && snap.body.text) || "").slice(0, 300) || null,
      images: imgs.filter(im => im.url),
    };
  };
  const walk = (o) => {
    if (!o || typeof o !== "object") return;
    if (o.ad_archive_id) {
      const e = pick(o);
      const prev = found[e.library_id];
      if (!prev || (e.images.length && !prev.images.length)) found[e.library_id] = e;
    }
    for (const k in o) walk(o[k]);
  };
  const tryParse = (t) => {
    try { walk(JSON.parse(t)); return; } catch (e) {}
    for (const line of t.split("\n")) { try { walk(JSON.parse(line)); } catch (e) {} }
  };
  document.querySelectorAll('script[type="application/json"]')
          .forEach(s => tryParse(s.textContent));
  (extra || []).forEach(tryParse);
  return Object.values(found);
}
"""


def _djb2(s):
    h = 5381
    for ch in s:
        h = ((h * 33) ^ ord(ch)) & 0xFFFFFFFF
    return format(h, "08x")


# Duplicate threshold on the 256-bit dhash. Verified duplicates in the corpus
# are all byte-identical (hamming 0); ratio variants of one concept (a real
# second layout, which we WANT to keep) sit far above this — an audit of the
# corpus in a prior run found no pair between 1 and 10.
DUP_HAMMING = 8


def _dhash_bytes(data, size=16):
    """256-bit row-wise difference hash of an image's bytes.

    Returns None when PIL is missing or the bytes don't decode — the md5
    exact-match check still runs in that case, which alone catches every
    duplicate observed so far (re-uploads are served byte-identical).
    """
    try:
        from PIL import Image
    except ImportError:
        return None
    try:
        img = (Image.open(io.BytesIO(data)).convert("L")
               .resize((size + 1, size), Image.LANCZOS))
    except Exception:  # noqa: BLE001 — undecodable download, md5 still applies
        return None
    px = list(img.getdata())
    bits = 0
    for row in range(size):
        for col in range(size):
            bits = (bits << 1) | (px[row * (size + 1) + col]
                                  > px[row * (size + 1) + col + 1])
    return bits


def compact(ads):
    """One creative can run under many library IDs — dedupe by CDN filename."""
    by_img = {}
    for a in ads:
        for im in a.get("images") or []:
            url = im["url"]
            key = _djb2(url.split("?")[0].split("/")[-1][:64])
            if key not in by_img:
                by_img[key] = {
                    "creative_key": key, "url": url,
                    "page_name": a.get("page_name"), "cta_type": a.get("cta_type"),
                    "title": a.get("title"), "body": a.get("body"),
                    "link_url": im.get("link_url"),
                    "start_date": a.get("start_date"),
                    "collation_count": a.get("collation_count") or 0,
                    "library_ids": [],
                }
            by_img[key]["link_url"] = by_img[key]["link_url"] or im.get("link_url")
            by_img[key]["library_ids"].append(a.get("library_id"))
            by_img[key]["collation_count"] = max(
                by_img[key]["collation_count"], a.get("collation_count") or 0)
            if (a.get("start_date") or 9e12) < (by_img[key]["start_date"] or 9e12):
                by_img[key]["start_date"] = a.get("start_date")
    return list(by_img.values())


def harvest(page_id, country, max_scrolls, headed, media="all"):
    from playwright.sync_api import sync_playwright
    url = AD_LIBRARY_URL.format(country=country, page_id=page_id, media=media)
    print(f"harvest: {url}")
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=not headed)
        ctx = browser.new_context(
            viewport={"width": 1400, "height": 1000},
            user_agent=("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/131.0.0.0 Safari/537.36"),
        )
        page = ctx.new_page()
        gql, bodies = [], []
        page.on("response",
                lambda r: gql.append(r) if "/api/graphql" in r.url else None)

        def drain():
            # bodies are read here, between scrolls, not inside the listener
            while gql:
                r = gql.pop(0)
                try:
                    t = r.text()
                except Exception:  # noqa: BLE001 — body unavailable; the rest still count
                    continue
                if "ad_archive_id" in t:
                    bodies.append(t)

        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        try:
            page.wait_for_selector("text=/results/i", timeout=20000)
        except Exception:
            print("  (no results header — page may be empty or slow)")
        last_h, stable = 0, 0
        for i in range(max_scrolls):
            page.mouse.wheel(0, 20000)
            time.sleep(1.5)
            drain()
            h = page.evaluate("() => document.body.scrollHeight")
            if h == last_h:
                stable += 1
                if stable >= 3:
                    break
            else:
                stable = 0
            last_h = h
        else:
            print(f"  scroll ceiling hit (--max-scrolls {max_scrolls}) while results "
                  f"were still loading — raise it to see the rest")
        drain()
        ads = page.evaluate(EXTRACT_JS, bodies)
        evidence = page.evaluate("""() => {
            const t = document.body.innerText || "";
            const m = t.match(/~?([\\d,]+)\\s+results?/i);
            return {claimed: m ? parseInt(m[1].replace(/,/g, ''), 10) : null,
                    libraryIdMentions: (t.match(/Library ID/g) || []).length};
        }""")
        browser.close()
    creatives = compact(ads)
    claimed = evidence.get("claimed")
    print(f"harvest: {len(ads)} ads seen (page claims {claimed if claimed else '?'}) "
          f"-> {len(creatives)} unique image creatives")
    if claimed and len(ads) < 0.95 * claimed:
        print(f"  WARNING: saw {len(ads)} of ~{claimed} ads ({100 * len(ads) // claimed}%) — "
              f"the longest-running creatives may be among the ones not loaded")
    if not creatives and ((evidence.get("claimed") or 0) > 0
                          or (evidence.get("libraryIdMentions") or 0) > 0):
        sys.exit(f"HARVEST BLOCKED: page shows ads ({evidence}) but parser got 0. "
                 f"Not 'no ads' — retry in a few minutes.")
    return creatives


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--page-id", required=True)
    ap.add_argument("--slug", required=True)
    ap.add_argument("--top", type=int, default=12,
                    help="download the N longest-running creatives (default 12)")
    ap.add_argument("--country", default="US")
    # ~1.4 result pages load per scroll and a page stops growing once every ad is
    # in, so this is only a ceiling; 25 stopped a ~410-ad advertiser before the end
    ap.add_argument("--max-scrolls", type=int, default=80)
    ap.add_argument("--headed", action="store_true")
    ap.add_argument("--media", default="all", choices=["image", "all"],
                    help="Ad Library media_type filter (default: all — the "
                         "image filter has been unreliable Meta-side, "
                         "returning 0 for pages that do run "
                         "statics; 'all' still yields only real statics "
                         "because the extractor reads snapshot.images[]/"
                         "cards[] and never video_preview_image_url)")
    args = ap.parse_args()

    creatives = harvest(args.page_id, args.country, args.max_scrolls, args.headed,
                        args.media)
    # longest-running first (start_date asc) — longevity is the only public
    # performance proxy; collation_count breaks ties
    creatives.sort(key=lambda c: (c.get("start_date") or 9e12,
                                  -(c.get("collation_count") or 0)))

    # Walk the sorted list downloading until --top UNIQUE images are saved.
    # Content dedupe has to happen here, not in compact(): a re-uploaded
    # creative carries a fresh CDN filename, so only the bytes reveal it.
    out_dir = INSPO / args.slug
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest = []
    kept = []  # (md5 hexdigest, dhash bits or None, manifest entry)
    for c in creatives:
        if len(manifest) >= args.top:
            break
        try:
            req = urllib.request.Request(c["url"], headers={"User-Agent": "Mozilla/5.0"})
            data = urllib.request.urlopen(req, timeout=60).read()
        except Exception as e:  # noqa: BLE001 — skip expired/broken URLs, keep going
            print(f"  FAILED {c['creative_key']}: {e}")
            continue
        digest = hashlib.md5(data).hexdigest()
        h = _dhash_bytes(data)
        dup = next((e for m, hh, e in kept
                    if m == digest
                    or (h is not None and hh is not None
                        and bin(h ^ hh).count("1") <= DUP_HAMMING)), None)
        if dup is not None:
            dup["library_ids"] = sorted(
                set(dup["library_ids"]) | set(c["library_ids"]))
            dup["collation_count"] = max(dup["collation_count"] or 0,
                                         c.get("collation_count") or 0)
            dup["link_url"] = dup["link_url"] or c.get("link_url")
            print(f"  dup of {dup['file']} (re-upload under a new CDN "
                  f"filename) — skipped, library_ids merged")
            continue
        name = f"{args.slug}_{len(manifest) + 1:02d}.jpg"
        (out_dir / name).write_bytes(data)
        print(f"  saved {name}  (running since {c.get('start_date')}, "
              f"collation {c.get('collation_count')})")
        entry = {**{k: c[k] for k in
                    ("creative_key", "title", "body", "cta_type", "link_url",
                     "start_date", "collation_count", "library_ids")},
                 "file": name}
        manifest.append(entry)
        kept.append((digest, h, entry))
    manifest_path = out_dir / "manifest.json"
    if not manifest:
        # A 0-result run must never blank a good manifest (observed:
        # the page itself reported 0 results, so the HARVEST BLOCKED guard
        # can't catch this case).
        existing = 0
        if manifest_path.exists():
            try:
                existing = len(json.loads(manifest_path.read_text()))
            except Exception:  # noqa: BLE001
                pass
        print(f"WARNING: {args.slug}: harvest returned 0 creatives — "
              f"NOT writing manifest.json (existing manifest has {existing} "
              f"entries and was left untouched). Nothing was refreshed.")
        return
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print(f"{args.slug}: {len(manifest)} images -> {out_dir}")


if __name__ == "__main__":
    main()
