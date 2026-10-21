#!/usr/bin/env python3
"""asset_library.py — the per-client shared asset Library.

ONE registry of every reusable visual reference a client has: real pack cutouts, product
reference sheets, location sheets + canonical plates, character sheets, approved plates and
clips. The ad loop asks the Library first for a reference, and registers what it makes back
into it. Make it once, reuse it everywhere.

Home:   $AD_LOOP_HOME/<client>/library/
          library.json            the registry (this file owns its schema)
          product/ location/ character/ plate/ clip/ reference/   the files, by type

An entry:
  {id, type, name, status: draft|approved|rejected, file (relative to library/),
   sources: [paths the asset was made from], description (the locked words to paste into
   prompts verbatim), tags, gates: {print: {...}, ...}, media_id, figma_node_id,
   used_in: [{by, at}], created, updated, notes}

Rules the code enforces:
  - ids are kebab-case and unique; `add` refuses a duplicate id (use --replace on purpose).
  - files are COPIED in (never moved) and sha256-recorded, so a source edit cannot drift the lock.
  - `refs` only returns APPROVED entries unless --any is passed: a draft never silently
    becomes the reference for a paid roll.
  - a product entry cannot be approved while its print gate has wrong > 0 (--force records why).

CLI:
  asset_library.py init <client>
  asset_library.py add <client> --type product --id hw-pack-sheet --name "..." --file x.png
        [--source a.png ...] [--description "..."|--description-file f] [--tag t ...]
        [--status draft|approved] [--replace]
  asset_library.py list <client> [--type T] [--status S] [--json]
  asset_library.py get <client> <id> [--path]
  asset_library.py refs <client> <id> [<id> ...] [--any]      → "--ref /abs/a.png --ref ..."
  asset_library.py gate <client> <id> --print                  run the letter-perfect print gate
  asset_library.py set <client> <id> key=value ...             status / media_id /
                                                               figma_node_id / notes / description
  asset_library.py use <client> <id> --by <concept-or-batch>   record a usage
  asset_library.py seed <client>                               register the real pack shots
                                                               listed in <client>/library/seed.json
                                                               (idempotent)
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

WORK_ROOT = Path(os.path.expanduser(os.environ.get("AD_LOOP_HOME") or str(Path.home() / "ad-loop-work")))
TYPES = ("product", "location", "character", "plate", "clip", "reference")
STATUSES = ("draft", "approved", "rejected")
VISION = Path(__file__).resolve().parents[2] / "loop-engine" / "vision.py"
ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{1,63}$")


def now() -> str:
    return dt.datetime.now().isoformat(timespec="seconds")


def lib_dir(client: str) -> Path:
    return WORK_ROOT / client / "library"


def load(client: str) -> dict:
    p = lib_dir(client) / "library.json"
    if not p.exists():
        sys.exit(f"no library for {client}: run `asset_library.py init {client}`")
    return json.loads(p.read_text())


def touch(reg: dict, aid: str) -> None:
    reg.setdefault("_touched", set()).add(aid)


def save(client: str, reg: dict) -> None:
    """Merge-on-save under an exclusive lock: re-read the registry on disk and overlay ONLY the
    entries this process touched. Parallel writers (several ref_sheet runs at once) used to
    overwrite each other's entries with a stale whole-file write; now they cannot."""
    try:
        import fcntl
    except ImportError:          # Windows: no fcntl; single-writer use is still safe
        fcntl = None
    d = lib_dir(client)
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
    sys.exit(f"no asset '{aid}' in {reg['client']} library")


def abspath(client: str, e: dict) -> Path:
    return lib_dir(client) / e["file"]


# ------------------------------------------------------------------ commands
def cmd_init(a):
    d = lib_dir(a.client)
    if not (WORK_ROOT / a.client).is_dir():
        sys.exit(f"unknown client folder {WORK_ROOT / a.client}")
    for t in TYPES:
        (d / t).mkdir(parents=True, exist_ok=True)
    p = d / "library.json"
    if p.exists():
        print(f"exists: {p}")
        return
    p.write_text(json.dumps({"client": a.client, "schema": 1, "created": now(), "assets": []}, indent=1))
    print(f"created {p}")


