#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import pathlib
import re
import sys

from run_identity import current_identity


SCHEMA = "source-native-acceptance-v2"


def hash_paths(root: pathlib.Path, paths: list[pathlib.Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths):
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
        digest.update(b"\n")
    return digest.hexdigest()


def file_sha256(path: pathlib.Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def expected_cases(
    source: pathlib.Path,
    source_file: pathlib.Path,
    case_regex: str,
) -> list[dict[str, object]]:
    text = source_file.read_text(errors="replace")
    seen: dict[str, int] = {}
    cases = []
    names = re.findall(case_regex, text)
    if not all(isinstance(name, str) for name in names):
        raise ValueError("case regex must capture exactly one test name")
    for name in names:
        seen[name] = seen.get(name, 0) + 1
        cases.append(
            {
                "case_id": (
                    f"{source_file.relative_to(source).as_posix()}::{name}#{seen[name]}"
                ),
                "name": name,
                "occurrence": seen[name],
                "status": "NOT_RUN",
                "failure": "",
            }
        )
    if not cases:
        raise ValueError(f"no TEST_RUN cases discovered in {source_file}")
    return cases


def apply_log(
    cases: list[dict[str, object]],
    log_text: str,
    exit_code: int,
    *,
    start_regex: str,
    failure_regex: str,
    fatal_regex: str,
    pass_regex: str,
) -> tuple[bool, list[str]]:
    next_index = 0
    current: int | None = None
    errors: list[str] = []
    suite_passed = False
    for line in log_text.splitlines():
        running = re.search(start_regex, line)
        if running:
            if current is not None and cases[current]["status"] == "RUNNING":
                cases[current]["status"] = "PASS"
            name = running.group(1)
            if next_index >= len(cases) or cases[next_index]["name"] != name:
                errors.append(f"unexpected or out-of-order case start: {name}")
                current = None
            else:
                current = next_index
                next_index += 1
                cases[current]["status"] = "RUNNING"
            continue
        failure = re.search(failure_regex, line)
        if failure:
            if current is not None:
                cases[current]["status"] = "FAIL"
                cases[current]["failure"] = failure.group(2).strip()
            continue
        if current is not None and re.search(fatal_regex, line, re.I):
            cases[current]["status"] = "FAIL"
            cases[current]["failure"] = line.strip()
        if re.search(pass_regex, line):
            suite_passed = True

    protocol_complete = suite_passed and exit_code == 0 and next_index == len(cases) and not errors
    if protocol_complete:
        if current is not None and cases[current]["status"] == "RUNNING":
            cases[current]["status"] = "PASS"
    else:
        if not suite_passed:
            errors.append("suite completion marker is missing")
        if exit_code != 0:
            errors.append(f"suite exited with code {exit_code}")
        if next_index != len(cases):
            errors.append(f"suite started {next_index} of {len(cases)} expected cases")
        if current is not None and cases[current]["status"] == "RUNNING":
            cases[current]["status"] = "FAIL"
            cases[current]["failure"] = errors[0] if errors else "suite did not complete"

    for case in cases:
        if case["status"] == "RUNNING":
            case["status"] = "FAIL"
            case["failure"] = "suite did not prove case completion"
    return protocol_complete, errors


def parse_suite(value: str) -> tuple[str, pathlib.Path, pathlib.Path, int, str]:
    parts = value.split("|", 4)
    if len(parts) != 5:
        raise ValueError(
            "--suite must be NAME|SOURCE_TEST_FILE|LOG_FILE|EXIT_CODE|PASS_REGEX"
        )
    return (
        parts[0],
        pathlib.Path(parts[1]).resolve(),
        pathlib.Path(parts[2]).resolve(),
        int(parts[3]),
        parts[4],
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True)
    parser.add_argument("--target", default=".")
    parser.add_argument("--output", default="reports/source-acceptance.json")
    parser.add_argument("--suite", action="append", required=True)
    parser.add_argument(
        "--start-regex",
        default=r"\bRunning:\s*([A-Za-z_][A-Za-z0-9_]*)",
    )
    parser.add_argument(
        "--failure-regex",
        default=r"\bFAIL\s+([A-Za-z_][A-Za-z0-9_]*):\s*(.*)",
    )
    parser.add_argument(
        "--fatal-regex",
        default=r"panic|fatal runtime error|segmentation fault|abort",
    )
    parser.add_argument(
        "--case-regex",
        default=r"\bTEST_RUN\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)",
    )
    args = parser.parse_args()

    source = pathlib.Path(args.source).resolve()
    target = pathlib.Path(args.target).resolve()
    suites = []
    all_cases: list[dict[str, object]] = []
    for raw in args.suite:
        name, source_file, log_file, exit_code, pass_regex = parse_suite(raw)
        if not source_file.is_file() or not log_file.is_file():
            raise ValueError(f"suite input is missing: {raw}")
        cases = expected_cases(source, source_file, args.case_regex)
        protocol_complete, protocol_errors = apply_log(
            cases,
            log_file.read_text(errors="replace"),
            exit_code,
            start_regex=args.start_regex,
            failure_regex=args.failure_regex,
            fatal_regex=args.fatal_regex,
            pass_regex=pass_regex,
        )
        for case in cases:
            case["suite"] = name
            case["source_file"] = source_file.relative_to(source).as_posix()
        suites.append(
            {
                "name": name,
                "source_file": source_file.relative_to(source).as_posix(),
                "log": log_file.relative_to(target).as_posix(),
                "log_sha256": file_sha256(log_file),
                "exit_code": exit_code,
                "pass_regex": pass_regex,
                "protocol_complete": protocol_complete,
                "protocol_errors": protocol_errors,
                "total": len(cases),
                "passed": sum(case["status"] == "PASS" for case in cases),
            }
        )
        all_cases.extend(cases)

    passed = sum(case["status"] == "PASS" for case in all_cases)
    failed = sum(case["status"] == "FAIL" for case in all_cases)
    not_run = sum(case["status"] == "NOT_RUN" for case in all_cases)
    result = {
        "schema": SCHEMA,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "identity": current_identity(target),
        "total": len(all_cases),
        "passed": passed,
        "failed": failed,
        "not_run": not_run,
        "suites": suites,
        "cases": all_cases,
    }
    output = (target / args.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n")

    print(f"SOURCE_ACCEPTANCE: passed={passed} failed={failed} not_run={not_run} total={len(all_cases)}")
    first = next((case for case in all_cases if case["status"] != "PASS"), None)
    if first:
        print(
            "SOURCE_ACCEPTANCE_FIRST_FAILURE: "
            f"{first['case_id']} status={first['status']} detail={first['failure'] or 'not executed'}"
        )
    if (
        failed
        or not_run
        or any(
            suite["exit_code"] != 0 or not suite["protocol_complete"]
            for suite in suites
        )
    ):
        return 1
    print("SOURCE_ACCEPTANCE_PASS")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError) as exc:
        print(f"SOURCE_ACCEPTANCE_FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
