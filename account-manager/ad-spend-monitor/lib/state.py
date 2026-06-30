"""Persistent state — history JSONL + suppression list.

Two kinds of state:

1. History (append-only, never mutated):
    history/spend/{slug}-{YYYY-MM}.jsonl       — one line per daily run
    history/budgets/{slug}-{YYYY-MM}.json      — cached extracted budget (Phase 5)
    history/alerts/{YYYY-MM-DD}.jsonl          — every alert fired today (Phase 3)

2. Mutable state per client (Phase 2):
    state/{slug}.json — { suppression: { "<sig>": "<expires_at>" }, last_run: "<iso>" }

Suppression key shape: `{layer}:{platform}:{coarse_signature}`
"""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

SUPPRESSION_TTL_HOURS = 24


# ────────────────────────────────────────────────────────────────────────────
# History
# ────────────────────────────────────────────────────────────────────────────

def append_spend_record(history_dir: Path, slug: str, record: dict) -> Path:
    """Append one daily record to history/spend/{slug}-{YYYY-MM}.jsonl. Returns the path."""
    today_ym = dt.date.today().strftime("%Y-%m")
    path = history_dir / "spend" / f"{slug}-{today_ym}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(record, default=str) + "\n")
    return path


def append_alert_record(history_dir: Path, alert: dict) -> Path:
    """Append one alert to history/alerts/{YYYY-MM-DD}.jsonl. Phase 3."""
    today = dt.date.today().isoformat()
    path = history_dir / "alerts" / f"{today}.jsonl"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(json.dumps(alert, default=str) + "\n")
    return path


# ────────────────────────────────────────────────────────────────────────────
# Suppression (Phase 2)
# ────────────────────────────────────────────────────────────────────────────

def _state_path(state_dir: Path, slug: str) -> Path:
    return state_dir / f"{slug}.json"


def _load_state(state_dir: Path, slug: str) -> dict:
    p = _state_path(state_dir, slug)
    if not p.exists():
        return {"suppression": {}, "last_run": None}
    try:
        return json.loads(p.read_text())
    except (json.JSONDecodeError, FileNotFoundError):
        return {"suppression": {}, "last_run": None}


def _save_state(state_dir: Path, slug: str, state: dict) -> None:
    p = _state_path(state_dir, slug)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, indent=2, default=str))


_SEVERITY_RANK = {"yellow": 1, "red": 2}


def is_suppressed(state_dir: Path, slug: str, alert: dict) -> bool:
    """True if same signature already fired in last 24h at same OR higher severity.

    Escalation breaks suppression: yellow → red always fires through.
    """
    state = _load_state(state_dir, slug)
    suppression = state.get("suppression", {})
    entry = suppression.get(alert["signature"])
    if not entry:
        return False

    expires_at = dt.datetime.fromisoformat(entry["expires_at"].rstrip("Z"))
    if dt.datetime.utcnow() > expires_at:
        return False  # expired

    stored_severity = entry.get("severity", "yellow")
    new_severity = alert.get("severity", "yellow")
    if _SEVERITY_RANK.get(new_severity, 0) > _SEVERITY_RANK.get(stored_severity, 0):
        return False  # escalation — let it fire

    return True


def record_suppression(state_dir: Path, slug: str, alert: dict) -> None:
    """Add a fired alert to the suppression list with TTL."""
    state = _load_state(state_dir, slug)
    suppression = state.get("suppression", {})
    expires = dt.datetime.utcnow() + dt.timedelta(hours=SUPPRESSION_TTL_HOURS)
    suppression[alert["signature"]] = {
        "severity": alert.get("severity", "yellow"),
        "fired_at": dt.datetime.utcnow().isoformat() + "Z",
        "expires_at": expires.isoformat() + "Z",
        "summary": alert.get("summary", ""),
    }
    state["suppression"] = suppression
    _save_state(state_dir, slug, state)


def prune_expired_suppressions(state_dir: Path, slug: str) -> int:
    """Remove expired entries from suppression list. Returns count pruned."""
    state = _load_state(state_dir, slug)
    suppression = state.get("suppression", {})
    now = dt.datetime.utcnow()
    expired_keys = [
        k for k, v in suppression.items()
        if dt.datetime.fromisoformat(v["expires_at"].rstrip("Z")) < now
    ]
    for k in expired_keys:
        del suppression[k]
    if expired_keys:
        state["suppression"] = suppression
        _save_state(state_dir, slug, state)
    return len(expired_keys)


def mark_last_run(state_dir: Path, slug: str) -> None:
    """Record the timestamp of the most recent successful run for this client."""
    state = _load_state(state_dir, slug)
    state["last_run"] = dt.datetime.utcnow().isoformat() + "Z"
    _save_state(state_dir, slug, state)
