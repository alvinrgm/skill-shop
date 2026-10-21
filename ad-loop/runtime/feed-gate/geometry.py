#!/usr/bin/env python3
"""Single source of truth for Instagram surface geometry.

Every chrome rect, safe zone, and scroll position used by feedmock/ and
ablate.py comes from HERE. Nothing downstream hardcodes a pixel.

HONESTY ABOUT THESE NUMBERS
---------------------------
Two very different classes of number live in this file:

  1. META-PUBLISHED (confidence: high). Meta's own ads guide states, verbatim,
     to leave "roughly 14% of the top, 35% of the bottom, and 6% on each side"
     of a 9:16 Reels asset free of text/logos/key creative. That is the
     load-bearing constraint and it is defined on the ASSET, not the device,
     so it survives every letterbox-vs-cover-fill question.
     Source: facebook.com/business/ads-guide/update/video/facebook-facebook-reels
     Stories is lighter (20% bottom); we design to Reels' 35% as the strict case.

  2. COMPONENT ESTIMATES (confidence: low, tagged UNVERIFIED). Instagram does
     not publish the height of its top bar, post header, action rail, or CTA
     row. The values below are estimates from teardowns + iOS conventions.
     They are here as ONE tunable block precisely because they are soft: if
     someone measures a real 3x screenshot, they change these constants and
     every downstream report updates. Do not treat them as measured fact.

  Device metrics (status bar 47pt, tab bar 49pt, home indicator 34pt) are
  Apple-derived and reliable. 390x844 = iPhone 12/13/14 (notch class).
  Dynamic Island devices are 393x852 with a 54pt status bar - not modeled.
"""
from __future__ import annotations

from dataclasses import dataclass, field

# ---------------------------------------------------------------- device ----
VIEWPORT_W = 390
VIEWPORT_H = 844

STATUS_BAR_H = 47        # Apple, notch class            [high]
TAB_BAR_H = 49           # iOS standard tab bar          [high]
HOME_INDICATOR_H = 34    # Apple safe-area bottom inset  [high]
BOTTOM_NAV_H = TAB_BAR_H + HOME_INDICATOR_H  # 83


# ------------------------------------------------------------ meta spec ----
# Fractions of the ASSET frame. Meta-published, 9:16 creative.
META_SAFE = {
    "reels": {"top": 0.14, "bottom": 0.35, "side": 0.06},   # [high] published
    # Feed creative is not overlaid by chrome, so Meta publishes no equivalent
    # overlay safe zone. We still keep a nominal margin for edge-crowding.
    "feed": {"top": 0.04, "bottom": 0.04, "side": 0.04},    # [low] convention
}


@dataclass(frozen=True)
class Rect:
    """A chrome rectangle in device CSS px at 390x844.

    `opacity` is how much of the creative this chrome actually destroys:
      1.0  genuinely opaque - the tab bar, or pixels cropped off entirely
      ~0.7 a scrim with UI text on it - large high-contrast type survives,
           small or low-contrast type does not
      ~0.55 light scrim (status bar, Reels title)
    Modelling all chrome as solid black was the first calibration's biggest
    error: it wiped burned captions that survive fine behind a real scrim,
    and made an elite ad look like it died.
    """
    name: str
    x: float
    y: float
    w: float
    h: float
    overlays_creative: bool
    confidence: str = "unverified"
    note: str = ""
    opacity: float = 1.0

    @property
    def x2(self) -> float:
        return self.x + self.w

    @property
    def y2(self) -> float:
        return self.y + self.h

    def as_dict(self) -> dict:
        return {
            "name": self.name, "x": self.x, "y": self.y, "w": self.w, "h": self.h,
            "overlays_creative": self.overlays_creative,
            "confidence": self.confidence, "note": self.note,
        }


# ------------------------------------------------------------ reels ----
# Reels video is full-bleed: chrome sits ON TOP of the creative.
REELS_TOP_ROW_H = 44        # "Reels" title + camera icon   [unverified]
REELS_AUDIO_TICKER_H = 28   # [unverified]
REELS_USERNAME_ROW_H = 36   # avatar + handle + Follow      [unverified]
REELS_CAPTION_H = 40        # 2 lines + "... more"          [unverified]
REELS_CTA_H = 48            # "Shop now" pill               [unverified]
REELS_BOTTOM_CHROME_H = (
    REELS_AUDIO_TICKER_H + REELS_USERNAME_ROW_H
    + REELS_CAPTION_H + REELS_CTA_H + BOTTOM_NAV_H
)  # 235

