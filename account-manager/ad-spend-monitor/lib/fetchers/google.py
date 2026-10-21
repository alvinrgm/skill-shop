"""Google Ads spend fetcher.

Reads the Google Ads OAuth credentials (developer token, refresh token,
client id/secret, MCC login id) from an env file. By default this is the
package `.env`; override the location with the GOOGLE_ADS_ENV environment
variable. The same credentials can also be supplied directly in os.environ.

Output shape (per ad account):
{
    "yesterday": 1500.00,
    "mtd": 42000.00,
    "trailing_30d_daily_avg": 1500.00,
    "history_days": 31,
    "by_day": {"2025-01-29": 1500.00, "2025-01-28": 1400.00, ...},   # for debugging
}
"""
from __future__ import annotations

import os
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

from google.ads.googleads.client import GoogleAdsClient

# Google Ads credentials env file. Defaults to the package `.env`; override
# with GOOGLE_ADS_ENV. Credentials already present in os.environ also work.
PACKAGE_ROOT = Path(__file__).resolve().parents[3]
ENV_PATH = Path(os.environ.get("GOOGLE_ADS_ENV", PACKAGE_ROOT / ".env"))


def _load_env() -> dict:
    env = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                env[k.strip()] = v.strip()
    # Mirror into os.environ so the google-ads library picks them up if needed
    for k, v in env.items():
        os.environ.setdefault(k, v)
    # Fall back to anything already in the environment
    for k in (
        "GOOGLE_ADS_DEVELOPER_TOKEN", "GOOGLE_ADS_CLIENT_ID",
        "GOOGLE_ADS_CLIENT_SECRET", "GOOGLE_ADS_REFRESH_TOKEN",
        "GOOGLE_ADS_LOGIN_CUSTOMER_ID",
    ):
        if k not in env and k in os.environ:
            env[k] = os.environ[k]
    return env


def _make_client(login_customer_id: Optional[str] = None) -> GoogleAdsClient:
    env = _load_env()
    return GoogleAdsClient.load_from_dict({
        "developer_token": env["GOOGLE_ADS_DEVELOPER_TOKEN"],
        "client_id": env["GOOGLE_ADS_CLIENT_ID"],
        "client_secret": env["GOOGLE_ADS_CLIENT_SECRET"],
        "refresh_token": env["GOOGLE_ADS_REFRESH_TOKEN"],
        "login_customer_id": str(login_customer_id) if login_customer_id else env["GOOGLE_ADS_LOGIN_CUSTOMER_ID"],
        "use_proto_plus": True,
    })


def fetch_spend(
    google_customer_id: str,
    login_customer_id: Optional[str] = None,
    today: Optional[date] = None,
) -> dict:
    """Pull last 31 days of daily spend for one Google Ads account, derive the three metrics.

    `today` is injectable for tests; defaults to date.today() in the system tz.
    """
    today = today or date.today()
    yesterday = today - timedelta(days=1)
    range_start = today - timedelta(days=31)

    client = _make_client(login_customer_id)
    svc = client.get_service("GoogleAdsService")

    query = f"""
        SELECT
          segments.date,
          metrics.cost_micros
        FROM customer
        WHERE segments.date BETWEEN '{range_start.isoformat()}' AND '{today.isoformat()}'
    """

    by_day: dict[str, float] = {}
    for row in svc.search(customer_id=str(google_customer_id), query=query):
        d = row.segments.date
        cost = row.metrics.cost_micros / 1_000_000.0
        by_day[d] = by_day.get(d, 0.0) + cost

    yesterday_iso = yesterday.isoformat()
    today_iso = today.isoformat()
    month_prefix = today.strftime("%Y-%m")

    # MTD = sum of completed days in current month (everything up to and including yesterday)
    mtd = sum(c for d, c in by_day.items() if d.startswith(month_prefix) and d <= yesterday_iso)

    # Trailing 30d avg = mean of last 30 complete days (exclude partial 'today')
    complete_days_sorted = sorted(d for d in by_day if d != today_iso)
    last_30 = complete_days_sorted[-30:]
    trailing_30d_daily_avg = (
        sum(by_day[d] for d in last_30) / len(last_30) if last_30 else 0.0
    )

    return {
        "yesterday": round(by_day.get(yesterday_iso, 0.0), 2),
        "mtd": round(mtd, 2),
        "trailing_30d_daily_avg": round(trailing_30d_daily_avg, 2),
        "history_days": len([d for d in by_day if d != today_iso]),
        "by_day": {d: round(c, 2) for d, c in sorted(by_day.items())},
    }


