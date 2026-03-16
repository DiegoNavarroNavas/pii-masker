#!/usr/bin/env bash
set -euo pipefail

OUTPUT_DIR="${1:-results/release/macos}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"
OUTPUT_ROOT="$REPO_ROOT/$OUTPUT_DIR"
DIST_DIR="$OUTPUT_ROOT/bin"
WORK_DIR="$OUTPUT_ROOT/build"
SPEC_DIR="$OUTPUT_ROOT/spec"

mkdir -p "$DIST_DIR" "$WORK_DIR" "$SPEC_DIR"

cd "$REPO_ROOT"
uv sync --group dev

if [[ -x "$REPO_ROOT/.venv/bin/python" ]]; then
  PYTHON_BIN="$REPO_ROOT/.venv/bin/python"
else
  echo "Missing venv python at .venv/bin/python"
  exit 1
fi

"$PYTHON_BIN" -m PyInstaller \
  --onefile \
  --name host \
  --distpath "$DIST_DIR" \
  --workpath "$WORK_DIR" \
  --specpath "$SPEC_DIR" \
  "$REPO_ROOT/native_host/host.py"

echo "Built host binary:"
echo "  $DIST_DIR/host"
