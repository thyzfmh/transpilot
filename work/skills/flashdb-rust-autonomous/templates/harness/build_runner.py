#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import json
import pathlib
import shutil
import subprocess
import sys
import time

from adapter import expand_command, load_adapter, require_list
from run_identity import sha256


def run(command: list[str], target: pathlib.Path, timeout: int) -> None:
    result = subprocess.run(
        command,
        cwd=target,
        check=False,
        timeout=timeout,
    )
    if result.returncode != 0:
        raise ValueError(f"build command failed with exit {result.returncode}: {command}")


def main() -> int:
    target = pathlib.Path.cwd().resolve()
    adapter = load_adapter(target)
    timeout = int(adapter.get("runtime_timeout_seconds", 180))
    validations = adapter.get("build_validation_commands")
    if not isinstance(validations, list):
        raise ValueError("adapter build_validation_commands must be a list")
    for entry in validations:
        if not isinstance(entry, dict):
            raise ValueError("build validation entry must be an object")
        optional = entry.get("optional_tool")
        if isinstance(optional, str) and not shutil.which(optional):
            print(f"BUILD_VALIDATION_SKIP: optional tool is missing: {optional}")
            continue
        run(expand_command(entry.get("command"), target, adapter), target, timeout)
    run(expand_command(require_list(adapter, "build_command"), target, adapter), target, timeout)
    llvm_files: list[pathlib.Path] = []
    capabilities = adapter.get("capabilities")
    if isinstance(capabilities, dict) and capabilities.get("public_c_abi") is True:
        llvm_dir = target / "target/release/deps"
        llvm_dir.mkdir(parents=True, exist_ok=True)
        for stale in llvm_dir.glob("*.ll"):
            stale.unlink()
        abi_command = expand_command(
            require_list(adapter, "abi_ir_command"),
            target,
            adapter,
        )
        if adapter.get("abi_unique_metadata") is True:
            abi_command.extend(
                ["-C", f"metadata=source_translation_abi_{time.time_ns():x}"]
            )
        run(
            abi_command,
            target,
            timeout,
        )
        llvm_files = sorted(llvm_dir.glob("*.ll"))
        if not llvm_files or any(path.stat().st_size == 0 for path in llvm_files):
            raise ValueError("configured ABI build produced no non-empty LLVM IR")
    artifact = target / str(adapter.get("target_artifact", ""))
    if not artifact.is_file() or artifact.stat().st_size == 0:
        raise ValueError(f"target artifact is missing or empty: {artifact}")
    tracked = [artifact, *llvm_files]
    rlib_relative = adapter.get("target_rlib")
    if isinstance(rlib_relative, str) and rlib_relative:
        rlib = target / rlib_relative
        if not rlib.is_file() or rlib.stat().st_size == 0:
            raise ValueError(f"configured Rust rlib is missing or empty: {rlib}")
        tracked.append(rlib)
    report = {
        "schema": "source-translation-build-artifacts-v1",
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "artifacts": [
            {
                "path": path.relative_to(target).as_posix(),
                "sha256": sha256(path),
                "bytes": path.stat().st_size,
            }
            for path in tracked
        ],
        "llvm_ir": [path.relative_to(target).as_posix() for path in llvm_files],
    }
    reports = target / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "build-artifacts.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n"
    )
    print("CONFIGURED_BUILD_PASS")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print(f"CONFIGURED_BUILD_FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
