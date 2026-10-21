#!/usr/bin/env bash
# doctor.sh: health check for ad-library, written from dependencies.yml. Re-run anytime.
# Mac/Linux: bash doctor.sh    Windows: powershell -ExecutionPolicy Bypass -File doctor.ps1
# Exits non-zero if a REQUIRED dependency is missing.
#
#   --figma-confirmed   Claude has checked, in this session, that the Figma MCP tools are
#                       available (a shell cannot see MCP tools). Without it, and before
#                       .onboarded exists, Figma MCP stays ❌.

FIGMA_CONFIRMED=0
for arg in "$@"; do
  case "$arg" in
    --figma-confirmed) FIGMA_CONFIRMED=1 ;;
    -h|--help) sed -n '2,8p' "$0" | sed 's/^# \{0,1\}//'; exit 0 ;;
    *) echo "unknown option: $arg (try --help)"; exit 2 ;;
  esac
done

cd "$(dirname "$0")" || exit 1

# .env loader: KEY=value lines; a value already set in the environment wins (same as the scripts).
load_env() {
  [ -f "$1" ] || return 0
  while IFS= read -r line || [ -n "$line" ]; do
    line="${line#"${line%%[![:space:]]*}"}"
    case "$line" in ''|\#*) continue ;; *=*) ;; *) continue ;; esac
    k="${line%%=*}"; k="${k%"${k##*[![:space:]]}"}"
    v="${line#*=}"; v="${v#"${v%%[![:space:]]*}"}"; v="${v%"${v##*[![:space:]]}"}"
    v="${v#[\"\']}"; v="${v%[\"\']}"
    [[ "$k" =~ ^[A-Za-z_][A-Za-z0-9_]*$ ]] || continue
    [ -n "$v" ] && [ -z "${!k:-}" ] && export "$k=$v"
  done < "$1"
}
load_env ./.env
HOME_DIR="${AD_LIBRARY_HOME:-$HOME/ad-library}"
HOME_DIR="${HOME_DIR/#\~/$HOME}"
load_env "$HOME_DIR/.env"

# Prefer the package's own virtual environment when it exists.
if [ -x .venv/bin/python ]; then PY=.venv/bin/python; else PY=python3; fi

FAIL=0
SHELL_FAIL=0
ok()   { printf '✅ %-30s %s\n' "$1" "$2"; }
bad()  { printf '❌ %-30s %s\n' "$1" "$2"; FAIL=1; }
warn() { printf '⚠️  %-30s %s\n' "$1" "$2"; }
info() { printf 'ℹ️  %-30s %s\n' "$1" "$2"; }

echo "ad-library: dependency check (python: $PY)"
echo "============================"
echo

# --- Python packages (required) ---
if "$PY" -c 'import PIL, numpy' 2>/dev/null; then
  ok "Python packages" "Pillow + numpy importable"
else
  bad "Python packages" "MISSING -> install into a virtual environment in this folder:"
  echo "     python3 -m venv .venv && .venv/bin/pip install -r requirements.txt"
  echo "     (packages: https://pypi.org/project/pillow/ , numpy)"
  SHELL_FAIL=1
fi

# --- Gemini API key (required) ---
if [ -z "${GEMINI_API_KEY:-}" ]; then
  bad "Gemini API key" "NOT SET: plates and the print gate need it."
  echo "     1. Open   https://aistudio.google.com/apikey  -> Create API key"
  echo "     2. If there is no .env yet:  cp .env.example .env"
  echo "     3. Edit .env: fill in the existing  GEMINI_API_KEY=  line (do not add a second one)"
  echo "     4. Verify: $PY scripts/probe_gemini.py"
  SHELL_FAIL=1
else
  PROBE_OUT="$(mktemp 2>/dev/null || echo "/tmp/_adlibrary_probe.$$")"
  if "$PY" scripts/probe_gemini.py >"$PROBE_OUT" 2>&1; then
    ok "Gemini API key" "verified with a real API call"
  else
    bad "Gemini API key" "set, but the probe FAILED (bad key, quota, region or model id):"
    sed 's/^/     /' "$PROBE_OUT" | head -8
    echo "     Create or replace the key at https://aistudio.google.com/apikey , put it on the"
    echo "     GEMINI_API_KEY= line in .env, then re-run: $PY scripts/probe_gemini.py"
    SHELL_FAIL=1
  fi
  rm -f "$PROBE_OUT"
fi

# --- Figma MCP (required; a shell cannot see MCP tools, so Claude must confirm them) ---
if [ "$FIGMA_CONFIRMED" -eq 1 ]; then
  ok "Figma MCP" "confirmed by Claude in this session"
elif [ -f .onboarded ]; then
  ok "Figma MCP" "confirmed at onboarding (.onboarded); re-run setup if the Figma tools go missing"
else
  bad "Figma MCP" "Claude must confirm the Figma tools are connected"
  echo "                                  (use_figma / create_new_file / upload_assets / download_assets, then whoami)."
  echo "                                  No Figma account yet: https://www.figma.com/signup"
  echo "                                  Connect: claude plugin marketplace add anthropics/claude-plugins-official"
  echo "                                       then claude plugin install figma@claude-plugins-official"
  echo "                                  or: claude mcp add --transport http figma https://mcp.figma.com/mcp"
  echo "                                  Needs a Full or Dev seat on a paid plan: https://www.figma.com/pricing/"
  echo "                                  Once confirmed: bash doctor.sh --figma-confirmed"
fi

# --- curl (required) ---
if command -v curl >/dev/null 2>&1; then
  ok "curl" "found (posts files to upload_assets URLs)"
else
  bad "curl" "NOT FOUND -> https://curl.se/download.html  (apt install curl)"
  SHELL_FAIL=1
fi

# --- OpenCV + SciPy (optional, label repair) ---
if "$PY" -c 'import cv2, scipy' 2>/dev/null; then
  ok "OpenCV + SciPy (label repair)" "importable"
else
  warn "OpenCV + SciPy (label repair)" "optional, only for label_composite.py: .venv/bin/pip install -r requirements-repair.txt"
fi

# --- Meta read token (optional) ---
if [ -n "${META_ACCESS_TOKEN:-}" ] && [ -n "${META_AD_ACCOUNT_ID:-}" ]; then
  ok "Meta Marketing API read token" "META_ACCESS_TOKEN + META_AD_ACCOUNT_ID set (learn.py proves it on first run)"
else
  warn "Meta Marketing API read token" "optional: learn.py --no-meta works without it."
  echo "                                  Your own ads_read token: https://developers.facebook.com/tools/explorer/"
fi

# --- Figma personal access token (optional, comments) ---
if [ -n "${FIGMA_TOKEN:-}" ]; then
  ok "Figma token (comments)" "FIGMA_TOKEN set"
else
  warn "Figma token (comments)" "optional: Settings -> Security -> Personal access tokens"
  echo "                                  https://developers.figma.com/docs/rest-api/authentication/"
fi

# --- Optional overrides ---
info "Optional overrides" "AD_LIBRARY_VISION_MODEL / AD_LIBRARY_IMAGE_MODEL_PRO / AD_LIBRARY_IMAGE_MODEL_NB2 / FIGMA_REPLY_PREFIX (only if Google renames a model)"

# --- Brand facts and pack photos (produced during ONBOARD) ---
if [ -d "$HOME_DIR" ] && ls "$HOME_DIR"/*/state.json >/dev/null 2>&1; then
  ok "Brand folders" "$(ls -d "$HOME_DIR"/*/ | wc -l | tr -d ' ') in $HOME_DIR"
else
  info "Brand facts and pack photos" "none yet in $HOME_DIR: ONBOARD creates them"
  echo "                                  (init_brand.py, crawl_site.py, cutout.py; Shopify product images:"
  echo "                                  https://shopify.dev/docs/storefronts/themes/architecture/templates/product )."
fi

echo
if [ "$FAIL" -eq 0 ]; then
  echo "All required dependencies present. Next: $PY scripts/selftest.py"
  echo "Then in Claude Code: \"build the ad library for <brand>, site <url>\""
elif [ "$SHELL_FAIL" -eq 0 ]; then
  echo "Every shell-checkable dependency is present. Left: Claude confirms the Figma MCP tools,"
  echo "then re-runs: bash doctor.sh --figma-confirmed"
else
  echo "Fix the ❌ lines above, then re-run: bash doctor.sh"
fi
exit $FAIL
