"""
Triple Whale "campaign performance" table renderer.

Produces a clean, high-resolution PNG styled to match the Triple Whale reporting UI,
suitable for embedding into a Google Slides deck (crisp at ~2x, white background).

Public API:
    render_tw_table(rows, totals, out_path) -> (out_path, (width_px, height_px))

`rows` is a list of dicts:
    {
        "campaign": str,
        "spend":   (current, prior, delta_pct) | "-" for any missing piece,
        "roas":    (current, prior, delta_pct),
        "nc_roas": (current, prior, delta_pct),
        "nc_cpa":  (current, prior, delta_pct),
    }
Each metric value is a 3-tuple. Use the string "-" (or None) in any slot that has no data.
Values may be passed pre-formatted as strings, or as numbers (which get formatted
according to the column type).

`totals` is a dict:
    {
        "label":   "(7 Campaigns)",
        "spend":   "$5,000.00",
        "roas":    "4.00",
        "nc_roas": "2.00",
        "nc_cpa":  "$50.00",
    }
"""

from __future__ import annotations

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

# ---------------------------------------------------------------------------
# Palette (Triple Whale-ish clean analytics)
# ---------------------------------------------------------------------------
C_BG = "#FFFFFF"
C_HEADER_FILL = "#F4F5F7"
C_HEADER_TEXT = "#3A3F4B"
C_LINK_BLUE = "#2A66C7"
C_VALUE_DARK = "#1C2128"
C_COMPARE_GRAY = "#9AA0AA"
C_GRIDLINE = "#ECEDF0"
C_TOTAL_BORDER = "#C4C8CF"
C_GREEN = "#11936A"
C_RED = "#D2453B"

# Column layout: fractional x-positions (0..1) for the left edge of each column.
# Campaign is wide; metric columns share the rest.
COLS = ["campaign", "spend", "roas", "nc_roas", "nc_cpa"]
COL_HEADERS = ["Campaign", "Spend", "ROAS", "NC ROAS", "NC CPA"]
# Left edges of each column band (data area), as fractions of plot width.
COL_LEFT = {
    "campaign": 0.012,
    "spend": 0.265,
    "roas": 0.470,
    "nc_roas": 0.650,
    "nc_cpa": 0.835,
}
COL_RIGHT_PAD = 0.012  # right padding inside the last column band

# A metric column's content starts at its left edge.
METRIC_COLS = ["spend", "roas", "nc_roas", "nc_cpa"]

# Row geometry
ROW_H = 1.0  # logical units per row
HEADER_H = 1.15
TOTAL_H = 1.2


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------
def _is_missing(v):
    return v is None or (isinstance(v, str) and v.strip() in ("-", ""))


def _fmt_value(v, kind):
    """Format the big current value or the small prior value."""
    if _is_missing(v):
        return "-"
    if isinstance(v, str):
        return v
    if kind in ("spend", "nc_cpa"):  # currency
        return f"${v:,.2f}"
    return f"{v:.2f}"  # ratio (roas / nc_roas)


def _fmt_delta(d):
    """Return (text, is_up) for a delta percentage. None text if missing."""
    if _is_missing(d):
        return None, None
    if isinstance(d, str):
        s = d.strip().replace("%", "")
        try:
            num = float(s)
        except ValueError:
            return None, None
    else:
        num = float(d)
    up = num >= 0
    arrow = "↑" if up else "↓"
    return f"{arrow}{abs(num):g}%", up


def _delta_color(is_up, kind):
    """Good/bad coloring. For cost (nc_cpa) down=good."""
    if kind == "nc_cpa":
        good = not is_up
    else:
        good = is_up
    return C_GREEN if good else C_RED


