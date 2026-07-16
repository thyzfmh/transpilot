#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

for command in python3 cargo rustc "${CC:-cc}" nm opencode; do
  command -v "$command" >/dev/null 2>&1 || {
    echo "PREFLIGHT_BLOCKED: required command not found: $command" >&2
    exit 2
  }
done

test -r ../FlashDB/src/fdb.c || {
  echo "PREFLIGHT_BLOCKED: code/FlashDB source is unreadable" >&2
  exit 2
}
test -w . || {
  echo "PREFLIGHT_BLOCKED: target directory is not writable" >&2
  exit 2
}

available_kb="$(df -Pk . | awk 'NR == 2 { print $4 }')"
if [ "${available_kb:-0}" -lt 102400 ]; then
  echo "PREFLIGHT_BLOCKED: less than 100 MiB free disk space" >&2
  exit 2
fi

python3 ./harness/config_profile_check.py
python3 ./harness/trace_capture.py session --target "$ROOT"
echo "PREFLIGHT_PASS"
