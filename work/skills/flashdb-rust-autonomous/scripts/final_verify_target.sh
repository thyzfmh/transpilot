#!/usr/bin/env bash
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
REPO_ROOT="$(cd "$SKILL_DIR/../../.." && pwd)"
TARGET="$REPO_ROOT/code/flashDB_rust"

python3 "$SKILL_DIR/templates/harness/source_guard.py" --target "$TARGET"
python3 "$TARGET/harness/trace_capture.py" export --target "$TARGET"
(
  cd "$TARGET"
  ./harness/final_verify.sh
)
python3 "$SKILL_DIR/templates/harness/source_guard.py" --target "$TARGET"

echo "TRUSTED_FINAL_VERIFY_PASS"
