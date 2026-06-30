"""Slack notifier — DMs to you (the operator) via a Slack incoming webhook.
Recommend-only: this is the ONLY outward channel, and it goes to you, never to a
client. The webhook URL is read from SLACK_WEBHOOK in the package .env."""
import json
import os
import urllib.request

_WEBHOOK = None


def _webhook():
    global _WEBHOOK
    if _WEBHOOK:
        return _WEBHOOK
    path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))
    with open(path) as f:
        for line in f:
            if line.startswith("SLACK_WEBHOOK="):
                _WEBHOOK = line.split("=", 1)[1].strip()
    return _WEBHOOK


def notify(text):
    """Post a message to the Slack webhook. Returns HTTP status (int) or None on failure."""
    url = _webhook()
    if not url:
        return None
    data = json.dumps({"text": text}).encode()
    try:
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        resp = urllib.request.urlopen(req, timeout=20)
        return resp.getcode()
    except Exception:  # noqa: BLE001
        return None
