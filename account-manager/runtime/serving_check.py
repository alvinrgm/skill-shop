#!/usr/bin/env python3
"""Daily serving / disapproval check — catches the gap where an ENABLED campaign
silently stops serving (or an ad gets disapproved) and sits dead for days.
Deterministic, no Claude, no API cost. Runs under the GOOGLE-ADS venv (needs the
google-ads library + OAuth).

For each Google client in the roster it flags:
  - ENABLED campaigns that are NOT actually serving (primary_status NOT_ELIGIBLE /
    MISCONFIGURED), with the reasons
  - DISAPPROVED ads under enabled campaigns (with the policy topics)
Then Slack-DMs you if anything is wrong (or --always for an all-clear).

Run:  /path/to/google-ads/.venv/bin/python serving_check.py [--dry|--always]

MUST run under a venv that has the `google.ads` module installed. The
account-manager's own .venv may not have it — running it there throws
ModuleNotFoundError: No module named 'google.ads'. Point your scheduler at the
venv that has the google-ads library; only manual local runs hit this footgun.

Config:
  - Roster dir: AM_ROSTER_DIR env, else package-local runtime/clients.
  - GOOGLE_CLIENTS env (comma-separated slugs), else every roster slug.
  - Google OAuth: reuses the ad-spend-monitor google client builder (its own .env).
  - Default login_customer_id (manager/MCC): AM_LOGIN_CUSTOMER_ID env, else
    each client's own login_customer_id/cid from account.md.
"""
import json
import os
import re
import sys
import urllib.request

ROSTER = os.environ.get(
    "AM_ROSTER_DIR",
    os.path.abspath(os.path.join(os.path.dirname(__file__), "clients")))
# reuse the ad-spend-monitor google client builder (reads its .env OAuth).
# ad-spend-monitor is a sibling package dir at the package root.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "ad-spend-monitor")))
from lib.fetchers import google as gfetch  # noqa: E402

# Clients to check: AM_GOOGLE_CLIENTS env (comma-separated slugs), else all roster slugs.
_env_clients = os.environ.get("AM_GOOGLE_CLIENTS", "").strip()
GOOGLE_CLIENTS = ([s.strip() for s in _env_clients.split(",") if s.strip()]
                  if _env_clients else None)  # None -> resolved from roster at runtime

# campaign primary_status values that mean "enabled but not serving"
BAD_PRIMARY = {"NOT_ELIGIBLE", "MISCONFIGURED"}


def _field(text, key):
    m = re.search(rf"^\s*-\s*{re.escape(key)}\s*:\s*(.+)$", text, re.M)
    if not m:
        return None
    return re.split(r"\s{2,}#", m.group(1))[0].strip()


def _client_cfg(slug):
    path = os.path.join(ROSTER, slug, "account.md")
    if not os.path.exists(path):
        return None
    t = open(path).read()
    cid = _field(t, "google_customer_id") or _field(t, "cid")
    # manager/MCC: client's own login_customer_id, else the account-wide default, else the cid
    login = (_field(t, "login_customer_id")
             or os.environ.get("AM_LOGIN_CUSTOMER_ID")
             or cid)
    name = _field(t, "name") or slug
    return {"slug": slug, "cid": cid, "login": login, "name": name}


def check_client(cfg):
    """Return list of issue strings for one client."""
    issues = []
    client = gfetch._make_client(cfg["login"])
    svc = client.get_service("GoogleAdsService")
    cid = cfg["cid"]
    # 1) enabled-but-not-serving campaigns
    q = ("SELECT campaign.name, campaign.primary_status, campaign.primary_status_reasons "
         "FROM campaign WHERE campaign.status = 'ENABLED'")
    for r in svc.search(customer_id=cid, query=q):
        ps = r.campaign.primary_status.name
        if ps in BAD_PRIMARY:
            reasons = ", ".join(x.name for x in r.campaign.primary_status_reasons)
            issues.append(f"campaign '{r.campaign.name}' not serving ({ps}: {reasons})")
    # 2) disapproved ads under enabled campaigns
    # only LIVE ads: campaign ENABLED, ad group ENABLED, ad version ENABLED — so we
    # don't flag disapprovals on paused/removed ad versions (false positives — e.g.
    # a CAPITALIZATION policy flag that sits on REMOVED ads which never serve).
    q2 = ("SELECT campaign.name, ad_group.name, ad_group_ad.policy_summary.policy_topic_entries "
          "FROM ad_group_ad WHERE campaign.status = 'ENABLED' "
          "AND ad_group.status = 'ENABLED' AND ad_group_ad.status = 'ENABLED' "
          "AND ad_group_ad.policy_summary.approval_status = 'DISAPPROVED'")
    dis = {}
    for r in svc.search(customer_id=cid, query=q2):
        topics = ",".join(e.topic for e in r.ad_group_ad.policy_summary.policy_topic_entries)
        dis.setdefault(r.campaign.name, set()).add(topics)
    for camp, topicsets in dis.items():
        flat = ",".join(sorted({t for ts in topicsets for t in ts.split(",") if t}))
        issues.append(f"DISAPPROVED ads in '{camp}' ({flat})")
    return issues


def _slack(text):
    path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".env"))
    url = None
    for line in open(path):
        if line.startswith("SLACK_WEBHOOK="):
            url = line.split("=", 1)[1].strip()
    if not url:
        return None
    try:
        req = urllib.request.Request(url, data=json.dumps({"text": text}).encode(),
                                     headers={"Content-Type": "application/json"})
        return urllib.request.urlopen(req, timeout=20).getcode()
    except Exception:  # noqa: BLE001
        return None


def _roster_slugs():
    """Every slug in the roster dir that has an account.md."""
    if not os.path.isdir(ROSTER):
        return []
    out = []
    for name in sorted(os.listdir(ROSTER)):
        if name.startswith((".", "_")):
            continue
        if os.path.exists(os.path.join(ROSTER, name, "account.md")):
            out.append(name)
    return out


def main():
    dry = "--dry" in sys.argv
    always = "--always" in sys.argv
    clients = GOOGLE_CLIENTS if GOOGLE_CLIENTS is not None else _roster_slugs()
    all_issues = {}
    for slug in clients:
        cfg = _client_cfg(slug)
        if not cfg or not cfg["cid"]:
            continue
        try:
            issues = check_client(cfg)
        except Exception as e:  # noqa: BLE001
            issues = [f"check failed: {str(e)[:120]}"]
        status = "OK" if not issues else f"{len(issues)} issue(s)"
        print(f"{cfg['name']}: {status}")
        for i in issues:
            print(f"   - {i}")
        if issues:
            all_issues[cfg["name"]] = issues

    if dry:
        return 1 if all_issues else 0
    if all_issues or always:
        if all_issues:
            lines = ["🔴 *AM serving check: action needed*"]
            for name, issues in all_issues.items():
                lines.append(f"*{name}*")
                lines += [f"• {i}" for i in issues]
        else:
            lines = ["✅ *AM serving check: all campaigns serving, no disapprovals*"]
        _slack("\n".join(lines))
    return 1 if all_issues else 0


if __name__ == "__main__":
    sys.exit(main())