# ---------------------------------------------------------------------------
# Renderer
# ---------------------------------------------------------------------------
def render_tw_table(rows, totals, out_path="/tmp/tw_render.png"):
    n = len(rows)

    # Total logical height (in row units), from top: header + rows + total
    total_units = HEADER_H + n * ROW_H + TOTAL_H

    # Figure sizing — aim wide (16:9-friendly). Width fixed, height from content.
    fig_w_in = 16.0
    unit_in = 0.52  # vertical inches per logical row unit
    fig_h_in = total_units * unit_in + 0.2

    dpi = 150  # 16 in * 150 = 2400px wide -> crisp at 2x
    fig = plt.figure(figsize=(fig_w_in, fig_h_in), dpi=dpi)
    fig.patch.set_facecolor(C_BG)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_facecolor(C_BG)
    ax.set_xlim(0, 1)
    ax.set_ylim(0, total_units)
    ax.axis("off")

    # y grows downward visually; we draw from top. Convert "rows from top" to y.
    def y_top(units_from_top):
        return total_units - units_from_top

    # Font sizes
    FS_HEADER = 14
    FS_VALUE = 15
    FS_COMPARE = 10.5
    FS_DELTA = 11
    FS_CAMPAIGN = 13.5

    # ---- Header band ----
    hdr_top = total_units
    hdr_bot = total_units - HEADER_H
    ax.add_patch(
        Rectangle(
            (0, hdr_bot), 1, HEADER_H,
            facecolor=C_HEADER_FILL, edgecolor="none", zorder=1,
        )
    )
    hdr_y = hdr_bot + HEADER_H / 2
    # Campaign header left-aligned; metric headers left-aligned at their band.
    ax.text(
        COL_LEFT["campaign"], hdr_y, COL_HEADERS[0],
        ha="left", va="center", fontsize=FS_HEADER, fontweight="bold",
        color=C_HEADER_TEXT, zorder=3,
    )
    for col, label in zip(METRIC_COLS, COL_HEADERS[1:]):
        ax.text(
            COL_LEFT[col], hdr_y, label,
            ha="left", va="center", fontsize=FS_HEADER, fontweight="bold",
            color=C_HEADER_TEXT, zorder=3,
        )

    # ---- Data rows ----
    def draw_metric_cell(col, cell, y):
        """Draw value + prior + delta on one line starting at the col's left edge."""
        kind = col
        x = COL_LEFT[col]
        if isinstance(cell, (list, tuple)):
            cur, prior, delta = (list(cell) + [None, None, None])[:3]
        else:
            cur, prior, delta = cell, None, None

        # Big current value
        val_txt = _fmt_value(cur, kind)
        t_val = ax.text(
            x, y, val_txt,
            ha="left", va="center", fontsize=FS_VALUE, fontweight="bold",
            color=C_VALUE_DARK, zorder=3,
        )
        # Measure to place the comparison text after it.
        # Gaps are defined in pixels and converted to data units so they are
        # consistent regardless of figure width.
        renderer = fig.canvas.get_renderer()
        inv = ax.transData.inverted()

        def px_to_dx(px):
            x0 = inv.transform((0, 0))[0]
            x1 = inv.transform((px, 0))[0]
            return x1 - x0

        gap = px_to_dx(11)

        bb = t_val.get_window_extent(renderer=renderer)
        x_after = inv.transform((bb.x1, 0))[0]

        prior_txt = _fmt_value(prior, kind)
        if prior_txt != "-":
            t_prior = ax.text(
                x_after + gap, y, prior_txt,
                ha="left", va="center", fontsize=FS_COMPARE,
                color=C_COMPARE_GRAY, zorder=3,
            )
            bb2 = t_prior.get_window_extent(renderer=renderer)
            x_after = inv.transform((bb2.x1, 0))[0]

        dtxt, is_up = _fmt_delta(delta)
        if dtxt is not None:
            ax.text(
                x_after + px_to_dx(10), y, dtxt,
                ha="left", va="center", fontsize=FS_DELTA, fontweight="bold",
                color=_delta_color(is_up, kind), zorder=3,
            )

    # Prime the renderer once so get_window_extent returns valid bboxes.
    fig.canvas.draw()

    for i, row in enumerate(rows):
        row_top = HEADER_H + i * ROW_H
        y_center = y_top(row_top + ROW_H / 2)
        y_line = y_top(row_top + ROW_H)  # bottom gridline of this row

        # Campaign name (link blue)
        ax.text(
            COL_LEFT["campaign"], y_center, row["campaign"],
            ha="left", va="center", fontsize=FS_CAMPAIGN,
            color=C_LINK_BLUE, zorder=3,
        )
        for col in METRIC_COLS:
            draw_metric_cell(col, row.get(col, "-"), y_center)

        # Thin gridline under the row
        ax.plot(
            [0, 1], [y_line, y_line],
            color=C_GRIDLINE, linewidth=1.0, zorder=2,
        )

    # ---- Totals row ----
    tot_top = HEADER_H + n * ROW_H
    tot_y = y_top(tot_top + TOTAL_H / 2)
    tot_line = y_top(tot_top)  # heavier top border
    ax.plot(
        [0, 1], [tot_line, tot_line],
        color=C_TOTAL_BORDER, linewidth=2.0, zorder=2,
    )
    ax.text(
        COL_LEFT["campaign"], tot_y, totals.get("label", ""),
        ha="left", va="center", fontsize=FS_CAMPAIGN, fontweight="bold",
        color=C_VALUE_DARK, zorder=3,
    )
    for col in METRIC_COLS:
        val = totals.get(col, "")
        if not isinstance(val, str):
            val = _fmt_value(val, col)
        ax.text(
            COL_LEFT[col], tot_y, val,
            ha="left", va="center", fontsize=FS_VALUE, fontweight="bold",
            color=C_VALUE_DARK, zorder=3,
        )

    fig.savefig(out_path, dpi=dpi, facecolor=C_BG, bbox_inches=None)
    w_px = int(round(fig_w_in * dpi))
    h_px = int(round(fig_h_in * dpi))
    plt.close(fig)
    return out_path, (w_px, h_px)


