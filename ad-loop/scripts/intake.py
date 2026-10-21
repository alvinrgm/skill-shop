#!/usr/bin/env python3
"""intake.py — bootstrap a complete per-client layer for the ad-loop from one brand URL.

`/ad-loop intake <url>` starts from nothing but a domain and ends with a client layer the
loop can actually run against: the full product/image index at native resolution, pack shots
and logo candidates, colour and font CANDIDATES pulled from the theme (never eyeballed),
the review corpus with persona seed material and verdict-quote candidates, claim CANDIDATES
with their verbatim source strings, the Meta Ad Library page ids, and honest [GAP] stubs for
everything a human must still supply.

THE HONESTY RULE (the whole point):
    Anything that could not be harvested is written down as a [GAP], never invented.
    A thin honest client layer beats a rich fake one. Every harvested fact carries its
    source URL so a later session can re-verify instead of trusting.

WHAT INTAKE NEVER DOES:
    - never writes an approved-claims file (claims are a legal surface; a human approves)
    - never picks a North Star (those are hand-chosen by the operator, never harvested)
    - never writes art direction, brand tensions or persona psychology
    - never overwrites an existing file (idempotent, non-destructive, always)

Usage:
    python3 intake.py --url https://brand.com --slug brand
    python3 intake.py --url https://brand.com/products/thing --slug brand --max-images 60
    python3 intake.py --url https://brand.com --slug brand --root /tmp/intake-test --dry-run
    python3 intake.py --url https://brand.com --slug brand \
        --competitor "Rival Co" --library-id "brand|<AD_ARCHIVE_ID>"

Steps (each independently skippable with --skip NAME, each reports got vs could-not-get):
    probe     site fetch + platform detection + canonical domain      [REQUIRED]
    index     full product/image index (Shopify products.json)        [REQUIRED]
    images    download pack shots + logo candidates, measure natives
    palette   theme CSS hex frequency -> candidate tokens
    fonts     @font-face + Google Fonts -> families + downloaded files
    reviews   platform detection + Stamped/Yotpo/Okendo harvest -> SUMMARY.md
    claims    PDP/label copy -> claims-CANDIDATES.md [NEEDS HUMAN APPROVAL]
    packstrings  pack-shot OCR + copy -> pack-strings.json [DRAFT, NEEDS VERIFICATION]
    adlib     Meta Ad Library page-id resolution -> adlib-pages.md
    skeleton  [GAP] stubs + INTAKE-REPORT.md

Exit 0 on success; exit 2 if a REQUIRED step failed (so a calling skill's gate trips).

Dependencies: stdlib only, plus Pillow (optional, better image metrics) and Playwright
(optional, step `adlib` only). Both absences degrade to a documented [GAP], never a crash.
"""
from __future__ import annotations

import argparse
import gzip
import io
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

# Re-run under the package's own .venv when one exists (config.py does that at import).
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import config as _pkg_config  # noqa: E402,F401

UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36")
TIMEOUT = 30
SLEEP = 0.4                      # polite, sequential
MAX_CSS_FILES = 8
MAX_CSS_BYTES = 4_000_000
MAX_LOGOS = 5
MAX_FONT_FILES = 14
STEPS = ["probe", "index", "images", "palette", "fonts",
         "reviews", "claims", "packstrings", "adlib", "skeleton"]
MAX_PACK_OCR_SHOTS = 3

# pack readability is one division. s = native_width / delivered_width;
# generated/print micro-detail stops reading at s ~= 2.9, and a plate's MAXIMUM s is its
# full-frame value. So a pack shot's native width decides its scale class before layout.
S_READABLE = 2.9
CANVAS_W = 1080

ICON_HINT = re.compile(r"(sprite|favicon|payment|trust-badge|placeholder|loading|"
                       r"spinner|arrow|chevron|star-rating)", re.I)
LOGO_HINT = re.compile(r"logo|wordmark|brandmark", re.I)
SIZE_SUFFIX = re.compile(
    r"_(?:pico|icon|thumb|small|compact|medium|large|grande|original|master|"
    r"\d{2,4}x(?:\d{2,4})?)(?=\.[a-z0-9]+$)", re.I)
HEX_RE = re.compile(r"#([0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\b")
CSS_VAR_HEX = re.compile(r"(--[a-zA-Z0-9_-]+)\s*:\s*(#[0-9a-fA-F]{3,8})\b")
TAG_RE = re.compile(r"<[^>]+>")

CERT_WORDS = re.compile(
    r"\b(organic|non-?gmo|gluten[- ]free|certified|usda|kosher|halal|vegan|"
    r"plant[- ]based|cruelty[- ]free|leaping bunny|b[- ]?corp|fair[- ]?trade|"
    r"rainforest alliance|fsc|climate neutral|carbon neutral|recyclable|"
    r"compostable|bpa[- ]free|dermatologist[- ]tested|hypoallergenic|"
    r"third[- ]party|lab[- ]tested|clinically|fda|nsf|gmp|sustainably|"
    r"regenerative|grass[- ]fed|paleo|keto|dairy[- ]free|allergen[- ]free)\b", re.I)

STOP = set("""a an the and or but if of to in on for with at by from as is are was were be been
being it its this that these those you your yours we our ours i my me they them their he she his
her not no so very just really too also than then there here what which who whom how when where
all any some more most other into over under out up down about after before again once only own
same such can will would should could have has had do does did done get got make makes made
""".split())


# ───────────────────────────────────────────────────────────────── plumbing
class Ctx:
    """Everything the run accumulates. One object, no globals."""

    def __init__(self, cfg, slug, dry_run):
        self.cfg = cfg
        self.slug = slug
        self.dry = dry_run
        self.client = cfg.client_dir(slug)
        self.brand = cfg.brand_dir(slug)
        self.personas = cfg.personas_dir(slug)
        self.report = {}          # step -> {"got": [...], "gaps": [...]}
        self.writes = []          # (path, "wrote"|"skipped (exists)"|"dry-run")
        self.sources = []         # every URL we touched
        self.domain = None
        self.base = None
        self.home_html = ""
        self.platform = "unknown"
        self.brand_name = None
        self.products = []        # raw Shopify product dicts
        self.images = []          # {"url","w","h","product","handle","trusted"}
        self.saved_images = []    # {"path","w","h","alpha","soft","bytes","url","product"}
        self.css_text = ""
        self.pdp_url = None
        self.pdp_html = ""
        self.reviews = []

    # ---- reporting
    def step(self, name):
        self.report.setdefault(name, {"got": [], "gaps": [], "skipped": False})
        return self.report[name]

    def got(self, name, msg):
        self.step(name)["got"].append(msg)
        print(f"      + {msg}")

    def gap(self, name, msg):
        self.step(name)["gaps"].append(msg)
        print(f"      [GAP] {msg}")

    # ---- non-destructive writes
    def write_text(self, path: Path, content: str) -> str:
        return self._write(path, content.encode("utf-8"))

    def write_bytes(self, path: Path, data: bytes) -> str:
        return self._write(path, data)

    def _write(self, path: Path, data: bytes) -> str:
        rel = self._rel(path)
        if path.exists():
            self.writes.append((rel, "skipped (exists)"))
            return "skipped (exists)"
        if self.dry:
            self.writes.append((rel, "dry-run (would write)"))
            return "dry-run"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        self.writes.append((rel, "wrote"))
        return "wrote"

    def mkdir(self, path: Path):
        if not self.dry:
            path.mkdir(parents=True, exist_ok=True)

    def _rel(self, path: Path) -> str:
        try:
            return str(path.relative_to(self.cfg.WORK_ROOT))
        except ValueError:
            return str(path)


_CACHE: dict[str, bytes] = {}


def fetch(url: str, timeout: int = TIMEOUT, cache: bool = True) -> bytes:
    if cache and url in _CACHE:
        return _CACHE[url]
    req = urllib.request.Request(
        url, headers={"User-Agent": UA,
                      "Accept": "*/*",
                      "Accept-Encoding": "gzip, identity"})
    try:
        resp = urllib.request.urlopen(req, timeout=timeout)
    except urllib.error.HTTPError as e:
        # Some stdlib versions don't auto-follow 308 (and some sites 308 the
        # apex to www; found by a second-store test).
        if e.code in (301, 302, 307, 308) and e.headers.get("Location"):
            loc = urllib.parse.urljoin(url, e.headers["Location"])
            req = urllib.request.Request(
                loc, headers={"User-Agent": UA,
                              "Accept": "*/*",
                              "Accept-Encoding": "gzip, identity"})
            resp = urllib.request.urlopen(req, timeout=timeout)
        else:
            raise
    with resp as r:
        data = r.read()
        if r.headers.get("Content-Encoding") == "gzip":
            data = gzip.GzipFile(fileobj=io.BytesIO(data)).read()
    if cache:
        _CACHE[url] = data
    time.sleep(SLEEP)
    return data


def fetch_text(url: str, **kw) -> str:
    return fetch(url, **kw).decode("utf-8", "ignore")


def absolutise(base: str, u: str) -> str:
    if u.startswith("//"):
        return "https:" + u
    return urllib.parse.urljoin(base, u)


def strip_query(u: str) -> str:
    """Shopify CDN: ?v=... and ?width=... are cache/resize params, not the master."""
    return u.split("?")[0]


def master_url(u: str, trusted: bool) -> str:
    """Full-resolution master.

    `trusted` = came from products.json, whose `src` values are already originals
    (verified on a live Shopify store). For untrusted paths, also strip the
    `_NNNx`/`_grande` style downsample suffixes the storefront injects into the PATH.
    """
    u = strip_query(u)
    return u if trusted else SIZE_SUFFIX.sub("", u)


