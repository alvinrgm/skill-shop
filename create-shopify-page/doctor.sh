#!/usr/bin/env bash
# doctor.sh — create-shopify-page health check.
ok=1
if command -v node >/dev/null 2>&1 && node -e "process.exit(+process.versions.node.split('.')[0] >= 22 ? 0 : 1)"; then
  echo "✅ node $(node --version)"
else
  echo "❌ Node.js 22+ — https://nodejs.org/  (Mac: brew install node)"; ok=0
fi
if command -v shopify >/dev/null 2>&1; then
  echo "✅ shopify cli $(shopify version 2>/dev/null | tail -1)"
else
  echo "❌ Shopify CLI — npm install -g @shopify/cli@latest  (https://shopify.dev/docs/api/shopify-cli)"; ok=0
fi
echo "ℹ️  store access: run 'shopify theme list --store <store>.myshopify.com' and sign in; it must list the themes."
if command -v claude >/dev/null 2>&1 && claude mcp list 2>/dev/null | grep -qi figma; then
  echo "✅ a Figma MCP server is configured in Claude Code"
else
  echo "❓ Figma MCP server not found in 'claude mcp list' (it may be added via the plugin or account instead)."
  echo "    claude plugin install figma@claude-plugins-official"
  echo "    guide: https://developers.figma.com/docs/figma-mcp-server/remote-server-installation/"
fi
[ $ok = 1 ] && echo "ready — invoke with /create-shopify-page." || exit 1
