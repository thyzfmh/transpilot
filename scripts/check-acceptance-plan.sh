#!/usr/bin/env bash
# check-acceptance-plan.sh — review and lock T0 acceptance plan.
# Usage:
#   ./scripts/check-acceptance-plan.sh review
#   ./scripts/check-acceptance-plan.sh confirm
#   ./scripts/check-acceptance-plan.sh verify

set -euo pipefail

COMMAND="${1:-review}"
PLAN_FILE="acceptance-plan.yaml"
CONFIRM_FILE=".opencode/acceptance-confirmation.json"

hash_file() {
  if command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "$1" | awk '{print $1}'
  elif command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  else
    echo "ERROR: shasum or sha256sum is required" >&2
    exit 2
  fi
}

require_plan() {
  if [ ! -f "$PLAN_FILE" ]; then
    echo "ERROR: $PLAN_FILE not found. Run transpilot init first." >&2
    exit 2
  fi
}

review_plan() {
  require_plan

  local warnings=0
  local oracle="unknown"
  local ceiling="unknown"
  oracle="$(awk -F: '/oracle_primary:/ {sub(/#.*/, "", $2); gsub(/[[:space:]]/, "", $2); print $2; exit}' "$PLAN_FILE")"
  case "$oracle" in
    run-source) ceiling="95-99%" ;;
    record-replay) ceiling="90-95%" ;;
    dual-ai) ceiling="75-85%" ;;
    static-codegraph) ceiling="60-75%" ;;
  esac

  echo "=== Acceptance Plan Review ==="
  echo "Plan: $PLAN_FILE"
  echo "Oracle: $oracle"
  echo "Trust ceiling: $ceiling"
  echo ""

  if grep -q '<[^>][^>]*>' "$PLAN_FILE"; then
    echo "Review required: template placeholders remain."
    warnings=$((warnings + 1))
  fi
  if grep -q 'source_runnable: false' "$PLAN_FILE"; then
    echo "Review required: source project marked not runnable; behavior verification will be weaker."
    warnings=$((warnings + 1))
  fi
  if grep -Eq 'oracle_primary:[[:space:]]*(static-codegraph|dual-ai)' "$PLAN_FILE"; then
    echo "Review required: oracle mode has a lower trust ceiling than run-source."
    warnings=$((warnings + 1))
  fi
  if awk -F: '/source_test_coverage_pct:/ {gsub(/[[:space:]]/, "", $2); if ($2 + 0 < 30) exit 0; exit 1}' "$PLAN_FILE"; then
    echo "Review required: source test coverage is low; behavior confidence may be limited."
    warnings=$((warnings + 1))
  fi
  if ! grep -Eq '^e2e_command:[[:space:]]*".+"' "$PLAN_FILE"; then
    echo "Review required: e2e_command is missing or empty."
    warnings=$((warnings + 1))
  fi
  if ! grep -q 'must_pass: true' "$PLAN_FILE"; then
    echo "Review required: no must_pass acceptance case found."
    warnings=$((warnings + 1))
  fi

  echo ""
  echo "Before Wave 1, confirm these are true:"
  echo "1. scope.in / scope.out match the intended migration boundary."
  echo "2. oracle_primary is realistic for this source project."
  echo "3. e2e_command is non-interactive and has reliable exit codes."
  echo "4. must_pass cases cover the minimum viable behavior."
  echo "5. The target confidence does not exceed the Oracle's evidence ceiling."
  echo ""

  if [ "$warnings" -gt 0 ]; then
    echo "Review required: $warnings item(s) need human attention before confirmation."
  else
    echo "Review required: no obvious template risks found, but human confirmation is still mandatory."
  fi
}

confirm_plan() {
  require_plan
  mkdir -p .opencode

  local hash
  hash="$(hash_file "$PLAN_FILE")"
  python3 - "$hash" "$PLAN_FILE" > "$CONFIRM_FILE" <<'PYEOF'
import json
import os
import sys
from datetime import datetime, timezone

plan_hash, plan_file = sys.argv[1], sys.argv[2]
data = {
    "plan_file": plan_file,
    "sha256": plan_hash,
    "confirmed_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
    "confirmed_by": os.environ.get("USER", "unknown"),
}
json.dump(data, sys.stdout, indent=2)
sys.stdout.write("\n")
PYEOF
  echo "Acceptance plan confirmed."
  echo "Lock: $CONFIRM_FILE"
  echo "Hash: $hash"
}

verify_plan() {
  require_plan
  if [ ! -f "$CONFIRM_FILE" ]; then
    echo "ERROR: acceptance-plan.yaml is not confirmed." >&2
    echo "Run: ./scripts/transpilot acceptance review" >&2
    echo "Then: ./scripts/transpilot acceptance confirm" >&2
    exit 1
  fi

  local current expected
  current="$(hash_file "$PLAN_FILE")"
  expected="$(python3 - "$CONFIRM_FILE" <<'PYEOF'
import json
import sys
with open(sys.argv[1]) as f:
    print(json.load(f).get("sha256", ""))
PYEOF
)"

  if [ "$current" != "$expected" ]; then
    echo "ERROR: acceptance-plan.yaml changed after confirmation." >&2
    echo "Run: ./scripts/transpilot acceptance review" >&2
    echo "Then: ./scripts/transpilot acceptance confirm" >&2
    exit 1
  fi

  echo "Acceptance plan confirmed and unchanged."
}

case "$COMMAND" in
  review) review_plan ;;
  confirm) confirm_plan ;;
  verify|verify-confirmed) verify_plan ;;
  *)
    echo "Usage: $0 [review|confirm|verify]" >&2
    exit 2
    ;;
esac
