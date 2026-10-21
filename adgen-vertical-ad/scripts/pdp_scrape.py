#!/usr/bin/env python3
"""pdp_scrape.py — Link 1 of the product pipeline: get the REAL product imagery onto disk.

The #1 cause of "the product looks wrong in the ad" is that no real product photo ever
reached the contact-sheet generator, so Gemini invents the package. This script makes the
download reliable + EVERGREEN (works for any brand's PDP, no pre-existing kit), and when it
can't auto-download, it scaffolds the right folders and tells the user exactly where to drop
the images by hand.

Extraction cascade (most reliable first — naive <img> crawling fails on JS-rendered PDPs):
  1. Shopify product JSON  (<product-url>.json → product.images[].src)   ← most DTC stores
  2. JSON-LD               (<script type=application/ld+json> Product.image)
  3. Open Graph / Twitter  (og:image, twitter:image)
  4. <img> src + srcset    (largest candidate, logos/icons filtered out)

Usage:
  pdp_scrape.py --url <PDP_URL> --brand <slug> [--max 12]
Folders (scaffolded if missing, under $ADGEN_HOME, default ~/adgen):
  <brand>/brand/refs/scraped/      ← auto-downloaded PDP images land here
  <brand>/brand/product-images/    ← MANUAL drop zone if auto-download fails
Exit 0 if ≥1 image landed; exit 2 (with manual instructions) if none — so the skill gate trips.
"""
from __future__ import annotations
import argparse, gzip, io, json, os, re, sys, urllib.request, urllib.parse
from pathlib import Path

ADGEN = Path(os.environ.get("ADGEN_HOME") or os.environ.get("ADGEN_ROOT") or str(Path.home() / "adgen"))
UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
ICON_HINT = re.compile(r"(logo|icon|sprite|favicon|badge|payment|trust|stamp|placeholder|loading)", re.I)


def _fetch(url: str, timeout: int = 30) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip, identity"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            data = gzip.GzipFile(fileobj=io.BytesIO(data)).read()
        return data


def _abs(base: str, u: str) -> str:
    if u.startswith("//"):
        return "https:" + u
    return urllib.parse.urljoin(base, u)


def _strip_size_params(u: str) -> str:
    # Shopify CDN: drop ?width=... &v=... to fetch the full-res master.
    return u.split("?")[0]


def from_shopify_json(url: str) -> list[str]:
    base = _strip_size_params(url).rstrip("/")
    candidates = []
    if "/products/" in base:
        candidates.append(base + ".json")                          # <url>.json
    m = re.search(r"(https?://[^/]+)/products/([^/?#]+)", url)
    if m:
        candidates.append(f"{m.group(1)}/products/{m.group(2)}.json")
    for c in dict.fromkeys(candidates):
        try:
            d = json.loads(_fetch(c))
            imgs = d.get("product", {}).get("images", []) or d.get("images", [])
            srcs = [i.get("src") for i in imgs if isinstance(i, dict) and i.get("src")]
            if srcs:
                return srcs
        except Exception:
            continue
    return []


