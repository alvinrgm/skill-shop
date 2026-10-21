#!/usr/bin/env python3
"""Deck PATTERN LIBRARY — the canonical, executable layouts (built on dark_deck primitives).

This is where canon ACCRUES: every reusable slide layout is a function here, so future decks
call the function and get the exact look (no re-deriving coordinates from prose). Render the gallery
(build_gallery.py) and eyeball the result whenever these change.

Each function takes (d, sid, reqs, ...) and appends requests to `reqs` (flush per slide), matching
dark_deck's style. d = a dark_deck.Deck; sid = slide objectId; reqs = request list.
"""
import os, sys
# dark_deck is vendored alongside this file in deck-engine/.
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dark_deck as D

# ---- grid (EMU); mirrors DESIGN-SYSTEM.md ----
MARGIN = 620000
CW = D.PAGE_W - 2 * MARGIN          # 7904000
MX = MARGIN
EB_Y = 560000                       # eyebrow baseline
TITLE_Y = 820000                    # H1 baseline
SUB_Y = 1330000                     # italic subtitle baseline
CONTENT_Y = 1880000
KICKER_W, KICKER_H = 560000, 44000  # the signature amber kicker rule

# type scale (pt)
DISPLAY, SECTION, H1, H2 = 38, 33, 21, 12.5
BODY, BODYSM, LABEL, ROWLBL, CAP = 10, 9.5, 8.5, 7.5, 8.5
GHOST = 90


# ---- signature devices ----
def kicker(d, reqs, sid, x, y, w=KICKER_W):
    """The amber kicker rule — the unifying motif (under eyebrows, above stats/thesis, etc.)."""
    d.rect(reqs, sid, x, y, w, KICKER_H, fill=D.AMBER, line=None, rounded=False)


def eyebrow(d, reqs, sid, text, y=EB_Y):
    d.text(reqs, sid, MX, y, 6000000, 240000, text, size=LABEL, color=D.AMBER, bold=True, caps=True)


def header(d, reqs, sid, eb, title, sub=None, tsize=H1):
    """Eyebrow + title (+ optional ITALIC subtitle). Standard content-slide head."""
    eyebrow(d, reqs, sid, eb)
    d.text(reqs, sid, MX, TITLE_Y, CW, 520000, title, size=tsize, bold=True)
    if sub:
        d.text(reqs, sid, MX, SUB_Y, CW, 360000, sub, size=BODY, color=D.MUTED, italic=True)


