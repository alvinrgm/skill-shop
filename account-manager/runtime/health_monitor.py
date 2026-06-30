#!/usr/bin/env python3
"""Module D-lite — daily data-pipeline health monitor.

Checks every reporting client's raw-data sheets for staleness / broken
connectors (e.g. a sheet connector -> Meta, Looker-native -> Google, TikTok).
Alerts you via Slack on any issue. Recommend-only: it NEVER touches the sheets
or accounts — it only reports.

Run modes:
  --dry      print results, no Slack send
  (default)  send a Slack DM only if there are issues
  --always   send a Slack DM even when all-clear (use for a weekly heartbeat)
"""
import sys

sys.path.insert(0, __file__.rsplit("/", 1)[0])
from lib import clients, sheets_data, slack, audit  # noqa: E402


def main():
    dry = "--dry" in sys.argv
    always = "--always" in sys.argv
    roster = clients.roster()
    all_issues = []
    lines = []
    for cfg in roster:
        ok, issues, reports = sheets_data.check_client(cfg)
        all_issues += issues
        status = "OK" if ok else "STALE"
        ages = ", ".join(f"{r['name']}: {r['age_days']}d" for r in reports)
        lines.append(f"{'✅' if ok else '🔴'} {cfg['name']} [{status}] — {ages or 'no sheets'}")
    report = "\n".join(lines) if lines else "(no clients with reporting configured)"
    print(report)
    audit.log("health_check", clients=len(roster), issues=len(all_issues),
              detail=all_issues)

    if dry:
        return 0
    if all_issues or always:
        head = ("🔴 *AM data-health: action needed*" if all_issues
                else "✅ *AM data-health: all clear*")
        body = head + "\n" + report
        if all_issues:
            body += "\n\n*Issues:*\n• " + "\n• ".join(all_issues)
        code = slack.notify(body)
        audit.log("health_alert", sent=bool(code), http=code, issues=len(all_issues))
        print(f"\nslack notify -> {code}")
    return 1 if all_issues else 0


if __name__ == "__main__":
    sys.exit(main())
