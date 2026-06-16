#!/usr/bin/env bash
# check-oracle-independence.sh
# 用法: ./scripts/check-oracle-independence.sh <tests-dir>
# 退出码: 0=通过, 1=发现 AI 写的硬编码预期值, 2=参数错误
#
# 检测以下"自批改作业"模式：
#   assert_eq!(<call>, "literal-string")
#   assert_eq!(<call>, 123)
#   assert!(<call>.contains("literal"))
# 例外（视为合法 Oracle）：
#   assert_eq!(src_run(...), dst_run(...))
#   assert_eq!(src_run(...), <call>)
#   prop_assert_eq!(src_run(...), ...)
#   assert_eq!(EXPECTED, <call>)   # 大写常量视为 fixture 引用

set -u

TESTS_DIR="${1:-tests}"
if [ ! -d "$TESTS_DIR" ]; then
  echo "usage: $0 <tests-dir>" >&2
  exit 2
fi

# 收集所有 assert_eq! / assert! / prop_assert_eq!
HITS=$(grep -rEn --include='*.rs' \
  '(assert_eq!|prop_assert_eq!|assert!)' "$TESTS_DIR" 2>/dev/null || true)

# 过滤合法 Oracle 引用
VIOLATIONS=$(echo "$HITS" | grep -v 'src_run' \
                          | grep -v 'dst_run' \
                          | grep -v 'replay_fixture' \
                          | grep -v 'load_fixture' \
                          | grep -vE 'assert_eq!\([[:space:]]*[A-Z_][A-Z0-9_]+,' \
                          | grep -vE 'assert_eq!\([^,]+,[[:space:]]*[A-Z_][A-Z0-9_]+\)' \
                          | grep -vE 'assert!\(.*\.is_(ok|err|some|none|empty)\(\)\)' \
                          | grep -E '"[^"]+"|, *-?[0-9]+\)' \
                          || true)

if [ -n "$VIOLATIONS" ]; then
  echo "❌ AI-derived oracle violations (hardcoded expected values):"
  echo "$VIOLATIONS"
  echo ""
  echo "Fix: use src_run(input) as Oracle, or load fixture from source project."
  echo "See .agents/skills/differential-tester/reference.md"
  exit 1
fi

echo "✅ Oracle independence check passed for $TESTS_DIR"
exit 0
