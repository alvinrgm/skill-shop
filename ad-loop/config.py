#!/usr/bin/env python3
"""ad-loop: the ONE place every path and key resolves.

Nothing else in this package hardcodes a path, a home directory, or a credential.
Every value below is env-overridable, so you change environment variables (or `.env`),
never code.

NO SECRETS LIVE HERE. `gemini_key()` reads the key from the process environment or from
the package `.env` at call time and never writes it anywhere.

Two roots
---------
  package root  this folder: SKILL.md, loop-engine/, runtime/ (static-kit, feed-gate,
                gen, lib, scrub), design/ (the design laws). Code. Safe to re-clone.
  work root     AD_LOOP_HOME (default ~/ad-loop-work): YOUR data. Client layers, volume
                batches, finals, loop-state (learnings, verdict bank, iterations), North
                Stars, the inspo corpus. Never inside the package, so updating the package
                never touches your data.

Environment overrides (all optional except the key)
---------------------------------------------------
  GEMINI_API_KEY       image generation + every vision pass (required)
  AD_LOOP_HOME         the work root                         (default ~/ad-loop-work)
  AD_LOOP_NORTH_STARS  your hand-picked bar                  (default <work>/north-stars)
  AD_LOOP_TASTE_BRIEF  the polish doctrine                   (default runtime/taste-brief.md)
  AD_LOOP_DESIGN_LAWS  the design laws                       (default design/design-laws.md)
  AD_LOOP_GEN_IMAGE    the image generator script            (default runtime/gen/gen_image.py)
  AD_LOOP_VISION_MODEL vision-judge model                    (default gemini-3.1-pro-preview)
  AD_LOOP_VOLUME_CAP   plates per shot per volume batch      (default 15, the spend cap)
  AD_LOOP_VOLUME_SIZE  draft/triage plate size               (default 1K)
  AD_LOOP_WINNER_SIZE  locked-winner re-generation size      (default 4K)

usage:
  python3 config.py           # prints the resolved environment + what is missing
  python3 config.py --init    # creates the work root and seeds an empty loop-state
"""
from __future__ import annotations

import os
import re
import sys
from pathlib import Path

HOME = Path.home()


def _p(env: str, default: Path) -> Path:
    v = os.environ.get(env)
    return Path(os.path.expanduser(v)) if v else default


# ---------------------------------------------------------------- package root (code)
SKILL_DIR = Path(__file__).resolve().parent


def _prefer_venv() -> None:
    """If the package has its own virtual environment (.venv next to SKILL.md), a script
    started with another Python re-runs itself under .venv's Python, so
    `python3 <script>.py` just works on PEP 668 systems. Stdlib only."""
    venv = SKILL_DIR / ".venv"
    py = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not py.is_file() or Path(sys.prefix).resolve() == venv.resolve():
        return
    if not sys.argv or not sys.argv[0] or sys.argv[0] in ("-c", "-"):
        return  # imported from an interactive, -c or stdin session: nothing to re-run
    os.execv(str(py), [str(py), *sys.argv])


_prefer_venv()
LOOP_ENGINE = SKILL_DIR / "loop-engine"
REFERENCE = SKILL_DIR / "reference"
RUNTIME = SKILL_DIR / "runtime"
DOTENV = SKILL_DIR / ".env"


def _load_dotenv() -> None:
    """Pull keys from the package .env so nothing depends on shell-profile exports.
    The real process environment always outranks the file."""
    if not DOTENV.is_file():
        return
    for line in DOTENV.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            k, v = line.split("=", 1)
            v = v.strip().strip("'\"")
            if v:
                os.environ.setdefault(k.strip(), v)


_load_dotenv()

STATIC_KIT = RUNTIME / "static-kit"         # templates/, tokens.css, render.js, fonts/
RENDER_JS = STATIC_KIT / "render.js"
HARVEST_INSPO = STATIC_KIT / "tools" / "harvest_inspo.py"
SHEET = STATIC_KIT / "tools" / "sheet.py"
FEED_GATE = RUNTIME / "feed-gate"           # feedmock/ + ablate.py + geometry.py
ASSET_LIBRARY = RUNTIME / "lib" / "asset_library.py"
REF_SHEET = RUNTIME / "lib" / "ref_sheet.py"
SCRUB = RUNTIME / "scrub" / "scrub.py"      # banned-phrase gate for copy (instrument 5a)

DESIGN_LAWS = _p("AD_LOOP_DESIGN_LAWS", SKILL_DIR / "design" / "design-laws.md")
TASTE_BRIEF = _p("AD_LOOP_TASTE_BRIEF", RUNTIME / "taste-brief.md")

