param(
  [string]$InputDir = "results\release\windows",
  [string]$OutputZip = "results\release\pii-masker-native-host-windows.zip"
)

$ErrorActionPreference = "Stop"

$repoRoot = Resolve-Path (Join-Path $PSScriptRoot "..\..\..")
$inputRoot = Join-Path $repoRoot $InputDir
$outputPath = Join-Path $repoRoot $OutputZip
$outputParent = Split-Path -Parent $outputPath

if (-not (Test-Path $inputRoot)) {
  throw "Input directory does not exist: $inputRoot"
}
if (-not (Test-Path $outputParent)) {
  New-Item -ItemType Directory -Path $outputParent -Force | Out-Null
}

if (Test-Path $outputPath) {
  Remove-Item -Path $outputPath -Force
}

# Bundle install helpers with portable package.
$helperDir = Join-Path $inputRoot "helpers"
New-Item -ItemType Directory -Path $helperDir -Force | Out-Null
Copy-Item -Path (Join-Path $repoRoot "scripts\release\windows\install_native_host.ps1") -Destination $helperDir -Force
Copy-Item -Path (Join-Path $repoRoot "scripts\release\windows\generate_key.ps1") -Destination $helperDir -Force

Compress-Archive -Path "$inputRoot\*" -DestinationPath $outputPath

Write-Host "Created portable package:"
Write-Host "  $outputPath"
