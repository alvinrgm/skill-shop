"""Layer 2 — day-over-day rate vs. trailing 30-day daily average.

Fires for every client. Workhorse for clients with no monthly budget target.

Thresholds:
    yesterday > 1.25× trailing_30d_avg   yellow
    yesterday > 2.00× trailing_30d_avg   red

New-account handling: if <14 days of history, skip (insufficient baseline)
and rely on Layer 3 hard caps instead.
"""
from __future__ import annotations

YELLOW_RATIO = 1.25
RED_RATIO = 2.0
MIN_HISTORY_DAYS = 14


def evaluate(
    *,
    slug: str,
    platform: str,
    yesterday: float,
    trailing_30d_avg: float,
    history_days: int,
) -> dict | None:
    """Return alert dict if yesterday is anomalously high, else None."""
    if history_days < MIN_HISTORY_DAYS:
        return None
    if trailing_30d_avg <= 0:
        return None
    if yesterday <= 0:
        return None

    ratio = yesterday / trailing_30d_avg

    if ratio >= RED_RATIO:
        severity = "red"
        signature = "above_2x_30d_avg"
    elif ratio >= YELLOW_RATIO:
        severity = "yellow"
        signature = "above_1.25x_30d_avg"
    else:
        return None

    return {
        "layer": "rate",
        "platform": platform,
        "severity": severity,
        "signature": f"rate:{platform}:{signature}",
        "summary": (
            f"{platform.capitalize()} yesterday "
            f"{ratio:.2f}× trailing 30d daily avg "
            f"(${yesterday:,.2f} vs ${trailing_30d_avg:,.2f})"
        ),
        "data": {
            "yesterday": yesterday,
            "trailing_30d_avg": trailing_30d_avg,
            "ratio": round(ratio, 3),
        },
        "suggested_action": (
            "Check recent budget cap changes or campaign launches. "
            "If intentional (e.g. weekend lift, sale), reply 'ack' to silence."
        ),
    }
