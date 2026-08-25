#!/usr/bin/env bash
# doctor.sh — generated from dependencies.yml. Re-runnable health check.
# Run anytime: bash doctor.sh
# Exits non-zero if a REQUIRED dependency is missing.

cd "$(dirname "$0")" || exit 1
[ -f .env ] && set -a && . ./.env && set +a

FAIL=0
ok()   { printf '✅ %-26s %s\n' "$1" "$2"; }
bad()  { printf '❌ %-26s %s\n' "$1" "$2"; FAIL=1; }
warn() { printf '⚠️  %-26s %s\n' "$1" "$2"; }

echo "adlib-creative-intel — dependency check"
echo "======================================="
echo

# --- Python packages (required) ---
if python3 -c 'import playwright, requests' 2>/dev/null; then
  ok "Python packages" "playwright + requests importable"
else
  bad "Python packages" "MISSING → install:  pip install -r requirements.txt"
fi

# --- Chromium via Playwright (required) ---
if python3 -c 'import playwright' 2>/dev/null; then
  if python3 - <<'PY' 2>/dev/null
from playwright.sync_api import sync_playwright
p = sync_playwright().start()
b = p.chromium.launch()
b.close(); p.stop()
PY
  then
    ok "Chromium (Playwright)" "launches cleanly"
  else
    bad "Chromium (Playwright)" "NOT INSTALLED → install:  python3 -m playwright install chromium"
  fi
else
  bad "Chromium (Playwright)" "playwright missing → pip install -r requirements.txt first"
fi

# --- ffprobe (OPTIONAL) ---
if command -v ffprobe >/dev/null 2>&1; then
  ok "ffprobe (ffmpeg)" "found — format stats enabled"
else
  warn "ffprobe (ffmpeg)" "not found — OPTIONAL. Everything works; the profile just"
  echo "                            skips duration/resolution/aspect stats."
  echo "                            Enable:  brew install ffmpeg   (or apt install ffmpeg)"
fi

# --- Gemini key (REQUIRED for the main use case: watching the videos) ---
if [ -z "$GEMINI_API_KEY" ]; then
  bad "Gemini API key" "NOT SET — this is what lets the tool WATCH the ads."
  echo "     Without it you get metadata only (what ads exist, how long they ran)."
  echo "     With it you get the content-strategy breakdown: script, on-screen text,"
  echo "     shot changes, hooks, pacing, structure — the reason to use this tool."
  echo
  echo "     Set it up (about 2 minutes, free, no credit card):"
  echo "       1. Open   https://aistudio.google.com/apikey"
  echo "       2. Sign in with any Google account"
  echo "       3. Click  'Create API key'"
  echo "       4. Run:   echo 'GEMINI_API_KEY=your-key-here' >> .env"
  echo "       5. Verify: python3 scripts/probe_gemini.py"
  echo
  echo "     Deliberately running without it? Pass --no-cv for the metadata-only path."
else
  if python3 -c 'import google.genai' 2>/dev/null; then
    if python3 scripts/probe_gemini.py >/tmp/_adlib_probe.$$ 2>&1; then
      ok "Gemini API key" "verified with a real API call — video analysis ready"
    else
      bad "Gemini API key" "set, but the API call FAILED (bad key, quota, or region)"
      sed 's/^/     /' /tmp/_adlib_probe.$$ | head -12
    fi
    rm -f /tmp/_adlib_probe.$$
  else
    bad "google-genai" "MISSING → install:  pip install -r requirements.txt"
  fi
fi

# --- Page ID (manual input, informational) ---
echo
echo "ℹ️  Page ID to analyze       You supply this per run: --page-id <ID>"
echo "                            Find it: open the advertiser at"
echo "                            https://www.facebook.com/ads/library/ and copy"
echo "                            view_all_page_id=<ID> from the URL."
echo "                            No login or ad account needed — the page is public."

echo
if [ "$FAIL" -eq 0 ]; then
  echo "All required dependencies present. First run:"
  echo "  python3 scripts/full_run.py --page-id 178024832922517 --slug seed --no-cv"
else
  echo "Some required dependencies are missing — fix the ❌ lines above, then re-run: bash doctor.sh"
fi
exit $FAIL
