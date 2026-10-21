#!/usr/bin/env python3
"""HTML/CSS mock of the Instagram feed and Reels surfaces at true phone scale.

All dimensions come from ../geometry.py - nothing here invents a pixel. The
page is built at exactly VIEWPORT_W x VIEWPORT_H CSS px and screenshotted at
1x/2x/3x by the renderer.

Two render modes:
  "full"        - the whole believable surface (used for judgment screenshots)
  "chrome_only" - chrome drawn over a TRANSPARENT creative slot, so the PNG can
                  be overlaid onto any creative as a geometry proof.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import geometry as G  # noqa: E402

# --- inline SVG icons, stroked to read like IG's at 24-27px --------------
_H = ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
      'stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">')
IC = {
    "heart": _H + '<path d="M12 20.5S3.5 15 3.5 9.2A4.7 4.7 0 0 1 12 6.6a4.7 4.7 0 0 1 8.5 2.6c0 5.8-8.5 11.3-8.5 11.3z"/></svg>',
    "comment": _H + '<path d="M20.5 11.7c0 4.3-3.8 7.8-8.5 7.8a9.6 9.6 0 0 1-2.9-.45L4 20.5l1.5-3.7A7.5 7.5 0 0 1 3.5 11.7c0-4.3 3.8-7.8 8.5-7.8s8.5 3.5 8.5 7.8z"/></svg>',
    "share": _H + '<path d="M21.5 3.5 2.5 10.2l7.4 2.9 2.9 7.4z"/><path d="M21.5 3.5 9.9 13.1"/></svg>',
    "bookmark": _H + '<path d="M6 3.5h12v17l-6-4.4-6 4.4z"/></svg>',
    "more": _H + '<circle cx="12" cy="5.5" r="1.2" fill="currentColor"/><circle cx="12" cy="12" r="1.2" fill="currentColor"/><circle cx="12" cy="18.5" r="1.2" fill="currentColor"/></svg>',
    "dots_h": _H + '<circle cx="5.5" cy="12" r="1.2" fill="currentColor"/><circle cx="12" cy="12" r="1.2" fill="currentColor"/><circle cx="18.5" cy="12" r="1.2" fill="currentColor"/></svg>',
    "camera": _H + '<rect x="2.8" y="6.2" width="18.4" height="14" rx="3.4"/><circle cx="12" cy="13.2" r="3.7"/><path d="M8.4 6.2 9.9 3.6h4.2l1.5 2.6"/></svg>',
    "home": _H + '<path d="M3.5 10.4 12 3.5l8.5 6.9V20a.6.6 0 0 1-.6.6h-4.6v-6h-6.6v6H4.1a.6.6 0 0 1-.6-.6z"/></svg>',
    "search": _H + '<circle cx="10.8" cy="10.8" r="7"/><path d="M15.9 15.9 20.5 20.5"/></svg>',
    "reelsicon": _H + '<rect x="2.8" y="2.8" width="18.4" height="18.4" rx="4.4"/><path d="M2.8 8.6h18.4M8.6 2.8 11.6 8.6M15.1 2.8 18.1 8.6"/><path d="M10.2 12.1v5l4.3-2.5z"/></svg>',
    "shop": _H + '<path d="M3.5 8.2h17l-1.4 11.1a1.4 1.4 0 0 1-1.4 1.2H6.3a1.4 1.4 0 0 1-1.4-1.2z"/><path d="M8.4 8.2V6.4a3.6 3.6 0 0 1 7.2 0v1.8"/></svg>',
    "chev": _H + '<path d="M9 5.5 15.5 12 9 18.5"/></svg>',
    "audio": _H + '<path d="M9 17.5V5.2l9-1.7v12"/><circle cx="6.6" cy="17.9" r="2.6"/><circle cx="15.6" cy="15.8" r="2.6"/></svg>',
}

# iOS status bar: time + cell/wifi/battery glyphs
STATUS_SVG = ('<svg width="78" height="13" viewBox="0 0 78 13" fill="none">'
              '<path d="M1 9.5h2.2v3H1zM5.4 7.4h2.2v5.1H5.4zM9.8 5h2.2v7.5H9.8z'
              'M14.2 2.4h2.2v10.1h-2.2z" fill="currentColor"/>'
              '<path d="M28.6 4.2a9.3 9.3 0 0 1 12.4 0M31 6.9a5.8 5.8 0 0 1 7.6 0'
              'M33.4 9.5a2.4 2.4 0 0 1 2.8 0" stroke="currentColor" '
              'stroke-width="1.7" stroke-linecap="round"/>'
              '<rect x="53" y="2.2" width="21" height="10.2" rx="3" '
              'stroke="currentColor" stroke-opacity=".45" stroke-width="1.1"/>'
              '<rect x="54.5" y="3.7" width="15" height="7.2" rx="1.9" '
              'fill="currentColor"/><path d="M75.6 5.9v3" stroke="currentColor" '
              'stroke-opacity=".45" stroke-width="1.7" stroke-linecap="round"/>'
              '</svg>')


def _css() -> str:
    return f"""
