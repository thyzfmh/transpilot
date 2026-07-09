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

skill_files="$(find "$ROOT/work/skills" -type f | sort)"
expected_skill="$ROOT/work/skills/flashdb-rust-autonomous/SKILL.md"
if [ "$skill_files" != "$expected_skill" ]; then
  fail "work/skills must contain exactly one named skill file: work/skills/flashdb-rust-autonomous/SKILL.md"$'\n'"actual:"$'\n'"$skill_files"
fi

instruction_text="$(cat "$ROOT/INSTRUCTION.md")"
assert_contains "$instruction_text" "work/skills/flashdb-rust-autonomous/SKILL.md"
if [[ "$instruction_text" == *"c-to-rust"* || "$instruction_text" == *"openspec"* || "$instruction_text" == *"superpowers"* ]]; then
  fail "INSTRUCTION.md must only ask OpenCode to load work/skills/flashdb-rust-autonomous/SKILL.md"
fi
if [[ "$instruction_text" == *"不加载其它 skill"* || "$instruction_text" == *"Do not load any other skill"* ]]; then
  fail "INSTRUCTION.md should not emphasize loading no other skills"
fi
if [ -f "$ROOT/work/skills/SKILL.md" ]; then
  fail "work/skills/SKILL.md must not exist; skills must live under work/skills/{skill-name}/SKILL.md"
fi
if [ -d "$ROOT/.agent" ] || [ -d "$ROOT/.agents" ]; then
  fail ".agent/.agents directory must not exist in the competition package"
fi
assert_contains "$instruction_text" "Skill 名称：flashdb-rust-autonomous"

FLASHDB="$TMP/code/FlashDB"
mkdir -p "$FLASHDB/src" "$FLASHDB/tests"

cat > "$FLASHDB/src/fdb_kvdb.c" <<'CEOF'
int fdb_kv_set_default(void) {
    return 0;
}
CEOF

cat > "$FLASHDB/src/fdb_kvdb.h" <<'HEOF'
#define FDB_NO_ERR 0
int fdb_kv_set_default(void);
HEOF

cat > "$FLASHDB/tests/fdb_kvdb_test.c" <<'TEOF'
int test_fdb_kv_set_default_returns_ok(void) {
    return 0;
}
TEOF

init_out="$("$CLI" competition flashdb init "$FLASHDB" "$TMP/flashdb_rust")"
assert_contains "$init_out" "FlashDB competition harness initialized"

test -f "$TMP/flashdb_rust/Cargo.toml" || fail "Cargo.toml missing"
test -f "$TMP/flashdb_rust/AGENTS.md" || fail "AGENTS.md missing"
test -x "$TMP/flashdb_rust/harness/analyze_flashdb.sh" || fail "analyze harness missing"
test -x "$TMP/flashdb_rust/harness/final_verify.sh" || fail "final verify harness missing"

analyze_out="$(cd "$TMP/flashdb_rust" && ./harness/analyze_flashdb.sh "$FLASHDB")"
assert_contains "$analyze_out" "source-inventory"
inventory="$(cat "$TMP/flashdb_rust/reports/source-inventory.md")"
assert_contains "$inventory" "fdb_kvdb.c"
assert_contains "$inventory" "Recommended First Slices"

plan_out="$(cd "$TMP/flashdb_rust" && ./harness/plan_next_task.sh task-001 "Translate KVDB result code" "$FLASHDB/src/fdb_kvdb.c,$FLASHDB/src/fdb_kvdb.h")"
assert_contains "$plan_out" "plans/task-001.md"
plan="$(cat "$TMP/flashdb_rust/plans/task-001.md")"
assert_contains "$plan" "Translate KVDB result code"
assert_contains "$plan" "Source Evidence"
assert_contains "$plan" "Verification Commands"

build_out="$(cd "$TMP/flashdb_rust" && ./harness/build_check.sh)"
assert_contains "$build_out" "cargo check"

test_out="$(cd "$TMP/flashdb_rust" && ./harness/test_all.sh)"
assert_contains "$test_out" "test result: ok"

unsafe_out="$(cd "$TMP/flashdb_rust" && ./harness/unsafe_audit.sh 10)"
assert_contains "$unsafe_out" "unsafe ratio"

final_out="$(cd "$TMP/flashdb_rust" && ./harness/final_verify.sh)"
assert_contains "$final_out" "Final verification passed"
test -f "$TMP/flashdb_rust/reports/final-report.md" || fail "final report missing"

echo "test_flashdb_competition.sh: PASS"
