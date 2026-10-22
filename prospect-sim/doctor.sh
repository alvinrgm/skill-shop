#!/usr/bin/env bash
# doctor.sh — prospect-sim health check. Nothing is required beyond Claude Code.
home="${PROSPECT_SIM_HOME:-$HOME/prospect-sims}"
echo "prospect-sim: nothing required beyond Claude Code."
if [ -f "$home/approved-facts.md" ]; then
  echo "✅ work folder + approved facts: $home/approved-facts.md"
else
  echo "ℹ️  optional: create $home and copy reference/approved-facts-template.md to $home/approved-facts.md"
  echo "    (mkdir -p \"$home\" && cp \"$(cd "$(dirname "$0")" && pwd)/reference/approved-facts-template.md\" \"$home/approved-facts.md\")"
fi
echo "ℹ️  optional connectors (notes app, CRM/email) are checked by Claude in-session: https://claude.ai/settings/connectors"
echo "ℹ️  web access (optional): allow WebSearch / WebFetch when Claude Code asks, so agents can read the prospect's site and LinkedIn."
echo "ready — invoke with /prospect-sim, or 'prep me for my call with <company>'."
