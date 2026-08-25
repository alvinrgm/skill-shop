#!/usr/bin/env python3
"""Content-strategy synthesis across an advertiser's ENTIRE video corpus.

This is the payoff. compete.py answers "which features go with long runs";
this answers the bigger question: **what is their content strategy?** It reads
every per-second analysis produced by cv_analyze.py and synthesizes the corpus:

  formats      how long their ads are, what shape, what production style
  hooks        how they open, and whether the openers have shifted over time
  messaging    what they claim, and what they lead with
  structure    when the product appears, when the CTA lands, how fast they cut
  talent       who is on screen — creators, actors, nobody
  evolution    older creatives vs newer ones: what they moved toward
  repetition   which patterns they repeat (a repeated pattern is a bet)

Requires cv_*.json files, i.e. an API key was used. Run the corpus with
`full_run.py --cv-limit 0` to analyze every creative rather than the top few.

Usage as a lib:  from strategy import synthesize, render
CLI:             strategy.py --page-slug seed [--out outputs/strategy-seed.md]
"""
import argparse
import collections
import json
import os
from pathlib import Path

PKG_ROOT = Path(__file__).resolve().parent.parent
DATA = Path(os.environ.get("ADLIB_DATA", PKG_ROOT / "data"))
OUTPUT = Path(os.environ.get("ADLIB_OUTPUT", PKG_ROOT / "outputs"))


def _pct(n, total):
    return f"{round(100 * n / total)}%" if total else "—"


def _mode_table(counter, total, label):
    L = [f"**{label}**", ""]
    for k, n in counter.most_common():
        L.append(f"- {k} — {n} ({_pct(n, total)})")
    L.append("")
    return L


def load_corpus(page_slug):
    """Join each cv_*.json with its ledger facts (start date, days running)."""
    page_dir = DATA / page_slug
    ledger_path = DATA / "ledger.jsonl"
    by_key = {}
    if ledger_path.exists():
        for line in ledger_path.read_text().splitlines():
            if not line.strip():
                continue
            e = json.loads(line)
            if e.get("page_slug") != page_slug:
                continue
            k = e["creative_key"]
            prev = by_key.get(k)
            # keep the EARLIEST start date across the ads sharing this creative
            if not prev or (e.get("start_date") or "9999") < (prev.get("start_date") or "9999"):
                by_key[k] = e

    recs = []
    for f in sorted(page_dir.glob("cv_*.json")):
        try:
            d = json.loads(f.read_text())
        except Exception:  # noqa: BLE001
            continue
        key = f.name[3:-5]
        led = by_key.get(key, {})
        desc = d.get("descriptors") or {}
        hook = d.get("hook") or {}
        recs.append({
            "creative_key": key,
            "start_date": led.get("start_date"),
            "duration_sec": d.get("duration_sec"),
            "hook_archetype": hook.get("hook_archetype"),
            "hook_summary": hook.get("first_3s_summary"),
            "hook_has_face": hook.get("hook_has_face"),
            "hook_has_text": hook.get("hook_has_text"),
            "hook_has_product": hook.get("hook_has_product"),
            "descriptors": desc,
            "timeline": d.get("timeline") or [],
        })
    return recs


