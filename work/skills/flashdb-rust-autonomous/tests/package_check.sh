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

for dir in "$ROOT/.agent" "$ROOT/.agents" "$ROOT/config" "$ROOT/templates" "$ROOT/scripts" "$ROOT/tests" "$ROOT/harness" "$ROOT/examples"; do
  [ ! -e "$dir" ] || fail "root package should not contain $(basename "$dir")"
done

instruction_text="$(cat "$ROOT/INSTRUCTION.md")"
assert_contains "$instruction_text" "# 执行入口"
assert_contains "$instruction_text" "work/skills/flashdb-rust-autonomous/SKILL.md"
assert_contains "$instruction_text" "Skill 名称：flashdb-rust-autonomous"
assert_contains "$instruction_text" '源项目固定为 `code/FlashDB`'
assert_contains "$instruction_text" 'Rust 目标固定为 `code/flashDB_rust`'
assert_contains "$instruction_text" "不询问用户，不中断执行"
assert_contains "$instruction_text" "失败就按 Skill 内的循环修复并重新验证"
assert_contains "$instruction_text" 'code/flashDB_rust/harness/final_verify.sh'
assert_contains "$instruction_text" 'result/output.md'

if [[ "$instruction_text" == *"c-to-rust"* || "$instruction_text" == *"openspec"* || "$instruction_text" == *"superpowers"* ]]; then
  fail "INSTRUCTION.md must point directly to flashdb-rust-autonomous"
fi
if [[ "$instruction_text" == *"不加载其它 skill"* || "$instruction_text" == *"Do not load any other skill"* ]]; then
  fail "INSTRUCTION.md should not emphasize loading no other skills"
fi
if [[ "$instruction_text" == *"评分规则"* || "$instruction_text" == *"比赛"* ]]; then
  fail "INSTRUCTION.md must not include scoring or competition prose"
fi

skill_text="$(cat "$expected_skill_file")"
assert_contains "$skill_text" "C-to-Rust tactics for FlashDB"
assert_contains "$skill_text" "FlashBackend"
assert_contains "$skill_text" "final_verify.sh"
assert_contains "$skill_text" "result/output.md"
assert_contains "$skill_text" "templates/harness"
assert_contains "$skill_text" "Mandatory First Slice"
assert_contains "$skill_text" "layout-probe.md"
assert_contains "$skill_text" "libflashdb_rust.a"
assert_contains "$skill_text" "c_link_test.sh"

cargo_template="$(cat "$expected_skill_dir/templates/Cargo.toml")"
assert_contains "$cargo_template" 'crate-type = ["rlib", "staticlib"]'

for file in \
  "$expected_skill_dir/templates/Cargo.toml" \
  "$expected_skill_dir/templates/cargo-config.toml" \
  "$expected_skill_dir/templates/harness/build_check.sh" \
  "$expected_skill_dir/templates/harness/test_all.sh" \
  "$expected_skill_dir/templates/harness/c_link_test.sh" \
  "$expected_skill_dir/templates/harness/unsafe_audit.sh" \
  "$expected_skill_dir/templates/harness/c_coverage_check.py" \
  "$expected_skill_dir/templates/harness/final_verify.sh"
do
  [ -f "$file" ] || fail "missing skill template: ${file#$ROOT/}"
done

for script in "$expected_skill_dir/templates/harness/"*.sh; do
  [ -x "$script" ] || fail "harness template must be executable: ${script#$ROOT/}"
  bash -n "$script" || fail "invalid harness template syntax: ${script#$ROOT/}"
done

python3 -m py_compile "$expected_skill_dir/templates/harness/c_coverage_check.py"
rm -rf "$expected_skill_dir/templates/harness/__pycache__"

echo "package_check.sh: PASS"
