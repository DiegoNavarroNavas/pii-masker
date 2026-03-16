#!/usr/bin/env bash
set -euo pipefail

INPUT_DIR="${1:-results/release/linux}"
OUTPUT_FILE="${2:-results/release/pii-masker-native-host-linux.tar.gz}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"

INPUT_ROOT="$REPO_ROOT/$INPUT_DIR"
OUTPUT_PATH="$REPO_ROOT/$OUTPUT_FILE"

if [[ ! -d "$INPUT_ROOT" ]]; then
  echo "Input directory does not exist: $INPUT_ROOT"
  exit 1
fi

mkdir -p "$(dirname "$OUTPUT_PATH")"

# Bundle install helpers with portable package.
mkdir -p "$INPUT_ROOT/helpers"
cp "$REPO_ROOT/scripts/release/linux/install_native_host.sh" "$INPUT_ROOT/helpers/"
cp "$REPO_ROOT/scripts/release/linux/generate_key.sh" "$INPUT_ROOT/helpers/"

tar -C "$INPUT_ROOT" -czf "$OUTPUT_PATH" .

echo "Created portable package:"
echo "  $OUTPUT_PATH"
