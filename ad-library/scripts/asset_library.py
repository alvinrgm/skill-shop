#!/usr/bin/env python3
"""asset_library.py: the per-brand shared asset Library.

ONE registry of every reusable visual reference a brand has: real pack cutouts, product
reference sheets, location sheets and their canonical plates, character sheets, approved plates.
Ask the Library first before making or hunting for a reference; register every keeper back into
it. Make it once, reuse it everywhere.

Home:   $AD_LIBRARY_HOME/<brand>/library/
          library.json            the registry (this file owns its schema)
          product/ location/ character/ plate/ reference/   the files, by type

An entry:
  {id, type, name, status: draft|approved|rejected, file (relative to library/), sha,
   sources: [paths the asset was made from], description (the locked words to paste into
   prompts verbatim), tags, gates: {print: {...}}, figma_node_id, used_in: [{by, at}],
   created, updated, notes}

Rules the code enforces:
  - ids are kebab-case and unique; `add` refuses a duplicate id (use --replace on purpose).
  - files are COPIED in (never moved) and sha256-recorded, so a source edit cannot drift the lock.
  - `refs` only returns APPROVED entries unless --any is passed: a draft never silently
    becomes the reference for a paid generation.
  - a generated product image cannot be approved while its print gate has wrong > 0
    (--force records why). Real pack photos (file name starting `pack-`) are approved by provenance.

CLI:
  asset_library.py init <brand>
  asset_library.py register-packs <brand>        register every real cutout in <brand>/brand/packs/
  asset_library.py add <brand> --type plate --id hero-4x5 --name "..." --file x.png
        [--source a.png ...] [--description "..."|--description-file f] [--tag t ...]
        [--status draft|approved] [--replace]
  asset_library.py list <brand> [--type T] [--status S] [--json]
  asset_library.py get <brand> <id> [--path]
  asset_library.py refs <brand> <id> [<id> ...] [--any]     -> "--ref /abs/a.png --ref ..."
  asset_library.py gate <brand> <id> --print [--native]      run the letter-perfect print gate
  asset_library.py set <brand> <id> key=value ...            status / figma_node_id / notes / description / name
  asset_library.py use <brand> <id> --by <batch-or-concept>  record a usage
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import HOME as LIBRARY_HOME  # noqa: E402
TYPES = ("product", "location", "character", "plate", "reference")
STATUSES = ("draft", "approved", "rejected")
PRINT_GATE = Path(__file__).resolve().parent / "print_gate.py"
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,63}$")


def now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def lib_dir(brand: str) -> Path:
    return LIBRARY_HOME / brand / "library"


def load(brand: str) -> dict:
    p = lib_dir(brand) / "library.json"
    if not p.exists():
        sys.exit(f"no library for {brand}: run `asset_library.py init {brand}`")
    return json.loads(p.read_text())


def touch(reg: dict, aid: str) -> None:
    reg.setdefault("_touched", set()).add(aid)


def save(brand: str, reg: dict) -> None:
    """Merge-on-save under an exclusive lock: re-read the registry on disk and overlay ONLY the
    entries this process touched. Parallel writers (several ref_sheet runs at once) used to
    overwrite each other's entries with a stale whole-file write; now they cannot."""
    try:
        import fcntl  # Unix; on Windows the merge still runs, just without the lock
    except ImportError:
        fcntl = None
    d = lib_dir(brand)
    p = d / "library.json"
    touched = reg.pop("_touched", set())
    with open(d / ".library.lock", "w") as lk:
        if fcntl:
            fcntl.flock(lk, fcntl.LOCK_EX)
        disk = json.loads(p.read_text()) if p.exists() else {k: v for k, v in reg.items() if k != "assets"} | {"assets": []}
        mine = {e["id"]: e for e in reg["assets"] if e["id"] in touched}
        merged = [mine.pop(e["id"], e) for e in disk["assets"]] + list(mine.values())
        disk["assets"] = merged
        disk["updated"] = now()
        tmp = p.with_suffix(".tmp")
        tmp.write_text(json.dumps(disk, indent=1, ensure_ascii=False))
        tmp.replace(p)
    reg["assets"] = merged


def sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()[:16]


def entry(reg: dict, aid: str) -> dict:
    for e in reg["assets"]:
        if e["id"] == aid:
            return e
    sys.exit(f"no asset '{aid}' in {reg['brand']} library")


def abspath(brand: str, e: dict) -> Path:
    return lib_dir(brand) / e["file"]


# ------------------------------------------------------------------ commands
def cmd_init(a):
    d = lib_dir(a.brand)
    if not (LIBRARY_HOME / a.brand).is_dir():
        sys.exit(f"unknown brand folder {LIBRARY_HOME / a.brand}: run init_brand.py first")
    for t in TYPES:
        (d / t).mkdir(parents=True, exist_ok=True)
    p = d / "library.json"
    if p.exists():
        print(f"exists: {p}")
        return
    p.write_text(json.dumps({"brand": a.brand, "schema": 1, "created": now(), "assets": []}, indent=1))
    print(f"created {p}")


