#!/usr/bin/env bash
# doctor.sh — system-diagram health check.
here="$(cd "$(dirname "$0")" && pwd)"
echo "system-diagram needs the Figma MCP server (Claude checks it in-session for the generate_diagram tool)."
if command -v claude >/dev/null 2>&1 && claude mcp list 2>/dev/null | grep -qi figma; then
  echo "✅ a Figma MCP server is configured in Claude Code"
else
  echo "❓ no Figma MCP server found in 'claude mcp list' (it may be added at the account level instead)."
  echo "    add it: claude mcp add --transport http figma https://mcp.figma.com/mcp"
  echo "    guide:  https://developers.figma.com/docs/figma-mcp-server/remote-server-installation/"
fi
if [ -f "$here/config.local.json" ]; then
  echo "✅ config.local.json present (plan_key)"
else
  echo "ℹ️  optional: cp config.example.json config.local.json to pin a Figma team or plan"
fi
echo "ready once generate_diagram is available — invoke with /system-diagram <system>."
