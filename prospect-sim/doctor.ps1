# doctor.ps1 — prospect-sim health check (Windows). Nothing is required beyond Claude Code.
$home_dir = if ($env:PROSPECT_SIM_HOME) { $env:PROSPECT_SIM_HOME } else { Join-Path $HOME "prospect-sims" }
Write-Output "prospect-sim: nothing required beyond Claude Code."
if (Test-Path (Join-Path $home_dir "approved-facts.md")) { Write-Output "OK work folder + approved facts: $home_dir" }
else { Write-Output "optional: create $home_dir and copy reference\approved-facts-template.md to approved-facts.md there" }
Write-Output "optional connectors (notes app, CRM/email): https://claude.ai/settings/connectors"
Write-Output "web access (optional): allow WebSearch / WebFetch when Claude Code asks."
Write-Output "ready - invoke with /prospect-sim, or 'prep me for my call with <company>'."
