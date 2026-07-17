#!/usr/bin/env python3
from __future__ import annotations

import json
import pathlib
import sys

from run_identity import sha256


def main() -> int:
    target = pathlib.Path.cwd().resolve()
    report = target / "reports/build-artifacts.json"
    if not report.is_file():
        raise ValueError("build artifact manifest is missing")
    data = json.loads(report.read_text())
    entries = data.get("artifacts")
    if (
        data.get("schema") != "source-translation-build-artifacts-v1"
        or not isinstance(entries, list)
        or not entries
    ):
        raise ValueError("build artifact manifest is invalid")
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            raise ValueError("build artifact entry is invalid")
        path = (target / entry["path"]).resolve()
        try:
            path.relative_to(target)
        except ValueError as exc:
            raise ValueError("build artifact path escapes target") from exc
        if (
            not path.is_file()
            or path.stat().st_size != entry.get("bytes")
            or sha256(path) != entry.get("sha256")
        ):
            raise ValueError(f"build artifact changed: {entry['path']}")
    llvm_names = data.get("llvm_ir")
    if not isinstance(llvm_names, list):
        raise ValueError("build artifact LLVM IR index is invalid")
    current_llvm = {
        path.relative_to(target).as_posix()
        for path in (target / "target/release/deps").glob("*.ll")
        if path.is_file()
    }
    if current_llvm != set(llvm_names):
        raise ValueError("LLVM IR set differs from the build artifact manifest")
    print("BUILD_ARTIFACT_CHECK_PASS")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"BUILD_ARTIFACT_CHECK_FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
