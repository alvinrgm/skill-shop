#!/usr/bin/env python3
"""Align a video's CV timeline to its Meta retention curve + hook metrics.

Meta gives quartile retention (p25/p50/p75/p95/p100) + thruplay + CTR — NOT
per-second. This maps those coarse points onto the per-second creative timeline
so you can see WHAT is on screen where viewers drop, and computes hook/hold
rates. Within-video, descriptive (honest about the resolution limit).

Usage (library):
  from align import align
  result = align(cv_dict, metrics_dict)

metrics_dict keys (from Meta ads_get_ad_entities, numbers as ints/floats):
  impressions, ctr, video_p25/p50/p75/p95/p100_watched, thruplay (optional),
  duration_sec (optional; falls back to cv duration)
"""


def _at_second(timeline, sec):
    """Return the timeline entry nearest a given second."""
    if not timeline:
        return {}
    return min(timeline, key=lambda e: abs(e.get("t", 0) - sec))


def align(cv, metrics):
    dur = metrics.get("duration_sec") or cv.get("duration_sec") or 0
    tl = cv.get("timeline", [])
    impr = float(metrics.get("impressions") or 0)
    p = {q: float(metrics.get(f"video_p{q}_watched") or 0) for q in (25, 50, 75, 95, 100)}
    base = p[25] or 1.0  # normalize retention to the 25% cohort (engaged viewers)

    quartiles = []
    for q, frac in [(25, .25), (50, .50), (75, .75), (95, .95), (100, 1.0)]:
        sec = round(dur * frac)
        entry = _at_second(tl, sec)
        quartiles.append({
            "pct": q,
            "approx_sec": sec,
            "viewers": int(p[q]),
            "retained_vs_p25": round(p[q] / base, 3) if base else None,
            "on_screen": entry.get("shot", "")[:90],
            "on_screen_text": entry.get("on_screen_text", ""),
            "spoken": entry.get("spoken", ""),
        })

    # biggest absolute drop between adjacent quartiles
    drops = []
    seq = [(0, impr or p[25])] + [(q, p[q]) for q in (25, 50, 75, 95, 100)]
    for (qa, va), (qb, vb) in zip(seq, seq[1:]):
        if va:
            drops.append({"from_pct": qa, "to_pct": qb, "lost_frac": round((va - vb) / va, 3)})
    biggest = max(drops, key=lambda d: d["lost_frac"]) if drops else None
    biggest_at = None
    if biggest:
        sec = round(dur * biggest["to_pct"] / 100.0)
        e = _at_second(tl, sec)
        biggest_at = {"window": f"{biggest['from_pct']}%->{biggest['to_pct']}%",
                      "approx_sec": sec, "lost_frac": biggest["lost_frac"],
                      "on_screen": e.get("shot", "")[:90],
                      "on_screen_text": e.get("on_screen_text", ""),
                      "spoken": e.get("spoken", "")}

    hook = cv.get("hook", {})
    hook_rate = round(p[25] / impr, 4) if impr else None  # proxy: reached 25% / impressions
    hold_rate = round(p[100] / p[25], 4) if p[25] else None  # finished / engaged

    return {
        "duration_sec": dur,
        "ctr_pct": metrics.get("ctr"),
        "hook": {"archetype": hook.get("hook_archetype"),
                 "first_3s": hook.get("first_3s_summary"),
                 "hook_rate_p25_over_impr": hook_rate},
        "hold_rate_p100_over_p25": hold_rate,
        "retention_curve": quartiles,
        "biggest_drop": biggest_at,
        "note": ("Retention is quartile-resolution (Meta does not expose per-second). "
                 "Creative timeline is per-second; quartile points are mapped to the "
                 "nearest second. Within-video alignment is descriptive, not causal."),
    }
