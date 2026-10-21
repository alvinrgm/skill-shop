"""Daily ad-spend monitor — entry point.

Usage:
    python monitor.py                                  # run all clients
    python monitor.py --client example-brand           # one client
    python monitor.py --client example-brand --dry-run # no Slack send
    python monitor.py --skip-meta                      # debug: skip Meta fetch

The daily loop is intentionally simple. See ad-spend-monitor/README.md.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PACKAGE_ROOT = ROOT.parent

# Client roster. Defaults to the package roster (runtime/clients), where each
# client is a <slug>/account.md folder (copy runtime/clients/_template to start).
# Override with AM_ROSTER_DIR to point at an external roster.
CLIENTS_DIR = Path(os.environ.get("AM_ROSTER_DIR", PACKAGE_ROOT / "runtime" / "clients"))
HISTORY_DIR = ROOT / "history"
STATE_DIR = ROOT / "state"

# Make local modules importable regardless of cwd
sys.path.insert(0, str(ROOT))

# Per-run snapshot of budgets we used (so we can attach to each spend record)
_last_budget_snapshot: dict[str, dict] = {}

from clients_loader import load_all  # noqa: E402
from lib import state  # noqa: E402
from lib.fetchers import google as google_fetcher  # noqa: E402
from lib.fetchers import meta as meta_fetcher  # noqa: E402
from lib.layers import caps as caps_layer  # noqa: E402
from lib.layers import changes as changes_layer  # noqa: E402
from lib.layers import pacing as pacing_layer  # noqa: E402
from lib.layers import rate as rate_layer  # noqa: E402
from lib import budget_extractor  # noqa: E402
from lib import slack as slack_client  # noqa: E402
from lib import health  # noqa: E402


def main() -> int:
    args = _parse_args()
    today = dt.date.today()

    clients = load_all(CLIENTS_DIR)
    if args.client:
        clients = [c for c in clients if c["slug"] == args.client]
    if not clients:
        print(f"No client configs found in {CLIENTS_DIR}", file=sys.stderr)
        return 1

    # Pre-flight: confirm the shared Google OAuth token is alive before we run.
    # A dead token otherwise fails every client's Google fetch silently.
    if any(c.get("google_customer_id") for c in clients):
        h = health.check_google_auth()
        if not h["ok"] and h.get("is_auth"):
            print(f"FATAL: Google Ads auth pre-flight failed: {h['error']}", file=sys.stderr)
            res = slack_client.send_message(health.auth_alert_text(h["error"]), dry_run=args.dry_run)
            print(f"  ↳ auth-down DM: sent={res.get('sent')} via={res.get('via')}", file=sys.stderr)
            return 2
        elif not h["ok"]:
            # Non-auth (transient/network) failure — log but continue; per-client
            # error handling and next run will catch it.
            print(f"WARN: Google pre-flight non-auth failure, continuing: {h['error']}", file=sys.stderr)

    all_records: list[dict] = []

    for client in clients:
        slug = client["slug"]

        # Skip clients with no ad accounts configured for the monitor
        if not (client.get("google_customer_id") or client.get("meta_account_id")):
            print(f"  ⊘ {slug}: no ad accounts configured, skipping", file=sys.stderr)
            continue

        print(f"→ {slug}", file=sys.stderr)

        record = {
            "slug": slug,
            "run_ts": dt.datetime.utcnow().isoformat() + "Z",
            "today": today.isoformat(),
            "accounts": {},
        }

        # Google
        google_cid = client.get("google_customer_id")
        if google_cid:
            try:
                data = google_fetcher.fetch_spend(google_cid, today=today)
                _log_account(slug, "google", data)
                # Drop by_day from persisted record — too verbose for JSONL
                record["accounts"]["google"] = {k: v for k, v in data.items() if k != "by_day"}
            except Exception as exc:  # noqa: BLE001
                _log_error(slug, "google", exc)
                record["accounts"]["google"] = {"error": str(exc), "traceback": traceback.format_exc()}

        # Meta
        meta_acct = client.get("meta_account_id")
        if meta_acct and not args.skip_meta:
            try:
                data = meta_fetcher.fetch_spend(meta_acct, today=today)
                _log_account(slug, "meta", data)
                record["accounts"]["meta"] = {k: v for k, v in data.items() if k != "by_day"}
            except Exception as exc:  # noqa: BLE001
                _log_error(slug, "meta", exc)
                record["accounts"]["meta"] = {"error": str(exc), "traceback": traceback.format_exc()}

        # Layer 4 changes (Google only for v1; Meta snapshot-diff is TODO)
        record["budget_changes"] = {}
        if google_cid and not args.skip_changes:
            try:
                since = dt.datetime.utcnow() - dt.timedelta(hours=24)
                changes = google_fetcher.fetch_budget_changes(google_cid, since=since)
                record["budget_changes"]["google"] = changes
                if changes:
                    print(f"  google: {len(changes)} budget cap change(s) in last 24h", file=sys.stderr)
            except Exception as exc:  # noqa: BLE001
                print(f"  google changes: ERROR {type(exc).__name__}: {exc}", file=sys.stderr)
                record["budget_changes"]["google_error"] = str(exc)

        # Run anomaly layers + suppression
        state.prune_expired_suppressions(STATE_DIR, slug)
        alerts = _run_layers(slug, client, record["accounts"], today)
        # Snapshot the budget that was used (if any) into the daily record
        if (b := _last_budget_snapshot.get(slug)) is not None:
            record["budget"] = {
                "month": b.get("month"),
                "meta_budget": b.get("meta_budget"),
                "google_budget": b.get("google_budget"),
                "combined_budget": b.get("combined_budget"),
                "source": b.get("source"),
                "confidence": b.get("confidence"),
            }
        # Layer 4 — append cap-change alerts
        for platform, changes in record.get("budget_changes", {}).items():
            if not isinstance(changes, list):
                continue
            alerts.extend(changes_layer.evaluate(slug, platform, changes))
        record["alerts_fired"] = []
        record["alerts_suppressed"] = []
        for alert in alerts:
            if state.is_suppressed(STATE_DIR, slug, alert):
                print(f"  ⊘ suppressed: {alert['summary']}", file=sys.stderr)
                record["alerts_suppressed"].append(alert["signature"])
                continue
            tag = "🔴" if alert["severity"] == "red" else "🟡"
            print(f"  {tag} {alert['summary']}", file=sys.stderr)
            channel = client.get("slack_channel")
            slack_result = slack_client.send_alert(channel, slug, alert, dry_run=args.dry_run)
            record["alerts_fired"].append({**alert, "delivery": slack_result})
            state.append_alert_record(HISTORY_DIR, {**alert, "slug": slug, "channel": channel, "delivery": slack_result})
            state.record_suppression(STATE_DIR, slug, alert)
            print(f"      ↳ slack: {slack_result.get('via')} sent={slack_result.get('sent')}", file=sys.stderr)

        # Persist final record + mark last_run (after layers so alerts_fired is included)
        path = state.append_spend_record(HISTORY_DIR, slug, record)
        state.mark_last_run(STATE_DIR, slug)
        print(f"  → wrote {path.name}", file=sys.stderr)

        all_records.append(record)

    # Phase 3: send Slack alerts
    # Phase 9: daily roll-up thread per channel
    _write_daily_summary(today, all_records)
    return 0


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser()
    p.add_argument("--client", help="Only run for this client slug (e.g. example-brand)")
    p.add_argument("--dry-run", action="store_true", help="Don't send Slack alerts")
    p.add_argument("--skip-meta", action="store_true", help="Skip Meta fetch (debug)")
    p.add_argument("--skip-changes", action="store_true", help="Skip Layer 4 cap-change fetch (debug)")
    return p.parse_args()


def _run_layers(slug: str, client: dict, accounts: dict, today: dt.date) -> list[dict]:
    """Run Layers 1-3 (Layer 4 runs separately, has its own fetch path).

    Layer 1 (pacing) needs the monthly budget — pulled via budget_extractor.
    Skipped if client has budget_source: none, or if extraction failed.
    """
    alerts: list[dict] = []

    # Pull budget once per client (used by Layer 1 across all platforms)
    budget_dict = _get_budget(slug, client, today) if client.get("budget_source") == "google_sheet" else None
    if budget_dict:
        _last_budget_snapshot[slug] = budget_dict

    for platform, data in accounts.items():
        if "error" in data:
            continue
        cap_key = f"daily_{platform}_max"
        cap = client.get(cap_key)

        # Layer 3 — manual hard caps
        if a := caps_layer.evaluate(
            slug=slug,
            platform=platform,
            yesterday=data.get("yesterday", 0.0),
            cap=cap,
        ):
            alerts.append(a)

        # Layer 2 — rate vs trailing 30d avg
        if a := rate_layer.evaluate(
            slug=slug,
            platform=platform,
            yesterday=data.get("yesterday", 0.0),
            trailing_30d_avg=data.get("trailing_30d_daily_avg", 0.0),
            history_days=data.get("history_days", 0),
        ):
            alerts.append(a)

        # Layer 1 — budget pacing (per platform when channel_split=per-channel, else combined)
        if budget_dict and budget_dict.get("confidence", 0) >= 0.5:
            platform_budget = _budget_for_platform(client, budget_dict, platform)
            if platform_budget:
                if a := pacing_layer.evaluate(
                    slug=slug,
                    platform=platform,
                    mtd_spend=data.get("mtd", 0.0),
                    monthly_budget=platform_budget,
                    today=today,
                ):
                    alerts.append(a)

    # Red before yellow
    alerts.sort(key=lambda a: 0 if a["severity"] == "red" else 1)
    return alerts


def _get_budget(slug: str, client: dict, today: dt.date) -> dict | None:
    """Fetch + cache the current-month budget for this client. Returns None on failure."""
    sheet_id = client.get("budget_sheet_id")
    hint = client.get("budget_extraction_hint", "")
    if not sheet_id:
        return None
    month_first = today.replace(day=1)
    try:
        return budget_extractor.extract(
            slug=slug,
            sheet_id=sheet_id,
            extraction_hint=hint,
            month=month_first,
            cache_dir=HISTORY_DIR / "budgets",
        )
    except Exception as exc:  # noqa: BLE001
        print(f"  budget extractor failed for {slug}: {exc}", file=sys.stderr)
        return None


def _budget_for_platform(client: dict, budget: dict, platform: str) -> float | None:
    """Return the budget number to use for a given platform.

    Respects budget_channel_split:
        per-channel → use meta_budget for Meta, google_budget for Google
        combined    → use combined_budget for both (split is informational only)
    """
    split = (client.get("budget_channel_split") or "combined").lower()
    if split == "per-channel":
        return budget.get(f"{platform}_budget")
    return budget.get("combined_budget")


def _log_account(slug: str, platform: str, data: dict) -> None:
    print(
        f"  {platform}: yesterday=${data['yesterday']:>9,.2f}  "
        f"mtd=${data['mtd']:>10,.2f}  "
        f"30d_avg=${data['trailing_30d_daily_avg']:>9,.2f}  "
        f"(history={data['history_days']}d)",
        file=sys.stderr,
    )


def _log_error(slug: str, platform: str, exc: Exception) -> None:
    print(f"  {platform}: ERROR {type(exc).__name__}: {exc}", file=sys.stderr)


def _write_daily_summary(today: dt.date, records: list[dict]) -> None:
    """Write a markdown roll-up of today's run to history/daily-summary-{date}.md."""
    path = HISTORY_DIR / f"daily-summary-{today.isoformat()}.md"
    lines = [f"# Daily summary — {today.isoformat()}", ""]
    for r in records:
        lines.append(f"## {r['slug']}")
        for platform, data in r["accounts"].items():
            if "error" in data:
                lines.append(f"- **{platform}**: ❌ {data['error']}")
            else:
                lines.append(
                    f"- **{platform}**: yesterday ${data['yesterday']:,.2f} · "
                    f"MTD ${data['mtd']:,.2f} · "
                    f"30d avg ${data['trailing_30d_daily_avg']:,.2f}"
                )
        fired = r.get("alerts_fired", [])
        suppressed = r.get("alerts_suppressed", [])
        if fired:
            lines.append("")
            lines.append("**Alerts fired:**")
            for a in fired:
                tag = "🔴" if a["severity"] == "red" else "🟡"
                lines.append(f"- {tag} {a['summary']}")
        if suppressed:
            lines.append(f"_Suppressed (already alerted recently): {len(suppressed)}_")
        lines.append("")
    path.write_text("\n".join(lines))


if __name__ == "__main__":
    sys.exit(main())
