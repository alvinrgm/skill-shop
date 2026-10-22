#!/usr/bin/env bash
# doctor.sh — fact-check health check.
here="$(cd "$(dirname "$0")" && pwd)"
ok=1
if command -v python3 >/dev/null 2>&1; then
  echo "✅ python3: $(python3 --version 2>&1)"
  tmp="$(mktemp)"
  printf '%s' '{"draft":"doctor","claims":[{"id":"c1","text":"doctor self-test","status":"verified","evidence":"doctor.sh dry run of receipt.py"}]}' > "$tmp"
  if python3 "$here/scripts/receipt.py" "$tmp" --dry-run >/dev/null 2>&1; then
    echo "✅ scripts/receipt.py runs"
  else
    echo "❌ scripts/receipt.py failed its dry run"; ok=0
  fi
  rm -f "$tmp"
else
  echo "❌ python3 not found — install from https://www.python.org/downloads/ (or brew install python)"; ok=0
fi
if [ -x "$HOME/.claude/hooks/fact-check-gate.sh" ]; then
  echo "✅ optional send gate installed (~/.claude/hooks/fact-check-gate.sh)"
else
  echo "ℹ️  optional send gate not installed (see SETUP.md, 'Optional: block unchecked sends')"
fi
[ $ok = 1 ] && echo "ready — invoke with /fact-check or 'check this before I send it'." || exit 1
