#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
PORTFOLIO_DIR="$REPO_ROOT/web-frontend"
STATIC_DIR="$REPO_ROOT/static"

echo "Building Vite frontend in $PORTFOLIO_DIR..."
(cd "$PORTFOLIO_DIR" && npm run build)

echo "Copying build output to $STATIC_DIR..."
mkdir -p "$STATIC_DIR"
rm -rf "$STATIC_DIR/assets"
cp -R "$PORTFOLIO_DIR/dist/"* "$STATIC_DIR/"

echo "Vite frontend built and deployed to static/ successfully!"