def html_text(fragment: str) -> str:
    t = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", fragment, flags=re.S | re.I)
    t = TAG_RE.sub(" ", t)
    t = (t.replace("&amp;", "&").replace("&nbsp;", " ").replace("&#39;", "'")
          .replace("&quot;", '"').replace("&lt;", "<").replace("&gt;", ">")
          .replace("&rsquo;", "'").replace("&ldquo;", '"').replace("&rdquo;", '"'))
    t = re.sub(r"&[a-zA-Z#0-9]+;", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def safe_name(u: str, fallback: str) -> str:
    base = os.path.basename(urllib.parse.urlparse(u).path)
    name = re.sub(r"[^A-Za-z0-9._-]", "-", base).strip("-") or fallback
    return name[:110]


# ───────────────────────────────────────────────────── image metrics
def _png_info(d: bytes):
    if len(d) < 33 or d[:8] != b"\x89PNG\r\n\x1a\n":
        return None
    w = int.from_bytes(d[16:20], "big")
    h = int.from_bytes(d[20:24], "big")
    colortype = d[25]
    alpha = colortype in (4, 6) or b"tRNS" in d[:8192]
    return w, h, alpha


def _jpeg_info(d: bytes):
    if d[:2] != b"\xff\xd8":
        return None
    i = 2
    while i + 9 < len(d):
        if d[i] != 0xFF:
            i += 1
            continue
        marker = d[i + 1]
        if marker in (0xD8, 0xD9) or 0xD0 <= marker <= 0xD7:
            i += 2
            continue
        seglen = int.from_bytes(d[i + 2:i + 4], "big")
        if marker in (0xC0, 0xC1, 0xC2, 0xC3, 0xC5, 0xC6, 0xC7,
                      0xC9, 0xCA, 0xCB, 0xCD, 0xCE, 0xCF):
            h = int.from_bytes(d[i + 5:i + 7], "big")
            w = int.from_bytes(d[i + 7:i + 9], "big")
            return w, h, False
        i += 2 + seglen
    return None


def _webp_info(d: bytes):
    if len(d) < 30 or d[:4] != b"RIFF" or d[8:12] != b"WEBP":
        return None
    chunk = d[12:16]
    if chunk == b"VP8X":
        alpha = bool(d[20] & 0x10)
        w = 1 + int.from_bytes(d[24:27], "little")
        h = 1 + int.from_bytes(d[27:30], "little")
        return w, h, alpha
    if chunk == b"VP8L":
        b = int.from_bytes(d[21:25], "little")
        w = (b & 0x3FFF) + 1
        h = ((b >> 14) & 0x3FFF) + 1
        alpha = bool((b >> 28) & 1)
        return w, h, alpha
    if chunk == b"VP8 ":
        w = int.from_bytes(d[26:28], "little") & 0x3FFF
        h = int.from_bytes(d[28:30], "little") & 0x3FFF
        return w, h, False
    return None


def image_info(data: bytes):
    """-> (width, height, has_alpha, soft_edge_fraction_or_None).

    Pillow when available (handles every format and can actually LOOK at the alpha
    channel); stdlib header parsing otherwise. `soft` = fraction of pixels with
    0 < alpha < 255 — a soft matte vs a hard lasso cut is a real signal about how the
    pack shot was cut, and a hard cut is what makes composites read as pasted.
    """
    try:
        from PIL import Image
        im = Image.open(io.BytesIO(data))
        w, h = im.size
        alpha = im.mode in ("RGBA", "LA", "PA") or "transparency" in im.info
        soft = None
        if alpha:
            a = im.convert("RGBA").getchannel("A")
            a.thumbnail((256, 256))
            hist = a.histogram()
            total = sum(hist) or 1
            soft = sum(hist[1:255]) / total
        return w, h, alpha, soft
    except Exception:
        pass
    for fn in (_png_info, _jpeg_info, _webp_info):
        try:
            r = fn(data)
        except Exception:
            r = None
        if r:
            return r[0], r[1], r[2], None
    return None, None, None, None


# ───────────────────────────────────────────────────────── step 1: probe
def step_probe(ctx: Ctx, url: str) -> bool:
    print("\n[1/10] site probe")
    p = urllib.parse.urlparse(url if "://" in url else "https://" + url)
    ctx.domain = p.netloc
    ctx.base = f"{p.scheme}://{p.netloc}"
    if "/products/" in p.path:
        ctx.pdp_url = f"{ctx.base}{p.path}"
        ctx.got("probe", f"input URL is a PDP: {ctx.pdp_url}")

    try:
        ctx.home_html = fetch_text(ctx.base + "/")
        ctx.sources.append(ctx.base + "/")
        ctx.got("probe", f"homepage fetched ({len(ctx.home_html):,} bytes of HTML)")
    except Exception as e:
        ctx.gap("probe", f"homepage fetch FAILED for {ctx.base}/ — {e}")
        return False

    canon = re.search(r'<link[^>]+rel=["\']canonical["\'][^>]+href=["\']([^"\']+)',
                      ctx.home_html, re.I)
    og_url = re.search(r'<meta[^>]+property=["\']og:url["\'][^>]+content=["\']([^"\']+)',
                       ctx.home_html, re.I)
    canonical = (canon or og_url).group(1) if (canon or og_url) else ctx.base + "/"
    ctx.got("probe", f"canonical domain: {urllib.parse.urlparse(canonical).netloc or ctx.domain}")

    for pat, label in ((r'<meta[^>]+property=["\']og:site_name["\'][^>]+content=["\']([^"\']+)',
                        "og:site_name"),
                       (r"<title[^>]*>([^<]{2,80})</title>", "<title>")):
        m = re.search(pat, ctx.home_html, re.I | re.S)
        if m:
            ctx.brand_name = html_text(m.group(1)).split("|")[0].split("–")[0].strip()
            ctx.got("probe", f"brand name from {label}: {ctx.brand_name!r}")
            break
    if not ctx.brand_name:
        ctx.brand_name = ctx.slug
        ctx.gap("probe", "no brand name in og:site_name/<title> — using the slug")

    shopify_markers = []
    if re.search(r"Shopify\.shop|cdn/shop/|myshopify\.com|shopify-features", ctx.home_html):
        shopify_markers.append("HTML markers (Shopify.shop / cdn/shop/ / myshopify)")
    try:
        d = json.loads(fetch_text(ctx.base + "/products.json?limit=1"))
        if "products" in d:
            shopify_markers.append("/products.json responds")
    except Exception:
        pass
    if shopify_markers:
        ctx.platform = "shopify"
        ctx.got("probe", "platform: SHOPIFY — " + "; ".join(shopify_markers))
    else:
        for name, pat in (("woocommerce", r"woocommerce|wp-content/plugins/woo"),
                          ("bigcommerce", r"bigcommerce\.com|stencil-utils"),
                          ("squarespace", r"squarespace\.com|Static\.SQUARESPACE"),
                          ("wix", r"wixstatic\.com|X-Wix"),
                          ("webflow", r"webflow\.com|w-webflow")):
            if re.search(pat, ctx.home_html, re.I):
                ctx.platform = name
                break
        ctx.gap("probe", f"platform is not Shopify (detected: {ctx.platform}) — "
                         "the complete-catalogue index is unavailable; falling back to "
                         "pdp_scrape.py's per-page cascade")
    return True


# ───────────────────────────────────────────────── step 2: product/image index
def step_index(ctx: Ctx) -> bool:
    print("\n[2/10] product + image index")
    if not ctx.base:
        ctx.gap("index", "the site probe was skipped, so there is no domain to index — "
                         "the index step cannot run without it")
        return False
    if ctx.platform == "shopify":
        page = 1
        while page <= 8:
            u = f"{ctx.base}/products.json?limit=250&page={page}"
            try:
                batch = json.loads(fetch_text(u)).get("products", [])
            except Exception as e:
                ctx.gap("index", f"products.json page {page} failed — {e}")
                break
            ctx.sources.append(u)
            if not batch:
                break
            ctx.products += batch
            if len(batch) < 250:
                break
            page += 1
        if ctx.products:
            for prod in ctx.products:
                for im in prod.get("images", []) or []:
                    if not im.get("src"):
                        continue
                    ctx.images.append({
                        "url": im["src"],
                        "w": im.get("width"), "h": im.get("height"),
                        "product": prod.get("title") or prod.get("handle"),
                        "handle": prod.get("handle"),
                        "type": prod.get("product_type") or "",
                        "position": im.get("position"),
                        "trusted": True,
                    })
            ctx.got("index", f"products.json: {len(ctx.products)} products, "
                             f"{len(ctx.images)} images (COMPLETE catalogue index — "
                             "the fastest complete image index there is)")
            if not ctx.pdp_url and ctx.products:
                ctx.pdp_url = f"{ctx.base}/products/{ctx.products[0].get('handle')}"
                ctx.got("index", f"PDP for copy/review probing: {ctx.pdp_url}")
            return True
        ctx.gap("index", "products.json returned no products")

    # ---- non-Shopify / empty catalogue: compose with pdp_scrape.py's cascade
    ps = _load_pdp_scrape(ctx)
    target = ctx.pdp_url or (ctx.base + "/")
    urls, src = [], "pdp_scrape"
    if ps:
        try:
            urls = ps.from_shopify_json(target)
            src = "pdp_scrape: Shopify product JSON"
            if not urls:
                html = ctx.home_html if target.endswith("/") else fetch_text(target)
                for label, fn in (("JSON-LD", ps.from_jsonld),
                                  ("OpenGraph", ps.from_meta),
                                  ("<img> src/srcset", ps.from_imgs)):
                    urls = fn(html, target)
                    if urls:
                        src = f"pdp_scrape: {label}"
                        break
            urls = ps.dedupe(urls)
        except Exception as e:
            ctx.gap("index", f"pdp_scrape cascade errored — {e}")
    else:
        ctx.gap("index", f"could not import pdp_scrape.py at {ctx.cfg.PDP_SCRAPE}")

    if urls:
        ctx.got("index", f"{src} — {len(urls)} image candidates from {target}")
        for u in urls:
            ctx.images.append({"url": u, "w": None, "h": None,
                               "product": None, "handle": None, "type": "",
                               "position": None, "trusted": False})
        ctx.gap("index", "this is a PER-PAGE cascade, NOT a complete catalogue — "
                         "run intake again per PDP, or drop images by hand into "
                         "brand/product-images/")
        return True

    ctx.gap("index", "NO product images could be indexed by any method. "
                     "Drop real pack shots into brand/product-images/ by hand — "
                     "do not let any downstream step invent the package.")
    return False


def _load_pdp_scrape(ctx: Ctx):
    """Import the EXISTING extraction cascade rather than forking its logic."""
    try:
        import importlib.util
        spec = importlib.util.spec_from_file_location("pdp_scrape", ctx.cfg.PDP_SCRAPE)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod
    except Exception:
        return None


# ───────────────────────────────────────────── step 3: pack shots + logos
def step_images(ctx: Ctx, cap: int):
    print("\n[3/10] pack shots + logos")
    dest = ctx.brand / "product-images"
    ctx.mkdir(dest)

    seen, ordered = set(), []
    for im in ctx.images:
        k = master_url(im["url"], im["trusted"])
        if k in seen:
            continue
        seen.add(k)
        ordered.append(im)
    # Position-1 images are the pack shot on almost every storefront; take them first.
    ordered.sort(key=lambda i: (i.get("position") or 99, i.get("handle") or ""))

    for i, im in enumerate(ordered):
        if len(ctx.saved_images) >= cap:
            break
        u = master_url(im["url"], im["trusted"])
        if ICON_HINT.search(u):
            continue
        try:
            data = fetch(u, cache=False)
        except Exception as e:
            ctx.gap("images", f"download failed: {u[:90]} — {e}")
            continue
        if len(data) < 6000 and not im["trusted"]:
            continue
        w, h, alpha, soft = image_info(data)
        name = f"{len(ctx.saved_images):02d}_{safe_name(u, f'image{i}.jpg')}"
        status = ctx.write_bytes(dest / name, data)
        rec = {"name": name, "w": w, "h": h, "alpha": alpha, "soft": soft,
               "bytes": len(data), "url": u, "product": im["product"],
               "declared": (im["w"], im["h"]), "status": status}
        ctx.saved_images.append(rec)
        if im["w"] and w and im["w"] != w:
            ctx.gap("images", f"{name}: products.json declared {im['w']}x{im['h']} but the "
                              f"file is {w}x{h} — a downsample was served, not the master")

    if ctx.saved_images:
        widths = [r["w"] for r in ctx.saved_images if r["w"]]
        ctx.got("images", f"{len(ctx.saved_images)} product images saved to "
                          f"{ctx._rel(dest)}"
                          + (f" (native widths {min(widths)}-{max(widths)} px)" if widths else ""))
        n_alpha = sum(1 for r in ctx.saved_images if r["alpha"])
        ctx.got("images", f"{n_alpha} of them carry an alpha channel "
                          "(transparent cut-outs — check the soft-edge column before compositing)")
        ctx.write_text(dest / "INDEX.md", _images_index_md(ctx))
    else:
        ctx.gap("images", "zero product images landed — brand/product-images/ is the "
                          "manual drop zone; the loop must not run without real pack shots")

    _logos(ctx)


def _images_index_md(ctx: Ctx) -> str:
    rows = []
    for r in ctx.saved_images:
        w, h = r["w"], r["h"]
        px = f"{w}x{h}" if w else "?"
        alpha = ("no" if r["alpha"] is False else
                 "unknown" if r["alpha"] is None else
                 ("yes, SOFT matte" if (r["soft"] or 0) > 0.02 else "yes, HARD cut"))
        cap = f"{int(w / S_READABLE)}" if w else "?"
        cover = f"{(w / S_READABLE) / CANVAS_W * 100:.0f}%" if w else "?"
        rows.append(f"| `{r['name']}` | {px} | {alpha} | {r['bytes'] // 1024} KB | "
                    f"{cap} px | {cover} | {r['product'] or '[GAP] unknown'} | {r['url']} |")
    return f"""# {ctx.brand_name} — product image index

Harvested by `ad-loop/scripts/intake.py` on {datetime.now():%Y-%m-%d}. Every row's source URL
is recorded so any later session can re-fetch instead of trusting this file.

## why the pixel columns are load-bearing

**Native resolution decides the ad before layout does.** With `s` = the pack's delivery
downsample against this native file, every quantity that matters is `k/s`, and a
plate's MAXIMUM `s` is its full-frame value — cropping only ever lowers it.
Micro-print stops reading at `s ≈ {S_READABLE}`, and downsampling real detail past legibility reads
as AI garble to a judge — the perception IS the verdict, so authenticity is not
inherited from the source file, it is re-earned at render scale.

- **`s={S_READABLE} cap`** = the widest this pack can be delivered while its on-pack print still reads.
- **`cover @1080`** = that cap as a share of a 1080-wide canvas. Law 2 wants 40-70% product
  coverage; anything well under that has a scale ceiling, and the honest move is to name the
  ceiling and carry product form by explicit naming — not to shrink the concept until it fits.

**Alpha column:** a soft matte and a hard lasso cut are different assets. A hard cut composited
onto a photographic ground is detected by physics, not edges — row-constant
gradients, uniform-density shadow blur, zero light exchange with the ground.

| file | native px | alpha | size | `s={S_READABLE}` cap | cover @1080 | product line | source URL |
|---|---|---|---|---|---|---|---|
{chr(10).join(rows) if rows else "| [GAP] no images landed | | | | | | | |"}

## [GAP] what a human still has to do here

- **Identify the true hero pack shot** — position-1 on the storefront is a guess, not a decision.
- **Verify what each file actually contains. Filenames lie** (a run of files named
  `...lifestyle_N` can show a different product from the one they are attached to).
- **Probe for unreferenced frames.** Storefront CDNs keep serving shoot frames that no
  product references — enumerate `-01..-12` style sequences on any promising filename. This
  can surface extra frames, sometimes including the best asset available.
- **Note which shots are real photography vs renders.** Provenance of publication is not a
  forensic guarantee; write down what you know and how you know it.
"""


def _logos(ctx: Ctx):
    html = ctx.home_html
    cands = []
    m = re.search(r"<header\b.*?</header>", html, re.S | re.I)
    head_block = m.group(0) if m else html[:40000]
    for tag in re.findall(r"<img[^>]+>", head_block, re.I):
        if not LOGO_HINT.search(tag):
            continue
        src = re.search(r'\ssrc=["\']([^"\']+)', tag, re.I)
        srcset = re.search(r'srcset=["\']([^"\']+)', tag, re.I)
        if srcset:
            parts = [s.strip().split(" ")[0] for s in srcset.group(1).split(",") if s.strip()]
            if parts:
                cands.append(parts[-1])
        if src:
            cands.append(src.group(1))
    for pat in (r'<meta[^>]+property=["\']og:logo["\'][^>]+content=["\']([^"\']+)',
                r'"logo"\s*:\s*"([^"]+)"',
                r'"logo"\s*:\s*\{[^}]*"url"\s*:\s*"([^"]+)"'):
        cands += re.findall(pat, html, re.I)
    for tag in re.findall(r"<svg\b[^>]*class=[\"'][^\"']*logo[^\"']*[\"']", html, re.I):
        ctx.gap("images", "the header logo is INLINE SVG — not downloadable as a file; "
                          "export it from the brand book or the site by hand")
        break

    seen, saved = set(), 0
    for u in cands:
        if saved >= MAX_LOGOS:
            break
        u = absolutise(ctx.base + "/", u)
        k = strip_query(u)
        if k in seen or k.endswith(".svg"):
            if k.endswith(".svg") and k not in seen:
                seen.add(k)
                ctx.got("images", f"logo is SVG (vector, best case): {u}")
            continue
        seen.add(k)
        try:
            data = fetch(master_url(u, False), cache=False)
        except Exception:
            continue
        w, h, alpha, soft = image_info(data)
        name = f"logo-candidate-{saved:02d}_{safe_name(u, 'logo.png')}"
        ctx.write_bytes(ctx.brand / name, data)
        ctx.got("images", f"logo candidate: {name} ({w}x{h}, alpha={alpha})")
        saved += 1
    if not saved and not seen:
        ctx.gap("images", "no logo file found in the header markup / og:logo / JSON-LD — "
                          "get the vector mark from the client's brand book")


# ────────────────────────────────────────────────────── theme CSS (4 + 5)
def _theme_css(ctx: Ctx) -> str:
    if ctx.css_text:
        return ctx.css_text
    chunks = re.findall(r"<style[^>]*>(.*?)</style>", ctx.home_html, re.S | re.I)
    hrefs = re.findall(r'<link[^>]+rel=["\']stylesheet["\'][^>]*>', ctx.home_html, re.I)
    hrefs += re.findall(r'<link[^>]+as=["\']style["\'][^>]*>', ctx.home_html, re.I)
    urls, seen = [], set()
    for tag in hrefs:
        h = re.search(r'href=["\']([^"\']+)', tag, re.I)
        if not h:
            continue
        u = absolutise(ctx.base + "/", h.group(1))
        if u in seen:
            continue
        seen.add(u)
        urls.append(u)
    for u in urls[:MAX_CSS_FILES]:
        try:
            t = fetch_text(u)
            if len(t) > MAX_CSS_BYTES:
                t = t[:MAX_CSS_BYTES]
            chunks.append(t)
            ctx.sources.append(u)
            ctx._css_urls = getattr(ctx, "_css_urls", []) + [u]
        except Exception:
            continue
    ctx.css_text = "\n".join(chunks)
    return ctx.css_text


def step_palette(ctx: Ctx):
    print("\n[4/10] palette (counted, never eyeballed)")
    css = _theme_css(ctx)
    if not css:
        ctx.gap("palette", "no theme CSS could be read — palette unresolved")
        return
    ctx.got("palette", f"{len(getattr(ctx, '_css_urls', []))} stylesheet(s) + inline "
                       f"<style> read ({len(css):,} chars)")

    counts = Counter()
    for h in HEX_RE.findall(css):
        h = h.lower()
        if len(h) == 3:
            h = "".join(c * 2 for c in h)
        if len(h) == 8:
            h = h[:6]
        counts[f"#{h}"] += 1
    named_vars = defaultdict(set)
    for var, hexv in CSS_VAR_HEX.findall(css):
        v = hexv.lower()
        if len(v) == 4:
            v = "#" + "".join(c * 2 for c in v[1:])
        named_vars[v[:7]].add(var)
    if not counts:
        ctx.gap("palette", "the theme CSS carries no literal hex values (variables may be "
                           "computed at runtime) — read the tokens from the brand book instead")
        return
    ctx.got("palette", f"{len(counts)} distinct hex values counted; "
                       f"{len(named_vars)} of them are named CSS custom properties")

    rows = []
    for hexv, n in counts.most_common(24):
        names = ", ".join(sorted(named_vars.get(hexv, ()))[:4]) or "—"
        rows.append(f"| `{hexv}` | {n} | {names} |")
    ctx.write_text(ctx.brand / "palette-CANDIDATES.md", f"""# {ctx.brand_name} — palette CANDIDATES

Counted, not eyeballed. Every value below is a literal hex found in the live theme CSS on
{datetime.now():%Y-%m-%d}; the count column is why it is here. **Nothing here is an approved
brand token** — frequency finds the theme's working colours, not the brand's intent (a hex used
600 times is often a UI grey, and the brand's actual accent can appear twice).

Sources read:
{chr(10).join('- ' + u for u in getattr(ctx, '_css_urls', [])) or '- inline <style> only'}

| hex | occurrences | CSS custom property |
|---|---|---|
{chr(10).join(rows)}

## [GAP] a human must still

- **Pick the token set** — ink, ground, accent, and the one colour that is never used. Rank by
  role, not by frequency.
- **Reconcile against the brand book** (PDF/print tokens usually differ from the web theme).
- **Name the forbidden colours.** What the brand must never look like is as load-bearing as
  what it is, and it is not derivable from CSS.
""")


def step_fonts(ctx: Ctx):
    print("\n[5/10] fonts")
    css = _theme_css(ctx)
    dest = ctx.brand / "fonts"
    faces = []
    for block in re.findall(r"@font-face\s*\{([^}]*)\}", css, re.I):
        fam = re.search(r"font-family\s*:\s*['\"]?([^;'\"]+)", block, re.I)
        wt = re.search(r"font-weight\s*:\s*([^;]+)", block, re.I)
        st = re.search(r"font-style\s*:\s*([^;]+)", block, re.I)
        srcs = re.findall(r"url\(\s*['\"]?([^)'\"]+)", block, re.I)
        faces.append({"family": (fam.group(1).strip() if fam else "[GAP] unnamed"),
                      "weight": (wt.group(1).strip() if wt else "normal"),
                      "style": (st.group(1).strip() if st else "normal"),
                      "srcs": srcs})
    gfonts = []
    for u in re.findall(r'https://fonts\.googleapis\.com/css2?\?[^"\'\s>]+', ctx.home_html):
        gfonts += [urllib.parse.unquote(f).split(":")[0].replace("+", " ")
                   for f in re.findall(r"family=([^&]+)", u)]
    gfonts = sorted(set(gfonts))

    if not faces and not gfonts:
        ctx.gap("fonts", "no @font-face or Google Fonts link found — the theme may load fonts "
                         "from JS or a system stack; read the typeface off the brand book")
        return
    if faces:
        ctx.got("fonts", f"{len(faces)} @font-face rules, "
                         f"{len({f['family'] for f in faces})} families")
    if gfonts:
        ctx.got("fonts", f"Google Fonts: {', '.join(gfonts)}")

    downloaded = []
    for f in faces:
        for s in f["srcs"]:
            if len(downloaded) >= MAX_FONT_FILES:
                break
            if not re.search(r"\.(woff2?|ttf|otf)(\?|$)", s, re.I):
                continue
            u = absolutise(ctx.base + "/", s)
            try:
                data = fetch(strip_query(u), cache=False)
            except Exception as e:
                ctx.gap("fonts", f"font download blocked: {u[:90]} — {e}")
                continue
            name = safe_name(u, "font.woff2")
            ctx.write_bytes(dest / name, data)
            downloaded.append((name, f["family"], f["weight"], f["style"], u))
    if downloaded:
        ctx.got("fonts", f"{len(downloaded)} font file(s) "
                         f"{'would be written into' if ctx.dry else 'into'} {ctx._rel(dest)}")
    else:
        ctx.gap("fonts", "no font FILES downloaded (CDN blocked or none referenced) — "
                         "families are named below but the binaries must be licensed/obtained")

    rows = [f"| `{n}` | {fam} | {w} | {st} | {u} |" for n, fam, w, st, u in downloaded]
    ctx.write_text(dest / "INDEX.md", f"""# {ctx.brand_name} — fonts

Harvested from the live theme on {datetime.now():%Y-%m-%d}.

## families referenced by the theme
{chr(10).join(f"- **{f['family']}** — weight {f['weight']}, style {f['style']}" for f in faces) or "- [GAP] none found in @font-face"}

## Google Fonts links on the homepage
{chr(10).join(f"- {g}" for g in gfonts) or "- none"}

## files downloaded here
| file | family | weight | style | source URL |
|---|---|---|---|---|
{chr(10).join(rows) if rows else "| [GAP] none downloaded | | | | |"}

## [GAP] LICENSING — read before anything renders

A webfont served to a browser is **not** a licence to render paid advertising. Confirm the
client's licence covers ad creative, or substitute a licensed face, before a single ad ships.
The theme's webfont is also frequently NOT the brand's display face — check the brand book.
""")


# ─────────────────────────────────────────────────────── step 6: reviews
# ── platform detection ───────────────────────────────────────────────────────
# TWO-TIER DETECTION. A bare substring match is not evidence: a modern
# Shopify theme ships one analytics snippet that NAMES every review platform it can
# integrate with, all set to null —
#     var MetafieldYotpoRating = null; var MetafieldLooxRating = null;
#     var okendoProduct = null;
# — so a substring scan reports three platforms on a store running none of them.
# (A vendor name can appear many times in a PDP and every occurrence be that
# boilerplate. "Detected" is then a false positive, and a false positive here sends
# a human hunting for a key that was never there.)
#
# STRONG = a request actually goes to that vendor, or its widget element exists.
# WEAK   = the name merely appears. Weak-only is reported as "named in the page
#          source, no live signal" and never as detected.
REVIEW_PLATFORMS = [
    ("stamped",
     r"stamped\.io|stamped-widget|data-widget-type=[\"']\w*stamped",       # strong
     r"stamped",                                                          # weak
     [r"(pubkey-[A-Za-z0-9]{16,})"],
     "IMPLEMENTED"),
    ("yotpo",
     r"staticw2\.yotpo\.com|api(?:-cdn)?\.yotpo\.com|cdn-widgetsrepository\.yotpo\.com"
     r"|yotpo-widget-instance|data-yotpo-instance-id|class=[\"'][^\"']*\byotpo\b",
     r"yotpo",
     [r"staticw2\.yotpo\.com/([A-Za-z0-9_-]{20,})",
      r"(?:appkey|app_key|appKey|yotpo-app-key|yotpoAppKey)[\"'\s:=]+([A-Za-z0-9_-]{20,})",
      r"yotpo\.com/v\d/widget/([A-Za-z0-9_-]{20,})"],
     "IMPLEMENTED"),
    ("okendo",
     r"okendo\.io|okendo-reviews|<oke-|oke-w-|data-oke-[a-z-]+|okeReviews",
     r"okendo|oke-",
     [r"data-oke-store-id=[\"']([0-9a-fA-F-]{36})",
      r"(?:subscriberId|okeSubscriberId|okendoSubscriberId)[\"'\s:=]+[\"']?([0-9a-fA-F-]{36})",
      r"api\.okendo\.io/v\d/stores/([0-9a-fA-F-]{36})"],
     "IMPLEMENTED"),
    ("judgeme",
     r"judge\.me/|jdgm-widget|jdgm-rev|data-shop-token",
     r"judge\.?me",
     [r"(?:shop_token|data-shop-token)[\"'\s:=]+([A-Za-z0-9_-]{10,})"],
     "detected only"),
    ("loox",
     r"loox\.io|loox-reviews|data-loox|looxReviews",
     r"loox",
     [r"loox[_-]?shop[\"'\s:=]+([A-Za-z0-9_.-]{6,})"],
     "detected only"),
]

# ── endpoint constants ───────────────────────────────────────────────────────
# All three paths below were LIVE-VERIFIED in a prior run against real public stores.
# GET only, no
# auth header, no token. Everything is still read DEFENSIVELY — these are public
# widget endpoints with no contract to us, and a vendor reshaping an envelope must
# degrade to a named [GAP], never to a crash.
YOTPO_REVIEWS = ("https://api-cdn.yotpo.com/v1/widget/{key}/products/{pid}"
                 "/reviews.json?per_page={per}&page={page}")
YOTPO_SITE_PID = "yotpo_site_reviews"   # a real path, but it returns only STORE
                                        # reviews — not every product's reviews
YOTPO_PER_PAGE = 150                    # hard cap; asking for more is silently clamped
MAX_YOTPO_PRODUCTS = 25                 # Yotpo has NO public all-products endpoint
                                        # (/v1/apps/{key}/reviews is 401 admin-only),
                                        # so coverage is a per-product fan-out and
                                        # has to be bounded. Raise with --yotpo-products.

OKENDO_REVIEWS = ("https://api.okendo.io/v1/stores/{key}/reviews"
                  "?limit={per}&orderBy=date%20desc")
OKENDO_BASE = "https://api.okendo.io/v1"   # `nextUrl` comes back as a PATH
OKENDO_PER_PAGE = 100                      # observed ceiling (docs say 25 — stale)

# Field aliases per platform, mapped onto the STAMPED record schema that
# `_reviews_summary_md` and `loop-engine/claims.py` already consume. Normalising
# into the existing schema is deliberate: a second schema would fork every
# downstream consumer.
REVIEW_FIELD_ALIASES = {
    "id": ["id", "reviewId", "review_id", "_id"],
    "reviewMessage": ["reviewMessage", "content", "body", "review_body", "text"],
    "reviewTitle": ["reviewTitle", "title", "heading"],
    "reviewRating": ["reviewRating", "score", "rating", "stars"],
    "reviewDate": ["reviewDate", "created_at", "createdAt", "dateCreated", "date"],
    "author": ["author", "reviewAuthor", "display_name", "displayName", "name",
               "reviewer_name"],
    "reviewVerifiedType": ["reviewVerifiedType", "verified_buyer", "verifiedBuyer",
                           "isVerified", "verified"],
    # NB: no bare "name" alias. A hoisted `user`/`reviewer` object often carries one,
    # and filing a reviewer's name as the PRODUCT LINE breaks the verification rule
    # that testimonial selection depends on.
    "productName": ["productName", "product_title", "productTitle", "product_name"],
    "productSKU": ["productSKU", "sku", "product_sku"],
}
# where a nested object may carry the author / product
NESTED_HOLDERS = ["user", "reviewer", "customer", "author", "product", "productDetails"]


def _flatten_review(o: dict) -> dict:
    """One level of nesting hoisted, so alias lookup finds `user.display_name`."""
    flat = dict(o)
    for h in NESTED_HOLDERS:
        v = o.get(h)
        if isinstance(v, dict):
            for k, vv in v.items():
                flat.setdefault(k, vv)
    return flat


def _norm_review(o: dict, platform: str) -> dict:
    """Map ONE raw record onto the Stamped schema. The raw record is saved verbatim
    beside this — this is a view, never a replacement for the evidence."""
    flat = _flatten_review(o)
    out = {"_platform": platform}
    for canon, aliases in REVIEW_FIELD_ALIASES.items():
        for a in aliases:
            if flat.get(a) not in (None, "", []):
                out[canon] = flat[a]
                break
    r = out.get("reviewRating")
    if isinstance(r, str) and r.replace(".", "", 1).isdigit():
        out["reviewRating"] = int(float(r))
    v = out.get("reviewVerifiedType")
    if isinstance(v, bool):
        out["reviewVerifiedType"] = 2 if v else 0
    return out


def _looks_like_review(o) -> bool:
    if not isinstance(o, dict):
        return False
    flat = _flatten_review(o)
    has_text = any(isinstance(flat.get(k), str) and len(flat[k]) > 2
                   for k in ("reviewMessage", "content", "body", "review_body", "text"))
    has_rating = any(k in flat for k in ("reviewRating", "score", "rating", "stars"))
    return has_text and has_rating


def _walk_generic(obj) -> list:
    """Find review-shaped dicts ANYWHERE in an unknown envelope. Same principle as
    `_walk_reviews`, without assuming Stamped's field names — which is what lets a
    vendor reshape its response without breaking the harvest."""
    out = []

    def walk(o):
        if isinstance(o, dict):
            if _looks_like_review(o):
                out.append(o)
                return
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(obj)
    return out


def _get_json(ctx: Ctx, platform: str, url: str, label: str):
    """(parsed, raw_bytes) or (None, None) with a named [GAP]. Never raises."""
    try:
        raw = fetch(url, cache=False)
    except Exception as e:
        ctx.gap("reviews", f"{platform}: {label} request failed — {e}")
        return None, None
    try:
        return json.loads(raw.decode("utf-8", "ignore")), raw
    except Exception as e:
        ctx.gap("reviews", f"{platform}: {label} did not parse as JSON — {e}")
        return None, None


def _harvest_yotpo(ctx: Ctx, key: str, pages: int, max_products: int) -> list:
    """Yotpo public widget API v1. Live-verified in a prior run.

    Yotpo has NO public all-reviews endpoint — `/v1/apps/{key}/reviews` is the
    authenticated admin API and returns 401. `yotpo_site_reviews` is a real path but
    holds only STORE-level reviews (a virtual product), not every product's. So full
    coverage is a bounded per-product fan-out over the Shopify ids we already
    indexed, and the bound is stated in the report rather than pretended away.
    """
    dest = ctx.brand / "reviews"
    pids = [str(p.get("id")) for p in ctx.products if p.get("id")][:max_products]
    targets = [(YOTPO_SITE_PID,
                "[store-level review — NOT filed against a product line]")]
    targets += [(pid, None) for pid in pids]
    if len(ctx.products) > len(pids):
        ctx.gap("reviews", f"yotpo: fanned out over {len(pids)} of {len(ctx.products)} "
                           "products (no public all-reviews endpoint exists). Reviews on "
                           "the remaining products are NOT in this corpus — raise "
                           "--yotpo-products or export from the client's Yotpo account.")

    recs, saved = [], 0
    for pid, note in targets:
        for p in range(1, pages + 1):
            url = YOTPO_REVIEWS.format(key=key, pid=pid, per=YOTPO_PER_PAGE, page=p)
            data, raw = _get_json(ctx, "yotpo", url, f"product {pid} page {p}")
            if data is None:
                break
            batch = _walk_generic(data)
            if not batch:
                break
            # The review object carries no product NAME — it lives in the envelope's
            # `response.products[]`. Join it here or every record files against
            # "[GAP] unnamed", which breaks the product-line verification rule
            # the summary depends on.
            pname = None
            try:
                prods = (data.get("response") or {}).get("products") or []
                pname = (prods[0] or {}).get("name")
            except Exception:
                pass
            ctx.write_bytes(dest / f"raw-yotpo-{pid}-p{p}.json", raw)
            ctx.sources.append(url)
            saved += 1
            for o in batch:
                n = _norm_review(o, "yotpo")
                if not n.get("productName"):
                    # `note` wins on the site-reviews target: its envelope name is a
                    # virtual product ("PROD - https://<store>/") and filing a
                    # store-level review under it would read as a product line.
                    n["productName"] = note or pname or ""
                if not n["productName"]:
                    n.pop("productName")
                recs.append(n)
            if len(batch) < YOTPO_PER_PAGE:
                break
    if recs:
        ctx.got("reviews", f"yotpo: {len(recs)} review records over {saved} page(s) "
                           f"across {len(targets)} product target(s)")
    else:
        ctx.gap("reviews", f"yotpo: NO records harvested with key `{key}`. A wrong key "
                           "returns 404 here, not 401 — and the loader GUID at "
                           "cdn-widgetsrepository.yotpo.com is a DIFFERENT id that always "
                           "404s against this API. Confirm the key from the "
                           "staticw2.yotpo.com/<key>/widget.js script src.")
    return recs


def _harvest_okendo(ctx: Ctx, key: str, pages: int) -> list:
    """Okendo storefront API. Live-verified in a prior run.

    Store-wide and cursor-paginated: one endpoint returns reviews across every
    product, and `nextUrl` comes back as a PATH that must be joined onto the API
    base. An unknown store id returns 200 with `{"reviews":[]}` — never an error —
    so an empty result is reported as "answered empty", not as a failure to reach.
    """
    dest = ctx.brand / "reviews"
    url = OKENDO_REVIEWS.format(key=key, per=OKENDO_PER_PAGE)
    recs, p = [], 0
    while url and p < pages:
        p += 1
        data, raw = _get_json(ctx, "okendo", url, f"page {p}")
        if data is None:
            break
        batch = _walk_generic(data)
        if not batch:
            if p == 1:
                ctx.gap("reviews", "okendo: the store endpoint answered 200 but held zero "
                                   f"reviews for subscriber id `{key}`. That id may be "
                                   "wrong (an unknown id returns an empty list, not an "
                                   "error) — confirm it from the "
                                   "`<meta name=\"oke:subscriber_id\">` tag on a PDP.")
            break
        ctx.write_bytes(dest / f"raw-okendo-p{p}.json", raw)
        ctx.sources.append(url)
        recs += [_norm_review(o, "okendo") for o in batch]
        nxt = data.get("nextUrl") if isinstance(data, dict) else None
        if not nxt:
            break
        url = nxt if str(nxt).startswith("http") else OKENDO_BASE + str(nxt)
    if recs:
        syn = sum(1 for o in recs if o.get("_platform") == "okendo")
        ctx.got("reviews", f"okendo: {len(recs)} review records over {p} page(s) "
                           f"(store-wide, cursor-paged){'' if syn else ''}")
        ctx.got("reviews", "okendo: only `status: approved` reviews are exposed — "
                           "moderation-pending and rejected reviews are invisible here")
    return recs


def step_reviews(ctx: Ctx, pages: int, yotpo_products: int = MAX_YOTPO_PRODUCTS):
    print("\n[6/10] reviews")
    if ctx.pdp_url:
        try:
            ctx.pdp_html = fetch_text(ctx.pdp_url)
            ctx.sources.append(ctx.pdp_url)
            ctx.got("reviews", f"PDP fetched for widget detection: {ctx.pdp_url}")
        except Exception as e:
            ctx.gap("reviews", f"PDP fetch failed ({e}) — detecting on the homepage only")
    blob = ctx.pdp_html + ctx.home_html

    detected, named_only = [], []
    for name, strong, weak, keypats, impl in REVIEW_PLATFORMS:
        is_strong = bool(re.search(strong, blob, re.I))
        is_weak = bool(re.search(weak, blob, re.I))
        key = None
        for kp in keypats:
            m = re.search(kp, blob)
            if m:
                key = m.group(1)
                break
        if not is_strong and not key:
            if is_weak:
                named_only.append(name)
            continue
        detected.append({"name": name, "key": key, "impl": impl,
                         "evidence": "strong marker" if is_strong else "key present"})
        ctx.got("reviews", f"platform detected: {name} "
                           f"({'key found' if key else 'NO key in the served HTML'}) "
                           f"[{impl}, {'strong marker' if is_strong else 'key present'}]")
    if named_only:
        ctx.gap("reviews", "named in the page source but with NO live signal (no vendor "
                           "request, no widget element, no key): "
                           f"{', '.join(named_only)}. Modern themes ship one analytics "
                           "snippet that names every review platform they can integrate "
                           "with, all set to null — so a bare name is boilerplate, not "
                           "evidence. NOT treated as detected.")
    if not detected:
        ctx.gap("reviews", "no review widget detected in the served HTML — the store may use "
                           "an unlisted platform, or reviews may render client-side only")

    dest = ctx.brand / "reviews"
    recs, harvested_from = [], []
    for d in detected:
        if d["impl"] != "IMPLEMENTED":
            ctx.gap("reviews", f"{d['name']} is DETECTED BUT UNIMPLEMENTED here — "
                               f"key={d['key'] or 'not found'}; see reference/intake.md "
                               "for the next step on this platform")
            continue
        if not d["key"]:
            ctx.gap("reviews", f"{d['name']} detected but its public widget key is NOT in "
                               "the served HTML (it may be injected by JS after load). "
                               "Open a PDP in a browser, find the vendor request in the "
                               "network tab, and re-run intake with the key — or export "
                               "from the client's review account, which is better anyway.")
            continue
        if d["name"] == "stamped":
            got = _harvest_stamped(ctx, d["key"], pages)
        elif d["name"] == "yotpo":
            got = _harvest_yotpo(ctx, d["key"], pages, yotpo_products)
        elif d["name"] == "okendo":
            got = _harvest_okendo(ctx, d["key"], pages)
        else:
            continue
        if got:
            recs += got
            harvested_from.append(d)

    ctx.reviews = recs
    if not recs:
        _reviews_stub(ctx, detected, named_only)
        return
    ctx.got("reviews", f"{len(recs)} review records saved verbatim to {ctx._rel(dest)} "
                       f"across {len(harvested_from)} platform(s)")
    ctx.write_text(dest / "SUMMARY.md",
                   _reviews_summary_md(ctx, detected, harvested_from, named_only))


def _harvest_stamped(ctx: Ctx, key: str, pages: int) -> list:
    """The original, unchanged path — Stamped's envelope is known, so it keeps its
    own walker rather than going through the generic one."""
    dest = ctx.brand / "reviews"
    recs = []
    for p in range(1, pages + 1):
        u = ("https://stamped.io/api/widget/reviews"
             f"?storeUrl={ctx.domain}&apiKey={key}&take=100&page={p}")
        try:
            raw = fetch(u, cache=False)
        except Exception as e:
            ctx.gap("reviews", f"Stamped page {p} failed — {e}")
            break
        ctx.write_bytes(dest / f"raw-stamped-p{p}.json", raw)
        ctx.sources.append(u)
        try:
            batch = _walk_reviews(json.loads(raw.decode("utf-8", "ignore")))
        except Exception as e:
            ctx.gap("reviews", f"Stamped page {p} did not parse — {e}")
            break
        if not batch:
            break
        for o in batch:
            o.setdefault("_platform", "stamped")
        recs += batch
        if len(batch) < 100:
            break
    if not recs:
        ctx.gap("reviews", "Stamped answered but returned zero parseable review records")
    else:
        ctx.got("reviews", f"stamped: {len(recs)} review records")
    return recs


def _walk_reviews(obj) -> list:
    """Find review records anywhere in the payload — the widget API's envelope varies."""
    out = []

    def walk(o):
        if isinstance(o, dict):
            if "reviewMessage" in o or "reviewRating" in o:
                out.append(o)
                return
            for v in o.values():
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)
    walk(obj)
    return out


