"""Parses the client roster's {slug}/account.md files into dicts.

Each account.md has key-value lines like `- foo: bar` under section headers.
We extract the four sections ad-spend-monitor cares about:
  ## Ad accounts        → google_customer_id, meta_account_id
  ## Budget tracking    → budget_source, budget_sheet_id, budget_extraction_hint, budget_channel_split
  ## Safety caps        → daily_google_max, daily_meta_max
  ## Stakeholders       → slack channel
"""
from __future__ import annotations

from pathlib import Path

MONITOR_SECTIONS = {
    "ad accounts",
    "budget tracking",
    "safety caps",
    "stakeholders",
}


def load_all(clients_dir: Path) -> list[dict]:
    """Walk clients_dir, return one dict per real client folder (skip _template, hidden)."""
    out = []
    for child in sorted(clients_dir.iterdir()):
        if not child.is_dir() or child.name.startswith("_") or child.name.startswith("."):
            continue
        account_md = child / "account.md"
        if not account_md.exists():
            continue
        cfg = _parse_account_md(account_md)
        cfg["slug"] = child.name
        out.append(cfg)
    return out


def _parse_account_md(path: Path) -> dict:
    """Parse `- key: value` lines under known section headers. Tolerant of inline `# comments`."""
    cfg: dict = {}
    current_section: str | None = None

    for raw in path.read_text().splitlines():
        line = raw.rstrip()
        if line.startswith("## "):
            # strip parenthetical hints like "## Safety caps (used by ad-spend-monitor — optional)"
            header = line[3:].split("(", 1)[0].strip().lower()
            current_section = header if header in MONITOR_SECTIONS else None
            continue
        if current_section is None or ":" not in line:
            continue
        key_part, value_part = line.split(":", 1)
        key = key_part.strip().lstrip("- ").lower().replace(" ", "_")
        value = _strip_inline_comment(value_part).strip()
        if not value:
            continue
        cfg[key] = value

    # Numeric coercion for the caps
    for k in ("daily_google_max", "daily_meta_max"):
        if k in cfg:
            try:
                cfg[k] = float(str(cfg[k]).replace("$", "").replace(",", ""))
            except ValueError:
                cfg.pop(k, None)

    return cfg


def _strip_inline_comment(s: str) -> str:
    """Strip `# comment` from end of value, but leave URLs/colors intact."""
    if " #" in s:
        return s.split(" #", 1)[0]
    if s.lstrip().startswith("#"):
        return ""
    return s


if __name__ == "__main__":
    # Smoke test: print parsed configs
    import json
    import os
    from pathlib import Path as _P

    root = _P(os.environ.get(
        "AM_ROSTER_DIR",
        _P(__file__).resolve().parent.parent / "runtime" / "clients",
    ))
    for c in load_all(root):
        print(json.dumps(c, indent=2))
