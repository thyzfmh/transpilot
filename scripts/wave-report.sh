#!/usr/bin/env bash
# wave-report.sh — 生成单个 wave 的综合报告
# 用法: ./scripts/wave-report.sh <wave-id>
# 输出: 打印到 stdout，也写入 .opencode/reports/wave-<id>.txt

set -euo pipefail

WAVE_ID="${1:?用法: $0 <wave-id>, 例: $0 1}"

STATE_FILE=".opencode/translation-state.jsonc"
WAVE_FILE=".opencode/wave-${WAVE_ID}.jsonc"
PARITY_FILE=".opencode/parity-${WAVE_ID}.jsonc"
HALLUC_FILE=".opencode/halluc-${WAVE_ID}.jsonc"
DIFF_FILE=".opencode/diff-${WAVE_ID}.jsonc"

mkdir -p .opencode/reports

report() {
  echo "$@"
  echo "$@" >> ".opencode/reports/wave-${WAVE_ID}.txt"
}

: > ".opencode/reports/wave-${WAVE_ID}.txt"

report "=== Wave $WAVE_ID Report ==="
report "Generated: $(date +%Y-%m-%d\ %H:%M)"
report ""

# Wave scope
if [ -f "$WAVE_FILE" ]; then
  MODULES=$(python3 -c "
import json
with open('$WAVE_FILE') as f: data = json.load(f)
mods = data.get('modules', [])
for m in mods:
    name = m.get('module', m) if isinstance(m, dict) else m
    print(f'  - {name}')
" 2>/dev/null || echo "  (parse error)")
  report "Modules in scope:"
  report "$MODULES"
else
  report "Modules: (wave file not found)"
fi
report ""

# Parity
if [ -f "$PARITY_FILE" ]; then
  report "Parity:"
  python3 -c "
import json
with open('$PARITY_FILE') as f: data = json.load(f)
print(f'  Overall: {data.get(\"overall_parity\", \"N/A\")}')
for m in data.get('modules', []):
    print(f'  {m.get(\"module\")}: {m.get(\"parity\", \"N/A\")}')
" 2>/dev/null | while read -r line; do report "$line"; done
else
  report "Parity: (not yet verified)"
fi
report ""

# Hallucination
if [ -f "$HALLUC_FILE" ]; then
  report "Hallucination Audit:"
  python3 -c "
import json
with open('$HALLUC_FILE') as f: data = json.load(f)
print(f'  Score: {data.get(\"hallucination_score\", \"N/A\")}')
print(f'  Verdict: {data.get(\"verdict\", \"N/A\")}')
findings = data.get('findings', [])
print(f'  Findings: {len(findings)}')
for f in findings[:5]:
    print(f'    - [{f.get(\"severity\")}] {f.get(\"type\")}: {f.get(\"loc\")}')
" 2>/dev/null | while read -r line; do report "$line"; done
else
  report "Hallucination: (not yet audited)"
fi
report ""

# Differential test
if [ -f "$DIFF_FILE" ]; then
  report "Differential Test:"
  python3 -c "
import json
with open('$DIFF_FILE') as f: data = json.load(f)
print(f'  Oracle: {data.get(\"oracle_mode\", \"N/A\")}')
print(f'  Cases: {data.get(\"cases_passed\", 0)}/{data.get(\"cases_total\", 0)} passed')
print(f'  AI-derived oracles: {data.get(\"ai_derived_oracles\", \"N/A\")}')
print(f'  Verdict: {data.get(\"verdict\", \"N/A\")}')
" 2>/dev/null | while read -r line; do report "$line"; done
else
  report "Differential Test: (not yet run)"
fi
report ""

report "=== End of Report ==="
echo ""
echo "Report saved to .opencode/reports/wave-${WAVE_ID}.txt"
