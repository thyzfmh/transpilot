#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../../../.." && pwd)"
SKILL="$ROOT/work/skills/flashdb-rust-autonomous"
HARNESS="$SKILL/templates/harness"
TEMP_ROOT=""
TEMP_TARGET=""

fail() {
  echo "FAIL: $*" >&2
  exit 1
}

cleanup() {
  if [ -n "$TEMP_ROOT" ]; then
    rm -rf "$TEMP_ROOT"
  fi
}
trap cleanup EXIT

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
  "references/autonomous-source-translation-method.md" \
  "references/c-to-rust-translation-spec.md" \
  "references/project-adapter.md" \
  "references/source-manifest.sha256" \
  "scripts/final_verify_target.sh" \
  "Source-Native Test Loop" \
  "project_discovery.py" \
  "source-native acceptance" \
  "source_oracle_runner.py" \
  "checkpoint.py show" \
  "evidence_runner.py" \
  "trace_capture.py" \
  "differential_compare.py" \
  "ready_for_final" \
  "result/output.md" \
  "result/output.md"
do
  assert_contains "$skill_text" "$needle"
done

cargo_template="$(cat "$SKILL/templates/Cargo.toml")"
assert_contains "$cargo_template" 'crate-type = ["rlib", "staticlib"]'

spec_file="$SKILL/references/c-to-rust-translation-spec.md"
method_file="$SKILL/references/autonomous-source-translation-method.md"
adapter_file="$SKILL/references/project-adapter.md"
manifest="$SKILL/references/source-manifest.sha256"
[ -s "$spec_file" ] || fail "missing Chinese C-to-Rust specification"
[ -s "$method_file" ] || fail "missing generic autonomous translation method"
[ -s "$adapter_file" ] || fail "missing current project adapter"
[ -s "$manifest" ] || fail "missing source hash manifest"
spec_text="$(cat "$spec_file")"
for rule_id in \
  BASE-01 PROF-01 IMM-01 COV-01 API-01 TDD-01 INT-01 LAY-01 \
  STA-01 PST-01 XIO-01 ABI-01 MEM-01 ERR-01 CBK-01 GLB-01 EVD-01 LOG-01 VER-01
do
  assert_contains "$spec_text" "$rule_id"
done
assert_contains "$spec_text" "必须采用源测试优先"
assert_contains "$spec_text" "公开 API 必须逐项闭合"
assert_contains "$spec_text" "必须验证双向兼容"
assert_contains "$spec_text" "证据必须自动绑定当前实现"
assert_contains "$spec_text" "交互和验证日志必须完整"
method_text="$(cat "$method_file")"
assert_contains "$method_text" "三层结构"
assert_contains "$method_text" "最早真实反馈"
assert_contains "$method_text" "断点恢复"
assert_contains "$method_text" "测试数量和模块名必须由仓库机械发现"
adapter_text="$(cat "$adapter_file")"
assert_contains "$adapter_text" '源项目：`code/FlashDB`'
assert_contains "$adapter_text" '目标项目：`code/flashDB_rust`'
assert_contains "$adapter_text" "原测试数量和顺序必须由测试源码机械发现"

