#!/usr/bin/env bash
# 拒绝跨 wave 的占位符 — wave commit 前强制运行
# 用法: ./scripts/forbid-placeholders.sh <src-dir> [allow-count]
# 退出码: 0 = 通过, 1 = 发现占位符, 2 = 参数错误
#
# 检测模式（均排除 tests/ 和 target/、// 注释行）:
#   - todo!()  todo!("...")  todo!("PLACEHOLDER: ...")
#   - unimplemented!()  unimplemented!("...")
#   - panic!("TODO ...")  panic!("FIXME ...")  panic!("not impl...")
#   - // TODO / // FIXME / // HACK  (仅计数，不强制阻断，除非 allow=0)

set -euo pipefail

SRC_DIR="${1:-src}"
ALLOW="${2:-0}"

if [ ! -d "$SRC_DIR" ]; then
  echo "[forbid-placeholders] ERROR: $SRC_DIR not found" >&2
  exit 2
fi

# Pattern 1: todo!(...) / unimplemented!(...) — 无论有无参数
# Pattern 2: panic!("TODO/FIXME/not impl/PLACEHOLDER/HACK")
HITS=$(grep -rEn \
  --include='*.rs' \
  --exclude-dir=tests \
  --exclude-dir=target \
  --exclude-dir=benches \
  '\b(todo|unimplemented)!\s*\(|panic!\s*\(\s*"(TODO|FIXME|not impl|PLACEHOLDER|HACK|Not yet)' \
  "$SRC_DIR" 2>/dev/null || true)

# 排除注释行（以 // 开头的行）
HITS=$(echo "$HITS" | grep -v '^\s*//' | grep -v '^\s*$' || true)

COUNT=0
if [ -n "$HITS" ]; then
  COUNT=$(echo "$HITS" | wc -l | tr -d ' ')
fi

if [ "$COUNT" -gt "$ALLOW" ]; then
  echo "[forbid-placeholders] FAIL: $COUNT placeholder(s) found (allow=$ALLOW)"
  echo ""
  echo "$HITS"
  echo ""
  echo "Rule: 占位符必须在当前 Wave 内清零 (AGENTS.md Rule 10)"
  exit 1
fi

echo "[forbid-placeholders] PASS ($COUNT placeholder(s), allow=$ALLOW)"
exit 0
