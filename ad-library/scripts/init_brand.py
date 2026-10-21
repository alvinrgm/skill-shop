#!/usr/bin/env python3
"""Create a brand's disk mirror under $AD_LIBRARY_HOME/<brand>/ from the starter templates.

Disk holds the facts, data and scripts' state; Figma holds the design. This scaffolds every
file the other scripts read, with clearly-marked examples to replace (the session fills them
in with you during ONBOARD). It never overwrites an existing file.

usage: init_brand.py <brand-slug> --name "Brand Name" [--site https://example.com]
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import HOME, TEMPLATES  # noqa: E402

LAYOUT = {
    "brand/truth-ledger.jsonl": "truth-ledger.jsonl",
    "brand/pack-strings.json": "pack-strings.json",
    "brand/copy-rules.json": "copy-rules.json",
    "roadmap/angles.json": "angles.json",
    "learnings/traits.json": "traits.json",
    "shotlist/shotlist.json": "shotlist.json",
}
DIRS = ["brand/packs", "brand/site-photography", "copy", "runs", "learnings", "roadmap", "shotlist",
        "library/product", "library/location", "library/character", "library/plate",
        "library/reference"]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("brand")
    ap.add_argument("--name", required=True)
    ap.add_argument("--site", default="")
    a = ap.parse_args()
    if not re.match(r"^[a-z0-9][a-z0-9-]{1,40}$", a.brand):
        sys.exit("brand slug: 2-41 characters, lowercase letters, digits and dashes, "
                 "starting with a letter or digit (e.g. example-snacks)")
    root = HOME / a.brand
    for d in DIRS:
        (root / d).mkdir(parents=True, exist_ok=True)
    made = []
    for rel, tpl in LAYOUT.items():
        dest = root / rel
        if not dest.exists():
            shutil.copy2(TEMPLATES / "brand" / tpl, dest)
            made.append(rel)
    sp = root / "state.json"
    if not sp.exists():
        sp.write_text(json.dumps({
            "brand": a.brand, "brand_name": a.name, "site": a.site, "file_key": "", "file_url": "",
            "created": dt.date.today().isoformat(), "fonts": {}, "vars": {}, "styles": {},
            "pages": {}, "components": {}, "templates": {}, "meta_ad_account_id": "",
            "batches": {}, "mcp_calls": {}, "lessons": []}, indent=1))
        made.append("state.json")
    lj = root / "library/library.json"
    if not lj.exists():
        lj.write_text(json.dumps({"brand": a.brand, "schema": 1,
                                  "created": dt.datetime.now().isoformat(timespec="seconds"),
                                  "assets": []}, indent=1))
        made.append("library/library.json")
    print(f"brand folder: {root}")
    print("created: " + (", ".join(made) if made else "nothing (all files already existed)"))
    print("next: replace the examples in brand/truth-ledger.jsonl, brand/pack-strings.json and "
          "roadmap/angles.json with the brand's real facts (ONBOARD walks you through it).")


if __name__ == "__main__":
    main()
