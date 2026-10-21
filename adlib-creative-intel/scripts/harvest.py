#!/usr/bin/env python3
"""Harvest a page's video ads from the public Meta Ad Library (headless).

NO CREDENTIALS NEEDED. The Ad Library is a public page — no login, no API key,
no ad account. That is the whole reason this pipeline can be shared: the only
thing standing between you and a competitor's raw creative is a browser.

WHY A BROWSER AND NOT THE API (all three tested; don't re-litigate):
  - The official Ad Library API returns metadata ONLY for commercial ads —
    page name, dates, a snapshot URL. No creative assets. Assets are exposed
    through the API only for political/issue ads and EU-served (DSA) ads.
  - yt-dlp ships a `facebook:ads` extractor, but Meta answers unauthenticated
    requests with a 403 client challenge, and TLS impersonation does not help.
    It only works with a logged-in session's cookies, which this tool refuses
    to require.
  - A real browser renders the public page fine. Videos arrive as SIGNED CDN
    mp4 URLs: SD in the <video> tags, HD inside the page's embedded JSON.

The signed URLs carry an `oe` expiry (measured ~5 days out), so a harvest is
not a race — but ingest in the same run anyway; that is what full_run.py does.

Usage:
  harvest.py --page-id 178024832922517 --out data/harvest.json
  harvest.py --page-id <id> --out <file> --country GB --max-scrolls 60 --headed
"""
import argparse
import json
import sys
import time
from pathlib import Path

AD_LIBRARY_URL = (
    "https://www.facebook.com/ads/library/"
    "?active_status=active&ad_type=all&country={country}"
    "&view_all_page_id={page_id}&media_type=video"
)

# Deep-walks the page's JSON for ad_archive_id objects. Kept as one string so
# the browser-driven and headless paths run byte-identical logic.
EXTRACT_JS = r"""
() => {
  const found = {};
  const pick = (o) => {
    const snap = o.snapshot || {};
    const vids = [];
    for (const v of (snap.videos || []))
      vids.push({hd: v.video_hd_url || null, sd: v.video_sd_url || null});
    for (const c of (snap.cards || []))
      if (c.video_hd_url || c.video_sd_url)
        vids.push({hd: c.video_hd_url || null, sd: c.video_sd_url || null});
    return {
      library_id: String(o.ad_archive_id),
      start_date: o.start_date || null,
      end_date: o.end_date || null,
      is_active: o.is_active !== undefined ? o.is_active : null,
      collation_count: o.collation_count || null,
      page_id: o.page_id || snap.page_id || null,
      page_name: o.page_name || snap.page_name || null,
      publisher_platform: o.publisher_platform || null,
      cta_type: snap.cta_type || null,
      link_url: (snap.link_url || "").slice(0, 200) || null,
      title: (snap.title || "").slice(0, 200) || null,
      body: ((snap.body && snap.body.text) || "").slice(0, 300) || null,
      videos: vids,
    };
  };
  const walk = (o) => {
    if (!o || typeof o !== "object") return;
    if (o.ad_archive_id) {
      const e = pick(o);
      const prev = found[e.library_id];
      if (!prev || (e.videos.length && !prev.videos.length)) found[e.library_id] = e;
    }
    for (const k in o) walk(o[k]);
  };
  const tryParse = (t) => {
    try { walk(JSON.parse(t)); return; } catch (e) {}
    for (const line of t.split("\n")) { try { walk(JSON.parse(line)); } catch (e) {} }
  };
  document.querySelectorAll('script[type="application/json"]')
          .forEach(s => tryParse(s.textContent));
  (window.__adlibCap || []).forEach(tryParse);
  return Object.values(found);
}
"""

# Installed before any navigation so paginated XHR responses are captured too.
CAPTURE_HOOK_JS = r"""
() => {
  if (window.__adlibHooked) return;
  window.__adlibCap = [];
  window.__adlibHooked = true;
  const of = window.fetch;
  window.fetch = function (...a) {
    const p = of.apply(this, a);
    try {
      const url = String((a[0] && a[0].url) || a[0] || "");
      if (url.includes("/api/graphql")) {
        p.then(r => r.clone().text().then(t => {
          if (t.includes("ad_archive_id")) window.__adlibCap.push(t);
        })).catch(() => {});
      }
    } catch (e) {}
    return p;
  };
}
"""


class HarvestBlocked(RuntimeError):
    """The page had ads but we extracted none — blocked, or the shape changed.

    Deliberately NOT the same as an empty result. An empty result is a finding;
    this is a failure, and the two must never be reported the same way.
    """


def _djb2(s):
    h = 5381
    for ch in s:
        h = ((h * 33) ^ ord(ch)) & 0xFFFFFFFF
    return format(h, "08x")


