#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "[test_all] cargo test --all-targets -- --nocapture"
cargo test --all-targets -- --nocapture
