# doctor.ps1 — fact-check health check (Windows).
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$py = Get-Command python3 -ErrorAction SilentlyContinue
if (-not $py) { $py = Get-Command python -ErrorAction SilentlyContinue }
if (-not $py) { Write-Output "MISSING python - install from https://www.python.org/downloads/"; exit 1 }
Write-Output "OK python: $(& $py.Source --version)"
$tmp = New-TemporaryFile
'{"draft":"doctor","claims":[{"id":"c1","text":"doctor self-test","status":"verified","evidence":"doctor.ps1 dry run of receipt.py"}]}' | Set-Content $tmp
& $py.Source "$here\scripts\receipt.py" $tmp --dry-run | Out-Null
if ($LASTEXITCODE -eq 0) { Write-Output "OK scripts/receipt.py runs" } else { Write-Output "FAIL scripts/receipt.py dry run"; exit 1 }
Remove-Item $tmp
Write-Output "ready - invoke with /fact-check or 'check this before I send it'. (The optional send-gate hook is bash; see SETUP.md.)"
