#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import pathlib
import re
import sys

TARGET = pathlib.Path.cwd()
SOURCE = (TARGET / "../FlashDB").resolve()
REPORTS = TARGET / "reports"
REQUIRED = REPORTS / "c-test-coverage-required.tsv"
COVERAGE = REPORTS / "c-test-coverage.tsv"
SUMMARY = REPORTS / "c-test-coverage-check.md"
C_TEST_FILES = [
    SOURCE / "tests/fdb_kvdb_tc.c",
    SOURCE / "tests/fdb_tsdb_tc.c",
]


def fail(message: str) -> None:
    print(f"[c_coverage_check] FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def extract_c_cases() -> list[dict[str, str]]:
    cases: list[dict[str, str]] = []
    seen: dict[tuple[str, str], int] = {}
    for path in C_TEST_FILES:
        if not path.is_file():
            fail(f"missing C test source: {path}")
        text = path.read_text(errors="replace")
        for name in re.findall(r"TEST_RUN\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)", text):
            key = (path.name, name)
            seen[key] = seen.get(key, 0) + 1
            case_id = f"{path.name}::{name}#{seen[key]}"
            cases.append({"case_id": case_id, "source_file": path.name, "c_test": name})
    if not cases:
        fail("no C TEST_RUN cases found")
    return cases


def find_matching_brace(text: str, open_index: int) -> int:
    depth = 0
    for index in range(open_index, len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index
    return len(text)


def extract_rust_tests() -> dict[str, dict[str, str]]:
    tests: dict[str, dict[str, str]] = {}
    for root in [TARGET / "src", TARGET / "tests"]:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*.rs")):
            text = path.read_text(errors="replace")
            for match in re.finditer(
                r"#\s*\[\s*(?:[A-Za-z0-9_:]+\s*)?test\s*\]\s*(?:\n\s*#\[[^\]]+\]\s*)*\n\s*fn\s+([A-Za-z_][A-Za-z0-9_]*)",
                text,
            ):
                body_start = text.find("{", match.end())
                body_end = find_matching_brace(text, body_start) if body_start >= 0 else match.end()
                tests[match.group(1)] = {
                    "file": path.relative_to(TARGET).as_posix(),
                    "body": text[body_start : body_end + 1] if body_start >= 0 else "",
                }
    return tests


def write_required(cases: list[dict[str, str]]) -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)
    with REQUIRED.open("w", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=["case_id", "source_file", "c_test"], delimiter="\t")
        writer.writeheader()
        writer.writerows(cases)


def read_coverage() -> list[dict[str, str]]:
    if not COVERAGE.is_file():
        fail(f"missing coverage map: {COVERAGE}")
    with COVERAGE.open(newline="") as fh:
        reader = csv.DictReader(fh, delimiter="\t")
        required_fields = {
            "case_id",
            "source_file",
            "c_test",
            "rust_test",
            "rust_file",
            "oracle",
            "evidence",
        }
        if not reader.fieldnames or not required_fields.issubset(set(reader.fieldnames)):
            fail(
                "coverage map must have columns: "
                "case_id, source_file, c_test, rust_test, rust_file, oracle, evidence"
            )
        return list(reader)


def rust_name_matches(c_test: str, rust_test: str) -> bool:
    normalized = c_test.removeprefix("test_")
    return c_test in rust_test or normalized in rust_test


def is_acceptance_file(path: str) -> bool:
    return path.startswith("tests/c_") and path.endswith("_cases.rs")


def body_has_real_assertion(body: str) -> bool:
    if "assert!(true)" in body.replace(" ", ""):
        return False
    return bool(
        re.search(r"\b(assert|assert_eq|assert_ne)\s*!", body)
        or re.search(r"\bmatches\s*!", body)
    )


def body_line_count(body: str) -> int:
    return sum(1 for line in body.splitlines() if line.strip())


def is_concrete_text(text: str) -> bool:
    if len(text.strip()) < 24:
        return False
    return not re.search(r"\b(TODO|fake|placeholder|name only|TBD)\b", text, re.I)


def verify() -> int:
    cases = extract_c_cases()
    write_required(cases)
    rust_tests = extract_rust_tests()
    rows = read_coverage()

    required_by_id = {case["case_id"]: case for case in cases}
    rows_by_case: dict[str, list[dict[str, str]]] = {}
    failures: list[str] = []
    used_rust_tests: dict[str, str] = {}

    for row in rows:
        case_id = row.get("case_id", "").strip()
        rows_by_case.setdefault(case_id, []).append(row)

    for case_id, case in required_by_id.items():
        matches = rows_by_case.get(case_id, [])
        if not matches:
            failures.append(f"missing coverage row for {case_id}")
            continue
        if len(matches) > 1:
            failures.append(f"duplicate coverage rows for {case_id}")
            continue
        row = matches[0]
        rust_test = row["rust_test"].strip()
        rust_file = row["rust_file"].strip()
        oracle = row["oracle"].strip()
        evidence = row["evidence"].strip()
        if not rust_test:
            failures.append(f"{case_id}: empty rust_test")
            continue
        if rust_test not in rust_tests:
            failures.append(f"{case_id}: rust_test not found in #[test] functions: {rust_test}")
            continue
        actual = rust_tests[rust_test]
        if rust_file != actual["file"]:
            failures.append(f"{case_id}: rust_file {rust_file} does not match actual location {actual['file']}")
        if not is_acceptance_file(actual["file"]):
            failures.append(f"{case_id}: rust_test must live in tests/c_*_cases.rs, got {actual['file']}")
        if case_id not in actual["body"]:
            failures.append(f"{case_id}: rust_test body must cite the exact C case id")
        if not body_has_real_assertion(actual["body"]):
            failures.append(f"{case_id}: rust_test must contain a real assertion")
        if body_line_count(actual["body"]) < 8:
            failures.append(f"{case_id}: rust_test body is too small for a C-derived acceptance case")
        if not rust_name_matches(case["c_test"], rust_test):
            failures.append(
                f"{case_id}: rust_test name must include `{case['c_test']}` or its normalized form"
            )
        if rust_test in used_rust_tests:
            failures.append(f"{case_id}: rust_test also used by {used_rust_tests[rust_test]}: {rust_test}")
        used_rust_tests[rust_test] = case_id
        if not is_concrete_text(oracle):
            failures.append(f"{case_id}: oracle must cite concrete C source, macro, trace, or probe evidence")
        if not is_concrete_text(evidence):
            failures.append(f"{case_id}: evidence must be concrete and non-placeholder")

    extra_cases = sorted(case_id for case_id in rows_by_case if case_id and case_id not in required_by_id)
    for case_id in extra_cases:
        failures.append(f"coverage row references unknown C case: {case_id}")

    SUMMARY.write_text(
        "\n".join(
            [
                "# C Test Coverage Check",
                "",
                f"- Required C TEST_RUN occurrences: {len(cases)}",
                f"- Rust #[test] functions: {len(rust_tests)}",
                f"- Coverage rows: {len(rows)}",
                "- Acceptance file rule: `tests/c_*_cases.rs`",
                f"- Status: {'FAILED' if failures else 'PASSED'}",
                "",
                "## Failures",
                "",
                *(f"- {failure}" for failure in failures),
                "",
            ]
        )
    )

    if failures:
        print("C_COVERAGE_CHECK_FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("C_COVERAGE_CHECK_PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--write-required", action="store_true")
    args = parser.parse_args()

    cases = extract_c_cases()
    write_required(cases)
    if args.write_required:
        print(f"wrote {REQUIRED}")
        print(f"required C TEST_RUN occurrences: {len(cases)}")
        return 0
    return verify()


if __name__ == "__main__":
    sys.exit(main())
