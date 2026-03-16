#!/usr/bin/env bash
set -euo pipefail

KEY_PATH="${1:-$HOME/.pii-masker/secret.key}"
KEY_DIR="$(dirname "$KEY_PATH")"
mkdir -p "$KEY_DIR"

KEY="$(head -c 24 /dev/urandom | base64 | tr '+/' '-_' | tr -d '=\n')"
printf "%s" "$KEY" > "$KEY_PATH"
chmod 600 "$KEY_PATH"

echo "Generated key file:"
echo "  $KEY_PATH"
