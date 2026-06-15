#!/bin/bash
# post-translate hook: 翻译后检测新模式
# 用法: ./hooks/post-translate.sh <rust_file> <source_file>

RUST_FILE="${1:?需要 Rust 文件路径}"
SOURCE_FILE="${2:?需要源文件路径}"
MEMORY_DIR="$(dirname "$0")/../memory"

echo "Post-translate: $RUST_FILE"

# 检查是否包含 unsafe
UNSAFE_COUNT=$(grep -c "unsafe" "$RUST_FILE" 2>/dev/null || echo 0)
if [ "$UNSAFE_COUNT" -gt 0 ]; then
    echo "WARNING: Found $UNSAFE_COUNT unsafe blocks - review needed"
fi

# 检查是否有 todo!/unimplemented!
TODO_COUNT=$(grep -cE "todo!|unimplemented!" "$RUST_FILE" 2>/dev/null || echo 0)
if [ "$TODO_COUNT" -gt 0 ]; then
    echo "WARNING: Found $TODO_COUNT placeholders (todo!/unimplemented!)"
fi

# 记录翻译事件
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
echo "{\"time\":\"$TIMESTAMP\",\"type\":\"translate\",\"source\":\"$SOURCE_FILE\",\"target\":\"$RUST_FILE\",\"unsafe_count\":$UNSAFE_COUNT,\"todo_count\":$TODO_COUNT}" >> "$MEMORY_DIR/episodes.jsonl"

echo "Done."