# ---- the 11 layouts ----
def cover(d, reqs, sid, title, subtitle, logo_url):
    """Centered cover: logo top-center, centered title + kicker + subtitle."""
    lw, lh = 660000, 215000
    d.image(reqs, sid, logo_url, (D.PAGE_W - lw) // 2, 760000, lw, lh)
    d.text(reqs, sid, MX, 1980000, CW, 760000, title, size=DISPLAY, bold=True, align="CENTER")
    kicker(d, reqs, sid, (D.PAGE_W - KICKER_W) // 2, 2960000)
    d.text(reqs, sid, MX, 3160000, CW, 360000, subtitle, size=14, color=D.MUTED, align="CENTER")


def section_divider(d, reqs, sid, num, eb, title):
    """LEFT: eyebrow + kicker under it + big 2-line title; giant ghost number top-right."""
    d.text(reqs, sid, 6750000, 520000, 1900000, 1100000, num, size=GHOST, color=D.GHOST, bold=True, align="END")
    eyebrow(d, reqs, sid, eb, y=1640000)
    kicker(d, reqs, sid, MX, 1900000)
    d.text(reqs, sid, MX, 2060000, CW - 1800000, 900000, title, size=SECTION, bold=True)


def stat_row(d, reqs, sid, eb, title, stats, sub=None):
    """eyebrow+title(+sub); N stats each = kicker + big number + caps label. stats=[(num,label)]."""
    header(d, reqs, sid, eb, title, sub)
    n = len(stats); gap = 240000
    cw = (CW - gap * (n - 1)) // n
    y = 2280000
    for i, (num, label) in enumerate(stats):
        x = MX + i * (cw + gap)
        kicker(d, reqs, sid, x, y, w=300000)
        d.text(reqs, sid, x, y + 150000, cw, 700000, num, size=44, bold=True)
        d.text(reqs, sid, x, y + 980000, cw, 300000, label, size=ROWLBL + 1, color=D.MUTED, caps=True)


def hero_stat(d, reqs, sid, eb, number, caption, sub):
    """One giant amber number + kicker + bold caption + grey sub."""
    eyebrow(d, reqs, sid, eb)
    d.text(reqs, sid, MX, 1450000, CW, 1300000, number, size=92, color=D.AMBER, bold=True)
    kicker(d, reqs, sid, MX, 2980000)
    d.text(reqs, sid, MX, 3180000, CW, 460000, caption, size=20, bold=True)
    d.text(reqs, sid, MX, 3720000, CW, 420000, sub, size=BODY, color=D.MUTED)


def hbar(d, reqs, sid, eb, title, rows, sub=None, maxbar=4900000):
    """Horizontal bar chart. rows=[(label, pct, flagged_bool)]; flagged bar = amber, rest grey."""
    header(d, reqs, sid, eb, title, sub)
    y0, rh = 2120000, 560000
    labelw = 1900000
    barx = MX + labelw
    mx = max((p for _, p, _ in rows), default=100) or 100
    for i, (label, pct, flag) in enumerate(rows):
        y = y0 + i * rh
        d.text(reqs, sid, MX, y + 10000, labelw - 120000, 300000, label, size=BODY, color=D.TEXT)
        bw = max(40000, int(maxbar * (pct / mx)))
        d.rect(reqs, sid, barx, y, bw, 250000, fill=(D.AMBER if flag else D.HAIR), line=None, rounded=False)
        d.text(reqs, sid, barx + bw + 130000, y - 5000, 900000, 300000, f"{pct}%", size=BODY, bold=True)


def clean_table(d, reqs, sid, eb, title, headers, rows, sub=None, source=None, right_cols=()):
    """Borderless table: amber caps headers + amber underline + hairline row dividers. right_cols=indices to right-align."""
    header(d, reqs, sid, eb, title, sub)
    n = len(headers)
    colw = CW // n
    hy = 2160000
    for c, h in enumerate(headers):
        al = "END" if c in right_cols else "START"
        d.text(reqs, sid, MX + c * colw, hy, colw - 120000, 260000, h, size=ROWLBL + 1, color=D.AMBER, bold=True, caps=True, align=al)
    d.rect(reqs, sid, MX, hy + 320000, CW, 6000, fill=D.AMBER, line=None, rounded=False)
    ry, rh = hy + 460000, 470000
    for r, row in enumerate(rows):
        for c, val in enumerate(row):
            al = "END" if c in right_cols else "START"
            d.text(reqs, sid, MX + c * colw, ry + 60000, colw - 120000, 300000, str(val), size=BODY, color=D.TEXT, align=al)
        if r < len(rows) - 1:
            d.rect(reqs, sid, MX, ry + rh - 70000, CW, 2200, fill=D.HAIR, line=None, rounded=False)
        ry += rh
    if source:
        d.text(reqs, sid, MX, 4500000, CW, 300000, source, size=CAP, color=D.MUTED, italic=True)


def grouped_bullets(d, reqs, sid, eb, title, groups, sub=None, thesis=None):
    """groups=[(subhead,[bullets])]; ends with an amber-kicker thesis line. The diagnosis slide."""
    header(d, reqs, sid, eb, title, sub)
    y = 2060000
    for subhead, bullets in groups:
        d.text(reqs, sid, MX, y, CW, 300000, subhead, size=H2, bold=True)
        y += 360000
        for bl in bullets:
            d.text(reqs, sid, MX + 120000, y, CW - 240000, 300000, "•   " + bl, size=BODY, color=D.TEXT)
            y += 320000
        y += 150000
    if thesis:
        kicker(d, reqs, sid, MX, 4220000)
        d.text(reqs, sid, MX, 4380000, CW, 360000, thesis, size=16, bold=True)


def statement(d, reqs, sid, eb, text, label):
    """Big thesis statement: eyebrow + kicker + huge statement + small grey label."""
    eyebrow(d, reqs, sid, eb)
    kicker(d, reqs, sid, MX, 1280000)
    d.text(reqs, sid, MX, 1480000, CW, 1700000, text, size=SECTION, bold=True, spacing=108)
    d.text(reqs, sid, MX, 3900000, CW, 300000, label, size=BODY, color=D.MUTED)


def numbered_columns(d, reqs, sid, eb, claim, cols):
    """Claim title + hairline divider + N columns: amber 0N + bold head + grey body. cols=[(num,head,body)]."""
    eyebrow(d, reqs, sid, eb)
    d.text(reqs, sid, MX, TITLE_Y, CW, 700000, claim, size=H1, bold=True)
    d.rect(reqs, sid, MX, 2060000, CW, 3000, fill=D.HAIR, line=None, rounded=False)
    n = len(cols); gap = 240000
    cw = (CW - gap * (n - 1)) // n
    y = 2320000
    for i, (num, head, body) in enumerate(cols):
        x = MX + i * (cw + gap)
        d.text(reqs, sid, x, y, cw, 320000, num, size=H1, color=D.AMBER, bold=True)
        d.text(reqs, sid, x, y + 420000, cw, 320000, head, size=H2, bold=True)
        d.text(reqs, sid, x, y + 860000, cw, 900000, body, size=BODYSM, color=D.MUTED, spacing=120)


def footer(d, reqs, sid, logo_url, page=None):
    """Chrome: amber baseline rule + white logo bottom-left + page number. Call per slide (page>1)."""
    d.rect(reqs, sid, 0, 5122000, D.PAGE_W, 15000, fill=D.AMBER, line=None, rounded=False)
    if page and page > 1:
        d.image(reqs, sid, logo_url, MX, 4900000, 384000, 125000)
        d.text(reqs, sid, D.PAGE_W - 770000, 4895000, 560000, 230000, str(page), size=CAP, color=D.MUTED, align="END")
