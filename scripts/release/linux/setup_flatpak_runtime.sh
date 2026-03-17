#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: $0 [chrome|chromium|brave] [auto|cpu|nvidia]"
  echo "Defaults: browser=chrome mode=auto"
}

BROWSER="${1:-chrome}"
MODE="${2:-auto}"

if [[ "$BROWSER" == "-h" || "$BROWSER" == "--help" ]]; then
  usage
  exit 0
fi

case "$BROWSER" in
  chrome)
    APP_ID="com.google.Chrome"
    ;;
  chromium)
    APP_ID="org.chromium.Chromium"
    ;;
  brave)
    APP_ID="com.brave.Browser"
    ;;
  *)
    echo "Unsupported browser: $BROWSER"
    usage
    exit 1
    ;;
esac

case "$MODE" in
  auto|cpu|nvidia)
    ;;
  *)
    echo "Unsupported mode: $MODE"
    usage
    exit 1
    ;;
esac

if ! flatpak info "$APP_ID" >/dev/null 2>&1; then
  echo "Flatpak app not installed: $APP_ID"
  exit 1
fi

if [[ "$MODE" == "auto" ]]; then
  if command -v nvidia-smi >/dev/null 2>&1 && nvidia-smi -L >/dev/null 2>&1; then
    RESOLVED_MODE="nvidia"
  else
    RESOLVED_MODE="cpu"
  fi
else
  RESOLVED_MODE="$MODE"
fi

if [[ "$RESOLVED_MODE" == "nvidia" ]]; then
  TORCH_INDEX_URL="https://download.pytorch.org/whl/cu128"
else
  TORCH_INDEX_URL="https://download.pytorch.org/whl/cpu"
fi

echo "Flatpak app: $APP_ID"
echo "Runtime mode: $MODE (resolved: $RESOLVED_MODE)"
echo "Torch index: $TORCH_INDEX_URL"

flatpak run --command=python3 "$APP_ID" -m ensurepip --upgrade

PY_MM="$(
  flatpak run --command=python3 "$APP_ID" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")'
)"
if [[ "$PY_MM" == "3.14" ]] || [[ "$PY_MM" =~ ^3\.1[5-9]$ ]]; then
  PRESIDIO_ANALYZER_SPEC="presidio-analyzer[stanza,transformers]==2.2.359"
  PRESIDIO_ANONYMIZER_SPEC="presidio-anonymizer==2.2.359"
else
  PRESIDIO_ANALYZER_SPEC="presidio-analyzer[stanza,transformers]>=2.2.361"
  PRESIDIO_ANONYMIZER_SPEC="presidio-anonymizer>=2.2.361"
fi

flatpak run --command=python3 "$APP_ID" -m pip install --user --index-url "$TORCH_INDEX_URL" torch
flatpak run --command=python3 "$APP_ID" -m pip install --user \
  "$PRESIDIO_ANALYZER_SPEC" \
  "$PRESIDIO_ANONYMIZER_SPEC" \
  "pypdf>=6.0.0" \
  "reportlab>=4.4.4"

echo "Flatpak runtime dependencies installed."
echo "Python version in Flatpak: $PY_MM"
