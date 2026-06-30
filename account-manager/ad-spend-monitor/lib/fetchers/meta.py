"""Meta Ads spend fetcher.

Standalone Python — hits the Graph API directly with an access token (no MCP,
since a cron job has no agent tools).

Token loading order:
    1. META_ACCESS_TOKEN in os.environ
    2. META_ACCESS_TOKEN in the package `.env` (or the file at META_ENV)

A user access token tied to one person may lack ads_read on all client
accounts. For reliable coverage, generate a long-lived SYSTEM USER token via
your Business Manager with ads_read scope across every ad account you want
monitored, and set it as META_ACCESS_TOKEN.

Output shape mirrors lib/fetchers/google.py:
{
    "yesterday": 1234.56,
    "mtd": 38400.00,
    "trailing_30d_daily_avg": 1300.00,
    "history_days": 31,
    "by_day": {"2026-05-29": 1234.56, ...},
}
"""
from __future__ import annotations

import os
from datetime import date, timedelta
from pathlib import Path
from typing import Optional

import requests

GRAPH_API_VERSION = "v18.0"
ROOT = Path(__file__).resolve().parents[2]          # ad-spend-monitor/
PACKAGE_ROOT = ROOT.parent                          # package root
# Env files checked (after os.environ): the monitor-local .env, then the
# package .env. Override the package one with META_ENV.
LOCAL_ENV = ROOT / ".env"
PACKAGE_ENV = Path(os.environ.get("META_ENV", PACKAGE_ROOT / ".env"))


def _load_token() -> str:
    if t := os.environ.get("META_ACCESS_TOKEN"):
        return t.strip().strip('"').strip("'")
    for env_file in (LOCAL_ENV, PACKAGE_ENV):
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if line.startswith("META_ACCESS_TOKEN="):
                    return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError(
        "META_ACCESS_TOKEN not found. Add it to ad-spend-monitor/.env or the "
        "package .env, or export it in the environment."
    )


def fetch_spend(
    meta_account_id: str,
    today: Optional[date] = None,
) -> dict:
    """Pull last 31 days of daily spend for one Meta ad account, derive the three metrics."""
    today = today or date.today()
    yesterday = today - timedelta(days=1)
    range_start = today - timedelta(days=31)

    token = _load_token()

    url = f"https://graph.facebook.com/{GRAPH_API_VERSION}/act_{meta_account_id}/insights"
    params = {
        "fields": "spend,date_start",
        "time_increment": 1,
        "time_range": '{"since":"%s","until":"%s"}' % (range_start.isoformat(), today.isoformat()),
        "level": "account",
        "limit": 500,
        "access_token": token,
    }

    by_day: dict[str, float] = {}
    while url:
        r = requests.get(url, params=params, timeout=30)
        if r.status_code != 200:
            raise RuntimeError(
                f"Meta API error {r.status_code} for act_{meta_account_id}: {r.text[:300]}"
            )
        payload = r.json()
        for row in payload.get("data", []):
            d = row.get("date_start")
            spend = float(row.get("spend", 0) or 0)
            if d:
                by_day[d] = by_day.get(d, 0.0) + spend
        # Pagination — Graph API uses cursor in paging.next
        next_url = payload.get("paging", {}).get("next")
        if next_url:
            url, params = next_url, None  # next is fully qualified
        else:
            break

    yesterday_iso = yesterday.isoformat()
    today_iso = today.isoformat()
    month_prefix = today.strftime("%Y-%m")

    mtd = sum(c for d, c in by_day.items() if d.startswith(month_prefix) and d <= yesterday_iso)

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


def fetch_budget_changes(meta_account_id: str, since: date) -> list[dict]:
    """Layer 4 — Meta campaign budget cap changes since `since`. Phase 7."""
    raise NotImplementedError("Phase 7 — implement Meta budget-change detection via Activities or snapshot diff")


if __name__ == "__main__":
    # Smoke test: pass a Meta ad account ID (no act_ prefix) as the first arg.
    import json
    import sys
    if len(sys.argv) < 2:
        print("usage: python meta.py <meta_account_id>", file=sys.stderr)
        sys.exit(1)
    acct = sys.argv[1]
    out = fetch_spend(acct)
    summary = {k: v for k, v in out.items() if k != "by_day"}
    print(json.dumps(summary, indent=2))
