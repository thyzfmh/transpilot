#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

python3 ./harness/preflight.py
python3 ./harness/config_profile_check.py
echo "PREFLIGHT_PASS"
