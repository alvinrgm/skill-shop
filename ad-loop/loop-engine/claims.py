#!/usr/bin/env python3
"""Byte-exact verification of every quoted fragment that ships, against the raw records.

Generalised from a per-iteration quote verifier (Stamped-style review exports), with the
client-specific ship list, product-line regex and SKU name lifted out into a spec.

WHAT IT ENFORCES, and why each rule exists:

  WHOLE UNIT       the fragment must be byte-identical to a whole title, or to a whole
                   sentence of the message split on terminal punctuation. Testimonial elision is a compliance surface, not a style choice —
                   dropping a reviewer's own uncertainty qualifier materially changes
                   meaning (FTC 16 CFR 255.1). Elide only whole trailing content, never an
                   internal qualifier; prefer quotes that need no elision at all.
  VERIFIED BUYER   the platform's verified flag, exactly.
  RATING           the star rating, exactly.
  AUTHOR / YEAR    what ships must match the record, character for character.
  WORD CAP         a fragment longer than the cap is a paragraph wearing quote marks.
  INVARIANT        optional regex the fragment must satisfy (e.g. the concept's shared
                   word must be TERMINAL). The device is only a device if
                   every fragment carries it in the same place.
  PRODUCT LINE     verify a testimonial's PRODUCT LINE, not only its text,
                   rating and verified flag. Review platforms file a review against the
                   order line it was solicited for, which can be an accessory rather than
                   the product in the frame. The quote can be entirely true and still
                   imply something the record does not support.
  BATCH MATCH      optional byte-comparison against the rendered batch.json, so the file
                   that actually shipped is the file that was verified.

Plus the DISCLOSURE BLOCK, computed rather than remembered: which fragments are filed
against the exact SKU in frame and which against a sibling line. If it
mismatches, disclose it and carry a matched alternative rather than discovering it at the
gate.

Exit 1 on any mismatch.

usage:
  python3 claims.py SPEC.json          # see SPEC_EXAMPLE below for the shape
"""
from __future__ import annotations

import argparse
import glob as globmod
import json
import re
import sys
from pathlib import Path

# Stamped's export schema. Override per platform with spec["schema"].
SCHEMA = {
    "records_key": "data",      # the array inside each export file
    "id": "id",
    "title": "reviewTitle",
    "message": "reviewMessage",
    "verified": "reviewVerifiedType",
    "rating": "reviewRating",
    "author": "author",
    "date": "reviewDate",
    "product": "productName",
}

SPEC_EXAMPLE = {
    "records": ["$AD_LOOP_HOME/<client>/statics/loop-<concept>/iter-<NN>/claims/reviews-p*.json"],
    "schema": SCHEMA,
    "sku_in_frame": "Original Sea Salt Crackers",
    "sku_match": "sea salt",
    "product_line_re": "cracker|snack|bundle|variety|pack",
    "invariant_re": "\\bevery time\\b[!.?]*$",
    "word_cap": 10,
    "require_rating": 5,
    "require_verified": 2,
    "rendered": {"batch": "../batch.json", "variant": 0,
                 "keys": ["q1", "q2", "q3", "q4", "q5", "q6"]},
    "fragments": [
        {"id": 100001, "field": "reviewMessage", "text": "My kids ask for these every time!",
         "author": "Sam P.", "year": "2026"}
    ],
}


def load_records(patterns, schema=SCHEMA, root=None):
    """id -> (source breadcrumb, record). Later files never overwrite earlier ones, so a
    duplicated export cannot quietly change which record a fragment was checked against."""
    out = {}
    for pat in patterns:
        for f in sorted(globmod.glob(str(Path(pat).expanduser()))):
            p = Path(f)
            try:
                src = str(p.relative_to(root)) if root else str(p)
            except ValueError:
                src = str(p)
            for r in json.load(open(p))[schema["records_key"]]:
                out.setdefault(r[schema["id"]], (src, r))
    return out


def whole_units(rec, field, title_fields=("reviewTitle",)):
    """The complete units of a field: the whole title, or each whole sentence of the
    message. Characters BEFORE and AFTER a unit inside the same message are OTHER WHOLE
    SENTENCES, not elided content — that distinction is the entire permission model."""
    v = (rec.get(field) or "")
    if field in title_fields:
        return [v.strip()] if v.strip() else []
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", v) if s.strip()]


