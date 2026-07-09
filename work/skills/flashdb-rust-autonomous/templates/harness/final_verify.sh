#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

require_nonempty_glob() {
  local label="$1"
  local pattern="$2"
  local matches=()
  while IFS= read -r file; do
    matches+=("$file")
  done < <(find . -path "$pattern" -type f 2>/dev/null | sort)
  if [ "${#matches[@]}" -eq 0 ]; then
    echo "[final_verify] FAIL: no $label files found" >&2
    exit 1
  fi
}

require_nonempty_glob "production Rust source" "./src/*.rs"
require_nonempty_glob "Rust test" "./tests/*.rs"

./harness/build_check.sh
./harness/test_all.sh
./harness/unsafe_audit.sh 10

python3 - <<'PY'
import pathlib
import sys

patterns = [
    "todo!(",
    "unimplemented!(",
    'panic!("TODO',
    "TODO: fake",
    "placeholder",
]

violations = []
for root in [pathlib.Path("src"), pathlib.Path("tests")]:
    if not root.exists():
        continue
    for path in sorted(root.rglob("*.rs")):
        text = path.read_text(errors="replace")
        lowered = text.lower()
        for pattern in patterns:
            haystack = lowered if pattern == "placeholder" else text
            needle = pattern.lower() if pattern == "placeholder" else pattern
            if needle in haystack:
                violations.append(f"{path}: contains {pattern}")

if violations:
    print("[final_verify] FAIL: placeholder audit failed", file=sys.stderr)
    for violation in violations:
        print(violation, file=sys.stderr)
    sys.exit(1)
PY

mkdir -p reports
{
  echo "# Final Verification Report"
  echo
  echo "- Status: PASSED"
  echo "- Command: ./harness/final_verify.sh"
  echo "- Timestamp: $(date -u +%Y-%m-%dT%H:%M:%SZ)"
} > reports/final-report.md

echo "Final verification passed"
