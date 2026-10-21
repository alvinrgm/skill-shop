#!/usr/bin/env python3
"""Render an ad candidate INTO a pixel-accurate Instagram surface.

    render_infeed.py <ad.png> [--surface feed|reels] [--out DIR]
                     [--no-detect] [--scales 1,2,3]

Statics only (PNG/JPG). Produces, per ad:
  01-first-encounter.png   the ad mid-viewport, as a scroller first meets it
  02-in-view.png           the ad fully in view with all chrome
  03-scrolled-past.png     60% scrolled past
  chrome-overlay.png       transparent-slot chrome layer (a geometry proof)
  collision.json / .md     geometric chrome-collision report

The collision report computes OVERLAP GEOMETRICALLY from the chrome rects in
geometry.py against detected element boxes. Nothing is eyeballed.

HONESTY RAIL: this harness shows you how the ad is ENCOUNTERED. It does not
judge whether the ad is any good. Nobody stops scrolling because the safe zone
was respected.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

# Re-run under the package's own .venv when one exists (config.py does that at import).
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
import config as _pkg_config  # noqa: E402,F401

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import geometry as G  # noqa: E402
import chrome_html as CH  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
# Neighbour posts: any images in your harvested inspo corpus (AD_LOOP_HOME/inspo), so the
# candidate is judged in company. With no corpus, neutral placeholder cards are generated.
WORK = Path(os.path.expanduser(os.environ.get("AD_LOOP_HOME") or str(Path.home() / "ad-loop-work")))
CORPUS = WORK / "inspo"
IMG_EXT = {".jpg", ".jpeg", ".png", ".webp"}


def sh(cmd: list[str]) -> str:
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"{' '.join(cmd[:3])}... failed:\n{r.stderr[-1500:]}")
    return r.stdout


def probe(path: Path) -> dict:
    out = sh(["ffprobe", "-v", "error", "-select_streams", "v:0",
              "-show_entries", "stream=width,height",
              "-of", "json", str(path)])
    st = json.loads(out)["streams"][0]
    return {"w": int(st["width"]), "h": int(st["height"])}


def _placeholder(out_dir: Path, i: int) -> Path:
    """A neutral, photo-like gradient card: organic-feed stand-in when no corpus exists."""
    from PIL import Image, ImageFilter
    import random
    rnd = random.Random(i)
    base = [(196, 182, 160), (150, 168, 176), (176, 160, 150)][i % 3]
    im = Image.new("RGB", (540, 675), base)
    px = im.load()
    for y in range(675):
        for x in range(0, 540, 3):
            k = 0.75 + 0.35 * (y / 675) + rnd.uniform(-0.03, 0.03)
            c = tuple(max(0, min(255, int(v * k))) for v in base)
            for dx in range(3):
                if x + dx < 540:
                    px[x + dx, y] = c
    p = out_dir / f"_neighbour{i}.jpg"
    im.filter(ImageFilter.GaussianBlur(6)).save(p, quality=88)
    return p


def pick_neighbours(exclude: str, n: int = 2, out_dir: Path | None = None) -> list[Path]:
    out = []
    if CORPUS.is_dir():
        for p in sorted(CORPUS.rglob("*")):
            if p.suffix.lower() in IMG_EXT and exclude.lower() not in str(p).lower():
                out.append(p)
            if len(out) >= n:
                break
    i = 0
    while len(out) < n and out_dir is not None:
        out.append(_placeholder(out_dir, i))
        i += 1
    return out[:n]



# ------------------------------------------------------- scroll math ----
def feed_layout(ad_media_h: float) -> dict:
    """Track geometry for the feed, in scroll-container-local px."""
    nb_post = (G.FEED_HEADER_H + 487.5 + G.FEED_ACTION_RAIL_H
               + G.FEED_LIKES_H + G.FEED_CAPTION_H + 14)
    ad_post = (G.FEED_HEADER_H + ad_media_h + G.FEED_CTA_H
               + G.FEED_ACTION_RAIL_H + G.FEED_LIKES_H + G.FEED_CAPTION_H + 14)
    view_h = G.VIEWPORT_H - G.STATUS_BAR_H - G.FEED_TOP_BAR_H
    # the bottom nav floats OVER the scroll area, so the genuinely unobscured
    # height is smaller than the scroll container
    clear_h = view_h - G.BOTTOM_NAV_H
    ad_top = nb_post
    first = ad_top - view_h * G.FIRST_ENCOUNTER_TOP_FRAC
    inview = (ad_top - 8 if ad_post <= clear_h - 16
              else ad_top + G.FEED_HEADER_H + ad_media_h / 2 - clear_h / 2)
    return {"first": max(0.0, first), "inview": max(0.0, inview),
            "past": max(0.0, inview + G.SCROLLED_PAST_FRAC * ad_post),
            "ad_post_h": ad_post, "view_h": view_h}


def reels_layout() -> dict:
    slide, ad_top = G.VIEWPORT_H, G.VIEWPORT_H
    return {"first": ad_top - G.VIEWPORT_H * G.FIRST_ENCOUNTER_TOP_FRAC,
            "inview": ad_top,
            "past": ad_top + G.SCROLLED_PAST_FRAC * slide,
            "ad_post_h": slide, "view_h": G.VIEWPORT_H}


# ---------------------------------------------------------- rendering ----
def render(surface: str, ad_uri: str, ad_media_h: float, nb_uris: list[str],
           brand: str, cta: str, caption: str, offset: float,
           out_png: Path, scale: int, slot: bool = False):
    from playwright.sync_api import sync_playwright
    if surface == "reels":
        body = CH.build_reels(ad_uri, nb_uris, brand, cta, caption, offset, slot)
    else:
        body = CH.build_feed(ad_uri, ad_media_h, nb_uris, brand, cta, caption,
                             offset, slot)
    html = CH.page(surface, body, transparent=slot)
    # Write to a real file and goto() it: a page served from about:blank via
    # set_content cannot load file:// subresources, so every <img> comes back
    # as a broken-image glyph. This cost an hour once; do not "simplify" it.
    tmp = out_png.parent / f"_{out_png.stem}.html"
    tmp.write_text(html)
    try:
        with sync_playwright() as p:
            b = p.chromium.launch(args=["--force-color-profile=srgb",
                                        "--allow-file-access-from-files"])
            pg = b.new_page(viewport={"width": G.VIEWPORT_W,
                                      "height": G.VIEWPORT_H},
                            device_scale_factor=scale)
            pg.goto(tmp.resolve().as_uri(), wait_until="load")
            pg.wait_for_timeout(350)
            pg.screenshot(path=str(out_png), omit_background=slot)
            b.close()
    finally:
        tmp.unlink(missing_ok=True)


def uri(p: Path) -> str:
    return p.resolve().as_uri()


# -------------------------------------------------------- collision ----
def _ov(a: dict, b: dict) -> float:
    x1, y1 = max(a["x"], b["x"]), max(a["y"], b["y"])
    x2 = min(a["x"] + a["w"], b["x"] + b["w"])
    y2 = min(a["y"] + a["h"], b["y"] + b["h"])
    return max(0.0, x2 - x1) * max(0.0, y2 - y1)


def collision_report(asset: Path, aw: int, ah: int, surface: str,
                     detect: bool, model: str) -> dict:
    box = G.fit(aw, ah, surface)
    zones: list[tuple[str, dict, str]] = []

    # zones carry an opacity so severity matches what the chrome really does:
    # the tab bar and a crop destroy pixels, a caption scrim degrades them.
    opac: dict[str, float] = {}
    for r in G.CHROME[surface]:
        if not r.overlays_creative:
            continue
        a = G.to_asset_space(r, box)
        if a:
            zones.append((f"chrome:{r.name}",
                          {"x": a[0], "y": a[1], "w": a[2], "h": a[3]},
                          r.confidence))
            opac[f"chrome:{r.name}"] = r.opacity
    sz = G.safe_zone_asset(aw, ah, surface)
    for k in ("top", "bottom", "left", "right"):
        zones.append((f"meta_safe:{k}", sz[k], "high"))
    fold = G.fold_crop(aw, ah, surface)
    if fold:
        zones.append(("fold:below_first_encounter",
                      {k: fold[k] for k in ("x", "y", "w", "h")}, "medium"))
        opac["fold:below_first_encounter"] = 1.0

    # cover-fill side crop is a real loss of pixels, report it as a zone
    if box["x"] < 0:
        crop_w = -box["x"] / box["scale"]
        zones.append(("crop:left", {"x": 0, "y": 0, "w": crop_w, "h": ah}, "high"))
        zones.append(("crop:right", {"x": aw - crop_w, "y": 0, "w": crop_w,
                                     "h": ah}, "high"))
        opac["crop:left"] = opac["crop:right"] = 1.0

    rep = {
        "asset": str(asset), "asset_px": [aw, ah], "surface": surface,
        "fit": {k: round(v, 2) for k, v in box.items()},
        "zones": [{"zone": n, "rect": {k: round(v, 1) for k, v in r.items()},
                   "confidence": c} for n, r, c in zones],
        "elements": [], "hits": [], "detected": detect,
    }
    if fold:
        rep["fold_visible_frac"] = round(fold["visible_frac"], 3)

    if not detect:
        rep["note"] = ("element detection SKIPPED (--no-detect): zones are "
                       "reported but nothing was measured against them.")
        return rep

    from lib.gemini import localize
    els = localize(asset, aw, ah, model=model)
    rep["elements"] = [{k: (round(v, 1) if isinstance(v, float) else v)
                        for k, v in e.items()} for e in els]
    for e in els:
        area = max(1.0, e["w"] * e["h"])
        for name, z, conf in zones:
            frac = _ov(e, z) / area
            if frac > 0.02:
                op = opac.get(name, 1.0)
                eff = frac * op
                rep["hits"].append({
                    "element": e["label"], "kind": e["kind"],
                    "criticality": e["criticality"], "zone": name,
                    "covered_frac": round(frac, 3),
                    "zone_opacity": op, "effective_frac": round(eff, 3),
                    "severity": ("destroyed" if eff >= 0.5
                                 else "degraded" if eff >= 0.25 else "grazed"),
                    "zone_confidence": conf,
                })
    rep["hits"].sort(key=lambda h: -h["covered_frac"])
    # Two very different things get called a "collision", and conflating them
    # made an elite ad look broken on the first calibration pass:
    #   OBSCURED - real chrome or a real crop physically covers the element.
    #   MARGIN   - the element merely sits inside Meta's advisory safe-zone
    #              band, or below the first-encounter fold. Common, and normal
    #              for a product; only a problem for text/logo/CTA.
    def _obscuring(z: str) -> bool:
        return z.startswith("chrome:") or z.startswith("crop:")

    obscured = [h for h in rep["hits"] if _obscuring(h["zone"])
                and h["effective_frac"] >= 0.25
                and (h["kind"] in ("text", "cta", "logo", "badge")
                     or h["criticality"] == "critical")]
    margin = [h for h in rep["hits"] if not _obscuring(h["zone"])
              and h["covered_frac"] >= 0.25]
    rep["obscured"] = obscured
    rep["margin"] = margin
    rep["critical_hits"] = [h for h in obscured
                            if h["criticality"] == "critical"]
    rep["verdict"] = ("COLLISION" if obscured
                      else "advisory" if margin else "clear")
    return rep


def collision_md(rep: dict) -> str:
    L = [f"# Chrome-collision report — {Path(rep['asset']).name}", "",
         f"surface **{rep['surface']}** · asset {rep['asset_px'][0]}x"
         f"{rep['asset_px'][1]} · verdict **{rep.get('verdict','n/a')}**", ""]
    if "fold_visible_frac" in rep:
        L += [f"At first encounter only **{rep['fold_visible_frac']:.0%}** of "
              f"the creative is on screen.", ""]
    if not rep["detected"]:
        L += ["_" + rep.get("note", "") + "_", ""]
    if rep.get("obscured"):
        L += ["## Physically obscured (chrome or crop covers it)", "",
              "| element | crit | zone | covered | opacity | severity | conf |",
              "|---|---|---|---|---|---|---|"]
        for h in rep["obscured"][:20]:
            L.append(f"| {h['element'][:40]} | {h['criticality']} | "
                     f"{h['zone']} | {h['covered_frac']:.0%} | "
                     f"{h['zone_opacity']:.2f} | {h['severity']} | "
                     f"{h['zone_confidence']} |")
        L += ["", "_A `bottom_scrim` collision is worse than the opacity "
              "suggests: Instagram draws its OWN caption text there, so your "
              "text competes with white UI type, not just a scrim._", ""]
    if rep.get("margin"):
        L += ["## Inside an advisory band (Meta safe zone / below the fold)",
              "", "| element | crit | zone | covered |", "|---|---|---|---|"]
        for h in rep["margin"][:20]:
            L.append(f"| {h['element'][:44]} | {h['criticality']} | "
                     f"{h['zone']} | {h['covered_frac']:.0%} |")
        L.append("")
    if rep["detected"] and not rep.get("obscured") and not rep.get("margin"):
        L.append("No element overlaps any chrome rect or safe-zone band.")
    L += ["", "---", "",
          "Overlap is computed geometrically from `geometry.py` rects against "
          "detected element boxes. Meta safe-zone rows are Meta-published "
          "(high confidence); `chrome:*` rows use estimated component heights "
          "(see geometry.py). **This report says nothing about whether the ad "
          "is good.**"]
    return "\n".join(L)


# --------------------------------------------------------------- main ----
def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("ad")
    ap.add_argument("--surface", choices=["feed", "reels"], default=None,
                    help="default: auto (9:16 -> reels, else feed)")
    ap.add_argument("--out", default=None)
    ap.add_argument("--brand", default="yourbrand")
    ap.add_argument("--cta", default="Shop now")
    ap.add_argument("--caption", default="the one we keep coming back to")
    ap.add_argument("--scales", default="1,3")
    ap.add_argument("--no-detect", action="store_true")
    ap.add_argument("--model", default="gemini-2.5-flash")
    a = ap.parse_args()

    ad = Path(a.ad).expanduser().resolve()
    if not ad.exists():
        sys.exit(f"no such ad: {ad}")
    if ad.suffix.lower() not in IMG_EXT:
        sys.exit(f"statics only: expected one of {sorted(IMG_EXT)}, got {ad.name}")
    meta = probe(ad)
    aw, ah = meta["w"], meta["h"]
    ar = ah / aw
    surface = a.surface or ("reels" if ar > 1.6 else "feed")
    out = Path(a.out).expanduser() if a.out else ROOT / "out" / ad.stem
    out.mkdir(parents=True, exist_ok=True)
    scales = [int(s) for s in a.scales.split(",") if s.strip()]

    print(f"[{ad.name}] {aw}x{ah} ar={ar:.2f} static -> surface={surface}")

    still = ad

    nbs = pick_neighbours(a.brand, 2, out_dir=out)
    if len(nbs) < 2:
        sys.exit("could not find or make 2 neighbour frames")
    print(f"  neighbours: {', '.join(n.parent.parent.name + '/' + n.name for n in nbs)}")
    nb_uris = [uri(n) for n in nbs]

    box = G.fit(aw, ah, surface)
    ad_media_h = box["h"] if surface == "feed" else G.VIEWPORT_H
    lay = feed_layout(ad_media_h) if surface == "feed" else reels_layout()

    shots = [("01-first-encounter", lay["first"]),
             ("02-in-view", lay["inview"]),
             ("03-scrolled-past", lay["past"])]
    made = []
    for name, off in shots:
        for s in scales:
            sfx = "" if s == 1 else f"@{s}x"
            p = out / f"{name}{sfx}.png"
            render(surface, uri(still), ad_media_h, nb_uris, a.brand, a.cta,
                   a.caption, off, p, s)
            made.append(p)
        print(f"  {name}: offset {off:.0f}px -> "
              f"{', '.join(str(s)+'x' for s in scales)}")

    # transparent chrome layer, as a geometry proof
    chrome_png = out / "chrome-overlay.png"
    render(surface, uri(still), ad_media_h, nb_uris, a.brand, a.cta, a.caption,
           lay["inview"], chrome_png, 3, slot=True)
    made.append(chrome_png)
    print(f"  chrome-overlay.png (3x, transparent slot)")

    rep = collision_report(still, aw, ah, surface,
                           detect=not a.no_detect, model=a.model)
    (out / "collision.json").write_text(json.dumps(rep, indent=2))
    (out / "collision.md").write_text(collision_md(rep))
    made += [out / "collision.json", out / "collision.md"]
    print(f"  collision: {rep.get('verdict','n/a')} "
          f"({len(rep['hits'])} overlaps, "
          f"{len(rep.get('critical_hits',[]))} critical)")
    print(f"  -> {out}")


if __name__ == "__main__":
    main()
