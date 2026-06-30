#!/usr/bin/env python3
"""Turn the strongest creative ASSOCIATIONS into Meta A/B experiment proposals —
the only rigorous path to causation. Recommend-only: this DRAFTS proposals; an
actual test is created (via ads_experiment_abtest_create_test) only after you
approve.

Input: the analyze() output dict. Output: ranked, ready-to-run test proposals.
"""

MIN_DAILY_BUDGET = 50      # per cell; matches the budget-automation floor
DEFAULT_RUN_DAYS = 14


def propose(analysis, max_tests=5):
    props = []
    for a in analysis.get("associations", []):
        if a["kind"] == "categorical" and a.get("lift_best_vs_worst", 0) and a["lift_best_vs_worst"] >= 0.15:
            hypo = (f"Ads with {a['feature']} = '{a['best_level']}' show "
                    f"{round(a['lift_best_vs_worst']*100)}% higher {a['outcome']} than "
                    f"'{a['worst_level']}' (observational, n={a['n']}).")
            variable = a["feature"]
            control = a["worst_level"]
            variant = a["best_level"]
        elif a["kind"] == "numeric" and abs(a.get("pearson_r", 0)) >= 0.3:
            direction = "lower" if a["pearson_r"] < 0 else "higher"
            hypo = (f"{direction.title()} {a['feature']} associates with higher {a['outcome']} "
                    f"(r={a['pearson_r']}, n={a['n']}).")
            variable = a["feature"]
            control = "current median"
            variant = f"{direction} {a['feature']}"
        else:
            continue
        props.append({
            "hypothesis": hypo,
            "test_variable": variable,
            "control": control,
            "variant": variant,
            "primary_metric": a["outcome"],
            "design": "Meta A/B (split test) — identical targeting/budget, creative is the only difference",
            "min_budget_per_cell_per_day": MIN_DAILY_BUDGET,
            "suggested_run_days": DEFAULT_RUN_DAYS,
            "confidence_today": a["confidence"],
            "status": "PROPOSED — create only on your approval via ads_experiment_abtest_create_test",
        })
        if len(props) >= max_tests:
            break
    return {"proposals": props,
            "note": "Recommend-only. These are the rigorous follow-ups to the correlational findings. "
                    "Pick which to run; the skill creates the split test after approval."}