def synthesize(page_slug):
    recs = load_corpus(page_slug)
    n = len(recs)
    if not n:
        return {"n": 0, "page_slug": page_slug}

    d = lambda k: [r["descriptors"].get(k) for r in recs]  # noqa: E731
    cnt = lambda vals: collections.Counter(  # noqa: E731
        str(v) for v in vals if v is not None)

    durs = [r["duration_sec"] for r in recs if r.get("duration_sec")]
    ttp = [v for v in d("time_to_first_product_sec") if isinstance(v, (int, float))]
    ctat = [v for v in d("cta_time_sec") if isinstance(v, (int, float))]
    cuts = [v for v in d("cuts_per_10s") if isinstance(v, (int, float))]

    dated = sorted([r for r in recs if r.get("start_date")],
                   key=lambda r: r["start_date"])
    half = len(dated) // 2
    older, newer = dated[:half], dated[half:]

    def era(group, key, from_desc=True):
        vals = [(r["descriptors"].get(key) if from_desc else r.get(key))
                for r in group]
        c = collections.Counter(str(v) for v in vals if v is not None)
        return c.most_common(1)[0] if c else None

    shifts = []
    for key, from_desc, label in [
        ("style", True, "production style"),
        ("claim_type", True, "claim type"),
        ("hook_archetype", False, "hook archetype"),
        ("talent_present", True, "talent on screen"),
        ("voiceover", True, "voiceover"),
        ("pacing", True, "pacing"),
    ]:
        o, nw = era(older, key, from_desc), era(newer, key, from_desc)
        if o and nw and o[0] != nw[0]:
            shifts.append({"dimension": label, "was": o[0], "now": nw[0],
                           "was_n": o[1], "now_n": nw[1]})

    # opening seconds: what is literally on screen at t<=2
    openers = []
    for r in recs:
        first = [t for t in r["timeline"] if isinstance(t.get("t"), int) and t["t"] <= 2]
        txt = next((t.get("on_screen_text") for t in first if t.get("on_screen_text")), "")
        spoken = next((t.get("spoken") for t in first if t.get("spoken")), "")
        openers.append({"key": r["creative_key"], "text": (txt or "").strip(),
                        "spoken": (spoken or "").strip(),
                        "archetype": r.get("hook_archetype"),
                        "days": r.get("start_date")})

    return {
        "n": n, "page_slug": page_slug, "recs": recs,
        "durations": durs, "ttp": ttp, "cta_times": ctat, "cuts": cuts,
        "styles": cnt(d("style")), "hooks": cnt([r["hook_archetype"] for r in recs]),
        "claims": cnt(d("claim_type")), "ctas": cnt(d("cta_type")),
        "tones": cnt(d("emotional_tone")), "pacing": cnt(d("pacing")),
        "talent": cnt(d("talent_present")), "vo": cnt(d("voiceover")),
        "text_density": cnt(d("on_screen_text_density")),
        "music": cnt(d("music_energy")),
        "hook_face": cnt([r["hook_has_face"] for r in recs]),
        "hook_text": cnt([r["hook_has_text"] for r in recs]),
        "hook_product": cnt([r["hook_has_product"] for r in recs]),
        "shifts": shifts, "openers": openers,
        "n_dated": len(dated),
        "older_range": (older[0]["start_date"], older[-1]["start_date"]) if older else None,
        "newer_range": (newer[0]["start_date"], newer[-1]["start_date"]) if newer else None,
    }


def _stat(vals):
    if not vals:
        return "—"
    s = sorted(vals)
    return (f"median {s[len(s) // 2]:.0f} · range {s[0]:.0f}–{s[-1]:.0f}")