def _rv(r, *keys, default=""):
    for k in keys:
        v = r.get(k)
        if v not in (None, ""):
            return v
    return default


def _reviews_summary_md(ctx: Ctx, detected, harvested_from, named_only) -> str:
    recs = ctx.reviews
    dist = Counter(int(_rv(r, "reviewRating", default=0) or 0) for r in recs)
    lines = Counter(str(_rv(r, "productName", default="[GAP] unnamed")) for r in recs)
    by_platform = Counter(str(r.get("_platform", "?")) for r in recs)

    # ---- persona seed material: recurring phrases, counted across DISTINCT reviews
    shingles = defaultdict(set)
    for r in recs:
        rid = str(_rv(r, "id", "reviewId", default="?"))
        words = re.findall(r"[a-z']+", str(_rv(r, "reviewMessage")).lower())
        for n in (3, 4):
            for i in range(len(words) - n + 1):
                g = words[i:i + n]
                if all(w in STOP for w in g) or len(g[0]) < 2:
                    continue
                if sum(1 for w in g if w not in STOP) < 2:
                    continue
                shingles[" ".join(g)].add(rid)
    seeds = sorted(((len(ids), p, sorted(ids)[:3]) for p, ids in shingles.items() if len(ids) >= 4),
                   key=lambda t: -t[0])[:30]

    # ---- verdict-quote candidates: verified 5-star, a WHOLE unit under ~10 words
    quotes = []
    for r in recs:
        msg = str(_rv(r, "reviewMessage")).strip()
        if not msg:
            continue
        words = msg.split()
        if len(words) > 10:
            continue
        body = msg.rstrip(".!?")
        if re.search(r"[.!?]", body):          # more than one sentence = not a whole unit
            continue
        if int(_rv(r, "reviewRating", default=0) or 0) != 5:
            continue
        if not _rv(r, "reviewVerifiedType", default=0):
            continue
        quotes.append(r)
    quotes = quotes[:40]

    qrows = [
        f"| `{_rv(r, 'id', 'reviewId', default='?')}` | {_rv(r, 'author', 'reviewAuthor', default='[GAP]')} "
        f"| {_rv(r, 'reviewDate', default='[GAP]')} | **{_rv(r, 'productName', default='[GAP]')}** "
        f"| {_rv(r, 'productSKU', default='—')} | {str(_rv(r, 'reviewMessage')).strip()} |"
        for r in quotes]
    srows = [f"| {n} | `{p}` | {', '.join(ids)} |" for n, p, ids in seeds]

    plat_rows = "\n".join(
        f"| **{d['name']}** | `{d['key'] or 'not found in served HTML'}` | {d['impl']} | "
        f"{d['evidence']} | {by_platform.get(d['name'], 0)} |" for d in detected)
    named_only_block = ""
    if named_only:
        named_only_block = (
            "\n**Named in the page source but NOT detected:** " + ", ".join(named_only)
            + ". A modern theme ships one analytics snippet naming every review platform it "
              "can integrate with, all set to null, so a bare name is boilerplate rather "
              "than evidence.\n")
    not_harvested = "\n".join(
        f"- **{d['name']}** — key: `{d['key'] or 'not found in served HTML'}` — {d['impl']}"
        for d in detected if d not in harvested_from
    ) or "- none: every detected platform was harvested"

    return f"""# {ctx.brand_name} — review corpus

Fetched live {datetime.now():%Y-%m-%d} from the public widget API of every detected and
implemented platform. Raw records are saved verbatim beside this file as
`raw-<platform>-*.json` — this summary is derived, the raw files are the evidence. Nothing
here is remembered or inferred.

## platforms on this store

Every key below is a PUBLIC widget key printed in the served HTML, not a secret.

| platform | public key | status | detection evidence | records here |
|---|---|---|---|---|
{plat_rows}
{named_only_block}
Endpoints used (GET, no auth, public widget keys):
```
stamped  GET https://stamped.io/api/widget/reviews?storeUrl=<domain>&apiKey=pubkey-...&take=100&page=N
yotpo    GET https://api-cdn.yotpo.com/v1/widget/<appkey>/products/<shopify_product_id>/reviews.json?per_page=150&page=N
okendo   GET https://api.okendo.io/v1/stores/<subscriberId>/reviews?limit=100&orderBy=date%20desc   (cursor: nextUrl)
```

## ⚠️ the shape of this sample (read before using ANY of it)

- **{len(recs)} records** across the pages fetched: {', '.join(f'{k} {v}' for k, v in by_platform.most_common()) or 'none'}.
  This is the most-recent window, not the archive.
- **These APIs each hide a different slice, and none of them tells you so.** Stamped's public
  widget has been observed to expose **only 5-star reviews**. Okendo returns **only
  `status: approved`** — moderation-pending and rejected reviews are invisible. Yotpo has **no
  public all-reviews endpoint**, so its coverage here is a bounded per-product fan-out and any
  product outside that fan-out contributed nothing.
- If the rating distribution below is 100% five, that is the API filtering, not the truth about
  the product. It means **every objection is missing** from this corpus, and personas built on it
  will be systematically flattering. **The single highest-value refresh is a full export from
  inside the client's review account, including 1-4 star reviews.**

| rating | count |
|---|---|
{chr(10).join(f"| {k} | {v} |" for k, v in sorted(dist.items(), reverse=True))}

## per product line

**verify a testimonial's PRODUCT LINE, not only its text, rating and verified flag.**
A glowing review filed against an accessory is not evidence for the product in frame.

| product line | reviews |
|---|---|
{chr(10).join(f"| {k} | {v} |" for k, v in lines.most_common(30))}

## persona seed material

Recurring phrases across DISTINCT reviews (3-4 word shingles, stopword-only removed, ≥4 reviews).
These are candidate arcs and vocabulary, **not** personas. A phrase here is a thread to pull —
open the cited records and read them whole before believing anything about the buyer.

| reviews | phrase | example record ids |
|---|---|---|
{chr(10).join(srows) if srows else "| [GAP] | no phrase recurred across 4+ reviews in this window | |"}

**[GAP]** the personas themselves. Every trait, complaint, love and objection in a persona file
must trace to a quoted, linked, real source — no invented psychology, no "she probably feels".
This table is raw material for that work, and it covers only this brand's own (positive) reviews:
competitor retailer reviews, craft forums and converting search queries are all still missing.

## verdict-quote candidates

Verified, 5-star, and a **whole unit under 10 words** — chosen so nothing has to be elided.
Testimonial elision is a compliance surface, not a style choice (FTC 16 CFR 255.1): elide only
whole trailing content, never an internal qualifier, and prefer quotes that need no elision at all.
Whatever ships must **byte-match** the raw record.

| record id | author | date | PRODUCT LINE | sku | verbatim text |
|---|---|---|---|---|---|
{chr(10).join(qrows) if qrows else "| [GAP] | no record met verified + 5-star + whole-unit-under-10-words | | | | |"}

**Before any of these ships:** confirm the record still exists live, confirm the product line
matches what is in frame, and copy the text byte-for-byte from the `raw-*.json` files into a
provenance file beside the ad. Attribution framing is itself a claims surface — an eyebrow like
"from the reviews" may cover only byte-verified quoted material.

**Field-name warning for byte-matching.** Records from Yotpo and Okendo are NORMALISED into
Stamped's field names in this summary so one schema serves every downstream consumer. The raw
files keep the vendor's own names (`content`/`score`/`user.display_name` for Yotpo,
`body`/`rating`/`reviewer.displayName` for Okendo). **Byte-match against the RAW file**, not
against this table.

## platforms detected but NOT harvested
{not_harvested}
"""


