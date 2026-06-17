#!/usr/bin/env bash
# check-oracle-independence.sh — 检测 AI 自批改作业模式
# 用法: ./scripts/check-oracle-independence.sh <tests-dir> [--strict]
# 退出码: 0=通过, 1=发现违规, 2=参数错误
#
# 检测模式 (单行+多行):
#   assert_eq!(<call>, "literal")     → 硬编码字符串预期
#   assert_eq!(<call>, 123)           → 硬编码数字预期
#   assert!(<call>.contains("..."))   → 硬编码 contains
#
# 白名单（合法 Oracle）:
#   assert_eq!(src_run(...), dst_run(...))   → 差分
#   assert_eq!(src_run(...), <any>)          → 源项目 Oracle
#   prop_assert_eq!(...)                     → property 测试
#   assert_eq!(UPPER_CASE, ...)              → fixture 常量
#   assert_eq!(..., UPPER_CASE)              → fixture 常量
#   assert!(...is_ok/is_err/is_some/is_none/is_empty) → 类型断言
#   load_fixture / replay_fixture            → 已录回放
#   // oracle:ok                             → 手动标记白名单

set -uo pipefail
# NOTE: 不用 set -e，因为 python 返回 1 表示"有违规"而非脚本错误

TESTS_DIR="${1:-tests}"
STRICT="${2:-}"

if [ ! -d "$TESTS_DIR" ]; then
  echo "[oracle-independence] ERROR: $TESTS_DIR not found" >&2
  echo "Usage: $0 <tests-dir> [--strict]" >&2
  exit 2
fi

# 使用 python3 做多行感知检测，通过环境变量传递 tests_dir
export ORACLE_CHECK_DIR="$TESTS_DIR"
VIOLATIONS=$(python3 - << 'PYEOF'
import os, re, sys

tests_dir = os.environ.get("ORACLE_CHECK_DIR", "tests")
violations = []

# Whitelist patterns (any of these in the same assert context → skip)
WHITELIST = [
    r'src_run',
    r'dst_run',
    r'replay_fixture',
    r'load_fixture',
    r'from_fixture',
    r'expected_from_source',
    r'//\s*oracle:\s*ok',
    r'#\[.*oracle_approved\]',
]

# Constant pattern (UPPER_CASE identifiers are fixture references)
CONST_PAT = re.compile(r'[A-Z][A-Z0-9_]{2,}')

for root, dirs, files in os.walk(tests_dir):
    # skip target/ and .git
    dirs[:] = [d for d in dirs if d not in ('target', '.git', 'node_modules')]
    for fname in files:
        if not fname.endswith('.rs'):
            continue
        fpath = os.path.join(root, fname)
        with open(fpath, 'r', errors='replace') as f:
            content = f.read()
        lines = content.split('\n')

        # Build "logical assertion blocks" — concatenate continuation lines
        # until the assert!/assert_eq! call's parentheses are balanced.
        i = 0
        while i < len(lines):
            line = lines[i]
            stripped = line.lstrip()
            line_num = i + 1

            if stripped.startswith('//'):
                i += 1
                continue

            m = re.search(r'(assert_eq!|prop_assert_eq!|assert!|assert_ne!)', line)
            if not m:
                i += 1
                continue

            # Accumulate full assertion across lines (paren balance)
            block_lines = [line]
            block_start = i
            text = line[m.start():]
            depth = 0
            seen_open = False
            for ch in text:
                if ch == '(':
                    depth += 1; seen_open = True
                elif ch == ')':
                    depth -= 1
            j = i
            while seen_open and depth > 0 and j + 1 < len(lines):
                j += 1
                nxt = lines[j]
                block_lines.append(nxt)
                for ch in nxt:
                    if ch == '(': depth += 1
                    elif ch == ')': depth -= 1
            block = '\n'.join(block_lines)

            # Check whitelist on the full block + 2 lines before
            ctx_start = max(0, block_start - 2)
            context = '\n'.join(lines[ctx_start:j + 1])
            if any(re.search(wp, context) for wp in WHITELIST):
                i = j + 1
                continue

            # Type-only assertions
            if re.search(r'\.is_(ok|err|some|none|empty)\(\)', block):
                i = j + 1
                continue

            # UPPER_CASE constant on either side of assert_eq!
            am = re.search(r'(assert_eq!|assert_ne!|prop_assert_eq!)\s*\((.*)\)\s*;?\s*$', block, re.DOTALL)
            if am:
                args = am.group(2)
                # Split top-level by comma (depth 0)
                parts, depth_, buf = [], 0, ''
                for ch in args:
                    if ch == '(' or ch == '[' or ch == '{': depth_ += 1
                    elif ch == ')' or ch == ']' or ch == '}': depth_ -= 1
                    if ch == ',' and depth_ == 0:
                        parts.append(buf); buf = ''
                    else:
                        buf += ch
                if buf: parts.append(buf)
                if len(parts) >= 2:
                    left = parts[0].strip()
                    right = parts[1].strip()
                    if CONST_PAT.match(left) or CONST_PAT.match(right):
                        i = j + 1
                        continue

            # Hardcoded literals (across the whole block)
            has_string_literal = re.search(r'"[^"\\]{1,}"', block)
            has_num_literal = re.search(r',\s*-?[0-9]+\.?[0-9]*\s*[,)]', block)
            has_contains = re.search(r'\.contains\s*\(\s*"', block)

            if has_string_literal or has_num_literal or has_contains:
                violations.append(f"{fpath}:{line_num}: {block_lines[0].strip()}")

            i = j + 1

if violations:
    print('\n'.join(violations))
    sys.exit(1)
else:
    sys.exit(0)
PYEOF
)
EXIT_CODE=$?

if [ $EXIT_CODE -eq 1 ]; then
  COUNT=$(echo "$VIOLATIONS" | wc -l | tr -d ' ')
  echo "[oracle-independence] FAIL: $COUNT violation(s) — hardcoded expected values"
  echo ""
  echo "$VIOLATIONS"
  echo ""
  echo "Fix options:"
  echo "  1. Use src_run(input) as Oracle"
  echo "  2. Load fixture from source project: load_fixture(\"case.json\")"
  echo "  3. Use UPPER_CASE constants for fixture data"
  echo "  4. Add '// oracle:ok' comment if this is a deliberate known-value test"
  echo ""
  echo "See: .agents/skills/differential-tester/reference.md"
  exit 1
elif [ $EXIT_CODE -ne 0 ]; then
  echo "[oracle-independence] ERROR: python script failed (exit=$EXIT_CODE)" >&2
  exit 2
fi

echo "[oracle-independence] PASS — no AI-derived oracles detected in $TESTS_DIR"
exit 0
