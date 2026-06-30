#!/usr/bin/env python3
"""Cross-video creative regression — find which creative features ASSOCIATE with
outcomes (hook rate, CTR, CVR, ROAS) across many ads.

HONEST BY DESIGN: this is observational and correlational. It reports effect
direction + strength + sample size + a confounder flag. It never claims
causation — that's what the experiment proposals (experiments.py) are for.

Input: list of records, each:
  {"label": str, "features": {<descriptor>: value}, "metrics": {hook_rate, ctr, cvr, roas, spend}}

Numeric features → Pearson r vs each outcome. Categorical features → per-level
mean outcome (best vs worst level). Anything with n below MIN_N is flagged
low-confidence, not dropped silently.
"""
import math
from collections import defaultdict

MIN_N = 6  # below this, associations are flagged low-confidence
OUTCOMES = ["hook_rate", "ctr", "cvr", "roas"]
NUMERIC = {"time_to_first_product_sec", "time_to_first_text_sec", "cuts_total",
           "cuts_per_10s", "cta_time_sec", "duration_sec"}


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


def analyze(records):
    n_total = len(records)
    results = []
    # collect feature universe
    feat_keys = set()
    for r in records:
        feat_keys |= set((r.get("features") or {}).keys())

    for outcome in OUTCOMES:
        ys_all = [(r, (r.get("metrics") or {}).get(outcome)) for r in records]
        for fk in sorted(feat_keys):
            pairs = [(r.get("features", {}).get(fk), y)
                     for r, y in ys_all
                     if r.get("features", {}).get(fk) is not None and y is not None]
            if len(pairs) < 3:
                continue
            is_num = fk in NUMERIC or all(isinstance(v, (int, float)) for v, _ in pairs)
            if is_num:
                xs = [float(v) for v, _ in pairs]
                ys = [float(y) for _, y in pairs]
                r = _pearson(xs, ys)
                if r is None:
                    continue
                results.append({
                    "feature": fk, "outcome": outcome, "kind": "numeric",
                    "pearson_r": round(r, 3), "n": len(pairs),
                    "direction": "higher feature -> higher " + outcome if r > 0 else "higher feature -> lower " + outcome,
                    "strength": _strength(abs(r)),
                    "confidence": "low (small n)" if len(pairs) < MIN_N else "moderate (observational)",
                })
            else:
                groups = defaultdict(list)
                for v, y in pairs:
                    groups[str(v)].append(float(y))
                levels = {g: (sum(v) / len(v), len(v)) for g, v in groups.items() if v}
                if len(levels) < 2:
                    continue
                best = max(levels.items(), key=lambda kv: kv[1][0])
                worst = min(levels.items(), key=lambda kv: kv[1][0])
                lift = (best[1][0] / worst[1][0] - 1) if worst[1][0] else None
                results.append({
                    "feature": fk, "outcome": outcome, "kind": "categorical",
                    "best_level": best[0], "best_mean": round(best[1][0], 4), "best_n": best[1][1],
                    "worst_level": worst[0], "worst_mean": round(worst[1][0], 4), "worst_n": worst[1][1],
                    "lift_best_vs_worst": round(lift, 3) if lift is not None else None,
                    "n": len(pairs),
                    "confidence": "low (small n)" if len(pairs) < MIN_N else "moderate (observational)",
                })

    # rank: numeric by |r|, categorical by lift; surface strongest first
    def score(x):
        return abs(x.get("pearson_r") or 0) + abs(x.get("lift_best_vs_worst") or 0)
    results.sort(key=score, reverse=True)
    return {
        "n_ads": n_total,
        "associations": results,
        "caveat": ("Observational and correlational. Effects are confounded by audience, "
                   "budget, bid, placement, and format. Treat as hypotheses to TEST, not "
                   "proof. Rank by effect size but weight by sample size. n<%d = low confidence." % MIN_N),
    }


def _strength(absr):
    if absr >= 0.5:
        return "strong"
    if absr >= 0.3:
        return "moderate"
    if absr >= 0.1:
        return "weak"
    return "negligible"