def _reviews_stub(ctx: Ctx, detected, named_only=()):
    ctx.write_text(ctx.brand / "reviews" / "SUMMARY.md", f"""# {ctx.brand_name} — review corpus [GAP]

Intake ran on {datetime.now():%Y-%m-%d} and could **not** harvest reviews.

## platforms detected in the served HTML
{chr(10).join(f"- **{d['name']}** — key: `{d['key'] or 'NOT FOUND in served HTML'}` — {d['impl']} — detected by {d['evidence']}" for d in detected) or "- none detected"}

## named in the page source but NOT detected
{chr(10).join(f"- {n}" for n in named_only) or "- none"}

A modern Shopify theme ships one analytics snippet naming every review platform it *could*
integrate with, all set to null. A bare name is boilerplate, not evidence — so these are
reported and not chased.

## what to try next, in order

1. **The public widget key may be injected by JS after load.** Open a PDP in a real browser,
   find the vendor request in the network tab, and re-run intake once you have the key.
   - Stamped: `pubkey-…` · Yotpo: the id in `staticw2.yotpo.com/<key>/widget.js` (NOT the
     `cdn-widgetsrepository.yotpo.com/v1/loader/<GUID>` — that is a different id and 404s
     against the reviews API) · Okendo: `<meta name="oke:subscriber_id" content="<uuid>">`
2. **Judge.me and Loox are detected-only** — see `ad-loop/reference/intake.md` →
   "review-platform detection" for the door on each.
3. **Best of all: the client's own review-account export**, including 1-4 star reviews. Every
   public widget API hides a slice (Stamped's exposes only 5-star; Okendo's only `approved`;
   Yotpo has no all-reviews endpoint at all), so even a successful harvest is a positive-skewed
   sample and the export is the corpus you actually want.

**Why this matters enough to go get by hand:** reviews are the only source of the buyer's own
words. Personas built without them are a writer's guess, and a writer's guess flatters whatever
concept it is shown.
""")


