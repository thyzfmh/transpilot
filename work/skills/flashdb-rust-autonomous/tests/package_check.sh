#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
SKILL="$ROOT/work/skills/flashdb-rust-autonomous"
HARNESS="$SKILL/templates/harness"

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

assert_contains() {
  local haystack="$1"
  local needle="$2"
  [[ "$haystack" == *"$needle"* ]] || fail "expected text to contain: $needle"
}

skill_dirs="$(find "$ROOT/work/skills" -mindepth 1 -maxdepth 1 -type d | sort)"
if [ "$skill_dirs" != "$SKILL" ]; then
  fail "work/skills must contain only flashdb-rust-autonomous"
fi

skill_files="$(find "$ROOT/work/skills" -name SKILL.md -type f | sort)"
if [ "$skill_files" != "$SKILL/SKILL.md" ]; then
  fail "expected only work/skills/flashdb-rust-autonomous/SKILL.md"
fi

for dir in \
  "$ROOT/.agent" "$ROOT/.agents" "$ROOT/.agent-handoff" \
  "$ROOT/config" "$ROOT/templates" "$ROOT/scripts" "$ROOT/tests" \
  "$ROOT/harness" "$ROOT/examples"
do
  [ ! -e "$dir" ] || fail "root package should not contain $(basename "$dir")"
done

instruction_text="$(cat "$ROOT/INSTRUCTION.md")"
assert_contains "$instruction_text" "# 执行入口"
assert_contains "$instruction_text" "work/skills/flashdb-rust-autonomous/SKILL.md"
assert_contains "$instruction_text" "Skill 名称：flashdb-rust-autonomous"
assert_contains "$instruction_text" '源项目固定为 `code/FlashDB`'
assert_contains "$instruction_text" 'Rust 目标固定为 `code/flashDB_rust`'
assert_contains "$instruction_text" "禁止使用 subagent 或 task agent"
assert_contains "$instruction_text" "不询问用户，不中断执行"
assert_contains "$instruction_text" "失败就按 Skill 内的循环修复并重新验证"
assert_contains "$instruction_text" 'work/skills/flashdb-rust-autonomous/scripts/final_verify_target.sh'
assert_contains "$instruction_text" 'result/output.md'
assert_contains "$instruction_text" 'logs/trace'
if printf '%s' "$instruction_text" | grep -Eqi 'opencode|c-to-rust|openspec|superpowers|评分规则|比赛'; then
  fail "INSTRUCTION.md must remain a tool-neutral direct skill entry"
fi
if [[ "$instruction_text" == *"不加载其它 skill"* || "$instruction_text" == *"Do not load any other skill"* ]]; then
  fail "INSTRUCTION.md should not emphasize loading no other skills"
fi

skill_text="$(cat "$SKILL/SKILL.md")"
for needle in \
  "references/c-to-rust-translation-spec.md" \
  "references/source-manifest.sha256" \
  "scripts/final_verify_target.sh" \
  "C-Test-First Translation" \
  "c_coverage_check.py --progress" \
  "api_surface_check.py --progress" \
  "translation_spec_check.py --progress" \
  "evidence_runner.py" \
  "trace_capture.py" \
  "c_interop_test.sh" \
  "ready_for_final" \
  "result/output.md" \
  "POSIX file mode" \
  "FDB_WRITE_GRAN=1"
do
  assert_contains "$skill_text" "$needle"
done

cargo_template="$(cat "$SKILL/templates/Cargo.toml")"
assert_contains "$cargo_template" 'crate-type = ["rlib", "staticlib"]'

spec_file="$SKILL/references/c-to-rust-translation-spec.md"
manifest="$SKILL/references/source-manifest.sha256"
[ -s "$spec_file" ] || fail "missing Chinese C-to-Rust specification"
[ -s "$manifest" ] || fail "missing source hash manifest"
spec_text="$(cat "$spec_file")"
for rule_id in \
  BASE-01 PROF-01 IMM-01 COV-01 API-01 TDD-01 INT-01 LAY-01 \
  STA-01 PST-01 XIO-01 ABI-01 MEM-01 ERR-01 CBK-01 GLB-01 EVD-01 LOG-01 VER-01
