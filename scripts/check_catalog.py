#!/usr/bin/env python3
"""Check catalog.json against the folders in this repo.

Fails if a catalog entry has no folder or no SETUP.md, if a folder is missing
from the catalog, if a field is missing, or if a slug repeats. Run it before
every push; the site build trusts this file.
"""
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FIELDS = ["slug", "kind", "tag", "name", "summary", "needs", "version", "published", "updated"]
KINDS = {"plugin", "skill"}

catalog = json.loads((ROOT / "catalog.json").read_text())
items = catalog["items"]
errors = []
seen = set()

for item in items:
    slug = item.get("slug", "?")
    for field in FIELDS:
        if not item.get(field):
            errors.append(f"{slug}: missing {field}")
    if slug in seen:
        errors.append(f"{slug}: listed twice")
    seen.add(slug)
    if item.get("kind") not in KINDS:
        errors.append(f"{slug}: kind must be plugin or skill")
    if not re.fullmatch(r"\d+\.\d+\.\d+", item.get("version", "")):
        errors.append(f"{slug}: version must look like 1.2.3")
    for field in ("published", "updated"):
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", item.get(field, "")):
            errors.append(f"{slug}: {field} must be YYYY-MM-DD")
    image = item.get("image")  # optional: repo-relative card image, e.g. <slug>/explainer/1080x1350.png
    if image and not (ROOT / image).is_file():
        errors.append(f"{slug}: image {image} not found")
    if not (ROOT / slug / "SETUP.md").is_file():
        errors.append(f"{slug}: no {slug}/SETUP.md in the repo")

folders = {p.name for p in ROOT.iterdir() if p.is_dir() and not p.name.startswith(".") and p.name != "scripts"}
for missing in sorted(folders - seen):
    errors.append(f"{missing}: folder exists but is not in catalog.json")

if errors:
    print("\n".join(errors))
    sys.exit(1)
print(f"catalog ok: {len(items)} items")