# ---------------------------------------------------------------------------
# Demo data (a generic campaign performance table)
# ---------------------------------------------------------------------------
def _demo_rows():
    # Synthetic, round numbers (not from any real account). Tuples are
    # (this week, prior week, % change). Current-week rows sum to the totals below:
    # spend $5,000 · revenue $20,000 (4.00x) · new-customer revenue $10,000 (2.00x)
    # · 100 new customers ($50 NC CPA).
    return [
        {"campaign": "PMax - All Products",
         "spend": (2000.00, 1600.00, 25), "roas": (4.00, 4.00, 0),
         "nc_roas": (2.50, 2.00, 25), "nc_cpa": (50.00, 40.00, 25)},
        {"campaign": "Search - Non-Brand",
         "spend": (1000.00, 1250.00, -20), "roas": (3.00, 2.50, 20),
         "nc_roas": (1.50, 1.00, 50), "nc_cpa": (50.00, 40.00, 25)},
        {"campaign": "Shopping - Primary",
         "spend": (800.00, 1000.00, -20), "roas": (3.00, 3.00, 0),
         "nc_roas": (1.50, 1.25, 20), "nc_cpa": (80.00, 64.00, 25)},
        {"campaign": "PMax - Category A",
         "spend": (500.00, 500.00, 0), "roas": (2.00, 2.50, -20),
         "nc_roas": (0.80, 1.00, -20), "nc_cpa": (100.00, 80.00, 25)},
        {"campaign": "Demand Gen",
         "spend": (400.00, 400.00, 0), "roas": (2.00, 1.00, 100),
         "nc_roas": (1.00, 0.50, 100), "nc_cpa": (80.00, 160.00, -50)},
        {"campaign": "Search - Brand",
         "spend": (300.00, 250.00, 20), "roas": (16.00, 16.00, 0),
         "nc_roas": (5.00, 4.00, 25), "nc_cpa": (15.00, 12.50, 20)},
        {"campaign": "Search - Competitors",
         "spend": (0.00, 0.00, 0), "roas": ("-", "-", "-"),
         "nc_roas": ("-", "-", "-"), "nc_cpa": ("-", "-", "-")},
    ]


def _demo_totals():
    return {
        "label": "(7 Campaigns)",
        "spend": "$5,000.00",
        "roas": "4.00",
        "nc_roas": "2.00",
        "nc_cpa": "$50.00",
    }


if __name__ == "__main__":
    path, dims = render_tw_table(_demo_rows(), _demo_totals(), "/tmp/tw_render.png")
    print(f"wrote {path}  {dims[0]}x{dims[1]}px")
