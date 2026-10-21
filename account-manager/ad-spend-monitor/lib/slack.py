"""Slack alert formatting + send.

Two delivery modes (auto-selected):

1. **Bot token (preferred)** — env var SLACK_BOT_TOKEN (xoxb-...). Uses
   chat.postMessage to post in the client's specific channel.
   Setup: api.slack.com/apps → your app → OAuth & Permissions →
   add chat:write scope, install/reinstall workspace, copy Bot User OAuth
   Token. Then /invite the bot into each client channel.

2. **Webhook fallback** — env var SLACK_WEBHOOK (an incoming-webhook URL).
   Posts to whatever channel/DM the webhook is bound to (no per-client
   routing). Alert text gets a [client_slug] prefix so you can tell which
   client tripped. (SLACK_WEBHOOK is also accepted for compatibility.)

Both are read from the environment / the package `.env` — no secrets are
hardcoded here.

If neither is configured, alerts still go to history JSONL — they just
don't reach Slack. The script logs a clear warning.

Alert format:
    🟡 example-brand — meta 1.50× trailing 30d daily avg
    Yesterday:  $3,000.00
    30d avg:    $2,000.00

    Likely cause: Layer 2 (rate)
    Suggested:   Check recent budget cap changes or campaign launches.
                 If intentional, reply 'ack' to silence.
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]          # ad-spend-monitor/
PACKAGE_ROOT = ROOT.parent                          # package root
LOCAL_ENV = ROOT / ".env"
PACKAGE_ENV = Path(os.environ.get("AM_ENV", PACKAGE_ROOT / ".env"))


def _load_env_into_os() -> None:
    """Merge the monitor-local .env and the package .env into os.environ (idempotent)."""
    for env_file in (LOCAL_ENV, PACKAGE_ENV):
        if env_file.exists():
            for line in env_file.read_text().splitlines():
                if "=" in line and not line.strip().startswith("#"):
                    k, v = line.split("=", 1)
                    k = k.strip()
                    v = v.strip().strip('"').strip("'")
                    os.environ.setdefault(k, v)


def _get_bot_token() -> str | None:
    _load_env_into_os()
    t = os.environ.get("SLACK_BOT_TOKEN")
    return t.strip() if t else None


def _get_fallback_webhook() -> str | None:
    """Slack incoming-webhook URL, read from the environment / .env only."""
    _load_env_into_os()
    for key in ("SLACK_WEBHOOK", "SLACK_WEBHOOK", "SLACK_WEBHOOK"):
        if w := os.environ.get(key):
            return w.strip()
    return None


def send_alert(channel: str | None, slug: str, alert: dict, dry_run: bool = False) -> dict:
    """Post one alert. Returns delivery info.

    Behavior:
        - If bot token present → chat.postMessage to the client's channel
        - Else if webhook present → post via the configured incoming webhook
        - Else log and return {"sent": False, "via": "none"}
    """
    blocks = _build_blocks(slug, alert)
    fallback = _format_fallback_text(slug, alert)

    if dry_run:
        print(f"[DRY] would post to {channel or 'DM'}:\n{fallback}\n", file=sys.stderr)
        return {"sent": True, "via": "dry-run", "channel": channel}

    token = _get_bot_token()
    if token and channel:
        return _post_via_bot(token, channel, blocks=blocks, fallback=fallback)

    webhook = _get_fallback_webhook()
    if webhook:
        return _post_via_webhook(webhook, blocks=blocks, fallback=fallback)

    print(
        "WARN: no SLACK_BOT_TOKEN or webhook configured. Alert recorded "
        "to history only, not sent.",
        file=sys.stderr,
    )
    return {"sent": False, "via": "none", "channel": channel}


def send_message(text: str, dry_run: bool = False) -> dict:
    """Post a plain-text ops message via the configured Slack webhook.

    Used for monitor-health alerts (e.g. dead Google OAuth token) that aren't
    tied to a specific client/alert shape. Prefers the webhook; falls back to
    the bot token only if no webhook is configured.
    """
    if dry_run:
        print(f"[DRY] would send Slack message:\n{text}\n", file=sys.stderr)
        return {"sent": True, "via": "dry-run"}

    webhook = _get_fallback_webhook()
    if webhook:
        r = requests.post(webhook, json={"text": text}, timeout=15)
        if r.status_code == 200:
            return {"sent": True, "via": "webhook"}
        return {"sent": False, "via": "webhook", "error": f"http_{r.status_code}: {r.text[:200]}"}

    token = _get_bot_token()
    if token:
        r = requests.post(
            "https://slack.com/api/chat.postMessage",
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            data=json.dumps({"channel": "#general", "text": text}),
            timeout=15,
        )
        body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        if r.status_code == 200 and body.get("ok"):
            return {"sent": True, "via": "bot"}
        return {"sent": False, "via": "bot", "error": body.get("error") or f"http_{r.status_code}"}

    print("WARN: no webhook or bot token for health message.", file=sys.stderr)
    return {"sent": False, "via": "none"}


def _post_via_bot(token: str, channel: str, blocks: list, fallback: str) -> dict:
    r = requests.post(
        "https://slack.com/api/chat.postMessage",
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        data=json.dumps({"channel": channel, "text": fallback, "blocks": blocks}),
        timeout=15,
    )
    body = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
    if r.status_code == 200 and body.get("ok"):
        return {"sent": True, "via": "bot", "channel": channel, "ts": body.get("ts")}
    return {
        "sent": False,
        "via": "bot",
        "channel": channel,
        "error": body.get("error") or f"http_{r.status_code}",
    }


def _post_via_webhook(webhook: str, blocks: list, fallback: str) -> dict:
    r = requests.post(webhook, json={"text": fallback, "blocks": blocks}, timeout=15)
    if r.status_code == 200:
        return {"sent": True, "via": "webhook"}
    return {"sent": False, "via": "webhook", "error": f"http_{r.status_code}: {r.text[:200]}"}


# ────────────────────────────────────────────────────────────────────────────
# Formatting — Block Kit
# ────────────────────────────────────────────────────────────────────────────
# Consistent message format across all senders:
#   ┌─ header ─────────────────────────────────┐
#   │ {sender_emoji} {TITLE} — {slug/subject}  │ ← header block (big bold)
#   └──────────────────────────────────────────┘
#   {severity_emoji} *{summary}*                  ← section
#
#   • {key}:    {value}                            ← section (numbers)
#   • {key}:    {value}
#
#   _Layer: {layer}_                                ← section (footer)
#   _{suggested_action}_
#
# Sender emoji for ad-spend-monitor is 💰 (across all alert layers).

SENDER_EMOJI = "💰"
SENDER_TITLE = "Ad Spend Alert"
_SEVERITY_EMOJI = {"red": "🔴", "yellow": "🟡"}


def _build_blocks(slug: str, alert: dict) -> list[dict]:
    severity = alert.get("severity", "yellow")
    sev_emoji = _SEVERITY_EMOJI.get(severity, "⚪")
    summary = alert.get("summary", "(no summary)")
    data = alert.get("data", {})
    layer = alert.get("layer", "?")
    suggested = alert.get("suggested_action", "")

    blocks: list[dict] = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"{SENDER_EMOJI} {SENDER_TITLE} — {slug.capitalize()}",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"{sev_emoji}  *{summary}*"},
        },
    ]

    num_lines = _numbers_block(data)
    if num_lines:
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": num_lines}})

    footer = f"_Layer: {layer}_"
    if suggested:
        footer += f"\n_{suggested}_"
    blocks.append({"type": "context", "elements": [{"type": "mrkdwn", "text": footer}]})

    return blocks


def _numbers_block(data: dict) -> str:
    """Render the data dict as a bullet list of relevant figures."""
    lines = []
    field_order = [
        ("yesterday", "Yesterday", "${:,.2f}"),
        ("mtd_spend", "MTD", "${:,.2f}"),
        ("monthly_budget", "Budget", "${:,.0f}"),
        ("projected_eom", "Projected EOM", "${:,.0f}"),
        ("ratio", "Ratio", "{:.2f}×"),
        ("trailing_30d_avg", "30d avg", "${:,.2f}"),
        ("cap", "Hard cap", "${:,.2f}"),
        ("overage", "Over by", "${:,.2f}"),
        ("old_amount", "Old cap", "${:,.2f}"),
        ("new_amount", "New cap", "${:,.2f}"),
        ("pct_change", "Change", "{:+.0%}"),
    ]
    for key, label, fmt in field_order:
        if key in data and data[key] is not None:
            try:
                lines.append(f"•  *{label}:*  {fmt.format(data[key])}")
            except (ValueError, TypeError):
                lines.append(f"•  *{label}:*  {data[key]}")
    return "\n".join(lines)


def _format_fallback_text(slug: str, alert: dict) -> str:
    """Plain-text fallback for accessibility, mobile notifications, clients without Block Kit."""
    sev_emoji = _SEVERITY_EMOJI.get(alert.get("severity", "yellow"), "⚪")
    return f"{SENDER_EMOJI} {SENDER_TITLE} — {slug.capitalize()}: {sev_emoji} {alert.get('summary', '')}"


def dm_operator(text: str) -> dict:
    """Send a plain system message (e.g. extraction failures) via the webhook."""
    webhook = _get_fallback_webhook()
    if not webhook:
        print(f"WARN: no webhook configured. Message dropped: {text[:80]}", file=sys.stderr)
        return {"sent": False, "via": "none"}
    r = requests.post(webhook, json={"text": text}, timeout=15)
    return {"sent": r.status_code == 200, "via": "webhook"}


if __name__ == "__main__":
    fake = {
        "layer": "pacing",
        "platform": "google",
        "severity": "red",
        "summary": "Google pacing 105.0% of monthly budget (projected EOM $12,600 vs $12,000 target)",
        "data": {
            "mtd_spend": 6300.00,   # day 15 of 30 -> 6,300 * 30 / 15 = 12,600
            "monthly_budget": 12000,
            "projected_eom": 12600.0,
            "ratio": 1.05,
        },
        "suggested_action": "Pause top spenders or lower daily caps. Tracking to overspend by $600.",
    }
    blocks = _build_blocks("example-brand", fake)
    print(json.dumps(blocks, indent=2))
    print("\n--- fallback text ---")
    print(_format_fallback_text("example-brand", fake))
