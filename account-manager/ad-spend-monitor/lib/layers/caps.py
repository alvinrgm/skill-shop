"""Layer 3 — manual hard safety caps.

Fires when yesterday's spend on a single account exceeds the dollar ceiling
the user set in account.md (e.g. daily_google_max = 5000).

Opinionated and absolute — no statistical reasoning. If a cap is set, it's
a hard line. Clients with no cap rely on Layer 2 instead.
"""
from __future__ import annotations


def evaluate(
    *,
    slug: str,
    platform: str,
    yesterday: float,
    cap: float | None,
) -> dict | None:
    """Return red alert dict if yesterday > cap, else None."""
    if cap is None or cap <= 0:
        return None
    if yesterday <= cap:
        return None

    overage = yesterday - cap
    return {
        "layer": "caps",
        "platform": platform,
        "severity": "red",
        "signature": f"caps:{platform}:over_{int(cap)}",
        "summary": (
            f"{platform.capitalize()} yesterday ${yesterday:,.2f} "
            f"exceeded hard cap ${cap:,.2f} by ${overage:,.2f}"
        ),
        "data": {
            "yesterday": yesterday,
            "cap": cap,
            "overage": round(overage, 2),
        },
        "suggested_action": (
            "Hard cap exceeded. Investigate immediately — likely a runaway "
            "campaign or cap change. Lower daily budgets or pause spenders."
        ),
    }
