# account-connectors: setup health check (Windows twin of doctor.sh). Follows dependencies.yml.
# Run:  powershell -ExecutionPolicy Bypass -File doctor.ps1          (full)
#       powershell -ExecutionPolicy Bypass -File doctor.ps1 -Quick   (local checks only)
param([switch]$Quick)
Set-Location -Path $PSScriptRoot
$script:Fail = 0
function Ok($n, $m)   { Write-Host ("  OK    {0,-30} {1}" -f $n, $m) -ForegroundColor Green }
function Bad($n, $m)  { Write-Host ("  MISS  {0,-30} {1}" -f $n, $m) -ForegroundColor Red; $script:Fail++ }
function Warn($n, $m) { Write-Host ("  WARN  {0,-30} {1}" -f $n, $m) -ForegroundColor Yellow }
function Info($n, $m) { Write-Host ("  --    {0,-30} {1}" -f $n, $m) -ForegroundColor DarkGray }

$envFile = if ($env:ACCOUNT_CONNECTORS_ENV) { $env:ACCOUNT_CONNECTORS_ENV } else { Join-Path $PSScriptRoot ".env" }
$cfg = @{}
if (Test-Path $envFile) {
    Get-Content $envFile | Where-Object { $_ -match '^\s*[A-Z0-9_]+=' } | ForEach-Object {
        $k, $v = $_ -split '=', 2
        $cfg[$k.Trim()] = $v.Trim().Trim('"').Trim("'")
    }
}
function V($k) { if ($cfg.ContainsKey($k)) { $cfg[$k] } else { "" } }

Write-Host ""
Write-Host "=== account-connectors: setup health check ==="
Write-Host ""
Write-Host "Tooling:"
if (Get-Command node -ErrorAction SilentlyContinue) {
    $major = [int]((node -p "process.versions.node.split('.')[0]") 2>$null)
    if ($major -ge 20) { Ok "node" "$(node --version) (npm and npx included)" } else { Bad "node" "need Node 20+ -> https://nodejs.org/en/download" }
} else { Bad "node" "NOT FOUND -> install Node 20+: https://nodejs.org/en/download" }
if (Test-Path "node_modules/wrangler") {
    if ($Quick) { Ok "npm_deps" "node_modules present" }
    else { npx tsc --noEmit *> $null; if ($LASTEXITCODE -eq 0) { Ok "npm_deps" "installed; npx tsc --noEmit passes" } else { Bad "npm_deps" "typecheck fails -> npx tsc --noEmit" } }
} else { Bad "npm_deps" "not installed -> run: npm install" }
if (Get-Command curl.exe -ErrorAction SilentlyContinue) { Ok "curl" "found (smoke test)" } else { Warn "curl" "optional -> https://curl.se/download.html" }

Write-Host ""
Write-Host "Cloudflare:"
if ($Quick) { Info "cloudflare (wrangler login)" "skipped (-Quick); check with: npx wrangler whoami" }
elseif ((Test-Path "node_modules/wrangler") -and ((npx wrangler whoami 2>$null | Out-String) -match "logged in")) { Ok "cloudflare (wrangler login)" "logged in" }
else { Bad "cloudflare (wrangler login)" "free account: https://dash.cloudflare.com/sign-up then: npx wrangler login" }
if (Select-String -Path wrangler.jsonc -Pattern "REPLACE_WITH_YOUR_KV_NAMESPACE_ID" -Quiet) {
    Bad "kv_namespace (OAUTH_KV)" "after npx wrangler login, run: npx wrangler kv namespace create OAUTH_KV, paste the id into wrangler.jsonc"
} else { Ok "kv_namespace (OAUTH_KV)" "id set in wrangler.jsonc" }