def add_entry(client, reg, *, type_, aid, name, file, sources=(), description="", tags=(),
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
    dest = lib_dir(client) / dest_rel
    shutil.copy2(src, dest)
    e = {
        "id": aid, "type": type_, "name": name, "status": status, "file": dest_rel,
        "sha": sha(dest), "sources": [str(Path(s).expanduser()) for s in sources],
        "description": description, "tags": list(tags), "gates": {},
        "media_id": None, "figma_node_id": None, "used_in": [],
        "created": old["created"] if old else now(), "updated": now(), "notes": notes,
    }
    if old:
        e["used_in"] = old.get("used_in", [])
        reg["assets"] = [x for x in reg["assets"] if x["id"] != aid]
    reg["assets"].append(e)
    touch(reg, aid)
    return e


def cmd_add(a):
    reg = load(a.client)
    desc = Path(a.description_file).read_text().strip() if a.description_file else (a.description or "")
    e = add_entry(a.client, reg, type_=a.type, aid=a.id, name=a.name, file=a.file,
                  sources=a.source or [], description=desc, tags=a.tag or [],
                  status=a.status, replace=a.replace, notes=a.notes or "")
    save(a.client, reg)
    print(f"added {e['id']} ({e['type']}, {e['status']}) → {abspath(a.client, e)}")


def cmd_list(a):
    reg = load(a.client)
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
        hf = " media" if e.get("media_id") else ""
        fg = " figma" if e.get("figma_node_id") else ""
        print(f"{e['type']:9s} {e['status']:8s} {e['id']:32s} {e['name'][:48]}{gp}{hf}{fg}"
              f"  used×{len(e.get('used_in', []))}")


def cmd_get(a):
    reg = load(a.client)
    e = entry(reg, a.id)
    print(abspath(a.client, e) if a.path else json.dumps(e, indent=1, ensure_ascii=False))


def cmd_refs(a):
    reg = load(a.client)
    out = []
    for aid in a.ids:
        e = entry(reg, aid)
        if e["status"] != "approved" and not a.any:
            sys.exit(f"'{aid}' is {e['status']}, not approved (pass --any to use a draft knowingly)")
        p = abspath(a.client, e)
        if not p.exists():
            sys.exit(f"file missing for '{aid}': {p}")
        if sha(p) != e["sha"]:
            sys.exit(f"'{aid}' file changed since it was registered (sha mismatch): re-add it")
        out += ["--ref", str(p)]
    print(" ".join(out))


def cmd_gate(a):
    reg = load(a.client)
    e = entry(reg, a.id)
    if not a.print:
        sys.exit("only --print is implemented")
    p = abspath(a.client, e)
    out = lib_dir(a.client) / "gates" / e["id"]
    out.mkdir(parents=True, exist_ok=True)
    # contact sheets are wide grids: read them at native scale; single plates at judge scale
    mode = "print-native" if a.native else "print"
    r = subprocess.run([sys.executable, str(VISION), mode, "--plates", str(p), "--out", str(out),
                        "--client", a.client], capture_output=True, text=True)
    print(r.stdout.strip()[-1500:])
    js = sorted(out.glob("print-*.json"), key=lambda x: x.stat().st_mtime)
    if r.returncode != 0 or not js:
        print(r.stderr[-1500:])
        sys.exit("print gate did not produce a result")
    rec = json.loads(js[-1].read_text())
    s = rec.get("scored") or {}
    touch(reg, e["id"])
    e["gates"]["print"] = {"wrong": s.get("n_wrong"), "pass": s.get("pass_"),
                           "wrong_reads": [w.get("read") for w in s.get("wrong", [])][:8],
                           "mode": mode, "report": str(js[-1]), "at": now(), "sha": e["sha"]}
    e["updated"] = now()
    save(a.client, reg)
    print(f"print gate {e['id']}: wrong={s.get('n_wrong')} pass={s.get('pass_')}")
    sys.exit(0 if s.get("n_wrong") == 0 else 1)


SETTABLE = {"status", "media_id", "figma_node_id", "notes", "description", "name"}


def cmd_set(a):
    reg = load(a.client)
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
    save(a.client, reg)
    print(f"{e['id']}: " + ", ".join(a.pairs))


def cmd_use(a):
    reg = load(a.client)
    e = entry(reg, a.id)
    e.setdefault("used_in", []).append({"by": a.by, "at": now()})
    touch(reg, e["id"])
    save(a.client, reg)
    print(f"{e['id']} used by {a.by} (×{len(e['used_in'])})")


# Real pack shots a client already has, listed per client in <client>/library/seed.json:
#   [{"type": "product", "id": "pack-original-8oz", "name": "...", "file": "brand/product-images/x.png",
#     "description": "The real ... Use as the pack reference; never re-letter it."}, ...]
# Paths are relative to the client folder. intake.py writes a draft of this file.
def seed_rows(client: str):
    p = lib_dir(client) / "seed.json"
    if not p.exists():
        return []
    return [(r["type"], r["id"], r["name"], r["file"], r.get("description", ""))
            for r in json.loads(p.read_text())]


def cmd_seed(a):
    reg = load(a.client)
    have = {e["id"] for e in reg["assets"]}
    n = 0
    for type_, aid, name, rel, desc in seed_rows(a.client):
        if aid in have:
            continue
        src = WORK_ROOT / a.client / rel
        if not src.exists():
            print(f"skip {aid}: missing {src}")
            continue
        add_entry(a.client, reg, type_=type_, aid=aid, name=name, file=src, sources=[src],
                  description=desc, tags=["real", "seed"], status="draft")
        # real photography is approved by provenance (it is the truth the gates compare to)
        reg["assets"][-1]["status"] = "approved"
        reg["assets"][-1]["notes"] = "real photography: approved by provenance"
        touch(reg, aid)
        n += 1
    save(a.client, reg)
    print(f"seeded {n} real assets into {a.client}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("init"); p.add_argument("client"); p.set_defaults(f=cmd_init)
    p = sp.add_parser("add"); p.add_argument("client")
    p.add_argument("--type", required=True, choices=TYPES); p.add_argument("--id", required=True)
    p.add_argument("--name", required=True); p.add_argument("--file", required=True)
    p.add_argument("--source", action="append"); p.add_argument("--description")
    p.add_argument("--description-file"); p.add_argument("--tag", action="append")
    p.add_argument("--status", default="draft", choices=STATUSES)
    p.add_argument("--replace", action="store_true"); p.add_argument("--notes")
    p.set_defaults(f=cmd_add)
    p = sp.add_parser("list"); p.add_argument("client"); p.add_argument("--type")
    p.add_argument("--status"); p.add_argument("--json", action="store_true"); p.set_defaults(f=cmd_list)
    p = sp.add_parser("get"); p.add_argument("client"); p.add_argument("id")
    p.add_argument("--path", action="store_true"); p.set_defaults(f=cmd_get)
    p = sp.add_parser("refs"); p.add_argument("client"); p.add_argument("ids", nargs="+")
    p.add_argument("--any", action="store_true"); p.set_defaults(f=cmd_refs)
    p = sp.add_parser("gate"); p.add_argument("client"); p.add_argument("id")
    p.add_argument("--print", action="store_true"); p.add_argument("--native", action="store_true")
    p.set_defaults(f=cmd_gate)
    p = sp.add_parser("set"); p.add_argument("client"); p.add_argument("id")
    p.add_argument("pairs", nargs="+"); p.add_argument("--force", action="store_true")
    p.set_defaults(f=cmd_set)
    p = sp.add_parser("use"); p.add_argument("client"); p.add_argument("id")
    p.add_argument("--by", required=True); p.set_defaults(f=cmd_use)
    p = sp.add_parser("seed"); p.add_argument("client"); p.set_defaults(f=cmd_seed)
    a = ap.parse_args(argv)
    a.f(a)


if __name__ == "__main__":
    main()
