#!/bin/bash
# pre-translate hook: 翻译前加载相关经验
# 用法: ./hooks/pre-translate.sh <source_file> <source_language>

SOURCE_FILE="${1:?需要源文件路径}"
SOURCE_LANG="${2:?需要源语言 (go|c)}"
MEMORY_DIR="$(dirname "$0")/../memory"

echo "Pre-translate: $SOURCE_FILE ($SOURCE_LANG)"
echo "Checking for related experiences..."

if [ -f "$MEMORY_DIR/episodes.jsonl" ]; then
    BASENAME=$(basename "$SOURCE_FILE" | sed 's/\.[^.]*$//')
    RELATED=$(grep -i "$BASENAME" "$MEMORY_DIR/episodes.jsonl" 2>/dev/null | tail -5)
    if [ -n "$RELATED" ]; then
        echo "WARNING: Found related history for this module"
        echo "$RELATED"
    fi
fi

echo "Done."