# ──────────────────────────────────────────────────────── step 7: claims
def step_claims(ctx: Ctx):
    print("\n[7/10] claim CANDIDATES")
    cands = []   # (text, source_string, source_url)

    def add(text, raw, url):
        t = re.sub(r"\s+", " ", text).strip(" •-–—\t")
        if 8 <= len(t) <= 240:
            cands.append((t, raw[:300], url))

    for prod in ctx.products[:25]:
        url = f"{ctx.base}/products/{prod.get('handle')}"
        body = prod.get("body_html") or ""
        for li in re.findall(r"<li[^>]*>(.*?)</li>", body, re.S | re.I):
            add(html_text(li), li, url)
        for para in re.findall(r"<p[^>]*>(.*?)</p>", body, re.S | re.I):
            txt = html_text(para)
            for sent in re.split(r"(?<=[.!?])\s+", txt):
                if CERT_WORDS.search(sent) or re.search(r"\d", sent):
                    add(sent, sent, url)

    if ctx.pdp_html:
        for li in re.findall(r"<li[^>]*>(.*?)</li>", ctx.pdp_html, re.S | re.I):
            t = html_text(li)
            if CERT_WORDS.search(t) or re.search(r"\d", t):
                add(t, li, ctx.pdp_url)
    for pat, url in ((r'<meta[^>]+name=["\']description["\'][^>]+content=["\']([^"\']+)',
                      ctx.base + "/"),):
        for m in re.findall(pat, ctx.home_html, re.I):
            add(html_text(m), m, url)

    seen, rows = set(), []
    for t, raw, url in cands:
        k = re.sub(r"[^a-z0-9]", "", t.lower())
        if k in seen:
            continue
        seen.add(k)
        kind = []
        if CERT_WORDS.search(t):
            kind.append("certification/qualifier")
        if re.search(r"\d", t):
            kind.append("numeral")
        rows.append((t, ", ".join(kind) or "descriptive", raw, url))
    rows = rows[:140]

    if rows:
        ctx.got("claims", f"{len(rows)} claim CANDIDATES extracted "
                          f"(from {len(ctx.products[:25])} PDP bodies + homepage meta)")
    else:
        ctx.gap("claims", "no claim candidates could be extracted from PDP/label copy — "
                          "transcribe them off the physical package by hand")

    body = "\n".join(
        f"| [NEEDS HUMAN APPROVAL] | {t} | {k} | `{raw.strip()[:160]}` | {u} |"
        for t, k, raw, u in rows)
    ctx.write_text(ctx.brand / "claims-CANDIDATES.md", f"""# {ctx.brand_name} — claim CANDIDATES

## NOTHING IN THIS FILE IS APPROVED

**Claims are a legal surface, not a copy surface.** Every row below was scraped off the client's
own live storefront on {datetime.now():%Y-%m-%d} and is a *candidate for a human to approve, reject
or rewrite* — the client owns their claims and their substantiation, and neither this file nor
any session speaks for them.

Three rules that apply the moment a row leaves this file:

1. **A hedge is the load-bearing word.** "Many find", "may support", "can help" are not padding
   a writer gets to tighten. Every rewrite that "sounds better" usually got there by deleting the
   hedge — which converts an approved statement into an unapproved health claim.
2. **The hedge never takes the headline.** A hedged claim promoted to headline reads as the
   lawyer talking and manufactures the reader's objection: "many find" invites "many don't". The
   unique checkable fact leads; the hedged claim supports.
3. **Approved text is byte-exact.** What ships must match what was approved, character for
   character, and the approval must be recorded next to the ad.

`intake.py` never writes `brand/approved-claims.md` with content. That file is a human's
signature, and a machine may not forge it.

| status | candidate | kind | verbatim source string | source URL |
|---|---|---|---|---|
{body if body else "| [GAP] | nothing extracted | | | |"}

## [GAP] what is missing from this list by construction

- **Everything printed on the physical package** that is not repeated in web copy — read the
  pack, or a photograph of the pack, and transcribe.
- **Substantiation.** A claim is approvable only with the study, certificate, test, or invoice
  behind it. None of that is on the storefront.
- **Regulated-category rules** (supplement, food, skincare, alcohol, health, finance) and the
  platform's own ad policy, which is stricter than the storefront's.
- **What the client has already been told they cannot say.** Ask. It is usually a short list and
  it is never online.
""")


# ────────────────────────────────────── step 8: pack-strings DRAFT (print gate)
# `loop-engine/vision.py score_print` needs <brand>/pack-strings.json as its TRUTH
# list, or it calls every transcribed string a fabrication. Intake did
# not create it, so the loop's own letter-perfect print gate was UNRUNNABLE on any
# freshly-onboarded client until a human transcribed the pack by hand.
# This step writes a DRAFT so the gate can run on day one — and marks it, loudly, as
# a draft that has not been verified against the physical package.

NETWT_RE = re.compile(
    r"\b(?:NET\s*(?:WT|WEIGHT)\.?\s*)?"
    r"\d+(?:\.\d+)?\s*(?:FL\s*)?(?:OZ|G|KG|LB|LBS|ML|L)\b"
    r"(?:\s*\(\s*\d+(?:\.\d+)?\s*(?:G|KG|ML|L)\s*\))?", re.I)


