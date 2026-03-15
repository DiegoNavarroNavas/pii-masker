param(
  [Parameter(Mandatory = $true)]
  [string]$ExtensionId,
  [switch]$BuildExe,
  [switch]$PreinstallRuntime,
  [ValidateSet("en", "es", "fr", "de", "it", "pt", "zh", "ja", "ko")]
  [string]$Language = "en"
)

$ErrorActionPreference = "Stop"

$manifestTemplate = Join-Path $PSScriptRoot "com.pii_masker.host.json"
$manifestOut = Join-Path $PSScriptRoot "com.pii_masker.host.installed.json"

if (-not (Test-Path $manifestTemplate)) {
  throw "Manifest template not found: $manifestTemplate"
}

$manifest = Get-Content $manifestTemplate -Raw | ConvertFrom-Json
$manifest.allowed_origins = @("chrome-extension://$ExtensionId/")

$hostExe = Join-Path $PSScriptRoot "host.exe"
$buildScript = Join-Path $PSScriptRoot "build_host_exe.ps1"
$preinstallScript = Join-Path $PSScriptRoot "preinstall_extension_runtime.ps1"

if ($PreinstallRuntime -and (Test-Path $preinstallScript)) {
  & $preinstallScript -Language $Language
}

if ($BuildExe -and (Test-Path $buildScript)) {
  & $buildScript
}

if (-not (Test-Path $hostExe)) {
  throw "host.exe not found: $hostExe. Build it first (for example with -BuildExe)."
}
$manifest.path = $hostExe

$manifest | ConvertTo-Json -Depth 6 | Out-File -Encoding ASCII $manifestOut

$registryRoots = @(
  "HKCU:\Software\Google\Chrome\NativeMessagingHosts\com.pii_masker.host",
  "HKCU:\Software\WOW6432Node\Google\Chrome\NativeMessagingHosts\com.pii_masker.host",
  "HKCU:\Software\Microsoft\Edge\NativeMessagingHosts\com.pii_masker.host",
  "HKCU:\Software\WOW6432Node\Microsoft\Edge\NativeMessagingHosts\com.pii_masker.host",
  "HKCU:\Software\Chromium\NativeMessagingHosts\com.pii_masker.host",
  "HKCU:\Software\BraveSoftware\Brave-Browser\NativeMessagingHosts\com.pii_masker.host",
  "HKCU:\Software\Vivaldi\NativeMessagingHosts\com.pii_masker.host",
  "HKCU:\Software\Opera Software\NativeMessagingHosts\com.pii_masker.host"
)

foreach ($registryPath in $registryRoots) {
  New-Item -Path $registryPath -Force | Out-Null
  Set-ItemProperty -Path $registryPath -Name "(default)" -Value $manifestOut
}

$machineWideRoots = @(
  "HKLM:\Software\Google\Chrome\NativeMessagingHosts\com.pii_masker.host",
  "HKLM:\Software\WOW6432Node\Google\Chrome\NativeMessagingHosts\com.pii_masker.host",
  "HKLM:\Software\Microsoft\Edge\NativeMessagingHosts\com.pii_masker.host",
  "HKLM:\Software\WOW6432Node\Microsoft\Edge\NativeMessagingHosts\com.pii_masker.host"
)

foreach ($registryPath in $machineWideRoots) {
  try {
    New-Item -Path $registryPath -Force | Out-Null
    Set-ItemProperty -Path $registryPath -Name "(default)" -Value $manifestOut
  } catch {
    Write-Host "WARNING: Could not write $registryPath (run as admin to enable machine-wide key)"
  }
}

Write-Host "Installed native host manifest:"
Write-Host "  $manifestOut"
Write-Host "Host executable path:"
Write-Host "  $($manifest.path)"
Write-Host "Registry keys:"
foreach ($registryPath in $registryRoots) {
  Write-Host "  $registryPath"
}
Write-Host "Machine-wide keys attempted:"
foreach ($registryPath in $machineWideRoots) {
  Write-Host "  $registryPath"
}