def add_entry(brand, reg, *, type_, aid, name, file, sources=(), description="", tags=(),
              status="draft", replace=False, notes=""):
    if not ID_RE.match(aid):
        sys.exit(f"bad id '{aid}': kebab-case, 2-64 chars")
    if type_ not in TYPES:
        sys.exit(f"type must be one of {TYPES}")
    src = Path(file).expanduser().resolve()
    if not src.is_file():
        sys.exit(f"no such file {src}")
    old = next((e for e in reg["assets"] if e["id"] == aid), None)
    if old and not replace:
        sys.exit(f"'{aid}' exists; pass --replace to overwrite it on purpose")
    if status == "approved" and type_ == "product" and not src.name.startswith("pack-"):
        # a generated product image must clear the print gate first (gate, then set status)
        status = "draft"
        print("note: product assets enter as draft; run `gate --print` then `set status=approved`")
    dest_rel = f"{type_}/{aid}{src.suffix.lower()}"
    dest = lib_dir(brand) / dest_rel
    shutil.copy2(src, dest)
    e = {
        "id": aid, "type": type_, "name": name, "status": status, "file": dest_rel,
        "sha": sha(dest), "sources": [str(Path(s).expanduser()) for s in sources],
        "description": description, "tags": list(tags), "gates": {},
        "figma_node_id": None, "used_in": [],
        "created": old["created"] if old else now(), "updated": now(), "notes": notes,
    }
    if old:
        e["used_in"] = old.get("used_in", [])
        reg["assets"] = [x for x in reg["assets"] if x["id"] != aid]
    reg["assets"].append(e)
    touch(reg, aid)
    return e


def cmd_add(a):
    reg = load(a.brand)
    desc = Path(a.description_file).read_text().strip() if a.description_file else (a.description or "")
    e = add_entry(a.brand, reg, type_=a.type, aid=a.id, name=a.name, file=a.file,
                  sources=a.source or [], description=desc, tags=a.tag or [],
                  status=a.status, replace=a.replace, notes=a.notes or "")
    save(a.brand, reg)
    print(f"added {e['id']} ({e['type']}, {e['status']}) → {abspath(a.brand, e)}")


def cmd_list(a):
    reg = load(a.brand)
    rows = [e for e in reg["assets"]
            if (not a.type or e["type"] == a.type) and (not a.status or e["status"] == a.status)]
    if a.json:
        print(json.dumps(rows, indent=1, ensure_ascii=False))
        return
    if not rows:
        print("(no assets)")
    for e in sorted(rows, key=lambda x: (x["type"], x["id"])):
        g = e.get("gates", {}).get("print")
        gp = f" print:wrong={g.get('wrong')}" if g else ""
        fg = " figma" if e.get("figma_node_id") else ""
        print(f"{e['type']:9s} {e['status']:8s} {e['id']:32s} {e['name'][:48]}{gp}{fg}"
              f"  used×{len(e.get('used_in', []))}")


def cmd_get(a):
    reg = load(a.brand)
    e = entry(reg, a.id)
    print(abspath(a.brand, e) if a.path else json.dumps(e, indent=1, ensure_ascii=False))


def cmd_refs(a):
    reg = load(a.brand)
    out = []
    for aid in a.ids:
        e = entry(reg, aid)
        if e["status"] != "approved" and not a.any:
            sys.exit(f"'{aid}' is {e['status']}, not approved (pass --any to use a draft knowingly)")
        p = abspath(a.brand, e)
        if not p.exists():
            sys.exit(f"file missing for '{aid}': {p}")
        if sha(p) != e["sha"]:
            sys.exit(f"'{aid}' file changed since it was registered (sha mismatch): re-add it")
        out += ["--ref", str(p)]
    print(" ".join(out))


def cmd_gate(a):
    reg = load(a.brand)
    e = entry(reg, a.id)
    if not a.print:
        sys.exit("only --print is implemented")
    p = abspath(a.brand, e)
    out = lib_dir(a.brand) / "gates" / e["id"]
    out.mkdir(parents=True, exist_ok=True)
    # contact sheets are wide grids: read them at native scale; single plates at judge scale
    mode = "native" if a.native else "judge"
    truth = LIBRARY_HOME / a.brand / "brand" / "pack-strings.json"
    cmd = [sys.executable, str(PRINT_GATE), "--plates", str(p), "--out", str(out), "--truth", str(truth)]
    if a.native:
        cmd.append("--native")
    r = subprocess.run(cmd, capture_output=True, text=True)
    print(r.stdout.strip()[-1500:])
    js = sorted(out.glob(f"print-{mode}-*.json"), key=lambda x: x.stat().st_mtime)
    if not js:
        print(r.stderr[-1500:])
        sys.exit("print gate did not produce a result")
    rec = json.loads(js[-1].read_text())
    s = rec.get("scored") or {}
    touch(reg, e["id"])
    e["gates"]["print"] = {"wrong": s.get("n_wrong"), "pass": s.get("pass_"),
                           "wrong_reads": [w.get("read") for w in s.get("wrong", [])][:8],
                           "mode": mode, "report": str(js[-1]), "at": now(), "sha": e["sha"]}
    e["updated"] = now()
    save(a.brand, reg)
    print(f"print gate {e['id']}: wrong={s.get('n_wrong')} pass={s.get('pass_')}")
    sys.exit(0 if s.get("n_wrong") == 0 else 1)


