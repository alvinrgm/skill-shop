"""Pre-flight health checks for the ad-spend-monitor.

The monitor reads the Google Ads OAuth refresh token from the package `.env`
(see lib/fetchers/google.py). When that token expires or is revoked, every
per-client Google fetch raises and the failure is only written into the daily
JSONL record — nobody gets pinged, and the monitor can silently go dark across
the whole roster.

`check_google_auth()` does one cheap auth call up front so the monitor can
post a Slack alert and abort loudly instead of failing quietly per-client.
"""
from __future__ import annotations

from typing import Optional

from .fetchers import google as google_fetcher


# Substrings that mark an auth/token failure specifically (vs. a transient
# network or per-account error we don't want to false-alarm on).
_AUTH_MARKERS = (
    "invalid_grant",
    "expired or revoked",
    "RefreshError",
    "unauthorized_client",
    "invalid_client",
    "AuthenticationError",
    "USER_PERMISSION_DENIED",
    "OAUTH_TOKEN",
)


def check_google_auth(login_customer_id: Optional[str] = None) -> dict:
    """Attempt a minimal authenticated Google Ads call against the MCC.

    Returns {"ok": True} on success, or
    {"ok": False, "is_auth": bool, "error": str} on failure.
    `is_auth` distinguishes a dead token (actionable: re-auth) from a transient
    error (retry next run).
    """
    try:
        env = google_fetcher._load_env()
        mcc = login_customer_id or env["GOOGLE_ADS_LOGIN_CUSTOMER_ID"]
        client = google_fetcher._make_client(login_customer_id)
        svc = client.get_service("GoogleAdsService")
        # Cheapest possible authenticated read: one row from the MCC itself.
        list(svc.search(
            customer_id=str(mcc),
            query="SELECT customer.id FROM customer LIMIT 1",
        ))
        return {"ok": True}
    except Exception as exc:  # noqa: BLE001
        msg = f"{type(exc).__name__}: {exc}"
        is_auth = any(m.lower() in msg.lower() for m in _AUTH_MARKERS)
        return {"ok": False, "is_auth": is_auth, "error": msg}


def auth_alert_text(error: str) -> str:
    """Slack alert body for a dead Google Ads token."""
    return (
        ":rotating_light: *ad-spend-monitor: Google Ads auth is DOWN*\n"
        "The Google Ads OAuth refresh token failed a pre-flight check, so "
        "*no Google spend was pulled for any client this run.*\n\n"
        f"```{error[:400]}```\n"
        "*Fix (≈2 min, needs a browser login):*\n"
        "Re-mint the refresh token via your Google Ads OAuth setup flow, "
        "signing in with the account that owns your MCC and granting the "
        "AdWords scope. The new token writes back to the env file the monitor "
        "reads (GOOGLE_ADS_ENV / the package `.env`)."
    )
