#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "Usage: $0 [auto|cpu|nvidia] [--python /path/to/python] [--dry-run]"
  echo "Default mode: auto"
}

MODE="auto"
DRY_RUN="false"
BASE_PYTHON_OVERRIDE=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    auto|cpu|nvidia)
      MODE="$1"
      ;;
    --dry-run)
      DRY_RUN="true"
      ;;
    --python)
      shift
      if [[ $# -eq 0 ]]; then
        echo "Missing value for --python"
        usage
        exit 1
      fi
      BASE_PYTHON_OVERRIDE="$1"
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown argument: $1"
      usage
      exit 1
      ;;
  esac
  shift
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

if [[ -f "$SCRIPT_DIR/../../../pii_masker.py" ]]; then
  REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
elif [[ -f "$SCRIPT_DIR/../pii_masker.py" ]]; then
  REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
else
  echo "Could not locate repo root containing pii_masker.py"
  echo "Run this script from the repository checkout."
  exit 1
fi

VENV_DIR="$REPO_ROOT/.venv"

if [[ -n "$BASE_PYTHON_OVERRIDE" ]]; then
  BASE_PYTHON="$BASE_PYTHON_OVERRIDE"
elif command -v python3 >/dev/null 2>&1; then
  BASE_PYTHON="python3"
elif [[ -x "/usr/bin/python3" ]]; then
  BASE_PYTHON="/usr/bin/python3"
elif command -v python >/dev/null 2>&1; then
  BASE_PYTHON="python"
else
  echo "Missing Python interpreter (python3/python)"
  exit 1
fi

has_nvidia() {
  if ! command -v nvidia-smi >/dev/null 2>&1; then
    return 1
  fi
  nvidia-smi -L >/dev/null 2>&1
}

if [[ "$MODE" == "auto" ]]; then
  if has_nvidia; then
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

echo "Runtime setup mode: $MODE (resolved: $RESOLVED_MODE)"
echo "Torch index: $TORCH_INDEX_URL"
echo "Virtual environment: $VENV_DIR"
echo "Base Python: $BASE_PYTHON"

if [[ "$DRY_RUN" == "true" ]]; then
  echo "Dry run enabled; no changes were made."
  exit 0
fi

rm -rf "$VENV_DIR"
"$BASE_PYTHON" -m venv --copies "$VENV_DIR"
PYTHON_BIN="$VENV_DIR/bin/python"

if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Missing venv python at $PYTHON_BIN"
  exit 1
fi

PYTHON_MM="$("$PYTHON_BIN" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')"

# Presidio 2.2.360+ currently declares Requires-Python < 3.14.
if [[ "$PYTHON_MM" == "3.14" ]] || [[ "$PYTHON_MM" =~ ^3\.1[5-9]$ ]]; then
  PRESIDIO_ANALYZER_SPEC="presidio-analyzer[stanza,transformers]==2.2.359"
  PRESIDIO_ANONYMIZER_SPEC="presidio-anonymizer==2.2.359"
else
  PRESIDIO_ANALYZER_SPEC="presidio-analyzer[stanza,transformers]>=2.2.361"
  PRESIDIO_ANONYMIZER_SPEC="presidio-anonymizer>=2.2.361"
fi

"$PYTHON_BIN" -m pip install --upgrade pip
"$PYTHON_BIN" -m pip install --index-url "$TORCH_INDEX_URL" torch
"$PYTHON_BIN" -m pip install \
  "$PRESIDIO_ANALYZER_SPEC" \
  "$PRESIDIO_ANONYMIZER_SPEC" \
  "pypdf>=6.0.0" \
  "reportlab>=4.4.4"

echo "Runtime dependencies installed for mode: $RESOLVED_MODE"
echo "Python version used: $PYTHON_MM"
echo "Run the app with:"
echo "  .venv/bin/python pii_masker.py --json-mode"
