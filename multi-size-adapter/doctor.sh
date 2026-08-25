#!/usr/bin/env bash
# multi-size-creative-adapter: health check. Re-runnable anytime.
# Needs: Python 3 + your team's Gemini API key. Pillow is OPTIONAL (only for extra formats).
set -u

# Always check the package this script lives in, not whatever folder you happen to be in.
cd "$(dirname "$0")" || exit 1

ok()   { printf "✅ %-20s %s\n" "$1" "$2"; }
fail() { printf "❌ %-20s %s\n" "$1" "$2"; }
opt()  { printf "➖ %-20s %s\n" "$1" "$2"; }

FAIL=0

echo "multi-size-creative-adapter: setup check"
echo "-------------------------------------------"

PY=""
for cand in python3 python py; do
  if command -v "$cand" >/dev/null 2>&1 && "$cand" -c 'import sys; sys.exit(0 if sys.version_info[0]==3 else 1)' >/dev/null 2>&1; then
    PY="$cand"; break
  fi
done
if [ -n "$PY" ]; then
  ok "Python 3" "$($PY --version 2>&1) (found as '$PY')"
else
  fail "Python 3" "not found. Install: https://www.python.org/downloads/ — on a work laptop your IT team may need to do this."
  FAIL=$((FAIL+1))
fi

if [ -n "$PY" ] && $PY -c "import PIL" >/dev/null 2>&1; then
  ver="$($PY -c 'import PIL; print(PIL.__version__)' 2>/dev/null)"
  ok "Pillow (optional)" "installed (v${ver}) — extra formats available"
else
  opt "Pillow (optional)" "not installed. Not needed for the four built-in formats."
fi

KEY=""
if [ -f config.yml ]; then
  # Match the engine's parser exactly: allow leading whitespace, strip trailing comments,
  # take the LAST matching line FIRST (before whitespace is collapsed), so a duplicated key
  # cannot concatenate into a bogus pass.
  # Strip a leading UTF-8 BOM first (Notepad/PowerShell write one), so this agrees with the
  # engine, which reads the file as utf-8-sig. Then: allow leading whitespace, strip trailing
  # comments, take the LAST matching line before whitespace is collapsed.
  KEY="$(sed '1s/^\xef\xbb\xbf//' config.yml \
         | sed -n 's/^[[:space:]]*gemini_api_key:[[:space:]]*//p' | sed 's/#.*//' \
         | tail -n 1 | tr -d "\"'" | tr -d '[:space:]')"
fi
[ -z "$KEY" ] && KEY="${GEMINI_API_KEY:-}"

if [ -z "$KEY" ]; then
  fail "Gemini key" "not set. Ask your team lead for the shared key and give it to Claude — it will save it for you. Team lead setup: SETUP.md."
  FAIL=$((FAIL+1))
elif [ "${#KEY}" -lt 30 ] || [ "${KEY#AIza}" = "$KEY" ]; then
  fail "Gemini key" "found, but it does not look like a real Google API key (they start with 'AIza' and are ~39 characters). Current value is ${#KEY} characters. Placeholder text left in by mistake?"
  FAIL=$((FAIL+1))
else
  ok "Gemini key" "configured (${#KEY} chars, starts with AIza)"
  opt "  note" "this check cannot tell whether billing is enabled on that key. Image generation requires a BILLED Google project — see SETUP.md."
fi

if [ -f .onboarded ]; then
  ok ".onboarded" "setup complete"
else
  opt ".onboarded" "first-time setup not finished yet (that's fine)"
fi

echo "-------------------------------------------"
if [ "$FAIL" -gt 0 ]; then
  echo "$FAIL required item(s) missing. Claude can walk you through each one — just ask."
  exit 1
else
  echo "All required checks passed."
  exit 0
fi
