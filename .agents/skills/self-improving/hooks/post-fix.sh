#!/bin/bash
# post-fix hook: 修复 bug 后记录经验
# 用法: ./hooks/post-fix.sh <fixed_file> <error_type>

FIXED_FILE="${1:?需要修复的文件路径}"
ERROR_TYPE="${2:?需要错误类型}"
MEMORY_DIR="$(dirname "$0")/../memory"

TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
echo "{\"time\":\"$TIMESTAMP\",\"type\":\"fix\",\"file\":\"$FIXED_FILE\",\"error_type\":\"$ERROR_TYPE\"}" >> "$MEMORY_DIR/episodes.jsonl"

echo "Recorded fix: $ERROR_TYPE in $FIXED_FILE"
