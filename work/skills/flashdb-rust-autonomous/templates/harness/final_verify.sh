#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

require_files() {
  local label="$1"
  local directory="$2"
  if [ ! -d "$directory" ] || [ -z "$(find "$directory" -name '*.rs' -type f -size +0c -print -quit)" ]; then
    echo "[final_verify] FAIL: no non-empty $label files found" >&2
    exit 1
  fi
}

require_files "production Rust source" src
require_files "Rust test" tests

python3 ./harness/source_guard.py --target "$ROOT"
./harness/preflight.sh
python3 ./harness/project_discovery.py --target "$ROOT"
python3 ./harness/checkpoint.py init
python3 ./harness/final_gate_runner.py

python3 ./harness/checkpoint.py seal-final
python3 ./harness/final_report.py
python3 ./harness/source_guard.py --target "$ROOT"

echo "FINAL_VERIFY_PASS"