do
  assert_contains "$spec_text" "$rule_id"
done
assert_contains "$spec_text" "必须采用 C 测试优先"
assert_contains "$spec_text" "公开 API 必须逐项闭合"
assert_contains "$spec_text" "必须验证 C 与 Rust 双向持久化兼容"
assert_contains "$spec_text" "证据必须绑定当前输入和当前实现"
assert_contains "$spec_text" "AI 交互和验证日志必须完整留存"

required_files=(
  "$SKILL/templates/Cargo.toml"
  "$SKILL/templates/cargo-config.toml"
  "$SKILL/references/c-to-rust-translation-spec.md"
  "$SKILL/references/source-manifest.sha256"
  "$SKILL/scripts/final_verify_target.sh"
  "$SKILL/scripts/self_check.sh"
  "$SKILL/tests/trace_capture_test.py"
  "$HARNESS/preflight.sh"
  "$HARNESS/build_check.sh"
  "$HARNESS/test_all.sh"
  "$HARNESS/c_link_test.sh"
  "$HARNESS/c_interop_test.sh"
  "$HARNESS/unsafe_audit.sh"
  "$HARNESS/final_verify.sh"
  "$HARNESS/c_coverage_check.py"
  "$HARNESS/api_surface_check.py"
  "$HARNESS/translation_spec_check.py"
  "$HARNESS/config_profile_check.py"
  "$HARNESS/evidence_runner.py"
  "$HARNESS/trace_capture.py"
  "$HARNESS/checkpoint.py"
  "$HARNESS/rust_policy_check.py"
  "$HARNESS/source_guard.py"
  "$HARNESS/interop/interop_driver.c"
)
for file in "${required_files[@]}"; do
  [ -s "$file" ] || fail "missing or empty skill asset: ${file#$ROOT/}"
done

for script in "$HARNESS"/*.sh "$SKILL/scripts"/*.sh "$SKILL/tests"/*.sh; do
  [ -x "$script" ] || fail "script must be executable: ${script#$ROOT/}"
  bash -n "$script" || fail "invalid shell syntax: ${script#$ROOT/}"
done

python3 -m py_compile "$HARNESS"/*.py
python3 "$SKILL/tests/trace_capture_test.py"
rm -rf "$HARNESS/__pycache__" "$SKILL/tests/__pycache__"

"${CC:-cc}" -fsyntax-only -Wall -Wextra \
  -I"$ROOT/code/FlashDB/tests" -I"$ROOT/code/FlashDB/inc" -I"$ROOT/code/FlashDB/src" \
  "$HARNESS/interop/interop_driver.c"

python3 - "$ROOT" "$manifest" <<'PY'
import hashlib
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
manifest = pathlib.Path(sys.argv[2])
expected = {}
for line in manifest.read_text().splitlines():
    if line.strip():
        digest, relative = line.split(None, 1)
        expected[relative.strip()] = digest

actual = set()
for directory in [root / "code/FlashDB/inc", root / "code/FlashDB/src", root / "code/FlashDB/tests"]:
    for path in directory.rglob("*"):
        if path.is_file() and (path.suffix in {".c", ".h"} or path.name == "Makefile"):
            actual.add(path.relative_to(root).as_posix())
if actual != set(expected):
    raise SystemExit("source manifest file set mismatch")
for relative, digest in expected.items():
    if hashlib.sha256((root / relative).read_bytes()).hexdigest() != digest:
        raise SystemExit(f"source manifest hash mismatch: {relative}")
PY

final_text="$(cat "$HARNESS/final_verify.sh")"
for needle in \
  "source_guard.py" "preflight.sh" "test_all.sh" "c_link_test.sh" \
  "c_interop_test.sh" "c_coverage_check.py" "api_surface_check.py" \
  "trace_capture.py verify" "translation_spec_check.py" \
  "checkpoint.py verify-final" "rust_policy_check.py"
do
  assert_contains "$final_text" "$needle"
done
if grep -Rq "RUSTC_BOOTSTRAP" "$HARNESS"; then
  fail "fixed harness must not depend on RUSTC_BOOTSTRAP"
fi

echo "package_check.sh: PASS"
