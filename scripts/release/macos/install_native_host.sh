#!/usr/bin/env bash
set -euo pipefail

if [[ $# -lt 2 ]]; then
  echo "Usage: $0 <host_binary_path> <extension_id> [browser]"
  echo "browser: chrome|edge|chromium (default: chrome)"
  exit 1
fi

HOST_BINARY_PATH="$1"
EXTENSION_ID="$2"
BROWSER="${3:-chrome}"
HOST_NAME="com.pii_masker.host"

if [[ ! -f "$HOST_BINARY_PATH" ]]; then
  echo "Host binary not found: $HOST_BINARY_PATH"
  exit 1
fi
HOST_BINARY_PATH="$(cd "$(dirname "$HOST_BINARY_PATH")" && pwd)/$(basename "$HOST_BINARY_PATH")"
chmod +x "$HOST_BINARY_PATH"

case "$BROWSER" in
  chrome)
    MANIFEST_DIR="$HOME/Library/Application Support/Google/Chrome/NativeMessagingHosts"
    ;;
  edge)
    MANIFEST_DIR="$HOME/Library/Application Support/Microsoft Edge/NativeMessagingHosts"
    ;;
  chromium)
    MANIFEST_DIR="$HOME/Library/Application Support/Chromium/NativeMessagingHosts"
    ;;
  *)
    echo "Unsupported browser: $BROWSER"
    exit 1
    ;;
esac

mkdir -p "$MANIFEST_DIR"
MANIFEST_PATH="$MANIFEST_DIR/$HOST_NAME.json"

cat > "$MANIFEST_PATH" <<EOF
{
  "name": "$HOST_NAME",
  "description": "Local PII masker native host for Chrome extension",
  "path": "$HOST_BINARY_PATH",
  "type": "stdio",
  "allowed_origins": [
    "chrome-extension://$EXTENSION_ID/"
  ]
}
EOF

echo "Installed native host manifest at: $MANIFEST_PATH"
