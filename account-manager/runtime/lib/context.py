"""Context loader — assembles the full institutional-knowledge pack for a client
so every AM workflow (weekly-report, creative-intel, account-ops) runs
"fully loaded" rather than context-free.

Two-tier context, both in the canonical roster folder:
  - strategy.md  : the LIVING strategy/positioning spine (slow-changing; operate against)
  - memory.md    : append-only tactical history + standing notes (fast-accumulating)
plus account.md (config) and, optionally, the latest diagnose snapshot
(<roster>/<slug>/snapshots/<week>/SUMMARY.md) if you supply one. This package
does not ship a diagnose tool; with no snapshot, that section is simply omitted.
"""
import os

from . import clients

ROSTER = clients.ROSTER_DIR


def _read(path):
    try:
        with open(path) as f:
            return f.read().strip()
    except FileNotFoundError:
        return ""


def _latest_snapshot(slug):
    snap_dir = os.path.join(ROSTER, slug, "snapshots")
    if not os.path.isdir(snap_dir):
        return "", ""
    weeks = sorted([d for d in os.listdir(snap_dir)
                    if os.path.isdir(os.path.join(snap_dir, d))], reverse=True)
    if not weeks:
        return "", ""
    latest = weeks[0]
    summary = _read(os.path.join(snap_dir, latest, "SUMMARY.md"))
    return latest, summary


def load_pack(slug):
    """Return the raw context pieces for a client."""
    slug = clients.ALIASES.get(slug.lower().strip(), slug.lower().strip())
    base = os.path.join(ROSTER, slug)
    week, snap = _latest_snapshot(slug)
    return {
        "slug": slug,
        "account": _read(os.path.join(base, "account.md")),
        "strategy": _read(os.path.join(base, "strategy.md")),
        "memory": _read(os.path.join(base, "memory.md")),
        "snapshot_week": week,
        "snapshot": snap,
        "has_strategy": os.path.exists(os.path.join(base, "strategy.md")),
    }


def render(slug, max_chars=14000):
    """Render a context preamble to inject at the top of any AM workflow.

    Strategy first (operate against it), then standing notes/memory, then the
    latest snapshot. Truncates memory tactical-history if very long.
    """
    p = load_pack(slug)
    out = [f"# CONTEXT PACK — {p['slug']} (load before analyzing)\n"]
    if not p["has_strategy"]:
        out.append("> WARNING: no strategy.md yet for this client. Run the strategy "
                   "backfill / strategy-crystallizer before relying on strategic context.\n")
    if p["strategy"]:
        out.append("## === LIVING STRATEGY (operate against this) ===\n" + p["strategy"])
    if p["account"]:
        out.append("\n## === ACCOUNT CONFIG ===\n" + p["account"])
    if p["memory"]:
        mem = p["memory"]
        if len(mem) > max_chars // 2:
            mem = mem[:max_chars // 2] + "\n...[tactical history truncated — read memory.md in full if needed]"
        out.append("\n## === MEMORY (standing notes + tactical history) ===\n" + mem)
    if p["snapshot"]:
        out.append(f"\n## === LATEST DIAGNOSE SNAPSHOT ({p['snapshot_week']}) ===\n" + p["snapshot"])
    text = "\n".join(out)
    return text[:max_chars] + ("\n...[context truncated]" if len(text) > max_chars else "")


def append_memory(slug, period, action, result, lesson):
    """Append a dated tactical-history entry to the client's memory.md."""
    slug = clients.ALIASES.get(slug.lower().strip(), slug.lower().strip())
    path = os.path.join(ROSTER, slug, "memory.md")
    entry = (f"\n### {period} — auto: AM workflow\n"
             f"- **Action**: {action}\n"
             f"- **Result**: {result}\n"
             f"- **Lesson**: {lesson}\n")
    with open(path, "a") as f:
        f.write(entry)
    return path
