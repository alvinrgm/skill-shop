"""Layer 4 — campaign budget cap change leading indicator.

Detects when a campaign's daily/lifetime budget was raised by a lot in the
last 24h, BEFORE the spend has happened. This is the fat-finger guard.

Thresholds (per individual change):
    daily cap raised by > 50%                    yellow
    daily cap raised by > 100%                   red
    lifetime cap raised by > 25%                 yellow
    lifetime cap raised by > 50%                 red
    paused → enabled with daily cap > $500       yellow

Inputs: list of change dicts from fetchers/{google,meta}.fetch_budget_changes.
Each dict has at least: campaign_id, campaign_name, old_amount, new_amount,
pct_change, type ('daily' | 'lifetime' | 'unpause').

Caveat: at daily cadence, this lags up to 23h. If we need real-time, this
layer splits off to a 15-min poll (design doc §7).
"""
from __future__ import annotations

DAILY_YELLOW_PCT = 0.50
DAILY_RED_PCT = 1.00
LIFETIME_YELLOW_PCT = 0.25
LIFETIME_RED_PCT = 0.50
UNPAUSE_DAILY_THRESHOLD = 500.0


def evaluate(slug: str, platform: str, changes: list[dict]) -> list[dict]:
    """Return one alert dict per qualifying change. Empty list if nothing fires."""
    alerts: list[dict] = []
    for ch in changes:
        alert = _evaluate_one(slug, platform, ch)
        if alert:
            alerts.append(alert)
    return alerts


def _evaluate_one(slug: str, platform: str, ch: dict) -> dict | None:
    ch_type = ch.get("type", "daily")
    pct = ch.get("pct_change")
    old_amt = ch.get("old_amount")
    new_amt = ch.get("new_amount")
    camp_id = ch.get("campaign_id", "?")
    camp_name = ch.get("campaign_name", "?")

    # Unpause case (old=0 or None, new>0)
    if ch_type == "unpause" or (old_amt in (None, 0) and new_amt and new_amt >= UNPAUSE_DAILY_THRESHOLD):
        return _build_alert(
            slug, platform, "yellow", "unpause",
            f"Campaign '{camp_name}' unpaused with daily cap ${new_amt:,.0f}",
            ch,
        )

    if pct is None or pct <= 0:
        return None

    if ch_type == "lifetime":
        if pct >= LIFETIME_RED_PCT:
            severity = "red"
        elif pct >= LIFETIME_YELLOW_PCT:
            severity = "yellow"
        else:
            return None
    else:  # daily
        if pct >= DAILY_RED_PCT:
            severity = "red"
        elif pct >= DAILY_YELLOW_PCT:
            severity = "yellow"
        else:
            return None

    return _build_alert(
        slug, platform, severity, ch_type,
        f"{camp_name} {ch_type} cap raised {pct*100:.0f}% (${old_amt:,.0f} → ${new_amt:,.0f})",
        ch,
    )


def _build_alert(slug: str, platform: str, severity: str, ch_type: str, summary: str, ch: dict) -> dict:
    return {
        "layer": "changes",
        "platform": platform,
        "severity": severity,
        "signature": f"changes:{platform}:{ch.get('campaign_id', '?')}:{ch_type}",
        "summary": f"{platform.capitalize()}: {summary}",
        "data": {
            "campaign_id": ch.get("campaign_id"),
            "campaign_name": ch.get("campaign_name"),
            "old_amount": ch.get("old_amount"),
            "new_amount": ch.get("new_amount"),
            "pct_change": ch.get("pct_change"),
            "change_ts": ch.get("change_ts"),
            "user_email": ch.get("user_email"),
            "type": ch_type,
        },
        "suggested_action": (
            "If intentional, reply 'ack' to silence. "
            "If accidental, revert in the ad platform UI immediately."
        ),
    }
