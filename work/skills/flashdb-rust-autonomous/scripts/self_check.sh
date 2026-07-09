#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"

"$ROOT/work/skills/flashdb-rust-autonomous/tests/package_check.sh"
bash -n "$ROOT/work/skills/flashdb-rust-autonomous/scripts/self_check.sh"

VALIDATOR="/Users/tanghui/.codex/skills/.system/skill-creator/scripts/quick_validate.py"
if [ -f "$VALIDATOR" ]; then
  python3 "$VALIDATOR" "$ROOT/work/skills/flashdb-rust-autonomous"
else
  echo "WARN: skill validator not found at $VALIDATOR"
fi

if [ -f "$ROOT/code/FlashDB/tests/Makefile" ]; then
  make -C "$ROOT/code/FlashDB/tests" test
else
  echo "WARN: code/FlashDB/tests/Makefile not found; skipping C source tests"
fi

echo "self_check.sh: PASS"
