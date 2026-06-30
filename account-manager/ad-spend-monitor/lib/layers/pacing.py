"""Layer 1 — budget pacing (asymmetric: -15% under, +2% over).

Fires only when client has `budget_source: google_sheet`. Hard rule: budget
comes from sheet (TARGET), spend comes from platform APIs (ACTUAL). Pacing
math is always computed here — never read from sheet cells.

Thresholds (projected EOM ÷ monthly budget):
    > 102%   red    "tracking to overspend by $X"
    > 101%   yellow
    < 90%    yellow
    < 85%    red    "tracking to underspend by $X"

Grace period: skip days 1-3 of month (projection math too noisy when
days_elapsed is tiny — a $500 day on day 2 projects to 1400% of budget).
"""
from __future__ import annotations

import calendar
from datetime import date

OVER_RED_RATIO = 1.02
OVER_YELLOW_RATIO = 1.01
UNDER_YELLOW_RATIO = 0.90
UNDER_RED_RATIO = 0.85

GRACE_DAYS = 3  # Skip Layer 1 on day 1-3 of month


def evaluate(
    *,
    slug: str,
    platform: str,
    mtd_spend: float,
    monthly_budget: float | None,
    today: date,
) -> dict | None:
    """Return alert dict if projected EOM is outside [-15%, +2%] of budget, else None."""
    if monthly_budget is None or monthly_budget <= 0:
        return None
    if today.day <= GRACE_DAYS:
        return None
    if mtd_spend < 0:
        return None

    days_in_month = calendar.monthrange(today.year, today.month)[1]
    days_elapsed = today.day - 1  # "yesterday" is the latest complete day; MTD covers days 1..yesterday
    if days_elapsed <= 0:
        return None

    projected_eom = mtd_spend * (days_in_month / days_elapsed)
    ratio = projected_eom / monthly_budget
    overage_or_under = projected_eom - monthly_budget  # signed dollars

    severity = None
    signature = None
    direction = None

    if ratio >= OVER_RED_RATIO:
        severity, signature, direction = "red", f"pacing:{platform}:over_102pct", "over"
    elif ratio >= OVER_YELLOW_RATIO:
        severity, signature, direction = "yellow", f"pacing:{platform}:over_101pct", "over"
    elif ratio <= UNDER_RED_RATIO:
        severity, signature, direction = "red", f"pacing:{platform}:under_85pct", "under"
    elif ratio <= UNDER_YELLOW_RATIO:
        severity, signature, direction = "yellow", f"pacing:{platform}:under_90pct", "under"
    else:
        return None

    if direction == "over":
        action = (
            "Pause top spenders or lower daily caps. "
            f"Tracking to overspend by ${overage_or_under:,.0f}."
        )
    else:
        action = (
            "Consider raising caps or launching new campaigns. "
            f"Tracking to leave ${-overage_or_under:,.0f} on the table."
        )

    return {
        "layer": "pacing",
        "platform": platform,
        "severity": severity,
        "signature": signature,
        "summary": (
            f"{platform.capitalize()} pacing {ratio * 100:.1f}% of monthly budget "
            f"(projected EOM ${projected_eom:,.0f} vs ${monthly_budget:,.0f} target)"
        ),
        "data": {
            "mtd_spend": round(mtd_spend, 2),
            "monthly_budget": round(monthly_budget, 2),
            "projected_eom": round(projected_eom, 2),
            "ratio": round(ratio, 4),
            "days_elapsed": days_elapsed,
            "days_in_month": days_in_month,
            "direction": direction,
        },
        "suggested_action": action,
    }