def render(S):
    if not S.get("n"):
        return (f"# Content strategy — {S['page_slug']}\n\nNo per-second analyses "
                f"found. Run with an API key and `--cv-limit 0` to analyze the "
                f"corpus, then re-run this.\n")
    n = S["n"]
    L = [f"# Content strategy — {S['page_slug']}", "",
         f"Synthesized from **{n} fully-analyzed creatives** (every one watched "
         f"second by second).", ""]

    L += ["## Format", "",
          f"- Length: {_stat(S['durations'])} seconds",
          f"- Cuts per 10s: {_stat(S['cuts'])}",
          f"- Product first appears: {_stat(S['ttp'])} seconds in",
          f"- CTA lands: {_stat(S['cta_times'])} seconds in", ""]
    L += _mode_table(S["styles"], n, "Production style")

    L += ["## How they open", ""]
    L += _mode_table(S["hooks"], n, "Hook archetype")
    L += [f"- Face in the first 3s: {dict(S['hook_face']).get('True', 0)}/{n}",
          f"- On-screen text in the first 3s: {dict(S['hook_text']).get('True', 0)}/{n}",
          f"- Product in the first 3s: {dict(S['hook_product']).get('True', 0)}/{n}", ""]
    L += ["<details><summary>Every opening, verbatim</summary>", ""]
    for o in S["openers"]:
        bit = o["text"] or o["spoken"] or "(no text or speech in first 2s)"
        L.append(f"- `{o['key']}` [{o['archetype']}] — {bit[:130]}")
    L += ["", "</details>", ""]

    L += ["## What they say", ""]
    L += _mode_table(S["claims"], n, "Claim type")
    L += _mode_table(S["ctas"], n, "Call to action (in-creative)")

    L += ["## Craft", ""]
    L += _mode_table(S["talent"], n, "Talent on screen")
    L += _mode_table(S["vo"], n, "Voiceover")
    L += _mode_table(S["pacing"], n, "Pacing")
    L += _mode_table(S["text_density"], n, "On-screen text density")
    L += _mode_table(S["music"], n, "Music energy")

    L += ["## How it has changed", ""]
    if S["n_dated"] < 4:
        L.append("Too few dated creatives to compare eras.")
    elif not S["shifts"]:
        L += [f"Comparing the older half ({S['older_range'][0]} → "
              f"{S['older_range'][1]}) with the newer half ({S['newer_range'][0]} → "
              f"{S['newer_range'][1]}): **no dominant pattern changed.** They are "
              "iterating within a fixed formula rather than changing approach."]
    else:
        L += [f"Older half ({S['older_range'][0]} → {S['older_range'][1]}) vs newer "
              f"half ({S['newer_range'][0]} → {S['newer_range'][1]}):", ""]
        for s in S["shifts"]:
            L.append(f"- **{s['dimension']}**: {s['was']} → {s['now']}")
        L += ["", "A shift is not automatically an improvement — it is what they "
              "decided to try. Treat it as their read of their own results."]
    L.append("")

    top_style = S["styles"].most_common(1)[0] if S["styles"] else None
    top_hook = S["hooks"].most_common(1)[0] if S["hooks"] else None
    top_claim = S["claims"].most_common(1)[0] if S["claims"] else None
    L += ["## The formula, in one paragraph", ""]
    parts = []
    if top_style:
        parts.append(f"**{top_style[0]}** production ({_pct(top_style[1], n)} of the corpus)")
    if top_hook:
        parts.append(f"opening on a **{top_hook[0]}** hook ({_pct(top_hook[1], n)})")
    if top_claim:
        parts.append(f"built on a **{top_claim[0]}** claim ({_pct(top_claim[1], n)})")
    if S["durations"]:
        s = sorted(S["durations"])
        parts.append(f"running about **{s[len(s) // 2]:.0f}s**")
    if S["ttp"]:
        t = sorted(S["ttp"])
        parts.append(f"with the product on screen by **{t[len(t) // 2]:.0f}s**")
    L += ["Their repeated bet: " + ", ".join(parts) + ".", "",
          "Repetition is the signal worth reading. A pattern an advertiser returns "
          "to across many creatives is a pattern they believe in — that is genuinely "
          "informative about their thinking. It is still not proof the pattern works: "
          "the Ad Library reports no spend, no impressions, and no conversions, so "
          "nothing here measures outcomes. Read it as their strategy, then test the "
          "parts worth testing on your own account.", ""]
    return "\n".join(L)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--page-slug", required=True)
    ap.add_argument("--out", default=None)
    args = ap.parse_args()
    S = synthesize(args.page_slug)
    md = render(S)
    print(md)
    OUTPUT.mkdir(parents=True, exist_ok=True)
    dest = Path(args.out) if args.out else OUTPUT / f"strategy-{args.page_slug}.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(md)
    print(f"\nwrote {dest}")


if __name__ == "__main__":
    main()
