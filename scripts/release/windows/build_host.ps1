param(
  [string]$OutputDir = "results\release\windows"
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..\..")
$outputRoot = Join-Path $repoRoot $OutputDir
$distDir = Join-Path $outputRoot "bin"
$workDir = Join-Path $outputRoot "build"
$specDir = Join-Path $outputRoot "spec"

New-Item -ItemType Directory -Path $distDir -Force | Out-Null
New-Item -ItemType Directory -Path $workDir -Force | Out-Null
New-Item -ItemType Directory -Path $specDir -Force | Out-Null

Push-Location $repoRoot
try {
  uv sync --group dev

  $venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
  if (-not (Test-Path $venvPython)) {
    throw "Missing venv python: $venvPython"
  }

  & $venvPython -m PyInstaller `
    --onefile `
    --name host `
    --distpath "$distDir" `
    --workpath "$workDir" `
    --specpath "$specDir" `
    "$repoRoot\native_host\host.py"
} finally {
  Pop-Location
}

Write-Host "Built host binary:"
Write-Host "  $(Join-Path $distDir 'host.exe')"
