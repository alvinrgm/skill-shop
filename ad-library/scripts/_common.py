"""Shared paths and .env loading for the ad-library scripts. Stdlib only.

AD_LIBRARY_HOME  where every brand folder lives (default: ~/ad-library).
                 One folder per brand: $AD_LIBRARY_HOME/<brand>/
The package's own .env (next to SKILL.md) is loaded first, then $AD_LIBRARY_HOME/.env.
Values already set in the environment always win.
If the package has its own virtual environment (.venv next to SKILL.md), a script started with
another Python re-runs itself under .venv's Python, so `python3 scripts/<x>.py` just works.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

PKG = Path(__file__).resolve().parent.parent
SCRIPTS = PKG / "scripts"
TEMPLATES = PKG / "templates"


def _prefer_venv() -> None:
    venv = PKG / ".venv"
    py = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not py.is_file() or Path(sys.prefix).resolve() == venv.resolve():
        return
    if not sys.argv or not sys.argv[0] or sys.argv[0] == "-c":
        return  # imported from an interactive or -c session: nothing to re-run
    os.execv(str(py), [str(py), *sys.argv])


_prefer_venv()


def _load_env_file(p: Path) -> None:
    if not p.is_file():
        return
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        k, v = k.strip(), v.strip().strip("'\"")
        if k and v and k not in os.environ:
            os.environ[k] = v


_load_env_file(PKG / ".env")
HOME = Path(os.environ.get("AD_LIBRARY_HOME", str(Path.home() / "ad-library"))).expanduser()
_load_env_file(HOME / ".env")


def brand_dir(slug: str, must_exist: bool = True) -> Path:
    d = HOME / slug
    if must_exist and not d.is_dir():
        sys.exit(f"no brand folder {d}: run `python3 scripts/init_brand.py {slug} --name \"...\"` first")
    return d


def gemini_key() -> str:
    k = os.environ.get("GEMINI_API_KEY", "").strip()
    if not k:
        sys.exit("GEMINI_API_KEY is not set. Get one at https://aistudio.google.com/apikey "
                 "and put it in .env (see SETUP.md).")
    return k
