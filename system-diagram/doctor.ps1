# doctor.ps1 — system-diagram health check (Windows).
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
Write-Output "system-diagram needs the Figma MCP server (Claude checks it in-session for the generate_diagram tool)."
$found = $false
if (Get-Command claude -ErrorAction SilentlyContinue) { $found = (claude mcp list 2>$null | Select-String -Pattern figma -Quiet) }
if ($found) { Write-Output "OK a Figma MCP server is configured in Claude Code" }
else { Write-Output "Not found in 'claude mcp list'. Add it: claude mcp add --transport http figma https://mcp.figma.com/mcp  (guide: https://developers.figma.com/docs/figma-mcp-server/remote-server-installation/)" }
if (Test-Path (Join-Path $here "config.local.json")) { Write-Output "OK config.local.json present" } else { Write-Output "optional: copy config.example.json to config.local.json to pin a Figma team or plan" }
