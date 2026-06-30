"""Append-only audit log — every AM action (data pull, deck prepend, alert)
is recorded so you have a verifiable record of what the system did.

One JSONL file per day under history/audit/.
"""
import datetime
import json
import os

AUDIT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "history", "audit"))


def log(event, **fields):
    os.makedirs(AUDIT_DIR, exist_ok=True)
    now = datetime.datetime.now()
    rec = {"ts": now.isoformat(timespec="seconds"), "event": event}
    rec.update(fields)
    path = os.path.join(AUDIT_DIR, f"{now:%Y-%m-%d}.jsonl")
    with open(path, "a") as f:
        f.write(json.dumps(rec) + "\n")
    return rec
