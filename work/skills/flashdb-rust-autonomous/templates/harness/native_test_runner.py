#!/usr/bin/env python3
from __future__ import annotations

import os
import pathlib
import shutil
import subprocess
import sys
from typing import Any

from adapter import expand_command, load_adapter, require_list, source_root
from runtime_snapshot import capture, scan


def command_for(
    raw: Any,
    *,
    target: pathlib.Path,
    source: pathlib.Path,
    artifact: pathlib.Path,
) -> list[str]:
    if not isinstance(raw, list) or not raw or not all(isinstance(item, str) for item in raw):
        raise ValueError("native suite command must be a non-empty string list")
    values = {
        "source": source.as_posix(),
        "target": target.as_posix(),
        "artifact": artifact.as_posix(),
        "cc": os.environ.get("CC", "cc"),
    }
    return [item.format(**values) for item in raw]


def run_logged(
    command: list[str],
    *,
    cwd: pathlib.Path,
    log: pathlib.Path,
    timeout: int,
) -> int:
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("w") as handle:
        try:
            result = subprocess.run(
                command,
                cwd=cwd,
                stdout=handle,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
                timeout=timeout,
            )
            return result.returncode
        except subprocess.TimeoutExpired:
            handle.write(f"\nHARNESS_TIMEOUT after {timeout} seconds\n")
            return 124


def remove_matches(root: pathlib.Path, patterns: Any) -> None:
    if not isinstance(patterns, list):
        raise ValueError("cleanup_globs must be a list")
    for raw in patterns:
        if not isinstance(raw, str) or pathlib.Path(raw).is_absolute() or ".." in pathlib.Path(raw).parts:
            raise ValueError(f"unsafe cleanup glob: {raw}")
        for path in root.glob(raw):
            if path.is_dir() and not path.is_symlink():
                shutil.rmtree(path)
            else:
                path.unlink(missing_ok=True)


def main() -> int:
    target = pathlib.Path.cwd().resolve()
    adapter = load_adapter(target)
    source = source_root(target, adapter)
    artifact = target / str(adapter.get("target_artifact", ""))
    timeout = int(adapter.get("runtime_timeout_seconds", 180))
    reports = target / "reports/source-acceptance-logs"
    reports.mkdir(parents=True, exist_ok=True)

    build = expand_command(
        require_list(adapter, "source_native_build_command"),
        target,
        adapter,
    )
    build_status = run_logged(
        build,
        cwd=target,
        log=reports / "target-build.log",
        timeout=timeout,
    )
    if build_status != 0 or not artifact.is_file() or artifact.stat().st_size == 0:
        print(
            f"SOURCE_NATIVE_RUNNER_FAIL: target build exit={build_status}",
            file=sys.stderr,
        )
        return build_status or 1

    suite_args: list[str] = []
    protocol = adapter.get("native_test_protocol")
    if not isinstance(protocol, dict):
        raise ValueError("native_test_protocol is missing")
    suites = require_list(adapter, "native_suites")
    ignore_patterns = adapter.get("differential_ignore_globs", [])
    if not isinstance(ignore_patterns, list) or not all(
        isinstance(pattern, str) for pattern in ignore_patterns
    ):
        raise ValueError("differential_ignore_globs must be a string list")
    seen_names: set[str] = set()
    for raw_suite in suites:
        if not isinstance(raw_suite, dict):
            raise ValueError("native suite must be an object")
        name = str(raw_suite.get("name", ""))
        if not name or name in seen_names:
            raise ValueError(f"native suite name is empty or duplicated: {name}")
        seen_names.add(name)
        source_file = source / str(raw_suite.get("source_file", ""))
        workdir = source / str(raw_suite.get("working_directory", "."))
        pass_regex = str(raw_suite.get("pass_regex", ""))
        if not source_file.is_file() or not workdir.is_dir() or not pass_regex:
            raise ValueError(f"native suite configuration is incomplete: {name}")
        remove_matches(workdir, raw_suite.get("cleanup_globs", []))
        prepare_log = reports / f"{name}-prepare.log"
        prepare_log.write_text("")
        for index, raw_command in enumerate(raw_suite.get("prepare_commands", []), start=1):
            command = command_for(
                raw_command,
                target=target,
                source=source,
                artifact=artifact,
            )
            step_log = reports / f"{name}-prepare-{index}.log"
            status = run_logged(command, cwd=workdir, log=step_log, timeout=timeout)
            with prepare_log.open("a") as combined:
                combined.write(f"$ {' '.join(command)}\n")
                combined.write(step_log.read_text(errors="replace"))
                combined.write(f"\nexit={status}\n")
            if status != 0:
                print(
                    f"SOURCE_NATIVE_RUNNER_FAIL: suite={name} prepare={index} exit={status}",
                    file=sys.stderr,
                )
                return status

        remove_matches(workdir, raw_suite.get("cleanup_globs", []))
        run_command = command_for(
            raw_suite.get("run_command"),
            target=target,
            source=source,
            artifact=artifact,
        )
        if shutil.which("stdbuf"):
            run_command = ["stdbuf", "-oL", "-eL", *run_command]
        log = reports / f"{name}.log"
        before = scan(workdir, ignore_patterns)
        status = run_logged(run_command, cwd=workdir, log=log, timeout=timeout)
        capture(
            target=target,
            suite=name,
            implementation="target",
            root=workdir,
            before=before,
            ignore_patterns=ignore_patterns,
        )
        suite_args.extend(
            [
                "--suite",
                f"{name}|{source_file}|{log}|{status}|{pass_regex}",
            ]
        )

    command = [
        sys.executable,
        str(target / "harness/source_acceptance.py"),
        "--source",
        str(source),
        "--target",
        str(target),
        "--start-regex",
        str(protocol.get("start_regex", "")),
        "--failure-regex",
        str(protocol.get("failure_regex", "")),
        "--fatal-regex",
        str(protocol.get("fatal_regex", "")),
        "--case-regex",
        str(protocol.get("case_regex", "")),
        *suite_args,
    ]
    result = subprocess.run(command, cwd=target, check=False)
    if result.returncode != 0:
        print("SOURCE_NATIVE_RUNNER_FAIL: acceptance incomplete", file=sys.stderr)
        return result.returncode
    print("SOURCE_NATIVE_RUNNER_PASS")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError) as exc:
        print(f"SOURCE_NATIVE_RUNNER_FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
