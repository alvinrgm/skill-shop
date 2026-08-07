#!/usr/bin/env bash
# doctor.sh — adgen-vertical-ad setup health check (generated from dependencies.yml).
# Run anytime:  bash doctor.sh        Exits non-zero if a REQUIRED dep is missing.
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
ADGEN="${ADGEN_HOME:-$HOME/Claude/adgen}"
FAIL=0

# Load keys from .env (adgen runtime) without printing them.
for env in "$ADGEN/.env" "$HERE/.env"; do
  [ -f "$env" ] && set -a && . "$env" 2>/dev/null && set +a
done

ok ()   { printf '  \033[32m✅ %-22s\033[0m %s\n' "$1" "$2"; }
warn () { printf '  \033[33m⚠️  %-22s\033[0m %s\n' "$1" "$2"; }
fail () { printf '  \033[31m❌ %-22s\033[0m %s\n' "$1" "$2"; FAIL=$((FAIL+1)); }
manual(){ printf '  \033[36m•  %-22s\033[0m %s\n' "$1" "$2"; }

echo ""; echo "=== adgen-vertical-ad — setup health check ==="; echo ""

echo "Path config:"
if [ -d "$ADGEN" ]; then ok "ADGEN_HOME" "$ADGEN"
else fail "ADGEN_HOME" "runtime folder missing → copy the adgen/ folder, or:  export ADGEN_HOME=/path/to/adgen"; fi
echo ""

echo "API keys (.env):"
[ -n "${GEMINI_API_KEY:-}" ]     && ok "GEMINI_API_KEY"     "set (images)"  || fail "GEMINI_API_KEY"     "https://aistudio.google.com/apikey  → add to .env"
[ -n "${ELEVENLABS_API_KEY:-}" ] && ok "ELEVENLABS_API_KEY" "set (voice)"   || fail "ELEVENLABS_API_KEY" "https://elevenlabs.io/app/settings/api-keys  → add to .env"
[ -n "${HEDRA_API_KEY:-}" ]      && warn "HEDRA_API_KEY"    "set but LEGACY — unused, safe to remove" || true
echo ""

echo "Command-line tools:"
command -v ffmpeg  >/dev/null 2>&1 && ok "ffmpeg"  "$(ffmpeg -version 2>/dev/null | head -1 | cut -c1-32)" || fail "ffmpeg"  "brew install ffmpeg"
command -v whisper >/dev/null 2>&1 && ok "whisper" "present (QA transcription)"                            || fail "whisper" "pip install openai-whisper"
command -v ffprobe >/dev/null 2>&1 && ok "ffprobe" "present (ships with ffmpeg)"                            || fail "ffprobe" "brew install ffmpeg"
manual "Suno" "music bed — generate the track at suno.com, drop into FCP (optional)"
echo ""

echo "Python packages:"
python3 -c 'import requests, dotenv' 2>/dev/null && ok "python deps" "requests, python-dotenv" || fail "python deps" "pip install -r \"\${ADGEN_HOME:-\$HOME/Claude/adgen}/requirements.txt\""
echo ""

echo "MCP connection (Claude verifies — shell can't see MCP tools):"
manual "Higgsfield (video)" "https://higgsfield.ai  → connect the Higgsfield MCP (SETUP.md §MCP). Claude confirms mcp__*__generate_video on first run."
echo ""

echo "Desktop app (manual):"
[ -d "/Applications/Final Cut Pro.app" ] && ok "Final Cut Pro" "installed" || manual "Final Cut Pro 12.2" "Mac App Store (\$299) — only to finish the cut"
echo ""

if [ "$FAIL" -gt 0 ]; then
  echo "→ $FAIL required item(s) missing. Fix the ❌ lines, then re-run:  bash doctor.sh"; exit 1
else
  echo "→ All required checks passed. Confirm the Higgsfield MCP with Claude, then kick off:"
  echo '   "make a vertical ad for <brand>"  (with a PDP URL or brief)'; exit 0
fi
