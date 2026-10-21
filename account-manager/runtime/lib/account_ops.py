"""Module C — account-ops recommender (Google).

Reads an OPTIONAL, bring-your-own Google Ads diagnose queue
(<roster>/<slug>/snapshots/<YYYY-Www>/queue.json — this package does not ship a
tool that produces it; with none, the queue is empty) and fuses it with the living strategy + memory so the recommendations are
context-aware and doctrine-aligned (maximize conv value s.t. ROAS floor; honor
the strategy's refusals). Recommend-only: produces a ranked action set for you;
never touches the account.

The deterministic part (load + merge + sort) is here; the JUDGMENT (final
recommendations, framing against strategy bets/refusals) is Claude's at skill run.
"""
import json
import os

from . import clients, context

ROSTER = clients.ROSTER_DIR


def latest_snapshot_dir(slug):
    slug = clients.ALIASES.get(slug.lower().strip(), slug.lower().strip())
    snaps = os.path.join(ROSTER, slug, "snapshots")
    if not os.path.isdir(snaps):
        return None
    weeks = sorted([d for d in os.listdir(snaps)
                    if os.path.isdir(os.path.join(snaps, d))], reverse=True)
    return os.path.join(snaps, weeks[0]) if weeks else None


def load_queue(slug):
    """Return the optional diagnose queue items (empty if you supply no queue.json)."""
    d = latest_snapshot_dir(slug)
    if not d:
        return {"week": None, "items": []}
    qpath = os.path.join(d, "queue.json")
    if not os.path.exists(qpath):
        return {"week": os.path.basename(d), "items": []}
    q = json.load(open(qpath))
    return {"week": os.path.basename(d), "generated": q.get("generated"), "items": q.get("items", [])}


def scaffold(slug):
    """Everything Claude needs to write recommendations: context + queue + doctrine."""
    q = load_queue(slug)
    items = q["items"]
    # split by kind, sort each by dollars at stake
    def at_stake(it):
        return (it.get("predicted_lift") or {}).get("abs_delta_at_stake") or it.get("rank_score") or 0
    by_kind = {}
    for it in items:
        by_kind.setdefault(it.get("kind", "other"), []).append(it)
    for k in by_kind:
        by_kind[k].sort(key=at_stake, reverse=True)
    return {
        "slug": clients.ALIASES.get(slug.lower().strip(), slug.lower().strip()),
        "context": context.render(slug),
        "queue_week": q["week"],
        "queue_by_kind": by_kind,
        "queue_counts": {k: len(v) for k, v in by_kind.items()},
        "doctrine": ("Maximize conversion value subject to the ROAS floor (constraint, "
                     "not target). Scale winners toward the floor; fix/cut below it. "
                     "Surface scaling AND cutting with equal weight. Honor the strategy's "
                     "refusals (memory veto). Recommend-only — you execute."),
    }


def write_recommendations(slug, period, recommendations_md):
    """Persist the recommendation set under the snapshot + return path."""
    d = latest_snapshot_dir(slug)
    if not d:
        d = os.path.join(ROSTER, clients.ALIASES.get(slug, slug))
    path = os.path.join(d, f"RECOMMENDATIONS-{period}.md")
    with open(path, "w") as f:
        f.write(recommendations_md)
    return path
