#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import pathlib
import re
import sys

from adapter import load_adapter, require_list, source_root
from run_identity import require_identity, sha256
from source_acceptance import SCHEMA


TARGET = pathlib.Path.cwd()
ADAPTER = load_adapter(TARGET)
SOURCE = source_root(TARGET, ADAPTER)
REPORTS = TARGET / "reports"
REQUIRED = REPORTS / "source-test-required.tsv"
COVERAGE = REPORTS / "source-test-coverage.tsv"
SUMMARY = REPORTS / "source-test-coverage-check.md"
ACCEPTANCE = REPORTS / "source-acceptance.json"
SUITES = require_list(ADAPTER, "native_suites")
TEST_FILES = [SOURCE / str(suite["source_file"]) for suite in SUITES if isinstance(suite, dict)]
PROTOCOL = ADAPTER.get("native_test_protocol")


def cases_from_source() -> list[dict[str, str]]:
    if not isinstance(PROTOCOL, dict) or not isinstance(PROTOCOL.get("case_regex"), str):
        raise ValueError("native_test_protocol.case_regex is missing")
    case_regex = str(PROTOCOL["case_regex"])
    cases: list[dict[str, str]] = []
    for path in TEST_FILES:
        if not path.is_file():
            raise ValueError(f"missing source-native test file: {path}")
        seen: dict[str, int] = {}
        names = re.findall(case_regex, path.read_text(errors="replace"))
        if not all(isinstance(name, str) for name in names):
            raise ValueError("case regex must capture exactly one test name")
        for name in names:
            seen[name] = seen.get(name, 0) + 1
            cases.append(
                {
                    "case_id": (
                        f"{path.relative_to(SOURCE).as_posix()}::{name}#{seen[name]}"
                    ),
                    "source_file": path.relative_to(SOURCE).as_posix(),
                    "c_test": name,
                }
            )
    if not cases:
        raise ValueError("no source-native tests discovered")
    return cases