def from_jsonld(html: str, base: str) -> list[str]:
    out = []
    for block in re.findall(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', html, re.S | re.I):
        try:
            data = json.loads(block.strip())
        except Exception:
            continue
        for node in (data if isinstance(data, list) else [data]) + (data.get("@graph", []) if isinstance(data, dict) else []):
            if not isinstance(node, dict):
                continue
            img = node.get("image")
            if isinstance(img, str):
                out.append(img)
            elif isinstance(img, list):
                out += [x.get("url") if isinstance(x, dict) else x for x in img]
            elif isinstance(img, dict) and img.get("url"):
                out.append(img["url"])
    return [_abs(base, u) for u in out if isinstance(u, str)]


def from_meta(html: str, base: str) -> list[str]:
    out = re.findall(r'<meta[^>]+(?:property|name)=["\'](?:og:image|twitter:image)(?::secure_url)?["\'][^>]+content=["\']([^"\']+)', html, re.I)
    return [_abs(base, u) for u in out]


def from_imgs(html: str, base: str) -> list[str]:
    out = []
    for tag in re.findall(r'<img[^>]+>', html, re.I):
        srcset = re.search(r'srcset=["\']([^"\']+)', tag, re.I)
        if srcset:
            cands = [s.strip().split(" ")[0] for s in srcset.group(1).split(",") if s.strip()]
            if cands:
                out.append(cands[-1])  # last = usually largest
        src = re.search(r'\ssrc=["\']([^"\']+)', tag, re.I)
        if src:
            out.append(src.group(1))
    out = [u for u in out if not u.startswith("data:") and not ICON_HINT.search(u)]
    return [_abs(base, u) for u in out]


def dedupe(urls: list[str]) -> list[str]:
    seen, out = set(), []
    for u in urls:
        k = _strip_size_params(u)
        if k not in seen:
            seen.add(k)
            out.append(u)
    return out


def download(urls: list[str], dest: Path, cap: int, trust: bool) -> list[Path]:
    saved = []
    for i, u in enumerate(urls):
        if len(saved) >= cap:
            break
        try:
            data = _fetch(_strip_size_params(u))
        except Exception as e:
            print(f"   skip (fetch failed): {u[:80]} — {e}", file=sys.stderr)
            continue
        if not trust and len(data) < 8000:   # likely an icon/sprite, unless it came from the trusted Shopify-JSON path
            continue
        ext = os.path.splitext(urllib.parse.urlparse(u).path)[1].lower()
        if ext not in (".png", ".jpg", ".jpeg", ".webp"):
            ext = ".jpg"
        name = re.sub(r"[^a-z0-9._-]", "-", os.path.basename(urllib.parse.urlparse(u).path).lower()) or f"img{i}{ext}"
        if not name.endswith(ext):
            name += ext
        p = dest / f"{i:02d}_{name}"
        p.write_bytes(data)
        saved.append(p)
    return saved


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--brand", required=True, help="brand folder slug (see CLIENTS.md)")
    ap.add_argument("--max", type=int, default=12)
    a = ap.parse_args()

    brand_root = ADGEN / a.brand / "brand"
    scraped = brand_root / "refs" / "scraped"
    manual = brand_root / "product-images"
    # SCAFFOLD the brand-global hierarchy (idempotent).
    for d in (scraped, manual, brand_root / "characters", brand_root / "reference-photos"):
        d.mkdir(parents=True, exist_ok=True)

    print(f"→ Scraping {a.url}\n→ Target: {scraped}")
    html = ""
    try:
        html = _fetch(a.url).decode("utf-8", "ignore")
    except Exception as e:
        print(f"   (page fetch failed: {e})", file=sys.stderr)

    urls, trust = from_shopify_json(a.url), True
    if urls:
        print(f"   source: Shopify product JSON ({len(urls)} images)")
    else:
        trust = False
        for label, fn in (("JSON-LD", from_jsonld), ("OpenGraph", from_meta), ("<img> tags", from_imgs)):
            urls = fn(html, a.url) if html else []
            if urls:
                print(f"   source: {label} ({len(urls)} candidates)")
                break

    saved = download(dedupe(urls), scraped, a.max, trust) if urls else []

    if saved:
        print(f"\n✅ Downloaded {len(saved)} product image(s) to {scraped}:")
        for p in saved:
            print(f"   {p.name}  ({p.stat().st_size // 1024} KB)")
        print(f"\nNext: build the product contact sheet — pass the best of these to gen_image.py via --ref.")
        sys.exit(0)

    # ── MANUAL FALLBACK — scaffold is ready, tell the user exactly where to drop images ──
    print("\n⚠️  COULD NOT auto-download product imagery (JS-rendered page / blocked / no parseable images).")
    print("    This is normal for some sites. Do NOT let the skill invent the product.")
    print(f"\n    👉 Save the real product photos (front, back, hero — ideally transparent PNG or clean studio JPG) into:")
    print(f"       {manual}")
    print(f"\n    The folder has been created for you. Drop the files there, then tell Claude:")
    print(f'       "the real product photos are in {a.brand}/brand/product-images/ — use them as --ref for the contact sheet."')
    sys.exit(2)


if __name__ == "__main__":
    main()
