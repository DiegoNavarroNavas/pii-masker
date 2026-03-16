param(
  [Parameter(Mandatory = $true)]
  [string]$ExtensionId,
  [Parameter(Mandatory = $true)]
  [string]$HostExePath,
  [string]$ManifestOutputPath = "$HOME\.pii-masker\native_host\com.pii_masker.host.json"
)

$ErrorActionPreference = "Stop"

$manifest = @{
  name = "com.pii_masker.host"
  description = "Local PII masker native host for Chrome extension"
  path = $HostExePath
  type = "stdio"
  allowed_origins = @("chrome-extension://$ExtensionId/")
}

if (-not (Test-Path $HostExePath)) {
  throw "Host executable not found: $HostExePath"
}

$resolvedHostExePath = (Resolve-Path $HostExePath).Path
$resolvedManifestPath = [System.IO.Path]::GetFullPath($ManifestOutputPath)

$manifest.path = $resolvedHostExePath

$manifestDir = Split-Path -Parent $resolvedManifestPath
if (-not (Test-Path $manifestDir)) {
  New-Item -ItemType Directory -Path $manifestDir -Force | Out-Null
}
$manifest | ConvertTo-Json -Depth 5 | Out-File -Encoding ASCII $resolvedManifestPath

$registryRoots = @(
  "HKCU:\Software\Google\Chrome\NativeMessagingHosts\com.pii_masker.host",
  "HKCU:\Software\WOW6432Node\Google\Chrome\NativeMessagingHosts\com.pii_masker.host",
  "HKCU:\Software\Microsoft\Edge\NativeMessagingHosts\com.pii_masker.host",
  "HKCU:\Software\WOW6432Node\Microsoft\Edge\NativeMessagingHosts\com.pii_masker.host",
  "HKCU:\Software\Chromium\NativeMessagingHosts\com.pii_masker.host"
)

foreach ($registryPath in $registryRoots) {
  New-Item -Path $registryPath -Force | Out-Null
  Set-ItemProperty -Path $registryPath -Name "(default)" -Value $resolvedManifestPath
}

Write-Host "Native host installed for current user."
Write-Host "Manifest: $resolvedManifestPath"
Write-Host "Host exe: $resolvedHostExePath"
