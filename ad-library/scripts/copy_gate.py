#!/usr/bin/env python3
"""Copy gate: every customer-facing line in a batch is checked BEFORE it goes into Figma.

Claims compliance is not waivable. This gate checks a batch copy file against the brand's
truth ledger and copy rules, and exits non-zero on any FAIL. A line that fails goes back to
whoever wrote it (you, your copywriter, or a model draft you asked for), it is not patched in
Figma.

usage: copy_gate.py <brand> <copy-file.json>

copy file (copy/<batch>.json):
  {"batch": "B01", "ads": [{"id": "A", "headline": "...", "sub": "...", "disclaimer": "...",
                            "claims": ["C01", "C04"], "quotes": ["Q02"]}]}
  claims  = truth-ledger ids of every factual claim the ad makes (labels included)
  quotes  = truth-ledger ids of customer quotes used verbatim

truth ledger (brand/truth-ledger.jsonl, one JSON object per line):
  {"id": "C01", "kind": "claim"|"quote"|"offer", "text": "...", "status": "verified"|"candidate",
   "source": "where it is proven (pack, lab report, site URL, review id)"}

copy rules (brand/copy-rules.json), all optional:
  {"banned": ["miracle", "cure"],                      # case-insensitive substrings
   "hedges": {"energy": "support"},                    # a line containing key must also contain value
   "required_fields": ["disclaimer"],                  # every ad must fill these
   "decade_lowercase_s": false,                        # optional, off by default: "1950s", never "1950S"
   "no_em_dash": true, "max_headline_words": 9}

FAIL: a claim id missing from the ledger, a quote not byte-exact, a banned phrase, a missing
hedge, a missing required field, "1950S"-style decades (if on), em dashes (if on), headline too long.
VERIFY (printed, not a fail): a claim whose ledger row is still `candidate`. It goes on the batch
cover's VERIFY list.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import brand_dir  # noqa: E402

TEXT_FIELDS = ("headline", "sub", "body", "disclaimer", "cta", "sticker", "badge")


def main() -> int:
    if len(sys.argv) > 1 and sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        return 0
    if len(sys.argv) < 3:
        print(__doc__, file=sys.stderr)
        return 2
    lib = brand_dir(sys.argv[1])
    copy = json.loads(Path(sys.argv[2]).expanduser().read_text())
    ledger = {}
    lp = lib / "brand/truth-ledger.jsonl"
    for ln in lp.read_text().splitlines() if lp.exists() else []:
        if ln.strip():
            row = json.loads(ln)
            ledger[row["id"]] = row
    rp = lib / "brand/copy-rules.json"
    rules = json.loads(rp.read_text()) if rp.exists() else {}
    fails, verify = [], []
    for ad in copy.get("ads", []):
        aid = ad.get("id", "?")
        texts = {k: ad[k] for k in TEXT_FIELDS if isinstance(ad.get(k), str)}
        texts.update({f"extra:{i}": t for i, t in enumerate(ad.get("extra_lines", []))})
        for f in rules.get("required_fields", []):
            if not str(ad.get(f, "")).strip():
                fails.append(f"{aid}: required field '{f}' is empty")
        for cid in ad.get("claims", []):
            row = ledger.get(cid)
            if not row:
                fails.append(f"{aid}: claim {cid} is not in the truth ledger")
            elif row.get("status") != "verified":
                verify.append(f"{aid}: claim {cid} '{row.get('text', '')}' is {row.get('status')}: confirm before ship")
        for qid in ad.get("quotes", []):
            row = ledger.get(qid)
            if not row or row.get("kind") != "quote":
                fails.append(f"{aid}: quote {qid} is not a quote row in the ledger")
            elif not any(row["text"] in t for t in texts.values()):
                fails.append(f"{aid}: quote {qid} is not used byte-exact (ledger: \"{row['text'][:60]}\")")
        for field, t in texts.items():
            low = t.lower()
            for b in rules.get("banned", []):
                if b.lower() in low:
                    fails.append(f"{aid}.{field}: banned phrase '{b}'")
            for k, h in rules.get("hedges", {}).items():
                if k.lower() in low and h.lower() not in low:
                    fails.append(f"{aid}.{field}: '{k}' needs its hedge '{h}'")
            if rules.get("decade_lowercase_s", False) and re.search(r"\b\d{4}S\b", t):
                fails.append(f"{aid}.{field}: decade with a capital S ('{t}'), write 1950s")
            if rules.get("no_em_dash") and "—" in t:
                fails.append(f"{aid}.{field}: em dash")
        mx = rules.get("max_headline_words")
        if mx and len(ad.get("headline", "").split()) > mx:
            fails.append(f"{aid}.headline: {len(ad['headline'].split())} words > {mx}")
    for v in verify:
        print("VERIFY", v)
    for f in fails:
        print("FAIL  ", f)
    n = len(copy.get("ads", []))
    print(f"copy gate: {n} ads, {len(fails)} fails, {len(verify)} to verify -> {'FAIL' if fails else 'PASS'}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
