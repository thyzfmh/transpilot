#!/usr/bin/env bash
# 拒绝跨 wave 的占位符 — 当 wave 准备 commit 时强制运行
# 用法: ./scripts/forbid-placeholders.sh <src-dir> [allow-count]
# 退出码: 0 = 通过, 1 = 发现占位符, 2 = 参数错误

set -euo pipefail

SRC_DIR="${1:-src}"
ALLOW="${2:-0}"

if [ ! -d "$SRC_DIR" ]; then
  echo "[forbid-placeholders] ERROR: $SRC_DIR not found" >&2
  exit 2
fi

HITS=$(grep -rEn \
  --include='*.rs' \
  --exclude-dir=tests \
  --exclude-dir=target \
  '(^[^/]*\b(todo|unimplemented)!\(\))|panic!\("(not impl|TODO|FIXME)' \
  "$SRC_DIR" 2>/dev/null | grep -v '^\s*//' || true)

COUNT=$(echo -n "$HITS" | grep -c '' || true)

if [ "$COUNT" -gt "$ALLOW" ]; then
  echo "[forbid-placeholders] FAIL: $COUNT placeholder(s) found (allow=$ALLOW)"
  echo "$HITS"
  echo
  echo "Rule: 占位符必须在当前 Wave 内清零 (translator/SKILL.md Rule 5)"
  exit 1
fi

echo "[forbid-placeholders] PASS ($COUNT placeholder(s), allow=$ALLOW)"
exit 0
