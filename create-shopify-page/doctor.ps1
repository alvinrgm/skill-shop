# doctor.ps1 — create-shopify-page health check (Windows).
$ok = $true
if (Get-Command node -ErrorAction SilentlyContinue) {
  $major = [int]((node --version).TrimStart('v').Split('.')[0])
  if ($major -ge 22) { Write-Output "OK node $(node --version)" } else { Write-Output "MISSING Node.js 22+ - https://nodejs.org/"; $ok = $false }
} else { Write-Output "MISSING Node.js 22+ - https://nodejs.org/"; $ok = $false }
if (Get-Command shopify -ErrorAction SilentlyContinue) { Write-Output "OK shopify cli" }
else { Write-Output "MISSING Shopify CLI - npm install -g @shopify/cli@latest (https://shopify.dev/docs/api/shopify-cli)"; $ok = $false }
Write-Output "store access: run 'shopify theme list --store <store>.myshopify.com' and sign in; it must list the themes."
$found = $false
if (Get-Command claude -ErrorAction SilentlyContinue) { $found = (claude mcp list 2>$null | Select-String -Pattern figma -Quiet) }
if ($found) { Write-Output "OK a Figma MCP server is configured" } else { Write-Output "Figma MCP not found in 'claude mcp list'. claude plugin install figma@claude-plugins-official (guide: https://developers.figma.com/docs/figma-mcp-server/remote-server-installation/)" }
if ($ok) { Write-Output "ready - invoke with /create-shopify-page." } else { exit 1 }
