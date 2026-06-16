#!/usr/bin/env bash
# CodeGraph 索引新鲜度校验 — 防止使用过期索引导致幻觉
# 用法: ./scripts/check-codegraph-freshness.sh <project-dir> [max-age-hours]
# 退出码: 0 = 新鲜, 1 = 过期, 2 = 未索引

set -euo pipefail

PROJ="${1:-.}"
MAX_AGE_H="${2:-24}"

DB="$PROJ/.codegraph/codegraph.db"
if [ ! -f "$DB" ]; then
  echo "[freshness] ERROR: $DB not found, run: codegraph init && codegraph index" >&2
  exit 2
fi

if [[ "$OSTYPE" == "darwin"* ]]; then
  DB_MTIME=$(stat -f %m "$DB")
else
  DB_MTIME=$(stat -c %Y "$DB")
fi

SRC_MTIME=$(find "$PROJ" \
  -type f \( -name '*.go' -o -name '*.rs' -o -name '*.c' -o -name '*.h' \) \
  -not -path '*/target/*' \
  -not -path '*/.git/*' \
  -not -path '*/.codegraph/*' \
  -not -path '*/node_modules/*' \
  -exec stat -f %m {} \; 2>/dev/null | sort -n | tail -1)

if [ -z "$SRC_MTIME" ]; then
  SRC_MTIME=$(find "$PROJ" \
    -type f \( -name '*.go' -o -name '*.rs' -o -name '*.c' -o -name '*.h' \) \
    -not -path '*/target/*' -not -path '*/.git/*' -not -path '*/.codegraph/*' \
    -printf '%T@\n' 2>/dev/null | sort -n | tail -1 | cut -d. -f1)
fi

NOW=$(date +%s)
AGE_H=$(( (NOW - DB_MTIME) / 3600 ))

if [ -n "$SRC_MTIME" ] && [ "$DB_MTIME" -lt "$SRC_MTIME" ]; then
  echo "[freshness] STALE: 源文件已修改但索引未更新"
  echo "  index mtime: $(date -r $DB_MTIME)"
  echo "  src   mtime: $(date -r $SRC_MTIME)"
  echo "Run: codegraph index"
  exit 1
fi

if [ "$AGE_H" -gt "$MAX_AGE_H" ]; then
  echo "[freshness] STALE: 索引已 ${AGE_H}h 未更新（上限 ${MAX_AGE_H}h）"
  echo "Run: codegraph index"
  exit 1
fi

echo "[freshness] FRESH (age=${AGE_H}h, limit=${MAX_AGE_H}h)"
exit 0