def _packstring_text_candidates(ctx: Ctx) -> list[tuple[str, str]]:
    """(string, provenance) pairs derivable from copy alone — no network, no key.

    Deliberately narrow. A pack prints its brand, its product line, its
    certifications and its net weight; it does not print marketing paragraphs. A
    long line here would poison the truth list in the safe direction (a real
    transcription would never match it) but pad the file into looking authoritative,
    which is the thing this draft must not do.
    """
    out: list[tuple[str, str]] = []
    seen = set()

    def add(s, prov):
        s = re.sub(r"\s+", " ", str(s)).strip(" .,-–—•|")
        if not (2 <= len(s) <= 60) or len(s.split()) > 7:
            return
        k = re.sub(r"[^a-z0-9]", "", s.lower())
        if not k or k in seen:
            return
        seen.add(k)
        out.append((s, prov))

    if ctx.brand_name:
        add(ctx.brand_name, "og:site_name / <title>")
        add(ctx.brand_name.upper(), "og:site_name / <title>, upper-cased")

    # Product lines — but ONLY for products whose pack shot we actually downloaded.
    # A catalogue title with no image on disk is not evidence about this pack.
    shot_products = {r["product"] for r in ctx.saved_images if r.get("product")}
    for title in sorted(p for p in shot_products if p):
        add(title, "product title (a pack shot for it is on disk)")
        add(title.upper(), "product title, upper-cased")

    blob = ""
    for prod in ctx.products[:25]:
        blob += " " + html_text(prod.get("body_html") or "")
        for v in (prod.get("variants") or [])[:12]:
            if v.get("title") and v["title"].lower() != "default title":
                add(v["title"], "variant title (size/format)")
    blob += " " + html_text(ctx.pdp_html or "")

    for m in NETWT_RE.findall(blob):
        add(m, "net-weight pattern in PDP/product copy")
        add(m.upper(), "net-weight pattern, upper-cased")

    for sent in re.split(r"[.!?•|\n]", blob):
        t = sent.strip()
        if 2 <= len(t.split()) <= 5 and CERT_WORDS.search(t):
            add(t, "certification phrase in PDP/product copy")
            add(t.upper(), "certification phrase, upper-cased")
    return out


def step_packstrings(ctx: Ctx, max_shots: int, use_vision: bool):
    print("\n[8/10] pack-strings DRAFT (the letter-perfect print gate's truth list)")
    dest = ctx.brand / "pack-strings.json"
    if dest.exists():
        ctx.got("packstrings", f"{ctx._rel(dest)} already exists — left untouched "
                               "(intake never overwrites)")
        return

    vision_rows: list[dict] = []          # {"text","legibility","where","file"}
    if not use_vision:
        ctx.gap("packstrings", "vision OCR skipped by flag (--no-pack-ocr) — the draft "
                               "below is derived from COPY only, so anything printed on "
                               "the pack and nowhere in the web copy is missing")
    elif not ctx.saved_images:
        ctx.gap("packstrings", "no pack shots on disk to read — nothing to OCR")
    else:
        try:
            sys.path.insert(0, str(Path(ctx.cfg.LOOP_ENGINE)))
            import vision as _vision          # the print filter, NOT a fork of it
            from PIL import Image as _Image
            shots = sorted((r for r in ctx.saved_images if r.get("w")),
                           key=lambda r: (-(r["w"] or 0)))[:max_shots]
            for rec in shots:
                p = ctx.brand / "product-images" / rec["name"]
                if not p.exists():
                    continue
                try:
                    d = _vision.jparse(_vision.ask(_vision.PRINT_PROMPT, _Image.open(p)))
                except Exception as e:
                    ctx.gap("packstrings", f"OCR call failed on {rec['name']} — "
                                           f"{type(e).__name__}: {e}")
                    continue
                if not d or not isinstance(d.get("strings"), list):
                    ctx.gap("packstrings", f"OCR returned no parseable strings for "
                                           f"{rec['name']}")
                    continue
                for s in d["strings"]:
                    if not isinstance(s, dict) or not str(s.get("text", "")).strip():
                        continue
                    vision_rows.append({"text": str(s["text"]).strip(),
                                        "legibility": s.get("legibility", "?"),
                                        "where": str(s.get("where", ""))[:60],
                                        "file": rec["name"]})
                ctx.got("packstrings", f"OCR read {rec['name']} "
                                       f"({len(d['strings'])} printed blocks)")
        except Exception as e:
            ctx.gap("packstrings", f"vision OCR unavailable — {type(e).__name__}: {e}. "
                                   "This needs GEMINI_API_KEY (config.gemini_key_present()) "
                                   "and network; the draft below is COPY-DERIVED only")

    # CONFIDENCE GATE: only `crisp` transcriptions enter `strings`. `soft` and
    # `unresolvable` are recorded for the human but stay OUT of the truth list — a
    # guessed string in the truth list silently launders a real garble into a pass,
    # which is the one failure this gate exists to catch.
    seen, strings, prov = set(), [], []

    def take(text, source):
        k = re.sub(r"[^a-z0-9]", "", text.lower())
        if not k or k in seen:
            return
        seen.add(k)
        strings.append(text)
        prov.append({"string": text, "source": source})

    for v in vision_rows:
        if v["legibility"] == "crisp":
            take(v["text"], f"OCR crisp · {v['file']} · {v['where']}")
    for text, source in _packstring_text_candidates(ctx):
        take(text, source)

    low_conf = [v for v in vision_rows if v["legibility"] != "crisp"]

    payload = {
        "_STATUS": "DRAFT — NOT VERIFIED. A human must check every string against the "
                   "physical package (or a 1:1 read of the real pack shot) before this "
                   "file is trusted.",
        "_WHY_IT_MATTERS": "This is the TRUTH LIST for loop-engine/vision.py's "
                           "letter-perfect print audit. A string missing from it makes a "
                           "correctly-printed line score as a fabrication; a string "
                           "wrongly IN it makes a real garble score as a pass. The second "
                           "error is the dangerous one, so this draft only admits "
                           "high-confidence strings and lists the rest below.",
        "_HOW_TO_VERIFY": [
            "Open the largest real pack shot at 1:1 and read every printed line off it.",
            "Add anything the pack prints that is not listed — small print and seal "
            "lines are the usual omissions (a top-seal line was missed for months).",
            "Delete anything here that the pack does not actually print.",
            "Then delete this _STATUS block. Its absence is the signal that a human "
            "has been through the file.",
        ],
        "_generated": f"{datetime.now():%Y-%m-%d}",
        "_generated_by": "ad-loop/scripts/intake.py step `packstrings`",
        "strings": strings,
        "_provenance": prov,
        "_low_confidence_NOT_in_strings": [
            {"text": v["text"], "legibility": v["legibility"], "where": v["where"],
             "file": v["file"]} for v in low_conf],
    }
    ctx.write_text(dest, json.dumps(payload, indent=1, ensure_ascii=False) + "\n")

    if strings:
        ctx.got("packstrings", f"{len(strings)} DRAFT pack strings "
                               f"{'would be written to' if ctx.dry else 'written to'} "
                               f"{ctx._rel(dest)} "
                               f"({sum(1 for v in vision_rows if v['legibility'] == 'crisp')} "
                               f"from OCR, rest from copy) — the print gate can now RUN, "
                               "but its truth list is UNVERIFIED")
    else:
        ctx.gap("packstrings", "the draft is EMPTY — nothing could be read off the pack "
                               "or derived from copy. The print gate will fail everything "
                               "until a human transcribes the package by hand")
    if low_conf:
        ctx.gap("packstrings", f"{len(low_conf)} transcribed string(s) were soft or "
                               "unresolvable and were deliberately NOT added to the truth "
                               "list — read them in the file and decide by eye")


# ─────────────────────────────────────────────── step 9: Meta Ad Library
# JS below is the page-id extraction logic proven in a prior run: a walk of the page's
# embedded JSON plus a graphql capture hook.
CAPTURE_HOOK_JS = r"""
() => {
  if (window.__adlibHooked) return;
  window.__adlibCap = []; window.__adlibHooked = true;
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

TALLY_JS = r"""
() => {
  const tally = {};
  const note = (pid, pname) => {
    if (!pid) return;
    const k = String(pid);
    if (!tally[k]) tally[k] = { page_id: k, page_name: pname || null, ads: 0 };
    tally[k].ads += 1;
    if (!tally[k].page_name && pname) tally[k].page_name = pname;
  };
  const walk = (o) => {
    if (!o || typeof o !== "object") return;
    if (o.ad_archive_id) {
      const snap = o.snapshot || {};
      note(o.page_id || snap.page_id, o.page_name || snap.page_name);
    }
    for (const k in o) walk(o[k]);
  };
  const tryParse = (t) => {
    try { walk(JSON.parse(t)); return; } catch (e) {}
    for (const line of t.split("\n")) { try { walk(JSON.parse(line)); } catch (e) {} }
  };
  document.querySelectorAll('script[type="application/json"]').forEach(s => tryParse(s.textContent));
  (window.__adlibCap || []).forEach(tryParse);
  return Object.values(tally);
}
"""

SEARCH_URL = ("https://www.facebook.com/ads/library/"
              "?active_status=active&ad_type=all&country={country}"
              "&q={query}&search_type=keyword_unordered&media_type=all")
AD_URL = ("https://www.facebook.com/ads/library/"
          "?active_status=all&ad_type=all&country={country}&id={lid}")


def _norm(s):
    import unicodedata
    s = unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]", "", s.lower())


def _score(cands, name):
    target = _norm(name)
    out = []
    for c in cands:
        n = _norm(c.get("page_name"))
        if not n:
            continue
        s = 3 if n == target else 2 if (n.startswith(target) or target.startswith(n)) \
            else 1 if (target in n or n in target) else 0
        out.append((s, c["ads"], c))
    out.sort(key=lambda t: (-t[0], -t[1]))
    return out


def step_adlib(ctx: Ctx, competitors, library_ids, country):
    print("\n[9/10] Meta Ad Library page ids")
    targets = [(ctx.slug, ctx.brand_name)] + [(_norm(c) or c, c) for c in competitors]
    resolved = []
    rejected = []          # match score 0/3 — a candidate list, NEVER a resolution

    try:
        from playwright.sync_api import sync_playwright
    except Exception:
        ctx.gap("adlib", "Playwright is not installed — page-id resolution not run. "
                         "`pip install playwright && playwright install chromium`, then "
                         "re-run with `--skip probe --skip index ...`, or resolve by hand "
                         "(manual steps are written into brand/adlib-pages.md)")
        ctx.write_text(ctx.brand / "adlib-pages.md",
                       _adlib_md(ctx, targets, [], [], library_ids, country,
                                 playwright=False))
        return

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        c = browser.new_context(viewport={"width": 1400, "height": 1000}, user_agent=UA)
        c.add_init_script("(" + CAPTURE_HOOK_JS + ")()")
        pg = c.new_page()

        for slug, name in targets:
            try:
                pg.goto(SEARCH_URL.format(country=country,
                                          query=urllib.parse.quote(name or slug)),
                        wait_until="domcontentloaded", timeout=60000)
                time.sleep(5)
                for _ in range(3):
                    pg.mouse.wheel(0, 15000)
                    time.sleep(1.5)
                scored = _score(pg.evaluate(TALLY_JS), name or slug)
                # A 0/3 match means the tally's best page NAME does not overlap the
                # brand name at all — on a brand sold through third parties the top
                # row is reliably a RETAILER. Printing that page id as "resolved" is
                # how a later session harvests the wrong brand's ads and never knows
                # (observed: a beverage brand resolved to a big-box retailer at 0/3
                # and was tabled as a success). Zero is a REJECTION with a candidate list, never a result.
                if scored and scored[0][0] > 0:
                    s, ads, top = scored[0]
                    resolved.append({"slug": slug, "query": name, "page_id": top["page_id"],
                                     "page_name": top["page_name"], "ads": ads, "score": s,
                                     "method": "keyword search"})
                    ctx.got("adlib", f"{slug}: page_id {top['page_id']} "
                                     f"({top['page_name']}, {ads} ads, match score {s}/3) "
                                     "via keyword search")
                elif scored:
                    cands = [{"page_id": c["page_id"], "page_name": c["page_name"],
                              "ads": ads} for _s, ads, c in scored[:6]]
                    rejected.append({"slug": slug, "query": name or slug,
                                     "candidates": cands})
                    ctx.gap("adlib", f"{slug}: REJECTED — no page id resolved. "
                                     f"{len(scored)} candidate page(s) found but the best "
                                     f"name match scored 0/3 (top: "
                                     f"{scored[0][2].get('page_name')!r} / "
                                     f"{scored[0][2].get('page_id')}), which on a brand sold "
                                     "through third parties is a RETAILER, not the brand. "
                                     "Candidates are listed in brand/adlib-pages.md for a "
                                     "human to confirm; recover definitively from a known "
                                     "library id with --library-id")
                else:
                    rejected.append({"slug": slug, "query": name or slug, "candidates": []})
                    ctx.gap("adlib", f"{slug}: REJECTED — no page id resolved. Keyword "
                                     "search returned no candidate pages at all "
                                     "(retailers commonly drown out the brand) — "
                                     "recover from a known library id instead")
            except Exception as e:
                ctx.gap("adlib", f"{slug}: keyword search errored — {e}")
            time.sleep(4)

        for spec in library_ids:
            slug, _, lid = spec.partition("|")
            if not lid:
                slug, lid = ctx.slug, spec
            try:
                pg.goto(AD_URL.format(country=country, lid=lid),
                        wait_until="domcontentloaded", timeout=60000)
                time.sleep(6)
                hits = {h["page_id"]: h for h in pg.evaluate(TALLY_JS) if h.get("page_id")}
                for pid, h in hits.items():
                    resolved.append({"slug": slug, "query": f"library id {lid}",
                                     "page_id": pid, "page_name": h.get("page_name"),
                                     "ads": h.get("ads"), "score": None,
                                     "method": f"from library id {lid} (DEFINITIVE)"})
                    ctx.got("adlib", f"{slug}: page_id {pid} ({h.get('page_name')}) "
                                     f"recovered from library id {lid} — DEFINITIVE")
                if not hits:
                    ctx.gap("adlib", f"{slug}: library id {lid} returned no page")
            except Exception as e:
                ctx.gap("adlib", f"{slug}/{lid}: errored — {e}")
            time.sleep(4)
        browser.close()

    ctx.write_text(ctx.brand / "adlib-pages.md",
                   _adlib_md(ctx, targets, resolved, rejected, library_ids, country,
                             playwright=True))


def _adlib_md(ctx, targets, resolved, rejected, library_ids, country, playwright) -> str:
    rows = [f"| {r['slug']} | `{r['page_id']}` | {r['page_name']} | {r['ads'] or '—'} | "
            f"{r['method']} |" for r in resolved]

    rej_lines = []
    for rj in rejected:
        rej_lines.append(f"\n### `{rj['slug']}` — **REJECTED, no page id resolved** "
                         f"(query: {rj['query']!r})\n")
        if rj["candidates"]:
            rej_lines.append("These are CANDIDATES a human must confirm or discard. None of "
                             "them matched the brand name, so the top row is most likely a "
                             "retailer. **Do not harvest from any of these until one is "
                             "confirmed by opening its library page.**\n")
            rej_lines.append("| candidate page_id | page name | ads seen | open it |")
            rej_lines.append("|---|---|---|---|")
            for c in rj["candidates"]:
                url = ("https://www.facebook.com/ads/library/?active_status=all&ad_type=all"
                       f"&country={country}&view_all_page_id={c['page_id']}")
                rej_lines.append(f"| `{c['page_id']}` | {c['page_name']} | "
                                 f"{c['ads'] or '—'} | {url} |")
        else:
            rej_lines.append("Keyword search returned **no candidate pages at all**. "
                             "Recover from a known library id (method 1 below).\n")
        rej_lines.append("")

    # Harvest commands are emitted ONLY for genuinely resolved rows. A rejected slug
    # gets a placeholder, never a runnable command carrying an unverified page id —
    # a printed command is an instruction, and a later session will run it.
    cmds = [f"python3 {ctx.cfg.HARVEST_INSPO} --page-id {r['page_id']} --slug {r['slug']} "
            f"--top 24 --country {country} --media all" for r in resolved]
    cmds += [f"# {rj['slug']}: NOT RESOLVED — confirm a page id by hand first, then:\n"
             f"# python3 {ctx.cfg.HARVEST_INSPO} --page-id <CONFIRMED_PAGE_ID> "
             f"--slug {rj['slug']} --top 24 --country {country} --media all"
             for rj in rejected]
    if not cmds:
        cmds = [f"python3 {ctx.cfg.HARVEST_INSPO} --page-id <PAGE_ID> --slug {t[0]} "
                f"--top 24 --country {country} --media all" for t in targets]
    return f"""# {ctx.brand_name} — Meta Ad Library

