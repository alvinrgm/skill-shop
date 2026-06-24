#!/usr/bin/env bash
# doctor.sh — gsuite-bridge setup health check. Generated from dependencies.yml.
# Run anytime:  bash doctor.sh
# Exits non-zero if any REQUIRED item is missing.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
FAIL=0

# Load .env so env-key checks see your values (without printing them).
[ -f "$HERE/.env" ] && set -a && . "$HERE/.env" 2>/dev/null && set +a

ok ()    { printf '  \033[32m✅ %-22s\033[0m %s\n' "$1" "$2"; }
warn ()  { printf '  \033[33m⚠️  %-22s\033[0m %s\n' "$1" "$2"; }
fail ()  { printf '  \033[31m❌ %-22s\033[0m %s\n' "$1" "$2"; FAIL=$((FAIL+1)); }
manual() { printf '  \033[36m• %-22s\033[0m %s\n' "$1" "$2"; }

echo ""
echo "=== gsuite-bridge — setup health check ==="
echo ""

echo "Command-line tools:"
if command -v python3 >/dev/null 2>&1; then
  ok "python3" "$(python3 --version 2>&1)"
else
  fail "python3" "install: https://www.python.org/downloads/ (preinstalled on macOS)"
fi
echo ""

echo "Config (.env):"
if [ -n "${GSUITE_BRIDGE_URL:-}" ] && [[ "${GSUITE_BRIDGE_URL:-}" == *"/exec" ]] \
   && [[ "${GSUITE_BRIDGE_URL:-}" != *"PASTE_YOUR"* ]]; then
  ok "GSUITE_BRIDGE_URL" "set (…${GSUITE_BRIDGE_URL: -18})"
else
  fail "GSUITE_BRIDGE_URL" "deploy the Apps Script, then put the /exec URL in .env (SETUP.md)"
fi
if [ -n "${GSUITE_BRIDGE_SECRET:-}" ] && [[ "${GSUITE_BRIDGE_SECRET:-}" != *"REPLACE_WITH"* ]]; then
  ok "GSUITE_BRIDGE_SECRET" "set"
else
  fail "GSUITE_BRIDGE_SECRET" "invent a random string; put it in .env AND in Code.gs SECRET"
fi
echo ""

echo "Deployment (manual — set up at https://script.google.com):"
manual "Apps Script Web App" "deploy apps-script/Code.gs as a Web App (Execute as: Me). SETUP.md steps 1-7."
manual "Slides API enabled"   "Apps Script → Services (+) → Slides API → Add. SETUP.md step 5."
echo ""

echo "Live end-to-end check:"
if [ -n "${GSUITE_BRIDGE_URL:-}" ] && [[ "${GSUITE_BRIDGE_URL:-}" != *"PASTE_YOUR"* ]] \
   && [ -n "${GSUITE_BRIDGE_SECRET:-}" ] && [[ "${GSUITE_BRIDGE_SECRET:-}" != *"REPLACE_WITH"* ]]; then
  if python3 "$HERE/scripts/verify_bridge.py" >/tmp/gsb_verify.out 2>&1; then
    ok "verify_bridge" "Docs + Sheets + Slides create/delete all passed"
    grep -E '^\[identity\]' /tmp/gsb_verify.out | sed 's/^/      /'
  else
    fail "verify_bridge" "ran but a check failed — see output:"
    sed 's/^/      /' /tmp/gsb_verify.out
  fi
else
  manual "verify_bridge" "skipped — fill .env first, then re-run: bash doctor.sh"
fi
echo ""

if [ "$FAIL" -gt 0 ]; then
  echo "→ $FAIL required item(s) missing. Fix the ❌ lines above, then re-run:  bash doctor.sh"
  exit 1
else
  echo "→ All required checks passed. You're set."
  exit 0
fi