REELS_RAIL_W = 44           # [unverified]
REELS_RAIL_ICON = 27        # [unverified]
REELS_RAIL_RIGHT_MARGIN = 10
REELS_RAIL_H = 265          # like/comment/share/more/audio disc stack
REELS_RAIL_BOTTOM_GAP = 250 # distance from viewport bottom to rail bottom

_REELS_SCRIM_H = REELS_BOTTOM_CHROME_H - BOTTOM_NAV_H  # 152, above the tab bar

REELS_CHROME = [
    Rect("status_bar", 0, 0, VIEWPORT_W, STATUS_BAR_H, True, "high",
         "Apple status bar, drawn over the video", opacity=0.55),
    Rect("reels_top_row", 0, STATUS_BAR_H, VIEWPORT_W, REELS_TOP_ROW_H, True,
         "unverified", "Reels title + camera", opacity=0.55),
    # the caption/username/CTA band is a gradient scrim with UI text on it,
    # NOT an opaque box - big type behind it survives, small type does not
    Rect("bottom_scrim", 0, VIEWPORT_H - REELS_BOTTOM_CHROME_H, VIEWPORT_W,
         _REELS_SCRIM_H, True, "unverified",
         "audio ticker + username + caption + CTA pill, over a scrim",
         opacity=0.72),
    # the tab bar + home indicator genuinely is an opaque bar
    Rect("bottom_nav", 0, VIEWPORT_H - BOTTOM_NAV_H, VIEWPORT_W, BOTTOM_NAV_H,
         True, "high", "tab bar + home indicator, opaque", opacity=1.0),
    Rect("right_rail",
         VIEWPORT_W - REELS_RAIL_RIGHT_MARGIN - REELS_RAIL_W,
         VIEWPORT_H - REELS_RAIL_BOTTOM_GAP - REELS_RAIL_H,
         REELS_RAIL_W, REELS_RAIL_H, True, "unverified",
         "like / comment / share / more / audio disc", opacity=0.75),
]

# ------------------------------------------------------------- feed ----
# Feed chrome is STACKED, not overlaid: it never covers the creative. The
# medium's weapon in feed is the FOLD, not occlusion - see fold_crop().
FEED_TOP_BAR_H = 44      # IG wordmark row       [unverified]
FEED_HEADER_H = 60       # avatar + handle + "Sponsored" + ...   [unverified]
FEED_AVATAR = 32
FEED_CTA_H = 48          # "Shop now" row, below creative        [medium]
FEED_ACTION_RAIL_H = 44  # like/comment/share/bookmark           [unverified]
FEED_LIKES_H = 22        # [unverified]
FEED_CAPTION_H = 40      # [unverified]

FEED_CHROME = [
    Rect("status_bar", 0, 0, VIEWPORT_W, STATUS_BAR_H, False, "high", ""),
    Rect("ig_top_bar", 0, STATUS_BAR_H, VIEWPORT_W, FEED_TOP_BAR_H, False,
         "unverified", "Instagram wordmark + DM icon"),
    Rect("bottom_nav", 0, VIEWPORT_H - BOTTOM_NAV_H, VIEWPORT_W, BOTTOM_NAV_H,
         False, "high", "tab bar + home indicator"),
]

CHROME = {"reels": REELS_CHROME, "feed": FEED_CHROME}

# Fraction of viewport height at which an ad's top edge sits at the moment a
# scroller FIRST encounters it. 0.70 => ad enters from the bottom third.
FIRST_ENCOUNTER_TOP_FRAC = 0.70
# How far past the ad we scroll for the "scrolled past" shot.
SCROLLED_PAST_FRAC = 0.60


