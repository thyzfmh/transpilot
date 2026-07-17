#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import re
import shutil
import subprocess
import sys

from adapter import expand_command, load_adapter, require_list, source_root
from native_test_runner import remove_matches, run_logged
from runtime_snapshot import capture, scan


def main() -> int:
    target = pathlib.Path.cwd().resolve()
    adapter = load_adapter(target)
    source = source_root(target, adapter)
    timeout = int(adapter.get("runtime_timeout_seconds", 180))
    reports = target / "reports/source-oracle-logs"
    reports.mkdir(parents=True, exist_ok=True)

    build_commands = require_list(adapter, "source_oracle_build_commands")
    for index, raw_command in enumerate(build_commands, start=1):
        command = expand_command(raw_command, target, adapter)
        status = run_logged(
            command,
            cwd=target,
            log=reports / f"build-{index}.log",
            timeout=timeout,
        )
        if status != 0:
            print(
                f"SOURCE_ORACLE_FAIL: build={index} exit={status}",
                file=sys.stderr,
            )
            return status

    protocol = adapter.get("native_test_protocol")
    if not isinstance(protocol, dict):
        raise ValueError("native_test_protocol is missing")
    repetitions = int(adapter.get("differential_source_repetitions", 2))
    if repetitions < 2:
        raise ValueError("differential_source_repetitions must be at least 2")
    suite_args: list[str] = []
    ignore_patterns = adapter.get("differential_ignore_globs", [])
    if not isinstance(ignore_patterns, list) or not all(
        isinstance(pattern, str) for pattern in ignore_patterns
    ):
        raise ValueError("differential_ignore_globs must be a string list")
    for raw_suite in require_list(adapter, "native_suites"):
        if not isinstance(raw_suite, dict):
            raise ValueError("native suite must be an object")
        name = str(raw_suite.get("name", ""))
        source_file = source / str(raw_suite.get("source_file", ""))
        workdir = source / str(raw_suite.get("working_directory", "."))
        pass_regex = str(raw_suite.get("pass_regex", ""))
        if not name or not source_file.is_file() or not workdir.is_dir() or not pass_regex:
            raise ValueError(f"source oracle suite is incomplete: {name}")
        command = expand_command(raw_suite.get("run_command"), target, adapter)
        if shutil.which("stdbuf"):
            command = ["stdbuf", "-oL", "-eL", *command]
        first_log: pathlib.Path | None = None
        first_status = 1
        for repetition in range(1, repetitions + 1):
            remove_matches(workdir, raw_suite.get("cleanup_globs", []))
            before = scan(workdir, ignore_patterns)
            log = reports / (
                f"{name}.log"
                if repetition == 1
                else f"{name}-calibration-{repetition}.log"
            )
            status = run_logged(command, cwd=workdir, log=log, timeout=timeout)
            capture(
                target=target,
                suite=name,
                implementation=f"source-{repetition}",
                root=workdir,
                before=before,
                ignore_patterns=ignore_patterns,
            )
            if status != 0 or re.search(pass_regex, log.read_text(errors="replace")) is None:
                print(
                    f"SOURCE_ORACLE_FAIL: suite={name} calibration={repetition} "
                    f"exit={status}",
                    file=sys.stderr,
                )
                return status or 1
            if repetition == 1:
                first_log = log
                first_status = status
        if first_log is None:
            raise ValueError(f"source oracle suite did not run: {name}")
        suite_args.extend(
            [
                "--suite",
                f"{name}|{source_file}|{first_log}|{first_status}|{pass_regex}",
            ]
        )

    command = [
        sys.executable,
        str(target / "harness/source_acceptance.py"),
        "--source",
        str(source),
        "--target",
        str(target),
        "--output",
        "reports/source-oracle.json",
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
        print("SOURCE_ORACLE_FAIL: baseline acceptance incomplete", file=sys.stderr)
        return result.returncode
    print("SOURCE_ORACLE_PASS")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError) as exc:
        print(f"SOURCE_ORACLE_FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
