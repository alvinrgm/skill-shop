"""Raw-data sheet freshness + light reads.

The per-client "raw data" sheets (Adveronix->Meta, Looker-native->Google,
TikTok) are the deterministic data source. This module checks they're fresh
(Module D-lite health) and exposes helpers to read tab values.

We rely on Drive modifiedTime for freshness (cheap, no row scan) and tab
row-counts to catch a connector that silently stopped writing.
"""
import datetime

from . import bridge


def _parse_rfc3339(s):
    # e.g. 2026-06-25T07:12:31.279Z
    s = s.replace("Z", "+00:00")
    try:
        return datetime.datetime.fromisoformat(s)
    except ValueError:
        return datetime.datetime.fromisoformat(s.split(".")[0] + "+00:00")


def freshness(sheet_id):
    """Return dict: {id, name, modified, age_days, tabs:[{title,rows,cols}]}."""
    meta = bridge.sheet_meta(sheet_id)
    mod = bridge.drive_file_modified(sheet_id)
    modified = mod.get("modifiedTime")
    age_days = None
    if modified:
        dt = _parse_rfc3339(modified)
        now = datetime.datetime.now(datetime.timezone.utc)
        age_days = round((now - dt).total_seconds() / 86400, 2)
    tabs = []
    for sh in meta.get("sheets", []):
        p = sh["properties"]
        g = p.get("gridProperties", {})
        tabs.append({"title": p["title"], "rows": g.get("rowCount"), "cols": g.get("columnCount")})
    return {
        "id": sheet_id,
        "name": meta.get("properties", {}).get("title"),
        "modified": modified,
        "age_days": age_days,
        "tabs": tabs,
    }


def check_client(cfg):
    """Check all of a client's data sheets. Returns (ok, [issues], [reports])."""
    issues = []
    reports = []
    sla = cfg.get("freshness_sla_days", 2)
    for sid in cfg.get("data_sheet_ids", []):
        try:
            fr = freshness(sid)
        except Exception as e:  # noqa: BLE001
            issues.append(f"{cfg['slug']}: sheet {sid} unreadable ({e})")
            continue
        reports.append(fr)
        if fr["age_days"] is not None and fr["age_days"] > sla:
            issues.append(f"{cfg['slug']}: '{fr['name']}' stale — {fr['age_days']}d old (SLA {sla}d)")
    return (len(issues) == 0, issues, reports)


def read_tab(sheet_id, tab_title, max_rows=None):
    """Read values from a tab. Returns list-of-rows."""
    rng = f"'{tab_title}'" if not max_rows else f"'{tab_title}'!1:{max_rows}"
    return bridge.sheet_values(sheet_id, rng)
