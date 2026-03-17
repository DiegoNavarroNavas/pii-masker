param(
  [string]$ExtensionId,
  [switch]$BuildExe,
  [switch]$PreinstallRuntime,
  [ValidateSet("en", "es", "fr", "de", "it", "pt", "zh", "ja", "ko")]
  [string]$Language = "en"
)

$ErrorActionPreference = "Stop"

$manifestTemplate = Join-Path $PSScriptRoot "com.pii_masker.host.json"
$manifestOut = Join-Path $PSScriptRoot "com.pii_masker.host.installed.json"
$extensionIdPattern = '^chrome-extension://([a-p]{32})/$'

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

function Get-ExtensionIdFromManifestPath {
  param([string]$Path)

  if (-not $Path -or -not (Test-Path $Path)) {
    return $null
  }
  try {
    $content = Get-Content $Path -Raw | ConvertFrom-Json
    if ($null -eq $content.allowed_origins -or $content.allowed_origins.Count -eq 0) {
      return $null
    }
    foreach ($origin in $content.allowed_origins) {
      $originText = [string]$origin
      if ($originText -match $extensionIdPattern) {
        return $Matches[1]
      }
    }
    return $null
  } catch {
    return $null
  }
}

function Resolve-ExtensionId {
  param([string]$Candidate)

  if ($Candidate) {
    return $Candidate.Trim()
  }

  $fromLocalManifest = Get-ExtensionIdFromManifestPath -Path $manifestOut
  if ($fromLocalManifest) {
    Write-Host "Reusing extension ID from existing manifest: $fromLocalManifest"
    return $fromLocalManifest
  }

  foreach ($registryPath in $registryRoots) {
    try {
      $value = (Get-ItemProperty -Path $registryPath -Name "(default)" -ErrorAction Stop)."(default)"
      $fromRegistryManifest = Get-ExtensionIdFromManifestPath -Path $value
      if ($fromRegistryManifest) {
        Write-Host "Reusing extension ID from registry manifest: $fromRegistryManifest"
        return $fromRegistryManifest
      }
    } catch {
      continue
    }
  }

  throw "Could not infer extension ID from existing installation. Pass -ExtensionId <id> once; future reinstalls will reuse it."
}

if (-not (Test-Path $manifestTemplate)) {
  throw "Manifest template not found: $manifestTemplate"
}

$ExtensionId = Resolve-ExtensionId -Candidate $ExtensionId
$ExtensionId = $ExtensionId.ToLowerInvariant()
if ($ExtensionId -notmatch '^[a-p]{32}$') {
  throw "ExtensionId must be a 32-char Chrome extension id (a-p). Got: $ExtensionId"
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
Write-Host "Allowed extension origin:"
Write-Host "  chrome-extension://$ExtensionId/"
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
