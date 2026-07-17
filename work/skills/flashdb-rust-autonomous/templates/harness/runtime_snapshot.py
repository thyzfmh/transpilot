from __future__ import annotations

import fnmatch
import json
import pathlib
import shutil
from typing import Any

from run_identity import current_identity, sha256


SCHEMA = "source-translation-runtime-snapshot-v1"


def ignored(relative: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(relative, pattern) for pattern in patterns)


def scan(root: pathlib.Path, ignore_patterns: list[str]) -> dict[str, dict[str, Any]]:
    root = root.resolve()
    files: dict[str, dict[str, Any]] = {}
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(root).as_posix()
        if ignored(relative, ignore_patterns):
            continue
        files[relative] = {
            "sha256": sha256(path),
            "bytes": path.stat().st_size,
        }
    return files


def capture(
    *,
    target: pathlib.Path,
    suite: str,
    implementation: str,
    root: pathlib.Path,
    before: dict[str, dict[str, Any]],
    ignore_patterns: list[str],
) -> pathlib.Path:
    after = scan(root, ignore_patterns)
    changed = sorted(
        path for path, metadata in after.items() if before.get(path) != metadata
    )
    deleted = sorted(set(before) - set(after))
    base = target / "reports/runtime-snapshots" / implementation
    files_dir = base / f"{suite}-files"
    if files_dir.exists():
        shutil.rmtree(files_dir)
    for relative in changed:
        source = root / relative
        output = files_dir / relative
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, output)
    manifest = {
        "schema": SCHEMA,
        "suite": suite,
        "implementation": implementation,
        "root": root.resolve().as_posix(),
        "identity": current_identity(target),
        "changed": [
            {"path": relative, **after[relative]}
            for relative in changed
        ],
        "deleted": deleted,
    }
    base.mkdir(parents=True, exist_ok=True)
    output = base / f"{suite}.json"
    output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    return output
