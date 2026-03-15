param()

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$venvPy = Join-Path $repoRoot ".venv\Scripts\python.exe"
$pyInstaller = Join-Path $repoRoot ".venv\Scripts\pyinstaller.exe"
$outputExe = Join-Path $PSScriptRoot "host.exe"

if (-not (Test-Path $venvPy)) {
  throw "Missing venv python: $venvPy"
}
if (-not (Test-Path $pyInstaller)) {
  throw "Missing pyinstaller in venv: $pyInstaller"
}

Push-Location $repoRoot
try {
  & $pyInstaller `
    --onefile `
    --name host `
    --distpath "$PSScriptRoot" `
    --workpath "$PSScriptRoot\build" `
    --specpath "$PSScriptRoot" `
    "$PSScriptRoot\host.py"
} finally {
  Pop-Location
}

if (-not (Test-Path $outputExe)) {
  throw "Host exe was not created: $outputExe"
}

Write-Host "Built native host executable:"
Write-Host "  $outputExe"
