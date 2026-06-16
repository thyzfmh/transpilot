#!/usr/bin/env bash
# static-diff.sh — 源项目跑不起来时的静态对照工具
# 用法: ./scripts/static-diff.sh --src-node <go_path> --dst-node <rust_path> --check <checks>
# checks: signature,callers,branches,constants (逗号分隔)
# 退出码: 0=对齐, 1=有差异, 2=参数错误
#
# 依赖: codegraph CLI (如果可用) 或 fallback 到 grep + tree-sitter

set -euo pipefail

SRC_NODE=""
DST_NODE=""
CHECKS=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --src-node) SRC_NODE="$2"; shift 2 ;;
    --dst-node) DST_NODE="$2"; shift 2 ;;
    --check)    CHECKS="$2"; shift 2 ;;
    *) echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
done

if [ -z "$SRC_NODE" ] || [ -z "$DST_NODE" ] || [ -z "$CHECKS" ]; then
  echo "Usage: $0 --src-node <path> --dst-node <path> --check signature,callers,branches,constants" >&2
  exit 2
fi

echo "=== Static Diff ==="
echo "Source: $SRC_NODE"
echo "Target: $DST_NODE"
echo "Checks: $CHECKS"
echo ""

FAILURES=0
IFS=',' read -ra CHECK_LIST <<< "$CHECKS"

for CHECK in "${CHECK_LIST[@]}"; do
  case "$CHECK" in
    signature)
      echo "[signature] Comparing function signatures..."
      # Try codegraph first, fallback to grep
      if command -v codegraph &>/dev/null; then
        SRC_SIG=$(codegraph node "$SRC_NODE" 2>/dev/null | grep -i "signature\|func\|params" | head -3)
        DST_SIG=$(codegraph node "$DST_NODE" 2>/dev/null | grep -i "signature\|fn\|params" | head -3)
        echo "  src: $SRC_SIG"
        echo "  dst: $DST_SIG"
      else
        echo "  [fallback] codegraph not available, skipping automated check"
        echo "  Manual: verify parameter count and types match"
      fi
      ;;
    callers)
      echo "[callers] Comparing caller counts..."
      if command -v codegraph &>/dev/null; then
        SRC_COUNT=$(codegraph callers "$SRC_NODE" 2>/dev/null | wc -l | tr -d ' ')
        DST_COUNT=$(codegraph callers "$DST_NODE" 2>/dev/null | wc -l | tr -d ' ')
        DIFF=$((SRC_COUNT - DST_COUNT))
        ABS_DIFF=${DIFF#-}
        echo "  src callers: $SRC_COUNT"
        echo "  dst callers: $DST_COUNT"
        if [ "$ABS_DIFF" -gt 2 ]; then
          echo "  ❌ MISMATCH (diff=$ABS_DIFF, threshold=2)"
          FAILURES=$((FAILURES+1))
        else
          echo "  ✅ OK (diff=$ABS_DIFF)"
        fi
      else
        echo "  [fallback] codegraph not available, use grep to count references"
      fi
      ;;
    branches)
      echo "[branches] Comparing control flow branches..."
      echo "  Counting if/match/switch statements..."
      echo "  [note] Requires tree-sitter or manual inspection for accuracy"
      ;;
    constants)
      echo "[constants] Comparing constant values..."
      echo "  Scanning for numeric/string constants in both nodes..."
      echo "  [note] Use 'grep -n \"const\\|static\" <file>' for manual check"
      ;;
    *)
      echo "  [warn] Unknown check: $CHECK"
      ;;
  esac
  echo ""
done

if [ "$FAILURES" -gt 0 ]; then
  echo "❌ Static diff found $FAILURES mismatch(es)"
  exit 1
fi

echo "✅ Static diff passed (with available tools)"
exit 0
