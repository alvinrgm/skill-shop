#!/usr/bin/env python3
"""Turn roadmap/tracker.json (and learnings/traits.json) into the compact payload the Roadmap and
Creative learnings SYNC calls consume. Zero Figma calls; the sync itself is one use_figma per page.

usage: sync_payload.py <brand> [--learnings]
  default      -> {"intro_tail": str, "subs": [[sub_id, [chip, ...], spend_line], ...]}
  --learnings  -> {"traits": [[trait_id, kind, title, evidence_line, applied_as], ...]}
chip = [label, bg, fg], colour keys matching the page build (ACCENT/ALERT/INK/WARM/COOL/MUTED/PAPER).
The sync call edits each existing row IN PLACE, found by node name = sub-angle or trait id.
It never rebuilds a page."""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import brand_dir  # noqa: E402

STAT = {"winner": ["WINNER", "ACCENT", "INK"], "leans winner": ["LEANS WINNER", "ACCENT", "INK"],
        "loser": ["LOSER", "ALERT", "PAPER"], "p1 test": ["P1 TEST", "ALERT", "PAPER"],
        "mixed": ["MIXED", "WARM", "PAPER"], "testing": ["TESTING", "INK", "PAPER"],
        "greenfield": ["GREENFIELD", "COOL", "INK"], "live": ["LIVE", "INK", "PAPER"],
        "tested": ["TESTED", "MUTED", "INK"], "light": ["LIGHT TEST", "MUTED", "INK"]}


def roadmap(lib: Path) -> dict:
    t = json.loads((lib / "roadmap/tracker.json").read_text())
    out = []
    for s in t["subs"]:
        v, st = (s.get("verdict") or "").lower(), s["status"].lower()
        chips = [STAT.get(v) or STAT.get(st) or STAT["tested"]]
        if v and st in STAT and v != st and v != "greenfield":
            chips.append(STAT[st])
        n = s.get("creatives", 0)
        top = [x["name"] for x in s.get("top", [])[:2]]
        line = (f"${s.get('spend', 0):,.0f} spent · {n} creative{'' if n == 1 else 's'}"
                + (f" · e.g. {' / '.join(top)}" if top else ""))
        out.append([s["id"], chips, line])
    tail = (f"(every Meta ad with spend, {t.get('n_ads', 0)} ads, mapped onto the angle tree by name; "
            f"refreshed {t.get('generated', '?')} by learn.py)")
    return {"intro_tail": tail, "subs": out}


def learnings(lib: Path) -> dict:
    tr = json.loads((lib / "learnings/traits.json").read_text())
    rows = []
    for x in tr.get("traits", []):
        ev = "; ".join(f"{e.get('date', '')} {e.get('source', '')}: {e.get('read', '')}".strip()
                       for e in x.get("evidence", [])[:2])
        rows.append([x["id"], x.get("kind", ""), x.get("title", ""), ev, x.get("applied_as", "")])
    return {"traits": rows}


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        sys.exit(0)
    if len(sys.argv) < 2 or sys.argv[1].startswith("-"):
        print(__doc__, file=sys.stderr)
        sys.exit(2)
    lib = brand_dir(sys.argv[1])
    payload = learnings(lib) if "--learnings" in sys.argv else roadmap(lib)
    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