def compact(ads):
    """Collapse ads to unique CREATIVES.

    Meta runs one video under many library IDs (placement/collation variants).
    Deduping by video asset is what keeps the download count and the analysis
    unit honest — counting ads would inflate everything several-fold.
    """
    by_vid = {}
    for a in ads:
        vids = a.get("videos") or []
        if not vids:
            continue
        v = vids[0]
        url = v.get("hd") or v.get("sd")
        if not url:
            continue
        # asset identity = the CDN filename, stable across signature params
        key = _djb2(url.split("?")[0].split("/")[-1][:64])
        if key not in by_vid:
            by_vid[key] = {
                "creative_key": key, "hd": v.get("hd"), "sd": v.get("sd"),
                "page_id": a.get("page_id"), "page_name": a.get("page_name"),
                "cta_type": a.get("cta_type"), "title": a.get("title"),
                "body": a.get("body"), "link_url": a.get("link_url"), "ads": [],
            }
        by_vid[key]["ads"].append({
            "library_id": a.get("library_id"), "start_date": a.get("start_date"),
            "is_active": a.get("is_active"),
            "collation_count": a.get("collation_count"),
            "publisher_platform": a.get("publisher_platform"),
        })
    return list(by_vid.values())


def harvest(page_id, country="US", max_scrolls=40, headed=False, quiet=False):
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        sys.exit("playwright not installed. Run: pip install -r requirements.txt "
                 "&& python3 -m playwright install chromium")

    url = AD_LIBRARY_URL.format(country=country, page_id=page_id)
    say = (lambda *a: None) if quiet else print
    say(f"harvest: {url}")

    with sync_playwright() as p:
        try:
            browser = p.chromium.launch(headless=not headed)
        except Exception as e:
            sys.exit(f"could not launch chromium: {e}\n"
                     f"Run: python3 -m playwright install chromium")
        ctx = browser.new_context(
            viewport={"width": 1400, "height": 1000},
            user_agent=("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) "
                        "Chrome/131.0.0.0 Safari/537.36"),
        )
        ctx.add_init_script("(" + CAPTURE_HOOK_JS + ")()")
        page = ctx.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        try:
            page.wait_for_selector("text=/results/i", timeout=20000)
        except Exception:
            say("  (no results header — page may be empty or slow)")

        last_h, stable = 0, 0
        for i in range(max_scrolls):
            page.mouse.wheel(0, 20000)
            time.sleep(1.5)
            h = page.evaluate("() => document.body.scrollHeight")
            if h == last_h:
                stable += 1
                if stable >= 3:      # 3 quiet rounds = genuinely the bottom
                    break
            else:
                stable = 0
            last_h = h
            if not quiet and i % 5 == 0:
                say(f"  scroll {i}: height={h}")

        ads = page.evaluate(EXTRACT_JS)
        # Distinguish "this advertiser genuinely has no ads" from "we were
        # blocked or the page shape changed and our parser found nothing."
        # Conflating those is the worst failure mode a research tool can have:
        # it reports a confident, wrong "no ads" instead of an honest error.
        evidence = page.evaluate("""() => {
            const t = document.body.innerText || "";
            const m = t.match(/~?([\\d,]+)\\s+results?/i);
            return {claimed: m ? parseInt(m[1].replace(/,/g, ''), 10) : null,
                    libraryIdMentions: (t.match(/Library ID/g) || []).length,
                    videoTags: document.querySelectorAll('video').length,
                    bodyLen: t.length};
        }""")
        browser.close()

    creatives = compact(ads)
    say(f"harvest: {len(ads)} ads -> {len(creatives)} unique creatives "
        f"({sum(1 for c in creatives if c['hd'])} with HD)")

    if not creatives:
        claimed = evidence.get("claimed")
        mentions = evidence.get("libraryIdMentions") or 0
        vids = evidence.get("videoTags") or 0
        if (claimed or 0) > 0 or mentions > 0 or vids > 0:
            raise HarvestBlocked(
                f"The page shows ads (results header: {claimed}, "
                f"'Library ID' mentions: {mentions}, <video> tags: {vids}) but the "
                f"parser extracted 0. This is NOT 'the advertiser has no ads' — it "
                f"means we were rate-limited/blocked, or the page structure changed. "
                f"Wait a few minutes and retry; if it persists, the extraction logic "
                f"needs updating.")
        say("  (page shows no ad results at all — this advertiser genuinely appears "
            "to have no active video ads in this country)")
    return creatives


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--page-id", required=True,
                    help="Meta Page ID. Find it in the Ad Library URL: open the "
                         "advertiser's page and copy view_all_page_id=<ID>")
    ap.add_argument("--out", required=True)
    ap.add_argument("--country", default="US", help="ISO-2 country (default US)")
    ap.add_argument("--max-scrolls", type=int, default=40)
    ap.add_argument("--headed", action="store_true", help="show the browser")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    try:
        creatives = harvest(args.page_id, args.country, args.max_scrolls,
                            args.headed, args.quiet)
    except HarvestBlocked as e:
        print(f"\nHARVEST BLOCKED: {e}")
        sys.exit(2)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    # never clobber a good harvest with an empty one
    if not creatives and out.exists():
        try:
            prior = json.loads(out.read_text())
        except Exception:  # noqa: BLE001
            prior = []
        if prior:
            print(f"refusing to overwrite {out} ({len(prior)} creatives) with an "
                  f"empty result — keeping the existing harvest.")
            sys.exit(2)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(creatives, indent=2))
    print(f"wrote {out} ({len(creatives)} creatives)")
    if not creatives:
        print("NOTE: zero creatives, and the page showed no ad results either. "
              "Either this advertiser runs no active VIDEO ads in this country, "
              "or the page ID is wrong.")


if __name__ == "__main__":
    main()
