#!/usr/bin/env python3
"""Deterministic structural flags for the Meta account-ops audit.

Takes the MCP JSON (campaigns, ad sets, audiences, opportunity score) and computes
the objective signals the rubric scores against. Judgment stays with Claude; this
just makes the structural facts consistent every run.

Inputs are the parsed lists/dicts from the Meta MCP (ads_get_ad_entities returns
ad_entities as a JSON STRING — json.loads it first).
"""
import re


def _money(s):
    if not s or "Not available" in str(s):
        return None
    m = re.search(r"[-\d][\d,]*\.?\d*", str(s).replace(",", ""))
    return float(m.group()) if m else None


def _has_own_budget(e):
    return _money(e.get("daily_budget")) is not None or _money(e.get("lifetime_budget")) is not None


def audit(campaigns, adsets, audiences, opp_score=None, learning_min_daily=60.0):
    campaigns = campaigns or []
    adsets = adsets or []
    audiences = audiences or []

    # --- structure ---
    cbo = [c for c in campaigns if _has_own_budget(c)]
    abo = [c for c in campaigns if not _has_own_budget(c)]
    asc = [c for c in campaigns if "asc" in (c.get("name", "").lower())]
    objectives = sorted({c.get("objective") for c in campaigns if c.get("objective")})

    # --- bidding / optimization ---
    bids = {}
    for e in campaigns + adsets:
        b = e.get("bid_strategy")
        if b and "Not available" not in str(b):
            bids[b] = bids.get(b, 0) + 1
    opt_goals = {}
    for a in adsets:
        g = a.get("optimization_goal")
        if g:
            opt_goals[g] = opt_goals.get(g, 0) + 1
    value_bidding = any("roas" in b.lower() or "value" in b.lower() for b in bids)

    # --- attribution consistency ---
    windows = {}
    for a in adsets:
        w = a.get("attribution_setting")
        if w:
            windows[w] = windows.get(w, 0) + 1

    # --- learning risk (small-budget ad sets) ---
    small = [a for a in adsets
             if (_money(a.get("daily_budget")) or 0) and _money(a.get("daily_budget")) < learning_min_daily]

    # --- audiences ---
    def active(a):
        return a.get("delivery_status") == "ACTIVE"
    stale_active = [a for a in audiences
                    if active(a) and re.search(r"not maintained", a.get("name", ""), re.I)]
    lals = [a for a in audiences if a.get("subtype") == "LOOKALIKE"]
    lals_active = [a for a in lals if active(a)]
    empty = [a for a in audiences
             if (a.get("approximate_count_upper_bound") or 0) <= 20 and active(a)]

    # --- opp score ---
    opp = {}
    if opp_score:
        opp["score"] = opp_score.get("opportunity_score")
        recs = sorted(opp_score.get("recommendations", []),
                      key=lambda r: int(r.get("recommendation_content", {}).get("opportunity_score_lift", 0)),
                      reverse=True)
        opp["top_recs"] = [{"type": r.get("type"),
                            "lift_pts": r.get("recommendation_content", {}).get("opportunity_score_lift"),
                            "benefit": r.get("recommendation_content", {}).get("lift_estimate")}
                           for r in recs]

    return {
        "structure": {
            "n_campaigns": len(campaigns), "n_adsets": len(adsets),
            "cbo_campaigns": len(cbo), "abo_campaigns": len(abo),
            "asc_campaigns": len(asc), "objectives": objectives,
            "asc_fragmentation": len(asc) >= 4,
        },
        "bidding": {
            "bid_strategy_mix": bids, "value_bidding_present": value_bidding,
            "optimization_goal_mix": opt_goals,
        },
        "attribution": {"window_mix": windows, "consistent": len(windows) <= 1},
        "learning_risk": {"small_budget_adsets": len(small),
                          "names": [a.get("name") for a in small][:10]},
        "audiences": {
            "total": len(audiences), "lookalikes": len(lals), "lookalikes_active": len(lals_active),
            "stale_but_active": len(stale_active),
            "stale_names": [a.get("name") for a in stale_active][:12],
            "empty_active": len(empty),
        },
        "opportunity": opp,
    }
