"""style — output format specs, safe zones, and caption placement defaults.

Safe zone values are percentages of frame height, derived from Instagram's
publisher guidelines for Reels/Stories and Feed placements. They define where
platform UI (username, actions bar, reply box, CTA sticker, music/location
pills) can overlap your creative. Keep captions and key subjects outside these.

References used when authoring:
  - Meta Ads Manager "asset customization" docs for Reels/Stories/Feed
  - TikTok Ads "safe zone" guide (overlaps heavily with IG Reels)

Design guidance baked in here:
  - Caption y_frac defaults sit ABOVE the bottom danger zone so they stay
    visible when the platform UI overlays the bottom ~22% of Reels/Stories.
  - For 4:5 (Feed), there's no UI overlay — captions can sit lower but still
    leave breathing room (5% margin).
"""
from __future__ import annotations
from dataclasses import dataclass


@dataclass(frozen=True)
class SafeZone:
    """All values are fractions of frame height/width (0..1)."""
    top: float       # frame-top danger zone (avoid captions & key subjects above this)
    bottom: float    # frame-bottom danger zone (avoid captions & key subjects below this)
    left: float
    right: float


@dataclass(frozen=True)
class FormatSpec:
    key: str                 # "9:16" or "4:5"
    label: str               # human-friendly name
    width: int
    height: int
    fps: int
    safe_zone: SafeZone
    # Default caption baseline (y fraction of frame); ABOVE bottom safe zone by design.
    caption_y_frac: float
    caption_fontsize_px: int
    caption_endcard_y_frac: float
    caption_endcard_fontsize_px: int


FORMATS: dict[str, FormatSpec] = {
    # Reels / Stories / TikTok. Bottom 22% reserved for UI chrome (reply box, CTA
    # sticker, music pill); top 14% reserved for username / close button.
    "9:16": FormatSpec(
        key="9:16", label="Reels / Stories",
        width=720, height=1280, fps=30,
        # Bottom safe zone at 0.14 reflects real-world Reels UI (reply box ~14%)
        # rather than the worst-case CTA-sticker stack at 22%. Lets captions sit
        # comfortably below subjects without kissing the reply box.
        safe_zone=SafeZone(top=0.14, bottom=0.14, left=0.04, right=0.04),
        caption_y_frac=0.82,       # below subject, above reply-box zone
        # Arial Black at 52px with 2-line wrap. Longest split line of the
        # brief's max caption ("americans bake with", 19 chars) lands ~555px,
        # fitting comfortably inside 662px usable width minus the box's ~36px
        # horizontal padding (~626px text budget). Heavy sans-serif is the
        # legibility floor — stroke-only styles were rejected twice.
        caption_fontsize_px=52,
        caption_endcard_y_frac=0.78,
        caption_endcard_fontsize_px=30,
    ),
    # Feed portrait placement. No platform-UI overlay, so more of the canvas is
    # usable. Still leave breathing room so the caption isn't kissing edges.
    "4:5": FormatSpec(
        key="4:5", label="Feed portrait",
        # 1080×1350 is Instagram's recommended feed portrait size and both dims
        # are divisible by 2 (libx264 rejects odd dims). 900×1125 was the exact
        # math but 1125 is odd, so we use the next common even size.
        width=1080, height=1350, fps=30,
        safe_zone=SafeZone(top=0.05, bottom=0.06, left=0.04, right=0.04),
        caption_y_frac=0.84,
        # Arial Black at 68px in 4:5 — scales roughly with the 1.5x canvas
        # height vs 9:16 (52px × 1.3 ≈ 68). Two-line wrap handles the longest
        # caption inside the 994px usable width.
        caption_fontsize_px=68,
        caption_endcard_y_frac=0.72,
        caption_endcard_fontsize_px=36,
    ),
    # 16:9 horizontal — included so we can repurpose PDP material if asked.
    "16:9": FormatSpec(
        key="16:9", label="Horizontal",
        width=1920, height=1080, fps=30,
        safe_zone=SafeZone(top=0.05, bottom=0.06, left=0.04, right=0.04),
        caption_y_frac=0.85,
        caption_fontsize_px=48,
        caption_endcard_y_frac=0.72,
        caption_endcard_fontsize_px=36,
    ),
}


def get_format(key: str) -> FormatSpec:
    if key not in FORMATS:
        raise ValueError(f"unknown format '{key}'. known: {list(FORMATS)}")
    return FORMATS[key]


def caption_y_pixels(spec: FormatSpec, y_frac: float | None = None) -> int:
    """Return a pixel y-coordinate respecting the bottom safe zone."""
    y_frac = spec.caption_y_frac if y_frac is None else y_frac
    # Clamp into the safe band
    top_limit = spec.safe_zone.top + 0.02
    bottom_limit = 1.0 - spec.safe_zone.bottom - 0.02
    y_frac = max(top_limit, min(bottom_limit - 0.05, y_frac))
    return int(spec.height * y_frac)


SUBJECT_PLACEMENT_NOTE = """\
When composing a scene with a subject (product pack, character, person):
  - Keep the subject's key information (logo, face, CTA super) INSIDE the safe
    box — i.e. above the bottom danger zone and below the top danger zone.
  - If the source footage has baked-in text/graphics (like a PDP super),
    either (a) trim the clip to a window before or after the super appears,
    or (b) move our caption to the opposite side of the frame.
  - Aim for plenty of negative space around captions. If caption and subject
    collide, shift caption up (inside safe zone) rather than shrinking the
    caption.
"""
