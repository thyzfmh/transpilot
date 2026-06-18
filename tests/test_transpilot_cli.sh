#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CLI="$ROOT/scripts/transpilot"

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

assert_contains() {
  local haystack="$1"
  local needle="$2"
  [[ "$haystack" == *"$needle"* ]] || fail "expected output to contain: $needle"$'\n'"actual:"$'\n'"$haystack"
}

TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

mkdir -p "$TMP/source-go"
cat > "$TMP/source-go/go.mod" <<'GOEOF'
module example.com/demo

go 1.22
GOEOF
cat > "$TMP/source-go/main.go" <<'GOEOF'
package main

func main() {}
GOEOF

init_out="$("$CLI" init "$TMP/source-go" "$TMP/target")"
assert_contains "$init_out" "Project initialized"
test -f "$TMP/target/acceptance-plan.yaml" || fail "acceptance-plan.yaml missing"
test -L "$TMP/target/scripts/transpilot" || fail "transpilot wrapper not linked into target"
test -L "$TMP/target/harness/run-autonomous.sh" || fail "harness not linked into target"

set +e
unconfirmed_run="$(cd "$TMP/target" && ./scripts/transpilot run --dry-run 2>&1)"
unconfirmed_code=$?
set -e
test "$unconfirmed_code" -ne 0 || fail "run should fail before acceptance confirmation"
assert_contains "$unconfirmed_run" "acceptance-plan.yaml is not confirmed"

review_out="$(cd "$TMP/target" && ./scripts/transpilot acceptance review)"
assert_contains "$review_out" "Acceptance Plan Review"
assert_contains "$review_out" "Review required"
assert_contains "$review_out" "Oracle: run-source"
assert_contains "$review_out" "Trust ceiling"
assert_contains "$review_out" "95-99%"

confirm_out="$(cd "$TMP/target" && ./scripts/transpilot acceptance confirm)"
assert_contains "$confirm_out" "Acceptance plan confirmed"
test -f "$TMP/target/.opencode/acceptance-confirmation.json" || fail "acceptance confirmation missing"

printf '\n# changed after confirmation\n' >> "$TMP/target/acceptance-plan.yaml"
set +e
changed_run="$(cd "$TMP/target" && ./scripts/transpilot run --dry-run 2>&1)"
changed_code=$?
set -e
test "$changed_code" -ne 0 || fail "run should fail after acceptance-plan.yaml changes"
assert_contains "$changed_run" "changed after confirmation"
confirm_out="$(cd "$TMP/target" && ./scripts/transpilot acceptance confirm)"
assert_contains "$confirm_out" "Acceptance plan confirmed"

status_out="$(cd "$TMP/target" && ./scripts/transpilot status)"
assert_contains "$status_out" "Progress"
assert_contains "$status_out" "Trust"
assert_contains "$status_out" "Next"

expert_out="$(cd "$TMP/target" && ./scripts/transpilot status --expert)"
assert_contains "$expert_out" "=== Transpilot Progress Report ==="

doctor_out="$(cd "$TMP/target" && ./scripts/transpilot doctor)"
assert_contains "$doctor_out" "Doctor"
assert_contains "$doctor_out" "OK"

check_out="$(cd "$TMP/target" && mkdir -p src tests && ./scripts/transpilot check)"
assert_contains "$check_out" "Check"
assert_contains "$check_out" "PASS"

analyze_out="$("$CLI" analyze "$TMP/source-go")"
assert_contains "$analyze_out" "Source language: go"
assert_contains "$analyze_out" "Target language: rust"
assert_contains "$analyze_out" "User sync"
assert_contains "$analyze_out" "Questions to ask before Wave 1"
assert_contains "$analyze_out" "OpenCode prompt"

scoped_analyze_out="$("$CLI" analyze "$TMP/source-go" --goal "translate message lifecycle" --scope "main.go,internal/msg")"
assert_contains "$scoped_analyze_out" "Goal: translate message lifecycle"
assert_contains "$scoped_analyze_out" "Requested scope:"
assert_contains "$scoped_analyze_out" "main.go"
assert_contains "$scoped_analyze_out" "internal/msg"

install_home="$TMP/home"
mkdir -p "$install_home"
install_out="$(HOME="$install_home" "$CLI" install)"
assert_contains "$install_out" "Installed transpilot"
test -L "$install_home/.local/bin/transpilot" || fail "transpilot install did not create symlink"
"$install_home/.local/bin/transpilot" help >/dev/null

plan_out="$(cd "$TMP/target" && ./scripts/transpilot plan new wave-1 --goal "translate message lifecycle" --scope "main.go,internal/msg")"
assert_contains "$plan_out" ".opencode/plans/wave-001.md"
test -f "$TMP/target/.opencode/plans/wave-001.md" || fail "wave plan was not created"
plan_text="$(cat "$TMP/target/.opencode/plans/wave-001.md")"
assert_contains "$plan_text" "Functional Requirements"
assert_contains "$plan_text" "Atomic Tasks"
assert_contains "$plan_text" "Test Matrix"
assert_contains "$plan_text" "Acceptance Criteria"
assert_contains "$plan_text" "Review Agent Gate"
assert_contains "$plan_text" "Goal for OpenCode"
assert_contains "$plan_text" "No shallow tests"
assert_contains "$plan_text" "translate message lifecycle"
assert_contains "$plan_text" "main.go"

plan_review_out="$(cd "$TMP/target" && ./scripts/transpilot plan review wave-1)"
assert_contains "$plan_review_out" "Wave Plan Review"
assert_contains "$plan_review_out" "Review agent"

run_out="$(cd "$TMP/target" && ./scripts/transpilot run --dry-run)"
assert_contains "$run_out" "Dry run"
assert_contains "$run_out" "OpenCode"
assert_contains "$run_out" "Goal for OpenCode"
assert_contains "$run_out" "Review agent"

echo "test_transpilot_cli.sh: PASS"