Write-Host ""
Write-Host "Secrets (.env staging -> Cloudflare secrets):"
if (Test-Path $envFile) { Ok ".env" "found" } else { Bad ".env" "copy .env.example to .env and fill it in (SETUP.md)" }
if (V "GOOGLE_CLIENT_ID") { Ok "GOOGLE_CLIENT_ID" "set" } else { Bad "GOOGLE_CLIENT_ID" "YOUR OWN OAuth client: https://console.cloud.google.com/apis/credentials (SETUP.md step 4)" }
if (V "GOOGLE_CLIENT_SECRET") { Ok "GOOGLE_CLIENT_SECRET" "set" } else { Bad "GOOGLE_CLIENT_SECRET" "shown with your OAuth client id (SETUP.md step 4)" }
if (V "COOKIE_ENCRYPTION_KEY") { Ok "COOKIE_ENCRYPTION_KEY" "set" } else { Warn "COOKIE_ENCRYPTION_KEY" "blank; generate: node -e ""console.log(require('crypto').randomBytes(32).toString('hex'))""" }
$allow = (V "ALLOWED_EMAILS") + (V "ALLOWED_DOMAINS")
if (-not $allow) { Bad "allowlist (ALLOWED_EMAILS)" "empty = nobody can sign in (SETUP.md step 5)" }
elseif ((V "ALLOWED_EMAILS") -eq "you@example.com" -and -not (V "ALLOWED_DOMAINS")) { Bad "allowlist (ALLOWED_EMAILS)" "still the placeholder; put your real email" }
else { Ok "allowlist (ALLOWED_EMAILS)" $allow }
$wb = V "WORKER_BASE"
if (-not $wb -or $wb -like "*your-subdomain*") { Warn "WORKER_BASE" "not set yet; printed by your first npx wrangler deploy" } else { Ok "WORKER_BASE" $wb }
if (V "ADMIN_EMAIL") { Ok "ADMIN_EMAIL" (V "ADMIN_EMAIL") } else { Info "ADMIN_EMAIL" "optional; but with the default ACL ({}) vendor tools are admin-only, so with no admin nobody can use them (SETUP.md step 5)" }

Write-Host ""
Write-Host "Vendors (all optional):"
if (V "META_ACCESS_TOKEN") { Ok "meta_read (META_ACCESS_TOKEN)" "set" } else { Info "meta_read (META_ACCESS_TOKEN)" "optional -> https://business.facebook.com/settings/system-users" }
if ((V "META_APP_ID") -and (V "META_APP_SECRET")) { Ok "meta_app (META_APP_ID)" "id + secret set" }
elseif ((V "META_APP_ID") -or (V "META_APP_SECRET")) { Bad "meta_app (META_APP_ID)" "set BOTH META_APP_ID and META_APP_SECRET" }
else { Info "meta_app (META_APP_ID)" "optional (Meta writes) -> https://developers.facebook.com/apps" }
$gads = @("GOOGLE_ADS_DEVELOPER_TOKEN","GOOGLE_ADS_CLIENT_ID","GOOGLE_ADS_CLIENT_SECRET","GOOGLE_ADS_REFRESH_TOKEN") | Where-Object { V $_ }
if ($gads.Count -eq 4) { Ok "gads_dev_token + gads_oauth" "all four Google Ads keys set" }
elseif ($gads.Count -eq 0) { Info "gads_dev_token + gads_oauth" "optional -> https://ads.google.com/aw/apicenter ; token: node scripts/mint-google-ads-refresh-token.mjs" }
else { Bad "gads_dev_token + gads_oauth" "partly set; need GOOGLE_ADS_DEVELOPER_TOKEN, _CLIENT_ID, _CLIENT_SECRET, _REFRESH_TOKEN" }
if ((V "SHOPIFY_CLIENT_ID") -or (V "SHOPIFY_TOKENS")) {
    if ((V "SHOPIFY_CLIENT_ID") -and -not (V "SHOPIFY_CLIENT_SECRET")) { Bad "shopify" "SHOPIFY_CLIENT_SECRET missing" } else { Ok "shopify" "configured" }
} else { Info "shopify" "optional -> https://dev.shopify.com" }
if (V "KLAVIYO_API_KEY") { Ok "klaviyo (KLAVIYO_API_KEY)" "set" } else { Info "klaviyo (KLAVIYO_API_KEY)" "optional -> https://www.klaviyo.com/settings/account/api-keys" }

if (-not $Quick -and (Get-Command node -ErrorAction SilentlyContinue)) {
    Write-Host ""
    Write-Host "Live vendor probes (same calls the server makes):"
    node scripts/check-vendors.mjs | Select-String -Pattern '^(OK|FAIL|--) ' | ForEach-Object { Write-Host "  $_" }
    if ($LASTEXITCODE -ne 0) { $script:Fail++ }
}

Write-Host ""
Write-Host "MCP connection (Claude verifies this, the shell can't):"
$wbShow = if ($wb) { $wb } else { "<WORKER_BASE>" }
Info "mcp_connection" "claude.ai: https://claude.ai/settings/connectors > Add custom connector > $wbShow/mcp"
Info "" "Claude Code: claude mcp add --transport http account-connectors $wbShow/mcp  then /mcp"
Info "" "then ask Claude to call the ping tool (mcp__account-connectors__ping)"
Write-Host ""
if ($script:Fail -gt 0) { Write-Host "-> $script:Fail required item(s) missing. Fix the MISS lines, then re-run doctor.ps1"; exit 1 }
Write-Host "-> All required checks passed. Next: connect the MCP in Claude and call ping."
exit 0
