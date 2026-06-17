#!/usr/bin/env bash
# harness/run-autonomous.sh — Transpilot 自驱翻译循环
# 用法: ./harness/run-autonomous.sh <target-parity> <max-waves>
# 例:   ./harness/run-autonomous.sh 95 20
#
# 前置条件:
#   - acceptance-plan.yaml 已通过 T0 确认
#   - CodeGraph 已索引（推荐）
#   - 当前目录为翻译项目根
#
# 需要环境: agent CLI (或替换为 AI IDE 的 skill 调用)
# 此脚本是实际可运行的框架，各 agent run 需按环境适配。

set -euo pipefail

TARGET=${1:-95}
MAX_WAVES=${2:-20}
WAVE=0
RETRY_COUNT=0

# 检查 acceptance-plan.yaml 已经由用户确认，且确认后未改动。
if [ ! -x scripts/check-acceptance-plan.sh ]; then
  echo "ERROR: scripts/check-acceptance-plan.sh not found. Run transpilot init first." >&2
  exit 2
fi
./scripts/check-acceptance-plan.sh verify >/dev/null

echo "Transpilot Autonomous Harness"
echo "Target parity: ${TARGET}% | Max waves: $MAX_WAVES"
echo "---"

while [ $WAVE -lt $MAX_WAVES ]; do
  WAVE=$((WAVE+1))
  echo ""
  echo "=== Wave $WAVE ==="

  # Step 1: 选择下一个 Wave 范围
  echo "[1/8] Selecting next wave scope..."
  agent run --skill translator --task "select-next-wave" \
    --input ".opencode/translation-state.jsonc" \
    --output ".opencode/wave-${WAVE}.jsonc" 2>/dev/null || {
    echo "WARN: agent not available, manual wave selection needed"
    echo "  Create .opencode/wave-${WAVE}.jsonc manually, then re-run"
    exit 10
  }

  # Step 2: 执行翻译
  echo "[2/8] Translating wave-${WAVE}..."
  agent run --skill translator --task "execute-wave" \
    --input ".opencode/wave-${WAVE}.jsonc" \
    --max-self-fix 3

  # Step 3: 索引新鲜度门控
  echo "[3/8] Checking CodeGraph freshness..."
  if [ -f scripts/check-codegraph-freshness.sh ]; then
    ./scripts/check-codegraph-freshness.sh . 24 || { echo "ESCALATE: stale index"; exit 4; }
  fi

  # Step 4: Parity 验证
  echo "[4/8] Verifying parity..."
  agent run --skill parity-checker --task "verify-wave-${WAVE}"
  PARITY=$(python3 -c "
import json, re
with open('.opencode/translation-state.jsonc') as f:
    c = re.sub(r'//.*', '', f.read())
    c = re.sub(r',\s*([}\]])', r'\1', c)
data = json.loads(c)
w = data.get('waves',{}).get('wave-${WAVE}',{})
print(int(float(w.get('parity', 0)) * 100))
" 2>/dev/null || echo "0")

  # Step 5: 幻觉审计
  echo "[5/8] Hallucination audit..."
  agent run --skill anti-hallucination --task "audit-wave-${WAVE}"
  HSCORE=$(python3 -c "
import json
with open('.opencode/halluc-${WAVE}.jsonc') as f: data = json.load(f)
print(data.get('hallucination_score', 0))
" 2>/dev/null || echo "0")
  VERDICT=$(python3 -c "
import json
with open('.opencode/halluc-${WAVE}.jsonc') as f: data = json.load(f)
print(data.get('verdict', 'pass'))
" 2>/dev/null || echo "pass")

  # Step 6: 占位符门控
  echo "[6/8] Checking placeholders..."
  ./scripts/forbid-placeholders.sh src 0 || { echo "ESCALATE: placeholders left"; exit 5; }

  # Step 6.5: Oracle 独立性门控
  echo "[6.5/8] Oracle independence check..."
  if [ -d tests ]; then
    ./scripts/check-oracle-independence.sh tests || { echo "ESCALATE: AI-derived oracle"; exit 7; }
  fi

  # Step 6.6: 差分测试
  echo "[6.6/8] Differential testing..."
  agent run --skill differential-tester --task "diff-wave-${WAVE}" 2>/dev/null || true
  if [ -f ".opencode/diff-${WAVE}.jsonc" ]; then
    AI_ORACLES=$(python3 -c "
import json
with open('.opencode/diff-${WAVE}.jsonc') as f: data = json.load(f)
print(data.get('ai_derived_oracles', 0))
" 2>/dev/null || echo "0")
    [ "$AI_ORACLES" -eq 0 ] || { echo "ESCALATE: ai_derived_oracles=$AI_ORACLES"; exit 7; }
  fi

  # Step 7: 升级判断
  echo "[7/8] Evaluating escalation triggers..."
  if [ "$PARITY" -lt 80 ]; then
    RETRY_COUNT=$((RETRY_COUNT+1))
    if [ "$RETRY_COUNT" -ge 3 ]; then
      echo "ESCALATE: parity stuck at ${PARITY}% after 3 retries"; exit 2
    fi
  else
    RETRY_COUNT=0
  fi
  if [ "$VERDICT" = "escalate" ]; then
    echo "ESCALATE: hallucination_score=$HSCORE"; exit 6
  fi

  # Step 8: 状态持久化
  echo "[8/8] Committing wave-${WAVE}..."
  git add -A && git commit -m "wave-${WAVE}: parity=${PARITY}% halluc=${HSCORE}" --allow-empty

  # 终止条件
  OVERALL=$(python3 -c "
import json, re
with open('.opencode/translation-state.jsonc') as f:
    c = re.sub(r'//.*', '', f.read())
    c = re.sub(r',\s*([}\]])', r'\1', c)
data = json.loads(c)
print(int(float(data.get('overall_parity', 0)) * 100))
" 2>/dev/null || echo "0")
  echo "  Overall parity: ${OVERALL}%"
  if [ "$OVERALL" -ge "$TARGET" ]; then
    echo ""
    echo "✅ DONE — target parity ${TARGET}% reached (actual: ${OVERALL}%)"
    exit 0
  fi
done

echo ""
echo "ESCALATE: max waves ($MAX_WAVES) reached, overall=${OVERALL}%"
exit 3
