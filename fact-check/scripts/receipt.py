#!/usr/bin/env python3
"""receipt.py — validate a fact-check claims file and write the receipt.

Usage: receipt.py <claims.json> [--dry-run]

Refuses (exit 1) when any load-bearing claim lacks a final status or evidence, or is
still unverified/broken. On success, writes the receipt to
$FACT_CHECK_HOME/receipts/ (default ~/.claude/fact-check) and prints the footer line
for the message. The fact-check-gate hook looks for a fresh receipt there.
"""
import datetime as dt
import json
import os
import re
import sys

FINAL = {"verified", "corrected", "labeled", "unverifiable", "cut"}


def home():
    return os.path.expanduser(os.environ.get("FACT_CHECK_HOME", "~/.claude/fact-check"))


def main(argv):
    args = [a for a in argv if not a.startswith("--")]
    dry = "--dry-run" in argv
    if len(args) != 1:
        print(__doc__.strip(), file=sys.stderr)
        return 2
    try:
        data = json.load(open(args[0]))
    except Exception as e:
        print(f"REFUSED: cannot read claims file: {e}", file=sys.stderr)
        return 1

    if not isinstance(data, dict):
        print("REFUSED: claims file must be a JSON object with a \"claims\" list.", file=sys.stderr)
        return 1
    claims = data.get("claims") or []
    if not claims:
        print("REFUSED: no claims listed. If the message truly has none, say so instead of writing a receipt.", file=sys.stderr)
        return 1

    problems, counts, ids = [], {}, set()
    for i, c in enumerate(claims):
        cid = c.get("id") or f"#{i + 1}"
        if cid in ids:
            problems.append(f"{cid}: duplicate id")
        ids.add(cid)
        status = (c.get("status") or "").strip().lower()
        lb = c.get("load_bearing", True)
        if not (c.get("text") or "").strip():
            problems.append(f"{cid}: empty claim text")
        if status not in FINAL:
            problems.append(f"{cid}: status '{status or 'missing'}' is not final "
                            f"(use {', '.join(sorted(FINAL))})")
            continue
        if lb and status != "cut" and len((c.get("evidence") or "").strip()) < 12:
            problems.append(f"{cid}: load-bearing claim has no evidence (say what you ran or read, and what it showed)")
        if status == "corrected" and not (c.get("correction") or c.get("evidence")):
            problems.append(f"{cid}: corrected claim must record the checked value")
        counts[status] = counts.get(status, 0) + 1

    if problems:
        print("REFUSED: the draft is not ready to send.", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        return 1

    n = sum(counts.values())
    order = ["verified", "corrected", "labeled", "unverifiable", "cut"]
    words = {"labeled": "labeled as inference", "unverifiable": "marked unverified", "cut": "cut"}
    parts = [f"{counts[k]} {words.get(k, k)}" for k in order if counts.get(k)]
    footer = f"Fact-checked: {n} claims ({', '.join(parts)}). Receipt on request."

    now = dt.datetime.now()
    slug = re.sub(r"[^a-z0-9]+", "-", (data.get("draft") or "draft").lower()).strip("-")[:40] or "draft"
    receipt = dict(data, checked_at=now.isoformat(timespec="seconds"), counts=counts, footer=footer)
    if not dry:
        out_dir = os.path.join(home(), "receipts")
        os.makedirs(out_dir, exist_ok=True)
        path = os.path.join(out_dir, f"{now:%Y-%m-%d-%H%M%S}-{slug}.json")
        with open(path, "w") as f:
            json.dump(receipt, f, indent=2)
        print(f"receipt: {path}", file=sys.stderr)
    print(footer)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
