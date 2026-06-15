#!/bin/bash
# Transpilot - Progress/Parity Report Generator
# Usage: ./scripts/parity-report.sh [summary|module <name>|wave <id>|risk|full]

set -euo pipefail

COMMAND="${1:-summary}"
ARG="${2:-}"
STATE_FILE=".opencode/translation-state.jsonc"

if [ ! -f "$STATE_FILE" ]; then
    echo "Error: $STATE_FILE not found. Are you in a translation project?"
    exit 1
fi

# Strip JSONC comments for parsing
strip_comments() {
    sed 's|//.*||g' "$STATE_FILE" | python3 -c "
import sys, json
data = json.load(sys.stdin)
json.dump(data, sys.stdout)
"
}

case "$COMMAND" in
    summary)
        echo "=== Transpilot Progress Report ==="
        strip_comments | python3 -c "
import sys, json
data = json.load(sys.stdin)
proj = data.get('project', {})
stats = data.get('statistics', {})
mods = data.get('modules', {})
total = len(mods) if mods else stats.get('total_modules', 0)
verified = sum(1 for m in mods.values() if m.get('status') == 'verified')
translated = sum(1 for m in mods.values() if m.get('status') == 'translated')
in_progress = sum(1 for m in mods.values() if m.get('status') == 'in_progress')
pending = sum(1 for m in mods.values() if m.get('status') == 'pending')
pct = (verified / total * 100) if total > 0 else 0
print(f'Project: {proj.get(\"name\", \"unknown\")}')
print(f'Language: {proj.get(\"source_language\", \"unknown\")}')
print(f'Progress: {verified}/{total} verified ({pct:.1f}%)')
print(f'  Verified:    {verified}')
print(f'  Translated:  {translated}')
print(f'  In Progress: {in_progress}')
print(f'  Pending:     {pending}')
print(f'Parity: {stats.get(\"parity_score\", 0):.1f}%')
print(f'Unsafe: {stats.get(\"unsafe_ratio\", 0):.1f}%')
"
        ;;
    module)
        if [ -z "$ARG" ]; then echo "Usage: $0 module <name>"; exit 1; fi
        echo "=== Module: $ARG ==="
        strip_comments | python3 -c "
import sys, json
data = json.load(sys.stdin)
mod = data.get('modules', {}).get('$ARG')
if not mod:
    print('Module not found: $ARG')
    sys.exit(1)
for k, v in mod.items():
    print(f'  {k}: {v}')
"
        ;;
    wave)
        if [ -z "$ARG" ]; then echo "Usage: $0 wave <id>"; exit 1; fi
        echo "=== Wave: $ARG ==="
        strip_comments | python3 -c "
import sys, json
data = json.load(sys.stdin)
wave = data.get('waves', {}).get('$ARG')
if not wave:
    print('Wave not found: $ARG')
    sys.exit(1)
for k, v in wave.items():
    print(f'  {k}: {v}')
"
        ;;
    risk)
        echo "=== Risk Assessment ==="
        strip_comments | python3 -c "
import sys, json
data = json.load(sys.stdin)
mods = data.get('modules', {})
high_risk = [(k,v) for k,v in mods.items() if v.get('difficulty') == 'very_hard' or v.get('unsafe_count',0) > 10]
if high_risk:
    print('HIGH RISK:')
    for name, mod in high_risk:
        print(f'  - {name}: difficulty={mod.get(\"difficulty\")}, unsafe={mod.get(\"unsafe_count\",0)}')
else:
    print('No high-risk modules detected.')
"
        ;;
    full)
        $0 summary
        echo ""
        $0 risk
        ;;
    *)
        echo "Usage: $0 [summary|module <name>|wave <id>|risk|full]"
        exit 1
        ;;
esac