Resolved {datetime.now():%Y-%m-%d}{'' if playwright else ' — **Playwright absent, nothing resolved automatically**'}.

## resolved page ids

Only rows whose page NAME actually matched the brand appear here. A 0/3 name match
is recorded below as REJECTED, never as a resolution — see "rejected" for why.

| slug | page_id | page name | active ads seen | match | method |
|---|---|---|---|---|---|
{chr(10).join(f"| {r['slug']} | `{r['page_id']}` | {r['page_name']} | {r['ads'] or '—'} | {r['score'] if r['score'] is not None else 'definitive'}{'/3' if r['score'] is not None else ''} | {r['method']} |" for r in resolved) if rows else "| [GAP] | — | — | — | — | nothing resolved |"}

## rejected — no page id resolved
{chr(10).join(rej_lines) if rej_lines else chr(10) + "None. Every target resolved to a name-matching page."}

**Why a 0/3 match is a rejection and not a weak answer.** The tally is scored by name
overlap against the brand. Zero means the top page's name shares nothing with the
brand — and on any product sold through third parties, that page is reliably a
**retailer**. Writing it into the resolved table as a success is how a later session
harvests the wrong brand's creative and never finds out (documented case: a
beverage brand resolved to a big-box retailer at 0/3 with 8 ads and was tabled as resolved). The
candidates are preserved above precisely so nothing is lost by refusing to guess.

## the two methods, ranked by reliability

1. **Recovery from a known `ad_archive_id` (library id) — DEFINITIVE.** Open
   `https://www.facebook.com/ads/library/?active_status=all&ad_type=all&country={country}&id=<LIBRARY_ID>`
   and read the owning page off the ad itself. This does not guess: it reads which page an ad we
   already have actually ran from. Feed intake a library id with
   `--library-id "<slug>|<ad_archive_id>"`.
2. **Public keyword search — good, sometimes defeated.** `?q=<brand>&search_type=keyword_unordered`,
   then tally page ids across the results and score by name match. **Retailers reliably drown out
   the brand** for anything sold through third parties (one documented case: a beverage brand returned NOT
   FOUND by keyword and had to be recovered from library ids twice).

**Do not reach for the advertiser typeahead endpoint.** `/ads/library/async/search_typeahead/` is
behind a bot-verification challenge — not a login wall, but **unusable headless**. This is
established; it is a settled finding, not something to re-discover.

Also settled: `harvest_inspo.py` defaults to `--media all` because Meta's server-side
`media_type=image` filter is unreliable (it returned "No ads" for pages demonstrably running
statics). `--media all` still yields only real statics because the extractor reads
`snapshot.images[]`/`cards[]` and never `video_preview_image_url`. And the harvester dedupes by
content (md5 + dhash), not filename — a re-uploaded creative gets a fresh CDN filename, so
filename identity alone inflates a corpus.

## next: harvest

Signed CDN URLs expire in about 5 days, so harvest downloads immediately. Run:

```bash
{chr(10).join(cmds)}
```

Output lands in `{ctx.cfg.INSPO}/<slug>/`.

## [GAP] a human must still

- **Confirm each page id is the brand's own page**, not a retailer, a regional page, or a
  lookalike. Open the library URL and look.
- **Choose the competitors worth harvesting.** Intake harvests who it is told to. Who is
  actually the bar is a judgement call — and an empty result for an active-status query can be a
  real finding (creative rotation), not a failure.
- **Never confuse a harvested competitor corpus with a North Star.** The corpus is what the
  category does; the North Stars are what the operator has decided is good. See
  `brand/north-star-picks/README.md`.
"""


# ────────────────────────────────────────────── step 9: skeleton + report
def step_skeleton(ctx: Ctx):
    print("\n[10/10] skeleton + report")
    for d in (ctx.brand, ctx.brand / "product-images", ctx.brand / "characters",
              ctx.brand / "reference-photos", ctx.brand / "site-photography",
              ctx.brand / "fonts", ctx.brand / "reviews", ctx.brand / "refs" / "scraped",
              ctx.brand / "north-star-picks", ctx.personas,
              ctx.cfg.statics_dir(ctx.slug)):
        ctx.mkdir(d)

    name = ctx.brand_name
    stubs = {
        ctx.brand / "bible.md": f"""# {name} — brand bible [STUB, written by intake]

**What this file is for:** the single source of truth for what this brand is, who it is for,
what it sells, and what it may and may not say. Every build reads it before anything renders.

**Everything below is a [GAP].** Intake can harvest a storefront. It cannot harvest intent.

## [GAP] 1. what the company actually is
One paragraph a stranger could repeat back. Not the About page's words.

## [GAP] 2. the product line
Which SKUs matter, which are noise, what the hero is and why. Harvested inventory is in
`product-images/INDEX.md` — which of those is the *ad's* product is a decision.

## [GAP] 3. who buys, and who does not
See `../personas/`. Until real personas exist, this section is empty on purpose.

## [GAP] 4. the category's default ad, and why this brand refuses it

## [GAP] 5. voice
Words the brand uses. Words it never uses. Read the client's own emails and packaging, not the
homepage headline.

## [GAP] 6. proof assets
What real evidence exists: photography, certifications, test results, press, founder story.
What is missing and would have to be shot or bought.

## [GAP] 7. the forbidden list
Everything the client has already said no to. Ask them — this is never online, and violating it
is the fastest way to lose a client's trust.

## [GAP] 8. claim rules
The pointer, not the list: candidates in `claims-CANDIDATES.md`, approvals in
`approved-claims.md`. A hedge is load-bearing; a hedge never takes the headline.
""",
        ctx.brand / "art-direction.md": f"""# {name} — art direction [STUB, written by intake]

**What this file is for:** the visual doctrine every build is judged against — the look, the
light, the surfaces, the type behaviour, and the specific things that are always wrong here.

**Intake cannot write any of this.** It can count hexes in a stylesheet
(`palette-CANDIDATES.md`) and name webfonts (`fonts/INDEX.md`). Turning that into art direction
is a human decision, and the ui-ux-pro-max style of automatic style/colour/font picking produces
exactly the generic mean this loop exists to beat.

## [GAP] the look in one sentence

## [GAP] tokens
Ink / ground / accent / the colour never used. Start from `palette-CANDIDATES.md`, then decide.

## [GAP] type
Display face, text face, the scale, and how a voice change is marked. Note: voice changes are
marked typographically (indent, scale, weight, colour) — **never with a drawn quote bar**; that
is template furniture and it is banned.

## [GAP] light and surface
One key or many? Cast shadows or none? What ground does product sit on? Type must live in the
image's light or on a surface with no light story — flat vector ink over a photographic field
with real luminance variance reads as layered-not-designed every time.

## [GAP] the reference photograph
Physics get calibrated against a real photograph of the same object class. Which photo is that
here?

## [GAP] always-wrong list
The specific moves that are wrong for THIS brand, whatever the rubric says.
""",
        ctx.brand / "ad-creative-principles.md": f"""# {name} — ad creative principles [STUB, written by intake]

**What this file is for:** the client-specific rules that sit ON TOP of the global design laws.
The global laws are not forked here — this file only carries what is true for {name} and false
elsewhere.

**Everything below is a [GAP].**

## [GAP] the job of an ad here
Stop, believe, buy — in this category, which of the three is actually the bottleneck?

## [GAP] product form
What must be unambiguous within the read: does the viewer know what arrives if they buy?

## [GAP] the evidence this brand leads with
Numbers, a named human, a certification, a demonstration. Whichever it is, name it here so
builds stop re-litigating it every round.

## [GAP] the emotion
Craft debt is finite; feeling debt is the ceiling. "Well-made, tasteful, forgettable" is worse
than ugly. What should someone feel, in one word?

## [GAP] hard nos
Formats, framings, subjects and effects this client has refused. Date each one.
""",
        ctx.brand / "approved-claims.md": f"""# {name} — APPROVED claims

**Empty on purpose. Intake may not write this file's content.**

An approved claim is a human's signature — the client's, on their own substantiated statement.
A machine that fills this in has forged an approval, and the file's whole value is that it
cannot have been forged.

Candidates that a human may approve, reject or rewrite are in
**`claims-CANDIDATES.md`**, each with its verbatim source string and source URL.

## how a row gets here

1. It starts as a row in `claims-CANDIDATES.md`.
2. A human — with the client — approves the exact wording and records the substantiation.
3. The approved wording is pasted here **byte-exact**, with the date, who approved it, and what
   backs it.

## the two rules that survive every rewrite

- **The hedge is the load-bearing word.** Deleting "many find" or "may support" to make a line
  read better converts an approved statement into an unapproved claim.
- **The hedge never takes the headline.** It reads as the lawyer talking and manufactures the
  objection. The unique checkable fact leads; the hedged claim supports.

| approved wording (byte-exact) | approved by | date | substantiation |
|---|---|---|---|
| [GAP] nothing approved yet | | | |
""",
        ctx.brand / "tensions.md": f"""# {name} — tensions [STUB, written by intake]

**What this file is for:** the true contradictions in this brand that make ads interesting —
the places where two things the brand wants are genuinely in conflict.

**Intake cannot find a tension.** A tension is not on a storefront; it surfaces in what a
client says out loud, what reviews complain about, and what the category refuses to admit.
A fabricated tension is worse than none: it sends every build chasing a conflict nobody has.

## [GAP] name the real ones

For each: what pulls one way, what pulls the other, and what evidence says it is real.
Two or three genuine tensions beat ten invented ones. Sources: client calls, low-star reviews
(the public review API generally shows only 5-star records, so this needs the client's own
export), competitor complaints, the founder's own account of why the company exists.
""",
        ctx.brand / "north-star-picks" / "README.md": f"""# {name} — North Star picks

**This folder is filled by the operator, by hand. Nothing here is ever harvested.**

A harvested competitor corpus tells you what the category *does*. A North Star tells you what
*good* is. They are different objects and collapsing them is how a loop converges on the
category mean — which is the failure this whole system exists to avoid.

## how to fill it

Drop in ads the operator has personally decided are the bar — from anywhere, any category, any
era. Beside each, one line: **why this one.** The why is the actual asset; the image is just
what the why points at.

A folder with 4 ads and 4 honest reasons is worth more than 200 harvested files.

## what goes elsewhere

- Competitor/category harvest → `{ctx.cfg.INSPO}/<slug>/` via `harvest_inspo.py` (see
  `../adlib-pages.md`).
- The operator's global picks → the shared North Star folder in `ad-loop/config.py`.

## [GAP] currently empty
""",
        ctx.personas / "README.md": f"""# {name} — judge personas [STUB, written by intake]

**What these are for:** buyer personas that get **roleplayed as judges** against copy and
concepts before anything is rendered or bought. The point is to get a believable *no* before the
market gives you an expensive one.