def verify(fragments, records, *, schema=SCHEMA, product_line_re=None, invariant_re=None,
           word_cap=None, require_rating=None, require_verified=None, rendered=None,
           sku_in_frame=None, sku_match=None, echo=True):
    """Returns (ok, rows). `fragments` is a list of dicts:
    {"id":, "field":, "text":, "author":, "year":}"""
    ok = True
    rows = []
    if echo:
        print(f"{'id':>12}  {'author':14s} {'date':10s} {'product line filed':34s} "
              f"{'op':12s} shipped")
        print("-" * 132)
    for i, fr in enumerate(fragments):
        rid, field, frag = fr["id"], fr["field"], fr["text"]
        if rid not in records:
            ok = False
            rows.append({"id": rid, "flags": ["NO-SUCH-RECORD"], "text": frag})
            if echo:
                print(f"{rid:>12}  !! NO-SUCH-RECORD for {frag!r}")
            continue
        src, r = records[rid]
        units = whole_units(r, field, (schema["title"],))
        flags = []
        if frag not in units:
            flags.append("NOT-A-WHOLE-UNIT")
        if require_verified is not None and r.get(schema["verified"]) != require_verified:
            flags.append("NOT-VERIFIED")
        if require_rating is not None and r.get(schema["rating"]) != require_rating:
            flags.append(f"NOT-{require_rating}-STAR")
        if fr.get("author") is not None and r.get(schema["author"]) != fr["author"]:
            flags.append(f"AUTHOR-MISMATCH({r.get(schema['author'])!r})")
        if fr.get("year") and not str(r.get(schema["date"], "")).endswith(str(fr["year"])):
            flags.append(f"YEAR-MISMATCH({r.get(schema['date'])})")
        if word_cap and len(frag.split()) > word_cap:
            flags.append(f"OVER-{word_cap}-WORDS({len(frag.split())})")
        if invariant_re and not re.search(invariant_re, frag, re.I):
            flags.append("INVARIANT-NOT-TERMINAL")
        # the product line the review was actually filed against
        if product_line_re and not re.search(product_line_re,
                                             str(r.get(schema["product"], "")), re.I):
            flags.append(f"OFF-CATEGORY-SKU({r.get(schema['product'])!r})")
        if rendered is not None:
            if i >= len(rendered) or rendered[i] != frag:
                flags.append("BATCH-MISMATCH")
        if flags:
            ok = False
        rows.append({"id": rid, "source": src, "author": r.get(schema["author"]),
                     "date": r.get(schema["date"]), "product": r.get(schema["product"]),
                     "text": frag, "flags": flags})
        if echo:
            print(f"{rid:>12}  {str(r.get(schema['author'],''))[:14]:14s} "
                  f"{str(r.get(schema['date'],''))[:10]:10s} "
                  f"{str(r.get(schema['product'],''))[:34]:34s} {'exact-unit':12s} {frag!r}")
            if flags:
                print(f"{'':>12}  !! {' '.join(flags)}")
    if echo:
        print("-" * 132)

    # ---- disclosure, computed rather than remembered
    if sku_in_frame and sku_match and echo:
        same, sibling = [], []
        for fr in fragments:
            if fr["id"] not in records:
                continue
            pn = str(records[fr["id"]][1].get(schema["product"], ""))
            label = f"{fr.get('author') or fr['id']} ({pn})"
            (same if sku_match.lower() in pn.lower() else sibling).append(label)
        n = len(same) + len(sibling)
        print(f"\nSKU of the product in the frame: {sku_in_frame}")
        print(f"  filed against that line ({len(same)}/{n}):")
        for s in same:
            print("    ·", s)
        print(f"  filed against a sibling line ({len(sibling)}/{n}):")
        for s in sibling:
            print("    ·", s)
        print("  -> if the ad's own copy names the CATEGORY rather than the "
              "SKU, this is consistent;")
        print("     if the copy names the SKU, a sibling-line fragment is a disclosure "
              "item, not a silent pass.")
    return ok, rows


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("spec", nargs="?", help="path to the verification spec JSON")
    ap.add_argument("--print-example", action="store_true")
    a = ap.parse_args(argv)
    if a.print_example or not a.spec:
        print(json.dumps(SPEC_EXAMPLE, indent=2))
        return 0
    spec_path = Path(a.spec).expanduser().resolve()
    spec = json.loads(spec_path.read_text())
    schema = {**SCHEMA, **spec.get("schema", {})}
    records = load_records(spec["records"], schema)

    rendered = None
    rspec = spec.get("rendered")
    if rspec:
        bp = Path(rspec["batch"]).expanduser()
        if not bp.is_absolute():
            bp = (spec_path.parent / bp).resolve()
        if bp.exists():
            f = json.load(open(bp))["variants"][rspec.get("variant", 0)]["fields"]
            rendered = [f[k] for k in rspec["keys"]]

    ok, _rows = verify(spec["fragments"], records, schema=schema,
                       product_line_re=spec.get("product_line_re"),
                       invariant_re=spec.get("invariant_re"),
                       word_cap=spec.get("word_cap"),
                       require_rating=spec.get("require_rating"),
                       require_verified=spec.get("require_verified"),
                       rendered=rendered,
                       sku_in_frame=spec.get("sku_in_frame"),
                       sku_match=spec.get("sku_match"))
    if rendered is None:
        print("\nno rendered batch compared — the strings above are the source of truth "
              "for it.")
        print("\nPASTE-READY:")
        for i, fr in enumerate(spec["fragments"], 1):
            print(f'    "q{i}": {json.dumps(fr["text"], ensure_ascii=False)},')
    else:
        print("\nbatch.json compared field-by-field.")
    print("\nRESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
