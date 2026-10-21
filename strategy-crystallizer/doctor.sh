#!/usr/bin/env bash
# doctor.sh — strategy-crystallizer health check. Zero external dependencies.
echo "strategy-crystallizer: no external dependencies (pure reasoning method)."
if [ -n "${WORK_HOME:-}" ]; then
  echo "  WORK_HOME=$WORK_HOME"
else
  echo "  WORK_HOME unset — strategy docs will default to ~/work/strategy-docs/ (optional; see SETUP.md)."
fi
echo "  ✅ ready — invoke with /strategy or 'build a strategy for <brand>'."