*{{margin:0;padding:0;box-sizing:border-box;}}
html,body{{width:{G.VIEWPORT_W}px;height:{G.VIEWPORT_H}px;overflow:hidden;}}
body{{font-family:-apple-system,"SF Pro Text","Helvetica Neue",Helvetica,Arial,sans-serif;
  -webkit-font-smoothing:antialiased;background:#000;color:#fff;}}
.phone{{position:relative;width:{G.VIEWPORT_W}px;height:{G.VIEWPORT_H}px;overflow:hidden;}}
svg{{display:block;width:100%;height:100%;}}
.ic{{width:24px;height:24px;flex:none;}}

/* ---- status bar ---- */
.status{{position:absolute;top:0;left:0;right:0;height:{G.STATUS_BAR_H}px;
  display:flex;align-items:center;justify-content:space-between;
  padding:0 26px 0 30px;z-index:60;pointer-events:none;}}
.status .t{{font-size:15px;font-weight:600;letter-spacing:.2px;
  font-family:-apple-system,"SF Pro Text",sans-serif;}}
.status .g{{width:78px;height:13px;}}
.status .g svg{{width:78px;height:13px;}}

/* ---- bottom nav ---- */
.nav{{position:absolute;left:0;right:0;bottom:0;height:{G.BOTTOM_NAV_H}px;z-index:55;}}
.nav .row{{height:{G.TAB_BAR_H}px;display:flex;align-items:center;
  justify-content:space-around;padding:0 14px;}}
.nav .ic{{width:25px;height:25px;}}
.nav .pfp{{width:24px;height:24px;border-radius:50%;border:1.4px solid currentColor;
  background:linear-gradient(135deg,#8e8e93,#3a3a3c);flex:none;}}
.homebar{{position:absolute;bottom:8px;left:50%;transform:translateX(-50%);
  width:134px;height:5px;border-radius:3px;}}

/* ================= FEED ================= */
.feed .phone{{background:#000;}}
.igtop{{position:absolute;top:{G.STATUS_BAR_H}px;left:0;right:0;
  height:{G.FEED_TOP_BAR_H}px;display:flex;align-items:center;
  justify-content:space-between;padding:0 16px;z-index:50;
  background:#000;border-bottom:.5px solid #1c1c1e;}}
.wordmark{{font-family:"Snell Roundhand","Segoe Script",cursive;
  font-size:26px;font-weight:600;letter-spacing:.3px;line-height:1;
  padding-bottom:4px;}}
.igtop .r{{display:flex;gap:18px;}}
.scroll{{position:absolute;top:{G.STATUS_BAR_H + G.FEED_TOP_BAR_H}px;left:0;
  right:0;bottom:0;overflow:hidden;}}
.track{{position:absolute;left:0;right:0;top:0;}}
.post{{background:#000;}}
.phead{{height:{G.FEED_HEADER_H}px;display:flex;align-items:center;
  gap:10px;padding:0 12px;}}
.av{{width:{G.FEED_AVATAR}px;height:{G.FEED_AVATAR}px;border-radius:50%;
  flex:none;background:#3a3a3c;background-size:cover;background-position:center;
  box-shadow:0 0 0 1.5px #000,0 0 0 3px #d62976;}}
.av.plain{{box-shadow:none;border:.5px solid #2c2c2e;}}
.pmeta{{flex:1;min-width:0;}}
.pn{{font-size:13px;font-weight:600;line-height:1.25;}}
.ps{{font-size:11.5px;color:#a8a8a8;line-height:1.25;}}
.media{{width:{G.VIEWPORT_W}px;background:#111;display:block;}}
.media img{{width:100%;display:block;}}
.ctarow{{height:{G.FEED_CTA_H}px;display:flex;align-items:center;
  justify-content:space-between;padding:0 14px;background:#1c1c1e;}}
.ctarow .l{{font-size:13.5px;font-weight:600;}}
.ctarow .c{{width:18px;height:18px;color:#a8a8a8;}}
.arail{{height:{G.FEED_ACTION_RAIL_H}px;display:flex;align-items:center;
  gap:15px;padding:0 12px;}}
.arail .sp{{flex:1;}}
.likes{{height:{G.FEED_LIKES_H}px;padding:0 12px;font-size:12.5px;
  font-weight:600;line-height:{G.FEED_LIKES_H}px;}}
.cap{{height:{G.FEED_CAPTION_H}px;padding:0 12px;font-size:12.5px;
  line-height:1.42;color:#fff;overflow:hidden;}}
.cap .u{{font-weight:600;}}
.cap .m{{color:#8e8e93;}}
.gap{{height:14px;}}

/* ================= REELS ================= */
.reels .phone{{background:#000;}}
.rtrack{{position:absolute;left:0;right:0;top:0;}}
.rslide{{position:relative;width:{G.VIEWPORT_W}px;height:{G.VIEWPORT_H}px;
  overflow:hidden;background:#000;}}
.rmedia{{position:absolute;inset:0;overflow:hidden;}}
/* BUG FIXED (found on a 9:16 re-layout).
   This rule was `min-width:100%;min-height:100%;object-fit:cover` with NO width/height.
   `object-fit` only has an effect on a replaced element that HAS a box; with only minimums
   set, the <img> laid out at its NATURAL size and the slide showed a 1:1 CENTRE CROP of the
   asset instead of a cover-fill. On a 1080x1920 still that meant the mock showed asset rows
   538..1382 at 1:1 — the headline was off-screen entirely — while geometry.fit() (used by
   the collision REPORT) correctly said scale 0.4396 with 96.4px cropped off each side.
   Report right, picture wrong, so nothing ever contradicted anything: the reels pictures
   were the only artifact that was lying, and only a still large enough to notice exposed it.
   The feed branch (.media img) was always correct and is untouched. */
.rmedia img{{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);
  width:100%;height:100%;object-fit:cover;}}
.rscrim-t{{position:absolute;top:0;left:0;right:0;height:150px;
  background:linear-gradient(180deg,rgba(0,0,0,.42),transparent);}}
.rscrim-b{{position:absolute;bottom:0;left:0;right:0;
  height:{G.REELS_BOTTOM_CHROME_H + 60}px;
  background:linear-gradient(0deg,rgba(0,0,0,.72) 24%,transparent);}}
.rtop{{position:absolute;top:{G.STATUS_BAR_H}px;left:0;right:0;
  height:{G.REELS_TOP_ROW_H}px;display:flex;align-items:center;
  justify-content:space-between;padding:0 16px;z-index:30;}}
.rtop .ti{{font-size:20px;font-weight:700;letter-spacing:-.2px;}}
.rrail{{position:absolute;
  right:{G.REELS_RAIL_RIGHT_MARGIN}px;
  bottom:{G.REELS_RAIL_BOTTOM_GAP}px;
  width:{G.REELS_RAIL_W}px;height:{G.REELS_RAIL_H}px;z-index:30;
  display:flex;flex-direction:column;align-items:center;
  justify-content:space-between;}}
.rrail .it{{display:flex;flex-direction:column;align-items:center;gap:3px;}}
.rrail .ic{{width:{G.REELS_RAIL_ICON}px;height:{G.REELS_RAIL_ICON}px;
  filter:drop-shadow(0 1px 3px rgba(0,0,0,.55));}}
.rrail .n{{font-size:11px;font-weight:600;
  text-shadow:0 1px 3px rgba(0,0,0,.6);}}
.disc{{width:26px;height:26px;border-radius:6px;border:1.5px solid #fff;
  background:linear-gradient(135deg,#5a5a5e,#232326);}}
.rbot{{position:absolute;left:0;bottom:{G.BOTTOM_NAV_H}px;
  width:{G.VIEWPORT_W - G.REELS_RAIL_W - G.REELS_RAIL_RIGHT_MARGIN - 8}px;
  padding:0 12px;z-index:30;}}
.ruser{{height:{G.REELS_USERNAME_ROW_H}px;display:flex;align-items:center;gap:9px;}}
.ruser .av{{width:28px;height:28px;box-shadow:none;border:1px solid #fff;}}
.ruser .n{{font-size:13.5px;font-weight:600;
  text-shadow:0 1px 3px rgba(0,0,0,.5);}}
.follow{{font-size:12.5px;font-weight:600;padding:4px 11px;
  border:1px solid rgba(255,255,255,.75);border-radius:7px;}}
.rcap{{height:{G.REELS_CAPTION_H}px;font-size:12.5px;line-height:1.42;
  overflow:hidden;text-shadow:0 1px 3px rgba(0,0,0,.5);}}
.rcap .m{{color:#d1d1d6;}}
.raud{{height:{G.REELS_AUDIO_TICKER_H}px;display:flex;align-items:center;
  gap:6px;font-size:11.5px;text-shadow:0 1px 3px rgba(0,0,0,.5);}}
.raud .ic{{width:12px;height:12px;}}
.rcta{{height:{G.REELS_CTA_H - 10}px;margin:5px 0;
  background:rgba(255,255,255,.16);backdrop-filter:blur(12px);
  border:.5px solid rgba(255,255,255,.28);border-radius:9px;
  display:flex;align-items:center;justify-content:space-between;
  padding:0 13px;font-size:13.5px;font-weight:600;}}
.rcta .c{{width:16px;height:16px;opacity:.85;}}
.spon{{font-size:11.5px;color:#e5e5ea;font-weight:500;}}

/* creative slot, transparent in chrome_only mode.
   Every ancestor that paints a background must be cleared too, or the PNG
   comes out opaque black and the composited creative is invisible underneath. */
.slot-transparent{{background:transparent !important;}}
.slot-transparent img{{visibility:hidden;}}
body.slot .phone,body.slot .rslide,body.slot .post,body.slot .scroll,
body.slot .track,body.slot .rtrack,body.slot .media{{background:transparent !important;}}
body.slot{{background:transparent !important;}}
"""


def _status(dark: bool = True) -> str:
    return (f'<div class="status"><div class="t">9:41</div>'
            f'<div class="g">{STATUS_SVG}</div></div>')


def _nav(surface: str) -> str:
    active = "reelsicon" if surface == "reels" else "home"
    items = ["home", "search", "reelsicon", "shop"]
    cells = ""
    for k in items:
        op = "1" if k == active else ".92"
        sw = "2.4" if k == active else "1.8"
        svg = IC[k].replace('stroke-width="1.8"', f'stroke-width="{sw}"')
        cells += f'<div class="ic" style="opacity:{op}">{svg}</div>'
    cells += '<div class="pfp"></div>'
    bg = ("background:linear-gradient(0deg,#000 60%,rgba(0,0,0,.86));"
          if surface == "reels" else
          "background:#000;border-top:.5px solid #1c1c1e;")
    return (f'<div class="nav" style="{bg}"><div class="row">{cells}</div>'
            f'<div class="homebar" style="background:#fff"></div></div>')


# ------------------------------------------------------------- feed ----
def _feed_post(img_src: str, user: str, sponsored: bool, cta: str,
               caption: str, likes: str, media_h: float,
               slot: bool = False) -> str:
    sub = ('<div class="ps">Sponsored</div>' if sponsored
           else '<div class="ps">Original audio</div>')
    ctarow = (f'<div class="ctarow"><div class="l">{cta}</div>'
              f'<div class="c">{IC["chev"]}</div></div>') if sponsored else ""
    avcls = "av" if sponsored else "av plain"
    slotcls = " slot-transparent" if slot else ""
    return f"""
<div class="post">
  <div class="phead">
    <div class="{avcls}"></div>
    <div class="pmeta"><div class="pn">{user}</div>{sub}</div>
    <div class="ic" style="width:20px;height:20px">{IC['dots_h']}</div>
  </div>
  <div class="media{slotcls}" style="height:{media_h:.1f}px">
    <img src="{img_src}" style="height:{media_h:.1f}px;object-fit:cover"/>
  </div>
  {ctarow}
  <div class="arail">
    <div class="ic">{IC['heart']}</div>
    <div class="ic">{IC['comment']}</div>
    <div class="ic">{IC['share']}</div>
    <div class="sp"></div>
    <div class="ic">{IC['bookmark']}</div>
  </div>
  <div class="likes">{likes} likes</div>
  <div class="cap"><span class="u">{user}</span> {caption}
    <span class="m">... more</span></div>
  <div class="gap"></div>
</div>"""


def build_feed(ad_src: str, ad_media_h: float, neighbors: list[str],
               brand: str, cta: str, caption: str,
               offset_y: float, slot: bool = False) -> str:
    """offset_y = px the track is scrolled up (higher = further down feed)."""
    n0 = _feed_post(neighbors[0], "weekend.kitchen", False, "",
                    "sunday reset, third attempt and finally got it right",
                    "1,204", 487.5)
    ad = _feed_post(ad_src, brand, True, cta, caption, "2,918", ad_media_h,
                    slot=slot)
    n1 = _feed_post(neighbors[1] if len(neighbors) > 1 else neighbors[0],
                    "the.slow.journal", False, "",
                    "notes from this week", "863", 487.5)
    return f"""<div class="phone">
  <div class="scroll">
    <div class="track" style="transform:translateY({-offset_y:.1f}px)">
      {n0}{ad}{n1}
    </div>
  </div>
  <div class="igtop"><div class="wordmark">Instagram</div>
    <div class="r"><div class="ic">{IC['heart']}</div>
      <div class="ic">{IC['share']}</div></div></div>
  {_status()}
  {_nav('feed')}
</div>"""


# ------------------------------------------------------------ reels ----
def _reel_slide(img_src: str, user: str, sponsored: bool, cta: str,
                caption: str, slot: bool = False) -> str:
    slotcls = " slot-transparent" if slot else ""
    ctablock = (f'<div class="rcta"><span>{cta}</span>'
                f'<div class="c">{IC["chev"]}</div></div>') if sponsored else ""
    spon = '<div class="spon">Sponsored</div>' if sponsored else ""
    follow = '<div class="follow">Follow</div>'
    aud = ("Sponsored &middot; " + user) if sponsored else "original audio"
    return f"""
<div class="rslide">
  <div class="rmedia{slotcls}"><img src="{img_src}"/></div>
  <div class="rscrim-t"></div><div class="rscrim-b"></div>
  <div class="rtop"><div class="ti">Reels</div>
    <div class="ic">{IC['camera']}</div></div>
  <div class="rrail">
    <div class="it"><div class="ic">{IC['heart']}</div><div class="n">14.2K</div></div>
    <div class="it"><div class="ic">{IC['comment']}</div><div class="n">318</div></div>
    <div class="it"><div class="ic">{IC['share']}</div><div class="n">1,904</div></div>
    <div class="it"><div class="ic">{IC['more']}</div></div>
    <div class="disc"></div>
  </div>
  <div class="rbot">
    <div class="ruser"><div class="av"></div><div class="n">{user}</div>
      {follow}</div>
    {spon}
    <div class="rcap">{caption} <span class="m">... more</span></div>
    <div class="raud"><div class="ic">{IC['audio']}</div><span>{aud}</span></div>
    {ctablock}
  </div>
  {_nav('reels')}
  {_status()}
</div>"""


def build_reels(ad_src: str, neighbors: list[str], brand: str, cta: str,
                caption: str, offset_y: float, slot: bool = False) -> str:
    prev = _reel_slide(neighbors[0], "home.and.hearth", False, "",
                       "weekend market haul")
    ad = _reel_slide(ad_src, brand, True, cta, caption, slot=slot)
    nxt = _reel_slide(neighbors[1] if len(neighbors) > 1 else neighbors[0],
                      "made.slow", False, "", "old way vs new way, side by side")
    return f"""<div class="phone">
  <div class="rtrack" style="transform:translateY({-offset_y:.1f}px)">
    {prev}{ad}{nxt}
  </div>
</div>"""


def page(surface: str, body: str, transparent: bool = False) -> str:
    bg = "transparent" if transparent else "#000"
    cls = f"{surface} slot" if transparent else surface
    return f"""<!doctype html><html><head><meta charset="utf-8">
<style>{_css()}
html,body{{background:{bg} !important;}}
</style></head><body class="{cls}">{body}</body></html>"""
