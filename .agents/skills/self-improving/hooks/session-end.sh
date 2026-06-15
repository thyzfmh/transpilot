#!/bin/bash
# session-end hook: 会话结束时总结经验
# 用法: ./hooks/session-end.sh

MEMORY_DIR="$(dirname "$0")/../memory"
TODAY=$(date +%Y-%m-%d)

echo "=== Session Summary ==="

if [ -f "$MEMORY_DIR/episodes.jsonl" ]; then
    TODAY_EVENTS=$(grep -c "$TODAY" "$MEMORY_DIR/episodes.jsonl" 2>/dev/null || echo 0)
    TODAY_FIXES=$(grep "$TODAY" "$MEMORY_DIR/episodes.jsonl" 2>/dev/null | grep -c '"type":"fix"' || echo 0)
    TODAY_TRANSLATES=$(grep "$TODAY" "$MEMORY_DIR/episodes.jsonl" 2>/dev/null | grep -c '"type":"translate"' || echo 0)
    
    echo "Today's activity:"
    echo "  Translations: $TODAY_TRANSLATES"
    echo "  Fixes: $TODAY_FIXES"
    echo "  Total events: $TODAY_EVENTS"
    
    if [ "$TODAY_FIXES" -gt 2 ]; then
        echo ""
        echo "WARNING: Multiple fixes today - consider extracting new patterns"
    fi
else
    echo "No episodes recorded yet."
fi

echo "=== End ==="
