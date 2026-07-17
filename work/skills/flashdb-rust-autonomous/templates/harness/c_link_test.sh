#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

python3 "$ROOT/harness/native_test_runner.py"
echo "C_LINK_TEST_PASS"
