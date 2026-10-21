#!/usr/bin/env bash
# doctor.sh — first-run health check. Generated from dependencies.yml (one block per dep).
# Run anytime:  bash doctor.sh
# Exits non-zero if any REQUIRED dependency is missing. Optional items only warn.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
FAIL=0

# Load runtime/.env so env-key checks see your keys (without printing them).
[ -f "$HERE/runtime/.env" ] && set -a && . "$HERE/runtime/.env" 2>/dev/null && set +a

ok ()   { printf '  \033[32m✅ %-26s\033[0m %s\n' "$1" "$2"; }
warn () { printf '  \033[33m⚠️  %-26s\033[0m %s\n' "$1" "$2"; }
fail () { printf '  \033[31m❌ %-26s\033[0m %s\n' "$1" "$2"; FAIL=$((FAIL+1)); }
manual(){ printf '  \033[36m•  %-26s\033[0m %s\n' "$1" "$2"; }

echo ""
echo "=== AI Account Manager — setup health check ==="
echo ""

echo "Required — core loop:"
# claude_code (cli)
if command -v claude >/dev/null 2>&1; then ok "Claude Code" "installed"
else fail "Claude Code" "install: https://claude.com/claude-code"; fi
# python_deps (python)
if python3 -c 'import requests, dotenv, matplotlib' 2>/dev/null; then ok "python deps" "requests, python-dotenv, matplotlib"
else fail "python deps" "install: pip install -r requirements.txt"; fi
# bridge (account-manual → check the two env keys, then verify_bridge if set)
if [ -n "${BRIDGE_URL:-}" ] && [ -n "${BRIDGE_SECRET:-}" ]; then ok "Apps Script bridge" "BRIDGE_URL + BRIDGE_SECRET set"
else fail "Apps Script bridge" "deploy your own (bridge/SETUP.md) → set BRIDGE_URL + BRIDGE_SECRET in runtime/.env"; fi
# slack (env-key)
if [ -n "${SLACK_WEBHOOK:-}" ]; then ok "Slack webhook" "SLACK_WEBHOOK set"
else fail "Slack webhook" "https://api.slack.com/messaging/webhooks → runtime/.env SLACK_WEBHOOK"; fi
# roster (account-manual)
if ls "$HERE"/runtime/clients/*/account.md 2>/dev/null | grep -qv _template; then ok "Client roster" "at least one client configured"
else fail "Client roster" "cp -R runtime/clients/_template runtime/clients/<slug>, fill account.md"; fi
echo ""

echo "Optional — data sources (wire up what you use):"
# google_ads
if python3 -c 'import google.ads.googleads' 2>/dev/null && [ -n "${GOOGLE_ADS_DEVELOPER_TOKEN:-}" ]; then ok "Google Ads API" "configured"
else warn "Google Ads API" "for account-ops + Google spend → see SETUP.md (GOOGLE_ADS_* keys)"; fi
# meta_api
if [ -n "${META_ACCESS_TOKEN:-}" ]; then ok "Meta Marketing API" "META_ACCESS_TOKEN set"
else warn "Meta Marketing API" "for ad-spend-monitor Meta spend → META_ACCESS_TOKEN"; fi
# triplewhale
if [ -n "${TRIPLEWHALE_API_KEY:-}" ]; then ok "Triple Whale" "TRIPLEWHALE_API_KEY set"
else warn "Triple Whale" "optional blended attribution → TRIPLEWHALE_API_KEY"; fi
# gemini
if python3 -c 'from google import genai' 2>/dev/null && [ -n "${GEMINI_API_KEY:-}" ]; then ok "Gemini (creative CV)" "configured"
else warn "Gemini (creative CV)" "for creative-intel video analysis → GEMINI_API_KEY (pip install google-genai)"; fi
echo ""

echo "Optional — MCP connections (Claude verifies these live; shell can't):"
manual "Meta Ads (MCP)" "pulls Meta metrics for meta-ops/creative-intel. Claude confirms tools on first run."
manual "Shopify (MCP)" "order/revenue attribution truth-check in the weekly report."
manual "Granola (MCP)" "call transcripts for strategy BACKFILL."
echo ""

if [ "$FAIL" -gt 0 ]; then
  echo "→ $FAIL required item(s) missing. Fix the ❌ lines above, then re-run:  bash doctor.sh"
  exit 1
else
  echo "→ All required checks passed. (Confirm any MCP tools with Claude, then you're set.)"
  exit 0
fi
