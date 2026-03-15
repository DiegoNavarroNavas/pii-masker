param(
  [ValidateSet("en", "es", "fr", "de", "it", "pt", "zh", "ja", "ko")]
  [string]$Language = "en"
)

$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$venvPython = Join-Path $repoRoot ".venv\Scripts\python.exe"
$modelMap = @{
  en = "en_core_web_sm"
  es = "es_core_news_sm"
  fr = "fr_core_news_sm"
  de = "de_core_news_sm"
  it = "it_core_news_sm"
  pt = "pt_core_news_sm"
  zh = "zh_core_web_sm"
  ja = "ja_core_news_sm"
  ko = "ko_core_news_sm"
}

if (-not (Test-Path $venvPython)) {
  Write-Host "Creating/updating virtualenv dependencies via uv sync..."
  Push-Location $repoRoot
  try {
    uv sync
  } finally {
    Pop-Location
  }
}

if (-not (Test-Path $venvPython)) {
  throw "Missing venv python after sync: $venvPython"
}

$model = $modelMap[$Language]
if (-not $model) {
  throw "No spaCy model mapping for language: $Language"
}

Push-Location $repoRoot
try {
  Write-Host "Ensuring runtime dependencies are installed..."
  uv sync

  Write-Host "Installing spaCy model for extension runtime: $model"
  & $venvPython -m spacy download $model

  Write-Host "Running JSON mode smoke test..."
  '{"action":"anonymize","text":"test","language":"en","engine":"spacy","model":"en_core_web_sm","key_file":"secret.key"}' `
    | & $venvPython "pii_masker.py" --json-mode | Out-Host
} finally {
  Pop-Location
}

Write-Host "Preinstall complete."