def fetch_budget_changes(
    google_customer_id: str,
    since: "dt.datetime",
    login_customer_id: Optional[str] = None,
) -> list[dict]:
    """Fetch campaign_budget changes since `since` (datetime, UTC). Layer 4.

    Returns list of dicts:
    [{
        "campaign_id": "123",
        "campaign_name": "Example Campaign",
        "change_ts": "2025-01-01T14:00:00Z",
        "user_email": "buyer@example.com",
        "changed_fields": ["amount_micros"],
        "old_amount": 250.0,
        "new_amount": 450.0,
        "pct_change": 0.80,
    }]
    """
    import datetime as dt
    client = _make_client(login_customer_id)
    svc = client.get_service("GoogleAdsService")

    import datetime as dt
    now = dt.datetime.utcnow()
    since_str = since.strftime("%Y-%m-%d %H:%M:%S")
    now_str = now.strftime("%Y-%m-%d %H:%M:%S")
    query = f"""
        SELECT
          change_event.change_date_time,
          change_event.changed_fields,
          change_event.old_resource,
          change_event.new_resource,
          change_event.resource_change_operation,
          change_event.user_email,
          change_event.change_resource_type,
          campaign.id,
          campaign.name
        FROM change_event
        WHERE change_event.change_date_time >= '{since_str}'
          AND change_event.change_date_time <= '{now_str}'
          AND change_event.change_resource_type = 'CAMPAIGN_BUDGET'
          AND change_event.resource_change_operation = 'UPDATE'
        ORDER BY change_event.change_date_time DESC
        LIMIT 100
    """

    out: list[dict] = []
    try:
        for row in svc.search(customer_id=str(google_customer_id), query=query):
            ce = row.change_event
            old_amount = _extract_budget_amount(ce.old_resource)
            new_amount = _extract_budget_amount(ce.new_resource)
            if old_amount is None or new_amount is None:
                continue
            pct = (new_amount - old_amount) / old_amount if old_amount > 0 else None
            out.append({
                "campaign_id": str(row.campaign.id),
                "campaign_name": row.campaign.name,
                "change_ts": str(ce.change_date_time),
                "user_email": ce.user_email,
                "changed_fields": [f for f in ce.changed_fields.paths] if ce.changed_fields else [],
                "old_amount": old_amount,
                "new_amount": new_amount,
                "pct_change": pct,
                "type": "daily",  # campaign_budget is daily for non-PMax; treat all as daily for v1
            })
    except Exception as exc:  # noqa: BLE001
        # change_event has data-retention limits; some accounts may not have data
        raise RuntimeError(f"change_event query failed for {google_customer_id}: {exc}") from exc

    return out


def _extract_budget_amount(resource_proto_str: str) -> float | None:
    """Parse `amount_micros: 250000000` from a CampaignBudget resource proto string.

    The Google Ads API returns old_resource/new_resource as a string repr of the
    proto. We grep for amount_micros and convert.
    """
    if not resource_proto_str:
        return None
    import re
    m = re.search(r"amount_micros[:\s]+(\d+)", str(resource_proto_str))
    if m:
        return int(m.group(1)) / 1_000_000.0
    return None


if __name__ == "__main__":
    # Smoke test: pass a Google Ads customer ID (no dashes) as the first arg.
    import json
    import sys
    if len(sys.argv) < 2:
        print("usage: python google.py <google_customer_id>", file=sys.stderr)
        sys.exit(1)
    cid = sys.argv[1]
    out = fetch_spend(cid)
    # Drop by_day for terse output
    summary = {k: v for k, v in out.items() if k != "by_day"}
    print(json.dumps(summary, indent=2))