# Image generation. Gemini-class key ONLY, never a credit-billing image service.
GEN_IMAGE = _p("AD_LOOP_GEN_IMAGE", RUNTIME / "gen" / "gen_image.py")
PDP_SCRAPE = RUNTIME / "gen" / "pdp_scrape.py"

VISION_MODEL = os.environ.get("AD_LOOP_VISION_MODEL", "gemini-3.1-pro-preview")

# ---------------------------------------------------------------- work root (your data)
WORK_ROOT = _p("AD_LOOP_HOME", HOME / "ad-loop-work")
WORK = WORK_ROOT
INSPO = WORK_ROOT / "inspo"                     # harvested elite/competitor corpus
LEDGER = WORK_ROOT / "ledger.jsonl"             # every ad + the operator's own verdict
NORTH_STARS = _p("AD_LOOP_NORTH_STARS", WORK_ROOT / "north-stars")

# ---------------------------------------------------------------- spend guard
# Gemini plates are NOT free. Volume x 4K is the cost driver: a few concepts' worth of
# 30-50-plate batches at 4K ran to tens of dollars in a single day. So: cap the batch,
# draft at 1K, and re-generate only the locked winner at 4K.
VOLUME_BATCH_CAP = int(os.environ.get("AD_LOOP_VOLUME_CAP", "15"))   # plates per shot per batch
VOLUME_PLATE_SIZE = os.environ.get("AD_LOOP_VOLUME_SIZE", "1K")      # draft/triage plates
WINNER_PLATE_SIZE = os.environ.get("AD_LOOP_WINNER_SIZE", "4K")      # ONLY the locked winner
PLATE_COST_USD = {"1K": 0.134, "2K": 0.134, "4K": 0.24}              # per image; check the pricing page


def plate_spend(n: int, size: str = VOLUME_PLATE_SIZE) -> float:
    """Dollars for n plates at size. Print this BEFORE every volume batch; refuses n > cap."""
    if n > VOLUME_BATCH_CAP:
        raise ValueError(f"volume batch of {n} exceeds VOLUME_BATCH_CAP={VOLUME_BATCH_CAP}; "
                         "raise AD_LOOP_VOLUME_CAP only with the operator's say-so")
    return round(n * PLATE_COST_USD[size], 2)


# ---------------------------------------------------------------- loop state
# Client-NEUTRAL, global, compounding. Every client's run appends here.
LOOP_STATE = WORK_ROOT / "loop-state"
LEARNINGS = LOOP_STATE / "learnings.md"          # the doctrine store (client-neutral, ALWAYS)
RUBRIC_LIVE = LOOP_STATE / "RUBRIC.md"           # live rubric; reference/RUBRIC.md is the seed
VERDICT_BANK = LOOP_STATE / "verdict-bank"       # labeled ads + the operator's exact words
ORCHESTRATOR_MARKER = LOOP_STATE / "ORCHESTRATOR.md"   # one driver per client-family

# ---------------------------------------------------------------- delivery canvas
CANVAS_W, CANVAS_H = 1080, 1350                  # 4:5 default
MARGIN = 100                                     # law 4: ~9-10% outer margin at 1080
BOTTOM_SAFE = 120                                # 4:5 feed chrome
FOLD_FRAC = 0.23                                 # first-encounter band


# ---------------------------------------------------------------- per client
def client_dir(slug: str) -> Path:
    return WORK_ROOT / slug


def brand_dir(slug: str) -> Path:
    """Everything client-specific lives under here. See reference/client-layer.md."""
    return WORK_ROOT / slug / "brand"


def library_dir(slug: str) -> Path:
    """The client's shared asset Library (runtime/lib/asset_library.py)."""
    return WORK_ROOT / slug / "library"


def personas_dir(slug: str) -> Path:
    return WORK_ROOT / slug / "personas"


def statics_dir(slug: str) -> Path:
    return WORK_ROOT / slug / "statics"


def client_loop_state(slug: str) -> Path:
    """THE canonical home for per-client loop state: iterations.jsonl, launch-brief.md,
    charters, ELI5-<concept>.md. Client-NEUTRAL doctrine (learnings.md, RUBRIC.md, the
    shared verdict bank) stays GLOBAL under LOOP_STATE and is never forked per client."""
    return statics_dir(slug) / "loop-state"


def client_iterations(slug: str) -> Path:
    """The ONE iterations.jsonl a run appends to."""
    return client_loop_state(slug) / "iterations.jsonl"


def client_launch_brief(slug: str) -> Path:
    """The launch interview's verbatim answers."""
    return client_loop_state(slug) / "launch-brief.md"


def iteration_dir(slug: str, concept: str, i: int) -> Path:
    return statics_dir(slug) / f"loop-{concept}" / f"iter-{i:02d}"