**Intake did not build any.** It cannot. A persona here is not a marketing persona deck — it is
**a curated anthology of real people's words with a name on it**, and intake has only one
source (this brand's own public reviews, which are systematically positive).

## THE GROUNDING RULE (absolute)

Every trait, complaint, love, objection and vocabulary item must trace to a quoted, linked, real
source. **No invented psychology. No "she probably feels…".** Where evidence is thin the file
says **[GAP]** and names what is missing. A thin honest persona beats a rich fake one.

If you catch yourself adding a detail because it would make the persona feel more real, stop.
That detail is the exact thing that makes these useless.

## what intake left you

- `../brand/reviews/SUMMARY.md` — persona seed material (recurring phrases with record ids) and
  the raw records beside it. **Positive-only**: the public widget API exposes 5-star reviews, so
  every objection is missing.
- **[GAP] the objection half.** Get the client's full review export including 1-4 stars; read
  competitor retailer reviews; read the forums where this buyer is blunt (interactively, in a
  logged-in browser — headless attempts get blocked and the block is worth writing down).
- **[GAP] converting search queries** from the ad account — cheap, high-quality, and it tells
  you which persona is actually buying rather than which one is fun to write.

## the honesty rail (this is what makes it work)

- The persona **defaults to scrolling past**. Not stopping is the correct answer most of the time.
- The persona **never flatters**. Fine-but-unremarkable is a verdict, and it scrolls.
- Reactions covered by a quote **cite it**; reactions reasoned in character are tagged
  `[extrapolation]`. Both are legitimate; blurring them is not.
- The persona may be **wrong about the world** — we model what buyers believe, not what is true.
- **Nobody is a spokesperson.** A persona liking a line does not approve a claim.

## what personas CANNOT do

Judge design craft. Predict ROAS. Size a market. Approve a claim. They tell you whether copy
*lands*, not whether it *performs*.
""",
        ctx.personas / "01-GAP.md": f"""# [GAP] persona 01 — not built

Placeholder written by intake on {datetime.now():%Y-%m-%d} so the loop fails loudly instead of
quietly proceeding without a buyer.

**Do not fill this in from imagination.** See `README.md` → THE GROUNDING RULE.

## what has to exist before this file is real

- [ ] A **hypothesis** of who this is — one sentence, and it is allowed to be overturned by the
      evidence (on one build, three of the original persona hypotheses were wrong, including the
      whole premise that anyone entered as a parent).
- [ ] **20+ verbatim quotes** from real people, each with a link or a record id, showing this
      person's arc, vocabulary and objections.
- [ ] **Objections from real buyers**, not just praise. This is the hardest half and the one
      that makes the persona able to say no.
- [ ] A **[GAP] section** naming what evidence is still missing and what was blocked.
- [ ] A **JUDGE PROTOCOL** section at the bottom: would you stop / would you believe it / would
      you buy, plus one line in their own idiom, plus the honesty rail.

## evidence available right now

`../brand/reviews/SUMMARY.md` (positive-only — see the README).
""",
    }
    # The GAP placeholder exists to make the loop fail loudly when no buyer has been built.
    # If real personas already exist it is just noise in someone's evidence folder.
    if any(p.name != "01-GAP.md" and re.match(r"\d\d-", p.name)
           for p in (ctx.personas.glob("*.md") if ctx.personas.exists() else [])):
        stubs.pop(ctx.personas / "01-GAP.md", None)
        ctx.got("skeleton", "real persona files already exist — the [GAP] placeholder was not written")

    for path, content in stubs.items():
        ctx.write_text(path, content)
    ctx.got("skeleton", f"{len(stubs)} stub files considered "
                        f"({sum(1 for p, s in ctx.writes if s == 'wrote')} writes so far)")


def write_report(ctx: Ctx, url: str, argv: str):
    lines = [f"# {ctx.brand_name} — INTAKE REPORT",
             "",
             f"Run {datetime.now():%Y-%m-%d %H:%M}  ·  slug `{ctx.slug}`  ·  "
             f"root `{ctx.cfg.WORK_ROOT}`",
             f"Input URL: {url}",
             f"Command: `{argv}`",
             "",
             "Intake harvests what a storefront can prove and marks everything else **[GAP]**.",
             "A [GAP] is a research to-do, not a blank to fill in with imagination.",
             "",
             "## what happened, step by step",
             ""]
    for s in STEPS:
        r = ctx.report.get(s)
        if r is None:
            lines.append(f"### {s} — not run")
            lines.append("")
            continue
        if r["skipped"]:
            lines += [f"### {s} — SKIPPED (`--skip {s}`)", ""]
            continue
        lines.append(f"### {s}")
        for g in r["got"]:
            lines.append(f"- got: {g}")
        for g in r["gaps"]:
            lines.append(f"- **[GAP]** {g}")
        if not r["got"] and not r["gaps"]:
            lines.append("- (nothing to report)")
        lines.append("")

    lines += ["## counts", "",
              f"- products indexed: **{len(ctx.products)}**",
              f"- image candidates found: **{len(ctx.images)}**",
              f"- product images downloaded: **{len(ctx.saved_images)}**",
              f"- review records harvested: **{len(ctx.reviews)}**",
              f"- platform: **{ctx.platform}**",
              ""]

    gaps = [(s, g) for s in STEPS for g in ctx.report.get(s, {}).get("gaps", [])]
    lines += ["## every [GAP], in one place", ""]
    lines += [f"- **{s}** — {g}" for s, g in gaps] or ["- none recorded"]
    lines += ["",
              "## what a human must do before this client is loop-ready", "",
              "1. **Fill `brand/art-direction.md`.** Intake counted hexes; it did not decide a look.",
              "2. **Fill `brand/bible.md`** — product line, voice, proof assets, the forbidden list.",
              "3. **Build at least one real persona** from quoted sources. Get the client's full "
              "review export (the public API is positive-only, so every objection is missing).",
              "4. **Approve claims.** `brand/claims-CANDIDATES.md` → `brand/approved-claims.md`, "
              "byte-exact, with substantiation. Never let a machine write the approved file.",
              "5. **Hand-pick North Stars** into `brand/north-star-picks/`, one line of why each.",
              "6. **Verify the pack shots.** Filenames lie; confirm what each file contains and "
              "which is the hero. Check the `s` column in `product-images/INDEX.md` — a pack with "
              "a low native width has a scale ceiling before any layout exists.",
              "7. **Confirm the Ad Library page ids** by opening them, then harvest. Any "
              "row under `rejected` in `brand/adlib-pages.md` resolved to NOTHING — its "
              "candidates are almost certainly retailers and must not be harvested from.",
              "7b. **Verify `brand/pack-strings.json`.** It is a DRAFT: read the pack at "
              "1:1, add every printed line that is missing, delete anything the pack does "
              "not print, then delete its `_STATUS` block. Until that happens the "
              "letter-perfect print gate runs against an unverified truth list.",
              "8. **Name the tensions** in `brand/tensions.md` from client calls and low-star "
              "reviews, never from imagination.",
              "",
              "## files written this run", ""]
    lines += [f"- `{p}` — {s}" for p, s in ctx.writes] or ["- none"]
    lines += ["", "## every source URL touched", ""]
    lines += [f"- {u}" for u in dict.fromkeys(ctx.sources)] or ["- none"]
    lines.append("")
    ctx.write_text(ctx.client / "INTAKE-REPORT.md", "\n".join(lines))


# ─────────────────────────────────────────────────────────────────── main
def write_library_seed(ctx):
    """Write <client>/library/seed.json from the harvested pack shots, so
    `runtime/lib/asset_library.py seed <client>` can register them as approved real
    photography. Never overwrites an existing seed.json (a human may have curated it)."""
    imgs = sorted(p for p in (ctx.brand / "product-images").glob("*")
                  if p.suffix.lower() in (".png", ".jpg", ".jpeg", ".webp"))
    if not imgs:
        return
    rows = []
    for i, p in enumerate(imgs, 1):
        stem = re.sub(r"[^a-z0-9]+", "-", p.stem.lower()).strip("-")[:40] or f"img{i}"
        rows.append({"type": "product", "id": f"prod-{i:02d}-{stem}", "name": p.stem,
                     "file": str(p.relative_to(ctx.client)),
                     "description": "harvested pack shot (intake); confirm which is the hero"})
    ctx.write_text(ctx.client / "library" / "seed.json", json.dumps(rows, indent=2) + "\n")


def main():
    ap = argparse.ArgumentParser(
        description="Bootstrap an ad-loop client layer from a brand URL.")
    ap.add_argument("--url", required=True, help="brand homepage or a PDP URL")
    ap.add_argument("--slug", required=True, help="client slug (the folder name under the work root)")
    ap.add_argument("--root", help="override the work root, AD_LOOP_HOME (use this for smoke tests)")
    ap.add_argument("--max-images", type=int, default=40)
    ap.add_argument("--review-pages", type=int, default=4,
                    help="pages per review target (Stamped/Yotpo 100-150 per page, "
                         "Okendo 100 per cursor page)")
    ap.add_argument("--yotpo-products", type=int, default=MAX_YOTPO_PRODUCTS,
                    help="how many products to fan out over on Yotpo, which has no "
                         f"public all-reviews endpoint (default {MAX_YOTPO_PRODUCTS})")
    ap.add_argument("--pack-ocr-shots", type=int, default=MAX_PACK_OCR_SHOTS,
                    help="how many of the largest pack shots to OCR for the "
                         "pack-strings.json draft (default 3; pennies each)")
    ap.add_argument("--no-pack-ocr", action="store_true",
                    help="skip the vision OCR half of the pack-strings draft "
                         "(no key / no network); the copy-derived half still runs")
    ap.add_argument("--competitor", action="append", default=[],
                    help="competitor brand name for Ad Library resolution (repeatable)")
    ap.add_argument("--library-id", action="append", default=[],
                    help='"<slug>|<ad_archive_id>" — the DEFINITIVE page-id method (repeatable)')
    ap.add_argument("--country", default="US")
    ap.add_argument("--skip", action="append", default=[], choices=STEPS,
                    help="skip a step (repeatable)")
    ap.add_argument("--dry-run", action="store_true",
                    help="fetch and report, write nothing")
    ap.add_argument("--force", action="store_true",
                    help="allow running against an EXISTING client layer "
                         "(intake is additive-only, but it will add ~6 files + "
                         "NN_-prefixed images into a live brand folder)")
    a = ap.parse_args()

    if a.root:
        os.environ["AD_LOOP_HOME"] = str(Path(a.root).expanduser())
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    import config

    ctx = Ctx(config, a.slug, a.dry_run)

    # Guard: an existing live client layer means a human curated this folder.
    # Intake never overwrites, but adding files to a curated layer is still a
    # decision — require --force so it can't happen by a mistyped slug.
    existing_bible = Path(ctx.client) / "brand" / "bible.md"
    if existing_bible.exists() and not (a.force or a.dry_run):
        print(f"REFUSED: {existing_bible} exists — this is a live, curated "
              f"client layer.\nRe-run with --force to add intake artifacts to "
              f"it, or use --root for a scratch run.")
        sys.exit(2)
    run = lambda s: s not in a.skip  # noqa: E731
    for s in a.skip:
        ctx.step(s)["skipped"] = True

    print("=" * 78)
    print(f"ad-loop intake  ·  {a.url}  ->  {ctx.client}")
    if a.dry_run:
        print("DRY RUN — nothing will be written")
    print("=" * 78)

    ok = True
    if run("probe"):
        ok = step_probe(ctx, a.url)
        if not ok:
            print("\nFATAL: site probe failed. Nothing downstream can be trusted.")
            write_report(ctx, a.url, " ".join(sys.argv))
            sys.exit(2)
    else:
        print("\n[1/10] site probe — SKIPPED (required step; downstream will be thin)")

    if run("index"):
        if not step_index(ctx):
            print("\nFATAL: no product image index. Drop real pack shots into "
                  f"{ctx._rel(ctx.brand / 'product-images')} by hand and re-run.")
            if run("skeleton"):
                step_skeleton(ctx)
            write_report(ctx, a.url, " ".join(sys.argv))
            sys.exit(2)

    for name, fn in (("images", lambda: step_images(ctx, a.max_images)),
                     ("palette", lambda: step_palette(ctx)),
                     ("fonts", lambda: step_fonts(ctx)),
                     ("reviews", lambda: step_reviews(ctx, a.review_pages,
                                                      a.yotpo_products)),
                     ("claims", lambda: step_claims(ctx)),
                     ("packstrings", lambda: step_packstrings(
                         ctx, a.pack_ocr_shots, not a.no_pack_ocr)),
                     ("adlib", lambda: step_adlib(ctx, a.competitor, a.library_id, a.country)),
                     ("skeleton", lambda: step_skeleton(ctx))):
        if not run(name):
            print(f"\n[{STEPS.index(name) + 1}/10] {name} — SKIPPED")
            continue
        try:
            fn()
        except Exception as e:  # a bad site must not take the whole intake down
            ctx.gap(name, f"step crashed — {type(e).__name__}: {e}")

    if not a.dry_run:
        write_library_seed(ctx)
    write_report(ctx, a.url, " ".join(sys.argv))

    print("\n" + "=" * 78)
    wrote = sum(1 for _, s in ctx.writes if s == "wrote")
    would = sum(1 for _, s in ctx.writes if s.startswith("dry-run"))
    skipped = sum(1 for _, s in ctx.writes if s.startswith("skipped"))
    gaps = sum(len(r["gaps"]) for r in ctx.report.values())
    if ctx.dry:
        print(f"dry run complete  ·  {would} files would be written, {skipped} would be left "
              f"alone (already exist), {gaps} [GAP]s recorded  ·  nothing was written")
        print(f"a real run would write: {ctx.client / 'INTAKE-REPORT.md'}")
    else:
        print(f"intake complete  ·  {wrote} files written, {skipped} left alone (already existed), "
              f"{gaps} [GAP]s recorded")
        print(f"read: {ctx.client / 'INTAKE-REPORT.md'}")
    print("=" * 78)


if __name__ == "__main__":
    main()
