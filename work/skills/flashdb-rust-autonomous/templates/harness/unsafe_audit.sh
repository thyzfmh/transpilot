#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

THRESHOLD="${1:-10}"

python3 - "$THRESHOLD" <<'PY'
import pathlib
import re
import sys

threshold = float(sys.argv[1])
src = pathlib.Path("src")
files = sorted(src.rglob("*.rs")) if src.exists() else []

line_count = 0
unsafe_hits = 0
pattern = re.compile(r"\bunsafe\b")

for path in files:
    text = path.read_text(errors="replace")
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped:
            continue
        line_count += 1
        if stripped.startswith("//"):
            continue
        unsafe_hits += len(pattern.findall(line))

ratio = (unsafe_hits / line_count * 100.0) if line_count else 0.0
print(f"[unsafe_audit] unsafe hits: {unsafe_hits}")
print(f"[unsafe_audit] rust source lines: {line_count}")
print(f"[unsafe_audit] unsafe ratio: {ratio:.2f}%")
print(f"[unsafe_audit] threshold: {threshold:.2f}%")

if ratio >= threshold:
    print("[unsafe_audit] FAIL: unsafe ratio is at or above threshold", file=sys.stderr)
    sys.exit(1)
PY
