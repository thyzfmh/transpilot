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
./harness/build_check.sh
./harness/test_all.sh
./harness/c_link_test.sh
./harness/c_interop_test.sh
python3 ./harness/c_coverage_check.py
python3 ./harness/api_surface_check.py
python3 ./harness/trace_capture.py verify --target "$ROOT"
python3 ./harness/translation_spec_check.py
python3 ./harness/checkpoint.py verify-final
python3 ./harness/rust_policy_check.py
python3 ./harness/source_guard.py --target "$ROOT"

mkdir -p reports
{
  echo "# Final Verification Report"
  echo
  echo "- Status: PASSED"
  echo "- Command: ./harness/final_verify.sh"
  echo "- Configuration: POSIX file mode, KVDB+TSDB, FDB_WRITE_GRAN=1, 32-bit timestamp"
  echo "- Rust static library: target/release/libflashdb_rust.a"
  echo "- C linked tests: PASSED"
  echo "- C/Rust bidirectional persistence: PASSED"
  echo "- Public C API surface: PASSED"
  echo "- C-to-Rust specification: PASSED"
  echo "- Rust safety policy: PASSED"
  echo "- Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
} > reports/final-report.md

echo "FINAL_VERIFY_PASS"
