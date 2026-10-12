#!/usr/bin/env bash
# Builds terraform/build/license_signing/ -- handler.py plus a vendored,
# Lambda-runtime-compatible build of `cryptography` (a compiled dependency,
# unlike every other Lambda here, which only needs boto3, already bundled
# in the runtime). Run this before `terraform apply` whenever
# src/license_signing/handler.py or its dependencies change; the
# archive_file data source in license_signing.tf just zips whatever's
# already on disk at plan time, so there's no automatic rebuild trigger.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
BUILD_DIR="$SCRIPT_DIR/build/license_signing"

rm -rf "$BUILD_DIR"
mkdir -p "$BUILD_DIR"

cp "$PROJECT_ROOT/src/license_signing/handler.py" "$BUILD_DIR/handler.py"

python3 -m pip install \
  --platform manylinux2014_x86_64 \
  --implementation cp \
  --python-version 3.12 \
  --only-binary=:all: \
  --target "$BUILD_DIR" \
  cryptography

find "$BUILD_DIR" -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$BUILD_DIR" -name "*.dist-info" -exec rm -rf {} + 2>/dev/null || true

echo "Built $BUILD_DIR"
