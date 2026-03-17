#!/usr/bin/env bash
set -euo pipefail

OUTPUT_DIR="${1:-results/release/linux}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
OUTPUT_ROOT="$REPO_ROOT/$OUTPUT_DIR"
DIST_DIR="$OUTPUT_ROOT/bin"
WORK_DIR="$OUTPUT_ROOT/build"
SPEC_DIR="$OUTPUT_ROOT/spec"
BUILD_VENV_DIR="$OUTPUT_ROOT/build-venv"

mkdir -p "$DIST_DIR" "$WORK_DIR" "$SPEC_DIR" "$BUILD_VENV_DIR"

cd "$REPO_ROOT"
# Build the native host in an isolated minimal venv.
# This avoids pulling runtime-heavy dependencies (for example CUDA wheels)
# that are not required to compile native_host/host.py.
if command -v python3 >/dev/null 2>&1; then
  BASE_PYTHON="python3"
elif command -v python >/dev/null 2>&1; then
  BASE_PYTHON="python"
else
  echo "Missing Python interpreter (python3/python)"
  exit 1
fi

"$BASE_PYTHON" -m venv "$BUILD_VENV_DIR"
PYTHON_BIN="$BUILD_VENV_DIR/bin/python"
if [[ ! -x "$PYTHON_BIN" ]]; then
  echo "Missing venv python at $PYTHON_BIN"
  exit 1
fi

"$PYTHON_BIN" -m pip install --upgrade pip
"$PYTHON_BIN" -m pip install pyinstaller

"$PYTHON_BIN" -m PyInstaller \
  --onefile \
  --name host \
  --distpath "$DIST_DIR" \
  --workpath "$WORK_DIR" \
  --specpath "$SPEC_DIR" \
  "$REPO_ROOT/native_host/host.py"

echo "Built host binary:"
echo "  $DIST_DIR/host"
