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
python3 ./harness/c_coverage_check.py
./harness/unsafe_audit.sh 10

python3 - <<'PY'
import pathlib
import re
import sys

patterns = [
    "todo!(",
    "unimplemented!(",
    'panic!("TODO',
    "TODO: fake",
    "placeholder",
]

violations = []

def strip_comments(text):
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    text = re.sub(r"(?m)//.*$", "", text)
    return text

for root in [pathlib.Path("src"), pathlib.Path("tests")]:
    if not root.exists():
        continue
    for path in sorted(root.rglob("*.rs")):
        text = strip_comments(path.read_text(errors="replace"))
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

prod_violations = []
for path in sorted(pathlib.Path("src").rglob("*.rs")):
    text = strip_comments(path.read_text(errors="replace"))
    for pattern in ["unwrap(", "expect("]:
        if pattern in text:
            prod_violations.append(f"{path}: contains {pattern}")

if prod_violations:
    print("[final_verify] FAIL: production unwrap/expect audit failed", file=sys.stderr)
    for violation in prod_violations:
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
