#!/usr/bin/env bash
set -euo pipefail

SKILL_DIR="$(cd "$(dirname "$0")/.." && pwd)"
REPO_ROOT="$(cd "$SKILL_DIR/../../.." && pwd)"
TARGET="${1:-$REPO_ROOT/code/flashDB_rust}"

python3 - "$SKILL_DIR" "$TARGET" <<'PY'
import pathlib
import shutil
import sys

skill = pathlib.Path(sys.argv[1])
target = pathlib.Path(sys.argv[2])
source = skill / "templates/harness"
destination = target / "harness"

for directory in (target / ".cargo", target / "src", target / "tests", target / "reports"):
    directory.mkdir(parents=True, exist_ok=True)
shutil.copyfile(skill / "templates/cargo-config.toml", target / ".cargo/config.toml")
if not (target / "Cargo.toml").is_file():
    shutil.copyfile(skill / "templates/Cargo.toml", target / "Cargo.toml")
if destination.exists():
    shutil.rmtree(destination)
shutil.copytree(
    source,
    destination,
    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
)
PY

find "$TARGET/harness" -type f -name '*.sh' -exec chmod +x {} +
echo "TARGET_HARNESS_INSTALLED"
