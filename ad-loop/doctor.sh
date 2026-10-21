#!/usr/bin/env bash
# doctor.sh: written from dependencies.yml. Re-runnable health check.
# Run anytime: bash doctor.sh        (skip the live Gemini call: bash doctor.sh --offline)
# Exits non-zero if a REQUIRED dependency is missing.

OFFLINE=0
for arg in "$@"; do
  case "$arg" in
    --offline) OFFLINE=1 ;;
    -h|--help) sed -n '2,4p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown option: $arg (try --help)"; exit 2 ;;
  esac
done

cd "$(dirname "$0")" || exit 1
[ -f .env ] && set -a && . ./.env && set +a
# Prefer the package's own virtual environment when it exists.
if [ -x .venv/bin/python ]; then PY=.venv/bin/python; else PY=python3; fi
WORK="${AD_LOOP_HOME:-$HOME/ad-loop-work}"; WORK="${WORK/#\~/$HOME}"
NS="${AD_LOOP_NORTH_STARS:-$WORK/north-stars}"; NS="${NS/#\~/$HOME}"

FAIL=0
ok()   { printf '✅ %-30s %s\n' "$1" "$2"; }
bad()  { printf '❌ %-30s %s\n' "$1" "$2"; FAIL=1; }
warn() { printf '⚠️  %-30s %s\n' "$1" "$2"; }

echo "ad-loop (Static ad loop): dependency check (python: $PY)"
echo "=========================================="
echo

# --- python_deps: Python packages (required) ---
if "$PY" -c 'import PIL, numpy, dotenv, playwright; from google import genai' 2>/dev/null; then
  ok "Python packages" "pillow, numpy, python-dotenv, playwright, google-genai"
else
  bad "Python packages" "MISSING -> install into a virtual environment in this folder:"
  echo "     python3 -m venv .venv && . .venv/bin/activate && python3 -m pip install -r requirements.txt"
  echo "     (pip help: https://pip.pypa.io/en/stable/installation/)"
fi

# --- node: Node.js 20+ (required) ---
if command -v node >/dev/null 2>&1; then
  NODE_MAJOR="$(node -p 'process.versions.node.split(".")[0]' 2>/dev/null || echo 0)"
  if [ "${NODE_MAJOR:-0}" -ge 20 ] 2>/dev/null; then
    ok "Node.js" "$(node --version)"
  else
    bad "Node.js" "$(node --version) is too old: need 20+ -> https://nodejs.org/  (or: brew install node)"
  fi
else
  bad "Node.js" "MISSING (need 20+) -> https://nodejs.org/  (or: brew install node)"
fi

# --- npm (required) ---
if command -v npm >/dev/null 2>&1; then
  ok "npm" "$(npm --version)"
else
  bad "npm" "MISSING -> ships with Node.js: https://nodejs.org/"
fi

# --- chromium_node: Chromium for the renderer (required) ---
if command -v node >/dev/null 2>&1 && (cd runtime/static-kit && node -e "
const { chromium } = require('playwright');
chromium.launch().then(b => b.close()).then(() => process.exit(0), () => process.exit(1));
") >/dev/null 2>&1; then
  ok "Chromium (renderer, Node)" "static-kit render.js can launch it"
else
  bad "Chromium (renderer, Node)" "MISSING -> cd runtime/static-kit && npm install && npx playwright install chromium"
  echo "     (Linux: npx playwright install --with-deps chromium; help: https://playwright.dev/docs/browsers)"
fi

# --- chromium_python: Chromium for Python (required) ---
if "$PY" - <<'PY' >/dev/null 2>&1
from playwright.sync_api import sync_playwright
p = sync_playwright().start(); b = p.chromium.launch(); b.close(); p.stop()
PY
then
  ok "Chromium (Python)" "harvester / intake / feed mock can launch it"
else
  bad "Chromium (Python)" "MISSING -> $PY -m playwright install chromium"
  echo "     (same pinned Playwright version as the renderer, so it reuses one download;"
  echo "      help: https://playwright.dev/python/docs/browsers)"
fi

# --- ffmpeg: ffmpeg and ffprobe (required for the feed-gate) ---
if command -v ffmpeg >/dev/null 2>&1 && command -v ffprobe >/dev/null 2>&1; then
  ok "ffmpeg + ffprobe" "feed-gate ready"
else
  bad "ffmpeg + ffprobe" "MISSING -> brew install ffmpeg  (or apt install ffmpeg) https://ffmpeg.org/download.html"
fi

# --- gemini_key: GEMINI_API_KEY (required) ---
if [ -z "$GEMINI_API_KEY" ]; then
  bad "Gemini API key" "NOT SET: it powers ALL plate generation and every vision instrument."
  echo "     1. Open   https://aistudio.google.com/apikey"
  echo "     2. Sign in with a Google account, click 'Create API key'"
  echo "     3. cp .env.example .env   then set GEMINI_API_KEY=<key> in .env"
  echo "     4. Verify: $PY loop-engine/selftest.py --live"
elif [ "$OFFLINE" -eq 1 ]; then
  warn "Gemini API key" "set (not verified: --offline)"
elif "$PY" loop-engine/selftest.py --live >/dev/null 2>&1; then
  ok "Gemini API key" "verified with a real vision call"
else
  bad "Gemini API key" "set, but the live call FAILED (bad key, quota, model access or region)."
  echo "     See why: $PY loop-engine/selftest.py --live"
fi

# --- optional env overrides: vision_model, volume_cap, volume_size, winner_size ---
echo
echo "ℹ️  Optional overrides (.env):  AD_LOOP_VISION_MODEL=${AD_LOOP_VISION_MODEL:-default}  AD_LOOP_VOLUME_CAP=${AD_LOOP_VOLUME_CAP:-15}"
echo "                               AD_LOOP_VOLUME_SIZE=${AD_LOOP_VOLUME_SIZE:-1K}  AD_LOOP_WINNER_SIZE=${AD_LOOP_WINNER_SIZE:-4K}"

# --- work root (created by config.py --init) ---
if [ -d "$WORK/loop-state" ]; then
  ok "Work root" "$WORK"
else
  warn "Work root" "not created yet (normal on a first run) -> $PY config.py --init"
fi

# --- north_stars: North Star ads (optional input) ---
if ls "$NS"/*.png "$NS"/*.jpg "$NS"/*.jpeg "$NS"/*.webp >/dev/null 2>&1; then
  ok "North Star ads" "$(ls "$NS" | wc -l | tr -d ' ') file(s) in $NS"
else
  warn "North Star ads" "none yet (optional). Drop 5-15 elite static ads into $NS,"
  echo "                                 or let the launch interview propose some from"
  echo "                                 https://www.facebook.com/ads/library/"
fi

# --- meta_ads: Meta Ads connector (optional, draft uploads only) ---
echo "ℹ️  Meta Ads connector          optional; checked by Claude in-session, not here."
echo "                               Without it a shipped concept ends as an upload packet."

# --- client_url: Client brand URL (input) ---
echo "ℹ️  Client brand URL            you supply it in the launch interview (scripts/intake.py --url),"
echo "                               e.g. https://www.example.com (the brand's public homepage or a product page)."

echo
if [ "$FAIL" -eq 0 ]; then
  echo "All required dependencies present. In Claude Code, run: /ad-loop"
else
  echo "Fix the ❌ lines above, then re-run: bash doctor.sh"
fi
exit $FAIL
