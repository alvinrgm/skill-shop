# doctor.ps1: Windows health check, written from dependencies.yml (mirror of doctor.sh).
# Run: powershell -ExecutionPolicy Bypass -File doctor.ps1   [-Offline]
param([switch]$Offline)
Set-Location -Path $PSScriptRoot
$fail = 0
function Ok($n, $m)   { Write-Host ("[OK]   {0,-28} {1}" -f $n, $m) }
function Bad($n, $m)  { Write-Host ("[MISS] {0,-28} {1}" -f $n, $m); $script:fail = 1 }
function Warn($n, $m) { Write-Host ("[--]   {0,-28} {1}" -f $n, $m) }

# load .env into this process
if (Test-Path ".env") {
  Get-Content ".env" | ForEach-Object {
    if ($_ -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)\s*$') {
      [Environment]::SetEnvironmentVariable($matches[1], $matches[2].Trim('"').Trim("'"), "Process")
    }
  }
}

# Prefer the package's own virtual environment when it exists.
$py = $null
if (Test-Path ".venv\Scripts\python.exe") { $py = (Resolve-Path ".venv\Scripts\python.exe").Path }
else { foreach ($c in @("python", "py", "python3")) { if (Get-Command $c -ErrorAction SilentlyContinue) { $py = $c; break } } }

Write-Host "ad-loop (Static ad loop): dependency check (python: $py)"
Write-Host "=========================================="

# python_deps
if ($py) {
  & $py -c "import PIL, numpy, dotenv, playwright; from google import genai" 2>$null
  if ($LASTEXITCODE -eq 0) { Ok "Python packages" "importable" } else { Bad "Python packages" "python -m venv .venv; .venv\Scripts\python -m pip install -r requirements.txt  (https://pip.pypa.io/en/stable/installation/)" }
} else { Bad "Python packages" "Python 3 not found -> https://www.python.org/downloads/" }

# node, npm
if (Get-Command node -ErrorAction SilentlyContinue) {
  $nodeMajor = [int]((node -p "process.versions.node.split('.')[0]") 2>$null)
  if ($nodeMajor -ge 20) { Ok "Node.js" (node --version) } else { Bad "Node.js" "$(node --version) is too old: need 20+ -> https://nodejs.org/" }
} else { Bad "Node.js" "need 20+ -> https://nodejs.org/" }
if (Get-Command npm -ErrorAction SilentlyContinue) { Ok "npm" (npm --version) } else { Bad "npm" "ships with Node.js: https://nodejs.org/" }

# chromium_node
if (Test-Path "runtime\static-kit\node_modules\playwright") {
  Push-Location "runtime\static-kit"
  node -e "require('playwright').chromium.launch().then(b=>b.close()).then(()=>process.exit(0),()=>process.exit(1))" 2>$null
  $r = $LASTEXITCODE; Pop-Location
  if ($r -eq 0) { Ok "Chromium (renderer, Node)" "launches" } else { Bad "Chromium (renderer, Node)" "cd runtime\static-kit; npx playwright install chromium  (https://playwright.dev/docs/browsers)" }
} else { Bad "Chromium (renderer, Node)" "cd runtime\static-kit; npm install; npx playwright install chromium  (https://playwright.dev/docs/browsers)" }

# chromium_python
if ($py) {
  & $py -c "from playwright.sync_api import sync_playwright; p=sync_playwright().start(); b=p.chromium.launch(); b.close(); p.stop()" 2>$null
  if ($LASTEXITCODE -eq 0) { Ok "Chromium (Python)" "launches" } else { Bad "Chromium (Python)" "$py -m playwright install chromium  (https://playwright.dev/python/docs/browsers)" }
}

# ffmpeg
if ((Get-Command ffmpeg -ErrorAction SilentlyContinue) -and (Get-Command ffprobe -ErrorAction SilentlyContinue)) { Ok "ffmpeg + ffprobe" "found" }
else { Bad "ffmpeg + ffprobe" "winget install ffmpeg  (https://ffmpeg.org/download.html)" }

# gemini_key (GEMINI_API_KEY)
if (-not $env:GEMINI_API_KEY) {
  Bad "Gemini API key" "NOT SET. https://aistudio.google.com/apikey -> copy .env.example to .env, set GEMINI_API_KEY"
} elseif ($Offline) {
  Warn "Gemini API key" "set (not verified: -Offline)"
} else {
  & $py loop-engine\selftest.py --live *> $null
  if ($LASTEXITCODE -eq 0) { Ok "Gemini API key" "verified with a real vision call" } else { Bad "Gemini API key" "set, but the live call FAILED. See: $py loop-engine\selftest.py --live" }
}

# optional overrides: vision_model, volume_cap, volume_size, winner_size
Warn "Optional overrides" "AD_LOOP_VISION_MODEL / AD_LOOP_VOLUME_CAP / AD_LOOP_VOLUME_SIZE / AD_LOOP_WINNER_SIZE in .env"

# work root
$work = if ($env:AD_LOOP_HOME) { $env:AD_LOOP_HOME } else { Join-Path $HOME "ad-loop-work" }
if (Test-Path (Join-Path $work "loop-state")) { Ok "Work root" $work } else { Warn "Work root" "not created yet (normal on a first run) -> $py config.py --init" }

# north_stars (optional)
$ns = if ($env:AD_LOOP_NORTH_STARS) { $env:AD_LOOP_NORTH_STARS } else { Join-Path $work "north-stars" }
$imgs = @(Get-ChildItem -Path $ns -Include *.png,*.jpg,*.jpeg,*.webp -Recurse -ErrorAction SilentlyContinue)
if ($imgs.Count -gt 0) { Ok "North Star ads" "$($imgs.Count) file(s)" } else { Warn "North Star ads" "optional: drop 5-15 elite ads into $ns (https://www.facebook.com/ads/library/)" }

# meta_ads (optional), client_url (input)
Warn "Meta Ads connector" "optional; Claude checks it in-session. Without it: upload packet only."
Warn "Client brand URL" "you supply it in the launch interview (scripts\intake.py --url), e.g. https://www.example.com"

if ($fail -eq 0) { Write-Host "`nAll required dependencies present. In Claude Code, run: /ad-loop" }
else { Write-Host "`nFix the [MISS] lines, then re-run doctor.ps1." }
exit $fail