SETTABLE = {"status", "figma_node_id", "notes", "description", "name"}


def cmd_set(a):
    reg = load(a.brand)
    e = entry(reg, a.id)
    for kv in a.pairs:
        k, _, v = kv.partition("=")
        if k not in SETTABLE:
            sys.exit(f"cannot set '{k}' (settable: {sorted(SETTABLE)})")
        if k == "status":
            if v not in STATUSES:
                sys.exit(f"status must be one of {STATUSES}")
            if v == "approved" and e["type"] == "product" and not Path(e["file"]).name.startswith("pack-"):
                g = e["gates"].get("print")
                fresh = g and g.get("sha") == e["sha"]
                if not (fresh and g.get("wrong") == 0) and not a.force:
                    sys.exit(f"'{e['id']}' has no passing print gate on this file "
                             f"(wrong={g.get('wrong') if g else 'not run'}); gate it, or --force "
                             "with a reason in notes=")
        e[k] = v
    e["updated"] = now()
    touch(reg, e["id"])
    save(a.brand, reg)
    print(f"{e['id']}: " + ", ".join(a.pairs))


def cmd_use(a):
    reg = load(a.brand)
    e = entry(reg, a.id)
    e.setdefault("used_in", []).append({"by": a.by, "at": now()})
    touch(reg, e["id"])
    save(a.brand, reg)
    print(f"{e['id']} used by {a.by} (×{len(e['used_in'])})")


IMG_EXT = {".png", ".jpg", ".jpeg", ".webp"}


def cmd_register_packs(a):
    """Register every real product cutout in <brand>/brand/packs/ (idempotent). Real photography
    is approved by provenance: it is the truth the gates compare generated images against."""
    reg = load(a.brand)
    have = {e["id"] for e in reg["assets"]}
    src_dir = LIBRARY_HOME / a.brand / "brand" / "packs"
    n = 0
    for src in sorted(src_dir.glob("*")) if src_dir.is_dir() else []:
        if src.suffix.lower() not in IMG_EXT:
            continue
        stem = re.sub(r"[^a-z0-9-]+", "-", src.stem.lower()).strip("-")
        aid = stem if stem.startswith("pack-") else f"pack-{stem}"
        if aid in have:
            continue
        add_entry(a.brand, reg, type_="product", aid=aid[:64], name=f"{src.stem}: real pack cutout",
                  file=src, sources=[src], tags=["real"], status="draft",
                  description=f"The real {src.stem} pack. Use as the pack reference; never re-letter it.")
        reg["assets"][-1]["status"] = "approved"
        reg["assets"][-1]["notes"] = "real photography: approved by provenance"
        n += 1
    save(a.brand, reg)
    print(f"registered {n} real pack cutouts from {src_dir}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("init"); p.add_argument("brand"); p.set_defaults(f=cmd_init)
    p = sp.add_parser("add"); p.add_argument("brand")
    p.add_argument("--type", required=True, choices=TYPES); p.add_argument("--id", required=True)
    p.add_argument("--name", required=True); p.add_argument("--file", required=True)
    p.add_argument("--source", action="append"); p.add_argument("--description")
    p.add_argument("--description-file"); p.add_argument("--tag", action="append")
    p.add_argument("--status", default="draft", choices=STATUSES)
    p.add_argument("--replace", action="store_true"); p.add_argument("--notes")
    p.set_defaults(f=cmd_add)
    p = sp.add_parser("list"); p.add_argument("brand"); p.add_argument("--type")
    p.add_argument("--status"); p.add_argument("--json", action="store_true"); p.set_defaults(f=cmd_list)
    p = sp.add_parser("get"); p.add_argument("brand"); p.add_argument("id")
    p.add_argument("--path", action="store_true"); p.set_defaults(f=cmd_get)
    p = sp.add_parser("refs"); p.add_argument("brand"); p.add_argument("ids", nargs="+")
    p.add_argument("--any", action="store_true"); p.set_defaults(f=cmd_refs)
    p = sp.add_parser("gate"); p.add_argument("brand"); p.add_argument("id")
    p.add_argument("--print", action="store_true"); p.add_argument("--native", action="store_true")
    p.set_defaults(f=cmd_gate)
    p = sp.add_parser("set"); p.add_argument("brand"); p.add_argument("id")
    p.add_argument("pairs", nargs="+"); p.add_argument("--force", action="store_true")
    p.set_defaults(f=cmd_set)
    p = sp.add_parser("use"); p.add_argument("brand"); p.add_argument("id")
    p.add_argument("--by", required=True); p.set_defaults(f=cmd_use)
    p = sp.add_parser("register-packs"); p.add_argument("brand"); p.set_defaults(f=cmd_register_packs)
    a = ap.parse_args(argv)
    a.f(a)


if __name__ == "__main__":
    main()
