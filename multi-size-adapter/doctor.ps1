# multi-size-creative-adapter: health check for Windows. Re-runnable anytime.
# Run: powershell -ExecutionPolicy Bypass -File doctor.ps1
# Needs: Python 3 + Pillow + your team's Gemini API key. Pillow is not used to generate; it
# measures every output during the quality check (and handles extra formats).

Set-Location -Path $PSScriptRoot   # check this package, not the current folder

function Show-Ok   { param($n, $m) Write-Host ("[OK]   {0,-20} {1}" -f $n, $m) }
function Show-Fail { param($n, $m) Write-Host ("[MISS] {0,-20} {1}" -f $n, $m) }
function Show-Opt  { param($n, $m) Write-Host ("[--]   {0,-20} {1}" -f $n, $m) }

$failCount = 0

Write-Host "multi-size-creative-adapter: setup check"
Write-Host "-------------------------------------------"

# On Windows the command is usually 'python' or the 'py' launcher, not 'python3'.
$py = $null
foreach ($cand in @("python", "py", "python3")) {
    $cmd = Get-Command $cand -ErrorAction SilentlyContinue
    if ($cmd) {
        $v = & $cand --version 2>&1
        if ($v -match "Python 3") { $py = $cand; break }
    }
}
if ($py) {
    Show-Ok "Python 3" "$(& $py --version 2>&1) (found as '$py')"
} else {
    Show-Fail "Python 3" "not found. Install from https://www.python.org/downloads/ (tick 'Add Python to PATH'). On a work laptop your IT team may need to do this."
    $failCount++
}

if ($py) {
    & $py -c "import PIL" 2>$null
    if ($LASTEXITCODE -eq 0) {
        $ver = & $py -c "import PIL; print(PIL.__version__)" 2>$null
        Show-Ok "Pillow" "installed (v$ver) - quality-check measurements available"
    } else {
        Show-Fail "Pillow" "not installed. Needed to measure outputs in the quality check. Claude installs it for you: python -m pip install --user Pillow"
        $failCount++
    }
}

$key = ""
if (Test-Path "config.yml") {
    foreach ($line in Get-Content "config.yml") {
        if ($line -match '^\s*gemini_api_key:\s*(.*)$') {
            $key = $matches[1] -replace '#.*$', '' -replace '["'']', ''
            $key = $key.Trim()
        }
    }
}
if ([string]::IsNullOrWhiteSpace($key)) { $key = $env:GEMINI_API_KEY }

if ([string]::IsNullOrWhiteSpace($key)) {
    Show-Fail "Gemini key" "not set. Ask your team lead for the shared key and give it to Claude - it will save it for you. Team lead setup: SETUP.md."
    $failCount++
} elseif ($key.Length -lt 30 -or -not $key.StartsWith("AIza")) {
    Show-Fail "Gemini key" "found, but it does not look like a real Google API key (they start with 'AIza' and are ~39 characters). Current value is $($key.Length) characters. Placeholder text left in by mistake?"
    $failCount++
} else {
    Show-Ok "Gemini key" "configured ($($key.Length) chars, starts with AIza)"
    Show-Opt "  note" "this check cannot tell whether billing is enabled on that key. Image generation requires a BILLED Google project - see SETUP.md."
}

if (Test-Path ".onboarded") {
    Show-Ok ".onboarded" "setup complete"
} else {
    Show-Opt ".onboarded" "first-time setup not finished yet (that's fine)"
}

Write-Host "-------------------------------------------"
if ($failCount -gt 0) {
    Write-Host "$failCount required item(s) missing. Claude can walk you through each one - just ask."
    exit 1
} else {
    Write-Host "All required checks passed."
    exit 0
}
