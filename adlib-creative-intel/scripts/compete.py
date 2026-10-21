#!/usr/bin/env python3
"""Competitor creative analysis — the longevity-proxy sibling of analyze.py.

analyze.py regresses creative features against REAL outcomes (hook rate, CTR,
CVR, ROAS). None of those exist for competitor ads: the Ad Library publishes no
performance data for US commercial ads. Running analyze.py on competitor
creatives would mean inventing metrics, so this module exists instead.

What we actually observe per competitor creative:
  days_running   — today - first start_date, for a still-active ad. The core
                   aggregator heuristic: an ad a competitor keeps paying for is
                   an ad that is working for them.
  n_library_ids  — how many ad IDs share the creative (placement/collation
                   spread = commitment).
  campaign       — from the link_url's utm_campaign, when present.

The proxy is DIRECTIONAL, not a metric. It is confounded by: brand budget,
evergreen/always-on strategy, seasonal windows, agency retainer habits, and
the plain fact that some brands never turn anything off. Anything this module
outputs is a HYPOTHESIS about what a competitor believes, not a measured
result — and never a claim about what will work for us.

Input: ledger entries (from adlib_fetch) joined with cv_analyze.py output.
  records = [{"creative_key", "days_running", "n_library_ids", "campaign",
              "features": <cv descriptors + duration>}]

Usage as a lib:
  from compete import analyze_competitors, compare_to_us
"""
import math
from collections import defaultdict

LONGEVITY_TIERS = [(90, "proven (90d+)"), (30, "working (30-89d)"), (0, "testing (<30d)")]
MIN_N = 4
# same numeric feature set as analyze.py — these correlate, they don't bucket
NUMERIC = {"time_to_first_product_sec", "time_to_first_text_sec", "cuts_total",
           "cuts_per_10s", "cta_time_sec", "duration_sec"}


def _tier(days):
    if days is None:
        return "unknown"
    for cut, label in LONGEVITY_TIERS:
        if days >= cut:
            return label
    return "unknown"


def _pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    vx = sum((x - mx) ** 2 for x in xs)
    vy = sum((y - my) ** 2 for y in ys)
    if vx == 0 or vy == 0:
        return None
    return cov / math.sqrt(vx * vy)


def analyze_competitors(records):
    """Which creative features cluster in the LONG-RUNNING competitor ads."""
    for r in records:
        r["_tier"] = _tier(r.get("days_running"))

    feat_keys = set()
    for r in records:
        feat_keys |= set((r.get("features") or {}).keys())

    findings = []
    for fk in sorted(feat_keys):
        pairs = [((r.get("features") or {}).get(fk), r.get("days_running"))
                 for r in records
                 if (r.get("features") or {}).get(fk) is not None
                 and r.get("days_running") is not None]
        if not pairs:
            continue
        is_num = fk in NUMERIC or all(isinstance(v, (int, float))
                                      and not isinstance(v, bool) for v, _ in pairs)
        if is_num:
            r_val = _pearson([float(v) for v, _ in pairs], [float(d) for _, d in pairs])
            if r_val is None:
                continue
            findings.append({
                "feature": fk, "kind": "numeric",
                "pearson_r_vs_days_running": round(r_val, 3),
                "direction": ("higher feature -> runs longer" if r_val > 0
                              else "higher feature -> runs shorter"),
                "n": len(pairs), "_rank": abs(r_val) * 100,
                "confidence": "low (small n)" if len(pairs) < MIN_N else "directional only",
            })
            continue
        by_level = defaultdict(list)
        for v, d in pairs:
            by_level[str(v)].append(d)
        if len(by_level) < 2:
            continue
        levels = {k: (sum(v) / len(v), len(v)) for k, v in by_level.items()}
        best = max(levels.items(), key=lambda kv: kv[1][0])
        worst = min(levels.items(), key=lambda kv: kv[1][0])
        findings.append({
            "feature": fk, "kind": "categorical",
            "longest_running_level": best[0],
            "mean_days_at_that_level": round(best[1][0], 1),
            "n_at_that_level": best[1][1],
            "shortest_running_level": worst[0],
            "mean_days_at_shortest": round(worst[1][0], 1),
            "spread_days": round(best[1][0] - worst[1][0], 1),
            "n": len(pairs), "_rank": abs(best[1][0] - worst[1][0]),
            "confidence": ("low (single-ad level)" if min(c for _, c in levels.values()) < 2
                           else "low (small n)" if len(pairs) < MIN_N else "directional only"),
        })
    findings.sort(key=lambda f: -f["_rank"])
    for f in findings:
        f.pop("_rank", None)

    tiers = defaultdict(list)
    for r in records:
        tiers[r["_tier"]].append(r.get("creative_key"))

    return {
        "n_creatives": len(records),
        "tiers": dict(tiers),
        "findings": findings,
        "caveat": (
            "Longevity is a PROXY, not a metric — the Ad Library publishes no "
            "impressions, spend, retention, or ROAS for US commercial ads. A "
            "long-running ad means the competitor keeps paying for it, which is "
            "confounded by budget, always-on strategy, seasonality, and inertia. "
            "Treat every finding as a hypothesis about what the COMPETITOR "
            "believes, to be tested on our own account — never as evidence that "
            "the feature will work for us. n<%d = low confidence." % MIN_N),
    }


def compare_to_us(competitor_records, our_records):
    """Where our creative approach diverges from theirs — the gap read.

    our_records use the same {"features": {...}} shape as analyze.py records,
    so pass the SAME cv descriptors. Returns per-feature side-by-side modes,
    flagging features where we and they systematically differ. A divergence is
    a QUESTION ("they all lead with a face by 1s; we lead with product — is
    that deliberate?"), never an instruction to copy.
    """
    def modes(recs, fk):
        counts = defaultdict(int)
        for r in recs:
            v = (r.get("features") or {}).get(fk)
            if v is not None:
                counts[str(v)] += 1
        if not counts:
            return None, 0, 0
        top = max(counts.items(), key=lambda kv: kv[1])
        return top[0], top[1], sum(counts.values())

    feat_keys = set()
    for r in list(competitor_records) + list(our_records):
        feat_keys |= set((r.get("features") or {}).keys())

    rows = []
    for fk in sorted(feat_keys):
        tv, tn, tt = modes(competitor_records, fk)
        ov, on, ot = modes(our_records, fk)
        if tv is None or ov is None:
            continue
        rows.append({
            "feature": fk,
            "them_most_common": tv, "them_share": f"{tn}/{tt}",
            "us_most_common": ov, "us_share": f"{on}/{ot}",
            "diverges": tv != ov,
        })
    return {
        "n_competitor": len(competitor_records),
        "n_ours": len(our_records),
        "rows": rows,
        "divergences": [r for r in rows if r["diverges"]],
        "caveat": ("A divergence is a question to ask, not a gap to close. They "
                   "have a different product, margin, audience, and funnel. Check "
                   "any 'they do X' finding against our living strategy — if X "
                   "contradicts a refusal or a failed test in memory, that's a "
                   "flag, not a recommendation."),
    }
