#!/bin/bash
# Transpilot - Progress/Parity Report Generator
# Usage: ./scripts/parity-report.sh [summary|module <name>|wave <id>|risk|full]
# Schema: aligned with .agents/skills/shared/interfaces.md §4 (v1.0)

set -euo pipefail

COMMAND="${1:-summary}"
ARG="${2:-}"
STATE_FILE=".opencode/translation-state.jsonc"

if [ ! -f "$STATE_FILE" ]; then
    echo "Error: $STATE_FILE not found. Are you in a translation project?"
    exit 1
fi

# Strip JSONC comments for parsing (handles // comments not inside strings)
parse_state() {
    python3 -c "
import sys, re, json

with open('$STATE_FILE') as f:
    content = f.read()

# Remove single-line comments (// ...) that aren't inside strings
# Simple approach: remove lines starting with optional whitespace then //
# and remove trailing // comments (heuristic, good enough for our structured JSONC)
lines = []
for line in content.split('\n'):
    stripped = line.lstrip()
    if stripped.startswith('//'):
        continue
    # Remove trailing // comment (only if not inside a string value)
    in_str = False
    result = []
    i = 0
    while i < len(line):
        c = line[i]
        if c == '\"' and (i == 0 or line[i-1] != '\\\\'):
            in_str = not in_str
        elif c == '/' and i+1 < len(line) and line[i+1] == '/' and not in_str:
            break
        result.append(c)
        i += 1
    lines.append(''.join(result))

cleaned = '\n'.join(lines)
# Remove trailing commas before } or ]
cleaned = re.sub(r',\s*([}\]])', r'\1', cleaned)
data = json.loads(cleaned)
json.dump(data, sys.stdout)
"
}

case "$COMMAND" in
    summary)
        echo "=== Transpilot Progress Report ==="
        parse_state | python3 -c "
import sys, json
data = json.load(sys.stdin)
proj = data.get('project', 'unknown')
src_lang = data.get('src_lang', 'unknown')
overall = data.get('overall_parity', 0)
cur_wave = data.get('current_wave', 'none')
mods = data.get('modules', {})
total = len(mods)
verified = sum(1 for m in mods.values() if m.get('status') == 'verified')
translated = sum(1 for m in mods.values() if m.get('status') == 'translated')
in_progress = sum(1 for m in mods.values() if m.get('status') == 'in_progress')
pending = sum(1 for m in mods.values() if m.get('status') == 'pending')
blocked = sum(1 for m in mods.values() if m.get('status') == 'blocked')
pct = (verified / total * 100) if total > 0 else 0
print(f'Project: {proj}')
print(f'Language: {src_lang} → rust')
print(f'Current Wave: {cur_wave}')
print(f'Overall Parity: {overall*100:.1f}%')
print(f'Modules: {total} total')
print(f'  Verified:    {verified} ({pct:.1f}%)')
print(f'  Translated:  {translated}')
print(f'  In Progress: {in_progress}')
print(f'  Pending:     {pending}')
print(f'  Blocked:     {blocked}')
"
        ;;
    module)
        if [ -z "$ARG" ]; then echo "Usage: $0 module <name>"; exit 1; fi
        echo "=== Module: $ARG ==="
        parse_state | python3 -c "
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
        parse_state | python3 -c "
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
        parse_state | python3 -c "
import sys, json
data = json.load(sys.stdin)
blockers = data.get('blockers', [])
if blockers:
    print('BLOCKERS:')
    for b in blockers:
        print(f'  - {b.get(\"module\")}: {b.get(\"reason\")} (since {b.get(\"since\")})')
else:
    print('No blockers.')
"
        ;;
    full)
        "$0" summary
        echo ""
        "$0" risk
        ;;
    *)
        echo "Usage: $0 [summary|module <name>|wave <id>|risk|full]"
        exit 1
        ;;
esac