required_files=(
  "$SKILL/templates/Cargo.toml"
  "$SKILL/templates/cargo-config.toml"
  "$SKILL/references/autonomous-source-translation-method.md"
  "$SKILL/references/c-to-rust-translation-spec.md"
  "$SKILL/references/project-adapter.md"
  "$SKILL/references/source-manifest.sha256"
  "$SKILL/scripts/install_target_harness.sh"
  "$SKILL/scripts/final_verify_target.sh"
  "$SKILL/scripts/self_check.sh"
  "$SKILL/tests/trace_capture_test.py"
  "$SKILL/tests/general_method_test.py"
  "$HARNESS/preflight.sh"
  "$HARNESS/preflight.py"
  "$HARNESS/adapter.py"
  "$HARNESS/run_identity.py"
  "$HARNESS/project-adapter.json"
  "$HARNESS/build_check.sh"
  "$HARNESS/build_runner.py"
  "$HARNESS/build_artifact_check.py"
  "$HARNESS/target_test_runner.py"
  "$HARNESS/final_gate_runner.py"
  "$HARNESS/test_all.sh"
  "$HARNESS/c_link_test.sh"
  "$HARNESS/native_test_runner.py"
  "$HARNESS/source_oracle_runner.py"
  "$HARNESS/project_discovery.py"
  "$HARNESS/source_acceptance.py"
  "$HARNESS/runtime_snapshot.py"
  "$HARNESS/differential_compare.py"
  "$HARNESS/unsafe_audit.sh"
  "$HARNESS/final_verify.sh"
  "$HARNESS/final_report.py"
  "$HARNESS/completion.py"
  "$HARNESS/c_coverage_check.py"
  "$HARNESS/api_surface_check.py"
  "$HARNESS/translation_spec_check.py"
  "$HARNESS/config_profile_check.py"
  "$HARNESS/evidence_runner.py"
  "$HARNESS/trace_capture.py"
  "$HARNESS/checkpoint.py"
  "$HARNESS/rust_policy_check.py"
  "$HARNESS/source_guard.py"
)
for file in "${required_files[@]}"; do
  [ -s "$file" ] || fail "missing or empty skill asset: ${file#$ROOT/}"
done

if find "$SKILL" \( -type d -name __pycache__ -o -type f -name '*.pyc' \) -print -quit | grep -q .; then
  fail "skill package contains generated Python cache"
fi

for script in "$HARNESS"/*.sh "$SKILL/scripts"/*.sh "$SKILL/tests"/*.sh; do
  [ -x "$script" ] || fail "script must be executable: ${script#$ROOT/}"
  bash -n "$script" || fail "invalid shell syntax: ${script#$ROOT/}"
done

TEMP_ROOT="$(mktemp -d)"
TEMP_TARGET="$TEMP_ROOT/missing/flashDB_rust"
"$SKILL/scripts/install_target_harness.sh" "$TEMP_TARGET" >/dev/null
[ -s "$TEMP_TARGET/Cargo.toml" ] || fail "cold install did not create Cargo.toml"
[ -s "$TEMP_TARGET/.cargo/config.toml" ] || fail "cold install did not create Cargo config"
[ -s "$TEMP_TARGET/harness/project-adapter.json" ] || fail "cold install did not create harness"
if find "$TEMP_TARGET/harness" \( -type d -name __pycache__ -o -type f -name '*.pyc' \) -print -quit | grep -q .; then
  fail "cold install copied generated Python cache"
fi
printf 'preserve-source\n' > "$TEMP_TARGET/src/lib.rs"
printf '\n# preserve-manifest\n' >> "$TEMP_TARGET/Cargo.toml"
"$SKILL/scripts/install_target_harness.sh" "$TEMP_TARGET" >/dev/null
grep -q 'preserve-source' "$TEMP_TARGET/src/lib.rs" || fail "reinstall overwrote Rust source"
grep -q 'preserve-manifest' "$TEMP_TARGET/Cargo.toml" || fail "reinstall overwrote Cargo.toml"

python3 -m py_compile "$HARNESS"/*.py
python3 "$SKILL/tests/trace_capture_test.py"
python3 "$SKILL/tests/general_method_test.py"
rm -rf "$HARNESS/__pycache__" "$SKILL/tests/__pycache__"

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
  "source_guard.py" "preflight.sh" "project_discovery.py" \
  "final_gate_runner.py" "checkpoint.py seal-final" "final_report.py"
do
  assert_contains "$final_text" "$needle"
done
trusted_text="$(cat "$SKILL/scripts/final_verify_target.sh")"
for needle in \
  "install_target_harness.sh" \
  "final_verify.sh" "completion.py stage" "trace_capture.py\" export" \
  "trace_capture.py\" verify" "completion.py finalize" \
  "trace_capture.py refresh-result" "completion.py verify --require-trace"
do
  assert_contains "$trusted_text" "$needle"
done
if grep -Rq "RUSTC_BOOTSTRAP" "$HARNESS"; then
  fail "fixed harness must not depend on RUSTC_BOOTSTRAP"
fi

echo "package_check.sh: PASS"
