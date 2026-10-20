#!/usr/bin/env python3
"""Check catalog.json against the folders in this repo.

Fails if a catalog entry has no folder or no SETUP.md, if a folder is missing
from the catalog, if a field is missing, or if a slug repeats. With
--base <old catalog.json> it also fails if a slug published there is gone,
since every slug is a live risegm.com/skills#<slug> link. Run it before every
push; the site build trusts this file.
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
    if image:
        path = (ROOT / image).resolve()
        if Path(image).is_absolute() or not path.is_relative_to(ROOT) or not path.is_file():
            errors.append(f"{slug}: image {image} is not a file inside this repo")
    if not (ROOT / slug / "SETUP.md").is_file():
        errors.append(f"{slug}: no {slug}/SETUP.md in the repo")

folders = {p.name for p in ROOT.iterdir() if p.is_dir() and not p.name.startswith(".") and p.name != "scripts"}
for missing in sorted(folders - seen):
    errors.append(f"{missing}: folder exists but is not in catalog.json")

if "--base" in sys.argv:
    base_path = Path(sys.argv[sys.argv.index("--base") + 1])
    if base_path.is_file() and base_path.stat().st_size:
        base = {i["slug"] for i in json.loads(base_path.read_text())["items"]}
        for gone in sorted(base - seen):
            errors.append(f"{gone}: was published and is now gone; slugs are permanent links")

if errors:
    print("\n".join(errors))
    sys.exit(1)
print(f"catalog ok: {len(items)} items")
