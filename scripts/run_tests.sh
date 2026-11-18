#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$REPO_ROOT"

export PYTHONPATH=".:${PYTHONPATH:-}"
PYTHON_BIN="$REPO_ROOT/.venv/bin/python"
PYTEST_BIN="$REPO_ROOT/.venv/bin/pytest"

echo "=================================================="
echo "1. Running Pytest Unit Tests..."
echo "=================================================="
"$PYTEST_BIN" -v

echo ""
echo "=================================================="
echo "2. Running Verification Scripts..."
echo "=================================================="

echo -e "\n[Identity Verification]"
"$PYTHON_BIN" tests/verify_identity.py

echo -e "\n[Metrics Backend Verification]"
"$PYTHON_BIN" tests/verify_metrics.py

echo -e "\n[Ramachandran Verification]"
"$PYTHON_BIN" tests/verify_ramachandran.py

echo ""
echo "=================================================="
echo "Verification Run Complete!"
echo "=================================================="