# ------------------------------------------------------------- fit ----
def fit(asset_w: float, asset_h: float, surface: str) -> dict:
    """Map an asset into the device viewport the way the surface renders it.

    reels: cover-fill (full-bleed, sides cropped on a 19.5:9 device)
    feed:  width-fit (390 wide, natural height, stacked in the post card)

    Returns scale + the asset's device-space box (may extend off-screen for
    reels cover-fill, which is correct - those pixels are genuinely cropped).
    """
    if surface == "reels":
        scale = max(VIEWPORT_W / asset_w, VIEWPORT_H / asset_h)
        w, h = asset_w * scale, asset_h * scale
        return {"scale": scale, "x": (VIEWPORT_W - w) / 2,
                "y": (VIEWPORT_H - h) / 2, "w": w, "h": h}
    scale = VIEWPORT_W / asset_w
    h = asset_h * scale
    top = STATUS_BAR_H + FEED_TOP_BAR_H + FEED_HEADER_H
    return {"scale": scale, "x": 0.0, "y": float(top), "w": float(VIEWPORT_W), "h": h}


def to_asset_space(rect: Rect, box: dict) -> tuple[float, float, float, float] | None:
    """Convert a device-space chrome rect into asset pixel coords.

    Returns None when the rect does not intersect the asset at all (e.g. feed
    chrome, which sits above/below the creative and never touches it).
    """
    ix1 = max(rect.x, box["x"])
    iy1 = max(rect.y, box["y"])
    ix2 = min(rect.x2, box["x"] + box["w"])
    iy2 = min(rect.y2, box["y"] + box["h"])
    if ix2 <= ix1 or iy2 <= iy1:
        return None
    s = box["scale"]
    return ((ix1 - box["x"]) / s, (iy1 - box["y"]) / s,
            (ix2 - ix1) / s, (iy2 - iy1) / s)


def safe_zone_asset(asset_w: float, asset_h: float, surface: str) -> dict:
    """Meta's published safe zone expressed in asset pixels."""
    f = META_SAFE[surface]
    return {
        "top": {"x": 0, "y": 0, "w": asset_w, "h": asset_h * f["top"]},
        "bottom": {"x": 0, "y": asset_h * (1 - f["bottom"]),
                   "w": asset_w, "h": asset_h * f["bottom"]},
        "left": {"x": 0, "y": 0, "w": asset_w * f["side"], "h": asset_h},
        "right": {"x": asset_w * (1 - f["side"]), "y": 0,
                  "w": asset_w * f["side"], "h": asset_h},
        "_fractions": f,
    }


def fold_crop(asset_w: float, asset_h: float, surface: str) -> dict | None:
    """The part of the creative NOT yet seen at first encounter, in asset px.

    This is feed's real weapon. When a post scrolls up from below, the scroll
    decision is made on the visible sliver, not the finished composition.
    Returns None for reels (full-bleed, no fold).
    """
    if surface == "reels":
        return None
    box = fit(asset_w, asset_h, surface)
    ad_top_at = VIEWPORT_H * FIRST_ENCOUNTER_TOP_FRAC
    # creative top sits header-height below the post's top edge
    creative_top = ad_top_at + FEED_HEADER_H
    visible_h_device = max(0.0, (VIEWPORT_H - BOTTOM_NAV_H) - creative_top)
    visible_h_asset = visible_h_device / box["scale"]
    if visible_h_asset >= asset_h:
        return None
    return {"x": 0, "y": visible_h_asset, "w": asset_w,
            "h": asset_h - visible_h_asset,
            "visible_frac": visible_h_asset / asset_h}


def summary() -> str:
    lines = ["Instagram surface geometry (390x844 CSS px)", ""]
    for surf, rects in CHROME.items():
        lines.append(f"[{surf}]")
        for r in rects:
            tag = "OVERLAYS" if r.overlays_creative else "stacked "
            lines.append(f"  {tag} {r.name:<16} "
                         f"({r.x:>5.0f},{r.y:>5.0f}) {r.w:>4.0f}x{r.h:<5.0f} "
                         f"opacity {r.opacity:.2f}  [{r.confidence}]")
        f = META_SAFE[surf]
        lines.append(f"  meta safe zone: top {f['top']:.0%} / "
                     f"bottom {f['bottom']:.0%} / side {f['side']:.0%}")
        lines.append("")
    return "\n".join(lines)


if __name__ == "__main__":
    print(summary())
