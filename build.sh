#!/bin/bash
set -e

echo "Building pii-masker executable..."
uv run pyinstaller pii_masker.spec --clean

echo "Build complete: dist/pii-masker"
ls -lh dist/pii-masker