def volume_dir(slug: str, concept: str, n: int) -> Path:
    return statics_dir(slug) / f"loop-{concept}" / f"volume-{n:02d}"


# ---------------------------------------------------------------- credentials
def gemini_key() -> str:
    """The Gemini key from the environment (the package .env is loaded into it above).
    Never printed, never logged, never passed on a command line by this skill."""
    k = os.environ.get("GEMINI_API_KEY")
    if k:
        return k
    raise RuntimeError(
        f"GEMINI_API_KEY not found. Put it in {DOTENV} (copy .env.example) or export it.\n"
        "Get one at https://aistudio.google.com/apikey. Images and vision passes use a "
        "Gemini key ONLY, never a credit-billing image service.")


def gemini_key_present() -> tuple[bool, str]:
    """(present?, where it came from) WITHOUT revealing the key. Use this instead of
    grepping a .env from the shell:

        python3 -c "import config; print(config.gemini_key_present())"
    """
    if os.environ.get("GEMINI_API_KEY"):
        return True, "environment (or the package .env)"
    return False, f"absent from the environment and from {DOTENV}"


# ---------------------------------------------------------------- work-root bootstrap
def init_work() -> list[str]:
    """Create the work root and seed an EMPTY loop-state. Idempotent: never overwrites."""
    made = []
    for d in (WORK_ROOT, NORTH_STARS, INSPO, LOOP_STATE, VERDICT_BANK):
        if not d.exists():
            d.mkdir(parents=True, exist_ok=True)
            made.append(str(d))
    seeds = {
        LEARNINGS: "# learnings\n\nOne line per kill/fix reason, client-neutral, numbered. "
                   "Appended by your own loop runs (see reference/logging.md).\n",
        VERDICT_BANK / "README.md": "# verdict bank\n\nEvery operator verdict lands here in "
                                    "their EXACT words (see reference/logging.md).\n",
        ORCHESTRATOR_MARKER: "# orchestrator lock\n\n(one driver per client-family; "
                             "see SKILL.md section 6.5)\n",
        LEDGER: "",
    }
    for p, body in seeds.items():
        if not p.exists():
            p.write_text(body)
            made.append(str(p))
    if not RUBRIC_LIVE.exists() and (REFERENCE / "RUBRIC.md").exists():
        RUBRIC_LIVE.write_text((REFERENCE / "RUBRIC.md").read_text())
        made.append(str(RUBRIC_LIVE))
    return made


# ---------------------------------------------------------------- doctor
def check() -> list[str]:
    """Human-readable problems. Empty list = ready to run."""
    problems = []
    required = {
        "work root (run: python3 config.py --init)": WORK_ROOT,
        "static-kit render.js": RENDER_JS,
        "design-laws.md": DESIGN_LAWS,
        "gen_image.py": GEN_IMAGE,
        "loop-state/learnings.md (run: python3 config.py --init)": LEARNINGS,
    }
    optional = {
        "static-kit node_modules (cd runtime/static-kit && npm install)":
            STATIC_KIT / "node_modules",
        "north-star picks": NORTH_STARS,
        "inspo corpus": INSPO,
        "feed-gate": FEED_GATE,
        "verdict bank": VERDICT_BANK,
        "taste brief": TASTE_BRIEF,
    }
    for name, p in required.items():
        if not p.exists():
            problems.append(f"MISSING (required): {name} -> {p}")
    for name, p in optional.items():
        if not p.exists():
            problems.append(f"missing (degrades the loop): {name} -> {p}")
    if not gemini_key_present()[0]:
        problems.append("MISSING (required): GEMINI_API_KEY (see .env.example)")
    return problems


if __name__ == "__main__":
    if {"-h", "--help"} & set(sys.argv[1:]):
        print("usage:" + __doc__.split("usage:", 1)[1].rstrip())
        sys.exit(0)
    if "--init" in sys.argv[1:]:
        made = init_work()
        print("work root:", WORK_ROOT)
        print("\n".join(f"  created {m}" for m in made) or "  already initialised")
        sys.exit(0)
    print("ad-loop resolved environment")
    print("=" * 72)
    for k, v in sorted(globals().items()):
        if k.isupper() and isinstance(v, (Path, str, int)) and not k.startswith("_"):
            if k in ("HOME",):
                continue
            mark = ""
            if isinstance(v, Path):
                mark = "  ok" if v.exists() else "  ABSENT"
            print(f"  {k:20s} {v}{mark}")
    print("=" * 72)
    probs = check()
    if probs:
        print("PROBLEMS:")
        for p in probs:
            print("  -", p)
    else:
        print("all checks pass")
    sys.exit(1 if any(p.startswith("MISSING") for p in probs) else 0)
