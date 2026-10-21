#!/usr/bin/env python3
"""Public-repo leak gate. Runs in CI on every push and PR.

This repo is public, so every package in it must be labeled `trust_level: public`.
A `team` or `client` package keeps client names and examples by design, and that is
how client material reached this repo before. The gate also catches the obvious
mechanical leaks: personal paths, stray emails, secret-shaped strings, a real .env,
and photo or editor metadata inside images.

It cannot recognize client material that has been renamed (copy, figures, layouts).
That needs the private, source-aware audit in make-portable, which runs before a
package is published here.

Usage: python3 scripts/check_public.py [repo-root]
"""
import re
import sys
from pathlib import Path

ROOT = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
SKIP_DIRS = {".git", ".github", "scripts", "node_modules", "__pycache__", ".venv"}
TEXT_EXT = {".md", ".py", ".sh", ".ps1", ".yml", ".yaml", ".json", ".txt", ".js",
            ".mjs", ".ts", ".gs", ".html", ".css", ".toml", ".cfg", ".ini", ".example"}

PERSONAL_PATH = re.compile(r"/Users/(?!you\b|your|<|\$|USER\b|name\b)[A-Za-z][\w.-]+|/home/(?!user\b|you\b|<|\$)[a-z][\w.-]+")
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
# Placeholder domains in tests (a@x.com, admin@corp.com) are fine; a real-looking inbox is not.
EMAIL_OK = re.compile(r"@([a-z]{1,4}\.com|example\.(com|org|net)|risegm\.com|mail\.risegm\.com|users\.noreply\.github\.com|anthropic\.com|[\w.-]*\.example)$|^(you|your|name|user|someone|me|noreply|no-reply)@", re.I)
SECRET = re.compile(r"(^|[^A-Za-z0-9_-])(sk-[A-Za-z0-9]{12}|sk_live_[A-Za-z0-9]{8}|ghp_[A-Za-z0-9]{12}|github_pat_[A-Za-z0-9_]{12}|xox[bp]-[A-Za-z0-9-]{10}|AIza[0-9A-Za-z_-]{20}|AKIA[0-9A-Z]{16}|EAA[A-Za-z0-9]{30}|hooks\.slack\.com/services/[A-Za-z0-9/]+)")

errors = []


def err(path, msg):
    errors.append(f"{path.relative_to(ROOT)}: {msg}")


def packages():
    for d in sorted(ROOT.iterdir()):
        if d.is_dir() and d.name not in SKIP_DIRS and not d.name.startswith("."):
            yield d


def check_trust_level(pkg):
    dep = pkg / "dependencies.yml"
    if not dep.exists():
        err(pkg, "no dependencies.yml, so no trust_level label")
        return
    m = re.search(r"^trust_level:\s*([A-Za-z]+)", dep.read_text(errors="replace"), re.M)
    if not m:
        err(dep, "missing top-level `trust_level:` (must be `public` in this repo)")
    elif m.group(1) != "public":
        err(dep, f"trust_level is `{m.group(1)}`; only `public` packages may live in this public repo. Re-port at public level with make-portable first.")


def image_metadata(path, data):
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        i = 8
        while i + 8 <= len(data):
            n = int.from_bytes(data[i:i + 4], "big")
            kind = data[i + 4:i + 8]
            if kind in (b"tEXt", b"iTXt", b"zTXt", b"eXIf"):
                return kind.decode()
            i += 12 + n
    elif data[:2] == b"\xff\xd8":
        i = 2
        while i + 4 <= len(data) and data[i] == 0xFF:
            marker = data[i + 1]
            if marker in (0xDA, 0xD9):
                break
            n = int.from_bytes(data[i + 2:i + 4], "big")
            seg = data[i + 4:i + 2 + n]
            if marker == 0xE1:
                return "EXIF/XMP"
            if marker == 0xFE and seg.strip(b"\x00 "):
                return "JPEG comment"
            i += 2 + n
    return None


def check_files(pkg):
    for f in pkg.rglob("*"):
        if not f.is_file() or any(p in SKIP_DIRS for p in f.relative_to(ROOT).parts[:-1]):
            continue
        if f.name == ".env":
            err(f, "a real .env file; ship .env.example only")
            continue
        if f.suffix.lower() in (".png", ".jpg", ".jpeg"):
            meta = image_metadata(f, f.read_bytes())
            if meta:
                err(f, f"image carries {meta} metadata; re-save it stripped")
            continue
        if f.suffix.lower() not in TEXT_EXT and f.name not in (".gitignore", "LICENSE", "LICENSE.txt"):
            continue
        for n, line in enumerate(f.read_text(errors="replace").splitlines(), 1):
            if PERSONAL_PATH.search(line):
                err(f, f"line {n}: personal path `{PERSONAL_PATH.search(line).group(0)}`")
            if SECRET.search(line):
                err(f, f"line {n}: secret-shaped string")
            for e in EMAIL.findall(line):
                if not EMAIL_OK.search(e):
                    err(f, f"line {n}: email address `{e}`")


for pkg in packages():
    check_trust_level(pkg)
    check_files(pkg)

if errors:
    print("public leak gate FAILED:")
    for e in errors:
        print("  " + e)
    sys.exit(1)
print(f"public leak gate ok: {sum(1 for _ in packages())} packages")
