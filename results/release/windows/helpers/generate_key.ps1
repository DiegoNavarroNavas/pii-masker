param(
  [string]$KeyPath = "$HOME\.pii-masker\secret.key"
)

$ErrorActionPreference = "Stop"

$keyDir = Split-Path -Parent $KeyPath
if (-not (Test-Path $keyDir)) {
  New-Item -ItemType Directory -Path $keyDir -Force | Out-Null
}

$bytes = New-Object byte[] 24
[System.Security.Cryptography.RandomNumberGenerator]::Fill($bytes)
$key = [Convert]::ToBase64String($bytes).TrimEnd('=').Replace('+', '-').Replace('/', '_')

Set-Content -Path $KeyPath -Value $key -Encoding ASCII -NoNewline

Write-Host "Generated key file:"
Write-Host "  $KeyPath"
