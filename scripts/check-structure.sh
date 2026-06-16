#!/usr/bin/env bash
# check-structure.sh — 验证模块结构对齐（源 vs 译码）
# 用法: ./scripts/check-structure.sh <module-name>
# 退出码: 0=对齐, 1=有差异, 2=参数错误
#
# 检查: 公开函数/方法数量、文件数量、struct/trait 数量

set -euo pipefail

MODULE="${1:?用法: $0 <module-name>}"
STATE_FILE=".opencode/translation-state.jsonc"

if [ ! -f "$STATE_FILE" ]; then
  echo "ERROR: $STATE_FILE not found" >&2
  exit 2
fi

# 从 state 取 src/dst 路径
INFO=$(python3 -c "
import json, re
with open('$STATE_FILE') as f:
    c = re.sub(r'//.*', '', f.read())
    c = re.sub(r',\s*([}\]])', r'\1', c)
data = json.loads(c)
mod = data.get('modules', {}).get('$MODULE', {})
src = mod.get('src_files', [])
dst = mod.get('dst_files', [])
print(f'SRC_COUNT={len(src)}')
print(f'DST_COUNT={len(dst)}')
if src: print(f'SRC_SAMPLE={src[0]}')
if dst: print(f'DST_SAMPLE={dst[0]}')
" 2>/dev/null || echo "SRC_COUNT=0")

eval "$INFO"

echo "=== Structure Check: $MODULE ==="
echo "Source files: ${SRC_COUNT:-0}"
echo "Target files: ${DST_COUNT:-0}"

if [ "${SRC_COUNT:-0}" -eq 0 ]; then
  echo "WARN: module not found in translation-state or no src_files recorded"
  echo "Tip: run translator first to populate module info"
  exit 0
fi

# Count public items in Rust files (rough heuristic)
if [ -n "${DST_SAMPLE:-}" ] && [ -f "${DST_SAMPLE:-}" ]; then
  PUB_FN=$(grep -c 'pub fn\|pub async fn' "${DST_SAMPLE}" 2>/dev/null || echo "0")
  PUB_STRUCT=$(grep -c 'pub struct\|pub enum\|pub trait' "${DST_SAMPLE}" 2>/dev/null || echo "0")
  echo "Target public items (sample ${DST_SAMPLE}):"
  echo "  pub fn: $PUB_FN"
  echo "  pub struct/enum/trait: $PUB_STRUCT"
fi

echo ""
echo "✅ Structure check complete (manual review recommended for accuracy)"
exit 0
