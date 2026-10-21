# doctor.ps1: Windows twin of doctor.sh for ad-library, written from dependencies.yml.
# Run:  powershell -ExecutionPolicy Bypass -File doctor.ps1 [-FigmaConfirmed]
#   -FigmaConfirmed  Claude has checked, in this session, that the Figma MCP tools are available
#                    (a shell cannot see MCP tools). Without it, and before .onboarded exists,
#                    Figma MCP stays [!!].
param([switch]$FigmaConfirmed)
Set-Location -Path $PSScriptRoot
$script:fail = 0
function Ok($n, $m)   { Write-Host ("[OK]  {0,-30} {1}" -f $n, $m) -ForegroundColor Green }
function Bad($n, $m)  { Write-Host ("[!!]  {0,-30} {1}" -f $n, $m) -ForegroundColor Red; $script:fail = 1 }
function Warn($n, $m) { Write-Host ("[--]  {0,-30} {1}" -f $n, $m) -ForegroundColor Yellow }
function Info($n, $m) { Write-Host ("[ii]  {0,-30} {1}" -f $n, $m) -ForegroundColor Cyan }

# .env loader: KEY=value lines; a value already set in the environment wins (same as the scripts).
function Load-Env($path) {
  if (-not (Test-Path $path)) { return }
  Get-Content $path | Where-Object { $_ -match '^\s*[A-Za-z_][A-Za-z0-9_]*\s*=' } | ForEach-Object {
    $k, $v = $_ -split '=', 2
    $k = $k.Trim(); $v = $v.Trim().Trim("'`"")
    if ($v -and -not [Environment]::GetEnvironmentVariable($k)) { [Environment]::SetEnvironmentVariable($k, $v) }
  }
}
Load-Env ".env"
$home_dir = if ($env:AD_LIBRARY_HOME) { $env:AD_LIBRARY_HOME } else { Join-Path $HOME "ad-library" }
Load-Env (Join-Path $home_dir ".env")
# Prefer the package's own virtual environment when it exists.
$py = if (Test-Path .venv\Scripts\python.exe) { ".venv\Scripts\python.exe" } elseif (Get-Command python3 -ErrorAction SilentlyContinue) { "python3" } else { "python" }

Write-Host "ad-library: dependency check"
Write-Host "============================"

# Python packages (required)
& $py -c "import PIL, numpy" 2>$null
if ($LASTEXITCODE -eq 0) { Ok "Python packages" "Pillow + numpy importable" }
else { Bad "Python packages" "MISSING -> python -m venv .venv ; .venv\Scripts\pip install -r requirements.txt  (https://pypi.org/project/pillow/)" }

# Gemini API key (required)
if (-not $env:GEMINI_API_KEY) {
  Bad "Gemini API key" "NOT SET -> https://aistudio.google.com/apikey , copy .env.example to .env if needed, fill in its existing GEMINI_API_KEY= line (do not add a second one), then $py scripts/probe_gemini.py"
} else {
  & $py scripts/probe_gemini.py | Out-Null
  if ($LASTEXITCODE -eq 0) { Ok "Gemini API key" "verified with a real API call" }
  else { Bad "Gemini API key" "set, but the probe FAILED: run $py scripts/probe_gemini.py to see why. Create or replace the key at https://aistudio.google.com/apikey" }
}

# Figma MCP (required; a shell cannot see MCP tools, so Claude must confirm them)
if ($FigmaConfirmed) { Ok "Figma MCP" "confirmed by Claude in this session" }
elseif (Test-Path .onboarded) { Ok "Figma MCP" "confirmed at onboarding (.onboarded); re-run setup if the Figma tools go missing" }
else {
  Bad "Figma MCP" "Claude must confirm the Figma tools are connected (use_figma / create_new_file / upload_assets / download_assets, then whoami)"
  Write-Host "      No Figma account yet: https://www.figma.com/signup"
  Write-Host "      Connect: claude plugin marketplace add anthropics/claude-plugins-official"
  Write-Host "           then claude plugin install figma@claude-plugins-official"
  Write-Host "      or: claude mcp add --transport http figma https://mcp.figma.com/mcp"
  Write-Host "      Needs a Full or Dev seat on a paid plan: https://www.figma.com/pricing/"
  Write-Host "      Once confirmed: doctor.ps1 -FigmaConfirmed"
}

# curl (required)
if (Get-Command curl.exe -ErrorAction SilentlyContinue) { Ok "curl" "found" }
else { Bad "curl" "NOT FOUND -> https://curl.se/download.html" }

# OpenCV + SciPy (optional)
& $py -c "import cv2, scipy" 2>$null
if ($LASTEXITCODE -eq 0) { Ok "OpenCV + SciPy (label repair)" "importable" }
else { Warn "OpenCV + SciPy (label repair)" "optional: .venv\Scripts\pip install -r requirements-repair.txt" }

# Meta read token (optional)
if ($env:META_ACCESS_TOKEN -and $env:META_AD_ACCOUNT_ID) { Ok "Meta Marketing API read token" "set" }
else { Warn "Meta Marketing API read token" "optional (learn.py --no-meta works): https://developers.facebook.com/tools/explorer/" }

# Figma personal access token (optional)
if ($env:FIGMA_TOKEN) { Ok "Figma token (comments)" "FIGMA_TOKEN set" }
else { Warn "Figma token (comments)" "optional: https://developers.figma.com/docs/rest-api/authentication/" }

Info "Optional overrides" "AD_LIBRARY_VISION_MODEL / AD_LIBRARY_IMAGE_MODEL_PRO / AD_LIBRARY_IMAGE_MODEL_NB2 / FIGMA_REPLY_PREFIX"

# Brand facts and pack photos (produced during ONBOARD)
if (Get-ChildItem -Path $home_dir -Filter state.json -Recurse -Depth 1 -ErrorAction SilentlyContinue) { Ok "Brand folders" "found in $home_dir" }
else { Info "Brand facts and pack photos" "none yet in ${home_dir}: ONBOARD creates them (init_brand.py, crawl_site.py, cutout.py; Shopify product images: https://shopify.dev/docs/storefronts/themes/architecture/templates/product)" }

Write-Host ""
if ($script:fail -eq 0) { Write-Host "All required dependencies present. Next: $py scripts/selftest.py" }
else { Write-Host "Fix the [!!] lines above, then re-run doctor.ps1" }
exit $script:fail
