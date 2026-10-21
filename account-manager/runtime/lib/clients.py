"""Client config loader — reads the roster at
<roster>/<slug>/account.md and extracts the `## AM reporting` section
(plus a few core fields) for the account manager.

The roster directory defaults to the package-local runtime/clients/, but can be
pointed at any roster you maintain via the AM_ROSTER_DIR env var.
"""
import os
import re

# Package-local roster by default; override with AM_ROSTER_DIR to reuse an existing roster.
# runtime/lib/clients.py -> runtime/clients
ROSTER_DIR = os.environ.get(
    "AM_ROSTER_DIR",
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "clients")))

# slug aliases: AM accepts friendly names, maps to roster folder names.
# Example: a multi-word brand name -> its underscore folder slug.
ALIASES = {
    "example-brand": "example_brand",
    "examplebrand": "example_brand",
    "example brand": "example_brand",
}


def _coerce(val):
    val = val.strip()
    if val.startswith("[") and val.endswith("]"):
        inner = val[1:-1].strip()
        return [x.strip() for x in inner.split(",") if x.strip()] if inner else []
    return val


def _parse_account_md(path):
    """Parse `- key: value` lines, tracking the current `## section`."""
    cfg = {"_sections": {}}
    section = None
    with open(path) as f:
        for raw in f:
            line = raw.rstrip("\n")
            h = re.match(r"^##\s+(.*)", line)
            if h:
                section = h.group(1).strip().lower()
                cfg["_sections"].setdefault(section, {})
                continue
            m = re.match(r"^\s*-\s*([a-zA-Z0-9_]+)\s*:\s*(.*)$", line)
            if m and section:
                key = m.group(1).strip()
                val = m.group(2)
                # strip trailing inline comments (after 2+ spaces then #)
                val = re.split(r"\s{2,}#", val)[0]
                cfg["_sections"][section][key] = _coerce(val)
    return cfg


def load(slug):
    """Return a flat config dict for one client. Raises if not found."""
    slug = ALIASES.get(slug.lower().strip(), slug.lower().strip())
    path = os.path.join(ROSTER_DIR, slug, "account.md")
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"No roster entry for '{slug}' at {path}. "
            f"Add a {slug}/account.md under your roster dir (copy clients/_template) before reporting.")
    parsed = _parse_account_md(path)
    s = parsed["_sections"]
    core = s.get("config", {})
    am = s.get("am reporting (used by account-manager / weekly-report)") or \
        s.get("am reporting") or {}
    if not am:
        # tolerate any section header that starts with "am reporting"
        for k, v in s.items():
            if k.startswith("am reporting"):
                am = v
                break
    ads = s.get("ad accounts (used by ad-spend-monitor)", {})
    return {
        "slug": slug,
        "name": core.get("name", slug),
        "cid": core.get("cid"),
        "google_customer_id": ads.get("google_customer_id") or core.get("cid"),
        "meta_account_id": ads.get("meta_account_id") or "",
        "roas_floor": core.get("roas_floor"),
        "currency": core.get("currency", "USD"),
        "slack_channel": s.get("stakeholders", {}).get("slack channel", ""),
        # AM reporting fields
        "deck_id": am.get("deck_id"),
        "deck_insert_index": int(am.get("deck_insert_index", 1)),
        "divider_label": am.get("divider_label", "Weekly dashboard"),
        "headline_metric": am.get("headline_metric", "roas"),
        "observation_split": am.get("observation_split", "combined"),
        "platforms": am.get("platforms", ["google"]),
        "attribution_source": am.get("attribution_source", "platform"),
        "attribution_fallback": am.get("attribution_fallback", "platform"),
        "comparison_window": am.get("comparison_window", "wow"),
        "data_sheet_ids": am.get("data_sheet_ids", []),
        "freshness_sla_days": int(am.get("freshness_sla_days", 2)),
        "has_reporting": bool(am.get("deck_id")),
        "_path": path,
    }


def roster():
    """All client slugs that have an AM reporting section configured."""
    out = []
    if not os.path.isdir(ROSTER_DIR):
        return out
    for name in sorted(os.listdir(ROSTER_DIR)):
        p = os.path.join(ROSTER_DIR, name, "account.md")
        if name.startswith((".", "_")) or not os.path.exists(p):
            continue
        try:
            cfg = load(name)
            if cfg["has_reporting"]:
                out.append(cfg)
        except Exception:  # noqa: BLE001
            continue
    return out
