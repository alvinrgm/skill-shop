#!/usr/bin/env python3
"""Crawl a brand's own website for full-resolution photography: the raw material for the
Assets page and for the real pack cutouts.

Two sources, both public, no login:
  1. Shopify stores: <site>/products.json (every product image at full resolution).
  2. Any site: the <img>, srcset and og:image URLs on the pages you list with --page.
Images are saved to <brand>/brand/site-photography/ as r###__<slug>.<ext>, with index.json
recording the source URL of each. Next step, in the session: classify each image (category,
product, text burned in, ad-usable) into classification.json and write INVENTORY.md with the gaps.

Only crawl a site you have the right to use images from (your own brand or a client that has
given you the assets).

usage: crawl_site.py <brand> --site https://example.com [--page /pages/about ...] [--min-px 800] [--max 400]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import brand_dir  # noqa: E402

UA = {"User-Agent": "Mozilla/5.0 (ad-library asset crawl)"}
STATS = {"requests": 0, "errors": 0}


def fetch(url: str, timeout: int = 60) -> bytes:
    STATS["requests"] += 1
    req = urllib.request.Request(url, headers=UA)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()
    except (urllib.error.URLError, OSError):  # HTTPError is a URLError; timeouts are OSError
        STATS["errors"] += 1
        raise


class ImgParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.urls: list[str] = []

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "img":
            for k in ("data-src", "src"):
                if a.get(k):
                    self.urls.append(a[k])
            for k in ("srcset", "data-srcset"):
                if a.get(k):  # take the largest candidate
                    cands = [c.strip().split(" ")[0] for c in a[k].split(",") if c.strip()]
                    if cands:
                        self.urls.append(cands[-1])
        if tag == "meta" and a.get("property") in ("og:image", "og:image:secure_url") and a.get("content"):
            self.urls.append(a["content"])


def shopify_images(site: str) -> list[tuple[str, str]]:
    out, page = [], 1
    while page < 50:
        try:
            data = json.loads(fetch(f"{site}/products.json?limit=250&page={page}"))
        except (urllib.error.URLError, OSError, json.JSONDecodeError):
            break
        prods = data.get("products", [])
        if not prods:
            break
        for p in prods:
            for i, img in enumerate(p.get("images", [])):
                out.append((img["src"], f"{p.get('handle', 'product')}-{i + 1}"))
        page += 1
    return out


def page_images(site: str, path: str) -> list[tuple[str, str]]:
    url = urllib.parse.urljoin(site + "/", path.lstrip("/"))
    try:
        html = fetch(url).decode("utf-8", "replace")
    except (urllib.error.URLError, OSError) as e:
        print(f"skip page {url}: {e}")
        return []
    p = ImgParser()
    p.feed(html)
    slug = re.sub(r"[^a-z0-9]+", "-", path.lower()).strip("-") or "home"
    return [(urllib.parse.urljoin(url, u), slug) for u in p.urls if not u.startswith("data:")]


def full_res(u: str) -> str:
    u = "https:" + u if u.startswith("//") else u
    u = re.sub(r"_(\d+x\d*|\d*x\d+)(?=\.(jpe?g|png|webp))", "", u)  # Shopify size suffix
    return re.sub(r"([?&])(width|w|height|h)=\d+&?", r"\1", u).rstrip("?&")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("brand")
    ap.add_argument("--site", required=True)
    ap.add_argument("--page", action="append", default=[], help="page path to read images from "
                    "(repeatable; the home page / is always included)")
    ap.add_argument("--min-px", type=int, default=800, help="drop images whose long side is smaller")
    ap.add_argument("--max", type=int, default=400)
    a = ap.parse_args()
    site = a.site.rstrip("/")
    out = brand_dir(a.brand) / "brand" / "site-photography"
    out.mkdir(parents=True, exist_ok=True)
    cands = shopify_images(site)
    print(f"products.json: {len(cands)} images" if cands else "products.json: none (not Shopify, or closed)")
    pages = list(dict.fromkeys("/" + p.strip().lstrip("/") for p in ["/", *a.page]))
    for pg in pages:
        cands += page_images(site, pg)
    seen, index = set(), []
    try:
        from PIL import Image
    except ImportError:
        Image = None
    for u, label in cands:
        u = full_res(u)
        key = u.split("?")[0]
        if key in seen or len(index) >= a.max:
            continue
        seen.add(key)
        ext = (Path(urllib.parse.urlparse(key).path).suffix or ".jpg").lower()
        if ext not in (".jpg", ".jpeg", ".png", ".webp"):
            continue
        name = f"r{len(index) + 1:03d}__{re.sub(r'[^a-z0-9-]+', '-', label.lower())[:40]}{ext}"
        try:
            data = fetch(u)
        except (urllib.error.URLError, OSError) as e:
            print(f"skip {u}: {e}")
            continue
        f = out / name
        f.write_bytes(data)
        size = None
        if Image:
            try:
                size = Image.open(f).size
            except Exception:
                size = None
            if size and max(size) < a.min_px:
                f.unlink()
                continue
        index.append({"file": name, "url": u, "size": size})
    (out / "index.json").write_text(json.dumps(index, indent=1))
    print(f"saved {len(index)} images to {out} (index.json lists the source of each)")
    if not index and STATS["requests"] and STATS["errors"] == STATS["requests"]:
        sys.exit(f"crawl failed: all {STATS['requests']} requests errored (check the --site URL and your network)")


if __name__ == "__main__":
    main()
