#!/usr/bin/env bash
set -euo pipefail
export PYTHONDONTWRITEBYTECODE=1

SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
REPO_ROOT="$(cd "$SKILL_DIR/../../.." && pwd)"
TARGET="$REPO_ROOT/code/flashDB_rust"

"$SKILL_DIR/scripts/install_target_harness.sh" "$TARGET"
python3 "$SKILL_DIR/templates/harness/source_guard.py" --target "$TARGET"
(
  cd "$TARGET"
  ./harness/final_verify.sh
  python3 ./harness/completion.py stage
)
python3 "$TARGET/harness/trace_capture.py" export --target "$TARGET"
python3 "$TARGET/harness/trace_capture.py" verify --target "$TARGET"
(
  cd "$TARGET"
  python3 ./harness/completion.py finalize
  python3 ./harness/trace_capture.py refresh-result --target "$TARGET"
  python3 ./harness/trace_capture.py verify --target "$TARGET"
  python3 ./harness/completion.py verify --require-trace
)
python3 "$SKILL_DIR/templates/harness/source_guard.py" --target "$TARGET"

echo "TRUSTED_FINAL_VERIFY_PASS"
