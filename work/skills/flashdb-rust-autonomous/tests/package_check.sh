#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

assert_contains() {
  local haystack="$1"
  local needle="$2"
  [[ "$haystack" == *"$needle"* ]] || fail "expected text to contain: $needle"
}

expected_skill_dir="$ROOT/work/skills/flashdb-rust-autonomous"
skill_dirs="$(find "$ROOT/work/skills" -mindepth 1 -maxdepth 1 -type d | sort)"
if [ "$skill_dirs" != "$expected_skill_dir" ]; then
  fail "work/skills must contain only flashdb-rust-autonomous"$'\n'"actual:"$'\n'"$skill_dirs"
fi

skill_files="$(find "$ROOT/work/skills" -name SKILL.md -type f | sort)"
expected_skill_file="$expected_skill_dir/SKILL.md"
if [ "$skill_files" != "$expected_skill_file" ]; then
  fail "expected only one SKILL.md at work/skills/flashdb-rust-autonomous/SKILL.md"
fi

for dir in "$ROOT/.agent" "$ROOT/.agents" "$ROOT/config" "$ROOT/templates" "$ROOT/scripts" "$ROOT/tests" "$ROOT/harness"; do
  [ ! -e "$dir" ] || fail "root package should not contain $(basename "$dir")"
done

instruction_text="$(cat "$ROOT/INSTRUCTION.md")"
assert_contains "$instruction_text" "work/skills/flashdb-rust-autonomous/SKILL.md"
assert_contains "$instruction_text" "Skill 名称：flashdb-rust-autonomous"

if [[ "$instruction_text" == *"c-to-rust"* || "$instruction_text" == *"openspec"* || "$instruction_text" == *"superpowers"* ]]; then
  fail "INSTRUCTION.md must point directly to flashdb-rust-autonomous"
fi
if [[ "$instruction_text" == *"不加载其它 skill"* || "$instruction_text" == *"Do not load any other skill"* ]]; then
  fail "INSTRUCTION.md should not emphasize loading no other skills"
fi

skill_text="$(cat "$expected_skill_file")"
assert_contains "$skill_text" "C-to-Rust tactics for FlashDB"
assert_contains "$skill_text" "FlashBackend"
assert_contains "$skill_text" "final_verify.sh"
assert_contains "$skill_text" "result/output.md"

echo "package_check.sh: PASS"
