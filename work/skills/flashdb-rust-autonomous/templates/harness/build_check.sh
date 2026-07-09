#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if command -v rustfmt >/dev/null 2>&1; then
  echo "[build_check] cargo fmt --check"
  cargo fmt --check
else
  echo "[build_check] WARN: rustfmt not found; skipping cargo fmt --check"
fi

echo "[build_check] cargo check --all-targets"
cargo check --all-targets