def write_tsv(path: pathlib.Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def initialize(cases: list[dict[str, str]]) -> int:
    write_tsv(REQUIRED, ["case_id", "source_file", "c_test"], cases)
    print(f"SOURCE_TEST_DISCOVERY_PASS: required={len(cases)}")
    return 0


def verify(progress: bool) -> int:
    required = cases_from_source()
    write_tsv(REQUIRED, ["case_id", "source_file", "c_test"], required)
    if not ACCEPTANCE.is_file():
        if progress:
            print(f"SOURCE_TEST_PROGRESS: passed=0 total={len(required)} acceptance=not-run")
            return 0
        raise ValueError(f"missing machine-generated acceptance result: {ACCEPTANCE}")

    data = json.loads(ACCEPTANCE.read_text())
    if data.get("schema") != SCHEMA:
        raise ValueError("source acceptance schema mismatch")
    require_identity(data.get("identity"), TARGET)
    raw_cases = data.get("cases")
    raw_suites = data.get("suites")
    if not isinstance(raw_cases, list) or not all(isinstance(case, dict) for case in raw_cases):
        raise ValueError("source acceptance cases are invalid")
    if not isinstance(raw_suites, list) or not all(isinstance(suite, dict) for suite in raw_suites):
        raise ValueError("source acceptance suites are invalid")
    case_ids = [str(case.get("case_id", "")) for case in raw_cases]
    if len(case_ids) != len(set(case_ids)) or "" in case_ids:
        raise ValueError("source acceptance contains empty or duplicate case ids")
    suite_names = [str(suite.get("name", "")) for suite in raw_suites]
    if len(suite_names) != len(set(suite_names)) or "" in suite_names:
        raise ValueError("source acceptance contains empty or duplicate suite names")

    configured_suites = {
        str(suite["name"]): str(suite["source_file"])
        for suite in SUITES
        if isinstance(suite, dict)
    }
    if set(suite_names) != set(configured_suites):
        raise ValueError("source acceptance suite set differs from the adapter")
    suite_logs: dict[str, str] = {}
    suite_case_totals: dict[str, int] = {}
    for suite in raw_suites:
        name = str(suite["name"])
        if suite.get("source_file") != configured_suites[name]:
            raise ValueError(f"suite source file mismatch: {name}")
        log_relative = str(suite.get("log", ""))
        log = (TARGET / log_relative).resolve()
        try:
            log.relative_to((TARGET / "reports/source-acceptance-logs").resolve())
        except ValueError as exc:
            raise ValueError(f"suite log escapes acceptance log directory: {name}") from exc
        if not log.is_file() or sha256(log) != suite.get("log_sha256"):
            raise ValueError(f"suite log hash mismatch: {name}")
        if (
            suite.get("exit_code") != 0
            or suite.get("protocol_complete") is not True
            or suite.get("protocol_errors") != []
        ):
            if not progress:
                raise ValueError(f"suite did not complete successfully: {name}")
        suite_logs[name] = log_relative
        suite_case_totals[name] = 0

    actual = {str(case["case_id"]): case for case in raw_cases}
    rows: list[dict[str, str]] = []
    failures: list[str] = []
    passed = 0
    suite_for_source = {source_file: name for name, source_file in configured_suites.items()}
    for case in required:
        result = actual.get(case["case_id"])
        status = str(result.get("status")) if result else "NOT_RUN"
        suite = str(result.get("suite", "")) if result else ""
        expected_suite = suite_for_source.get(case["source_file"], "")
        if result and (
            result.get("source_file") != case["source_file"]
            or result.get("name") != case["c_test"]
            or suite != expected_suite
        ):
            failures.append(f"{case['case_id']}: acceptance metadata mismatch")
        if suite in suite_case_totals:
            suite_case_totals[suite] += 1
        rows.append(
            {
                **case,
                "suite": suite,
                "status": status,
                "log": suite_logs.get(suite, ""),
            }
        )
        if status == "PASS":
            passed += 1
        else:
            detail = str(result.get("failure", "not executed")) if result else "not executed"
            failures.append(f"{case['case_id']}: {status}: {detail}")

    extra = sorted(set(actual) - {case["case_id"] for case in required})
    failures.extend(f"unknown source test in acceptance result: {case_id}" for case_id in extra)
    recomputed = {
        "total": len(raw_cases),
        "passed": sum(case.get("status") == "PASS" for case in raw_cases),
        "failed": sum(case.get("status") == "FAIL" for case in raw_cases),
        "not_run": sum(case.get("status") == "NOT_RUN" for case in raw_cases),
    }
    for field, value in recomputed.items():
        if data.get(field) != value:
            failures.append(f"acceptance summary mismatch: {field}")
    for suite in raw_suites:
        name = str(suite["name"])
        suite_cases = [case for case in raw_cases if case.get("suite") == name]
        if suite.get("total") != len(suite_cases):
            failures.append(f"suite total mismatch: {name}")
        if suite.get("passed") != sum(case.get("status") == "PASS" for case in suite_cases):
            failures.append(f"suite passed count mismatch: {name}")
    write_tsv(
        COVERAGE,
        ["case_id", "source_file", "c_test", "suite", "status", "log"],
        rows,
    )
    SUMMARY.write_text(
        "\n".join(
            [
                "# Source-Native Test Coverage",
                "",
                f"- Passed: {passed}",
                f"- Required: {len(required)}",
                f"- Status: {'PASSED' if not failures else 'IN_PROGRESS'}",
                "",
                "## First Failure",
                "",
                f"- {failures[0] if failures else 'none'}",
                "",
            ]
        )
    )
    if failures and not progress:
        print("SOURCE_TEST_COVERAGE_FAIL")
        for failure in failures[:10]:
            print(f"- {failure}")
        return 1
    if progress:
        print(f"SOURCE_TEST_PROGRESS: passed={passed} total={len(required)}")
    else:
        print(f"SOURCE_TEST_COVERAGE_PASS: passed={passed} total={len(required)}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--init", action="store_true")
    parser.add_argument("--progress", action="store_true")
    args = parser.parse_args()
    cases = cases_from_source()
    if args.init:
        return initialize(cases)
    return verify(args.progress)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"SOURCE_TEST_COVERAGE_FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
