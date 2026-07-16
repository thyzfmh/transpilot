#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import pathlib
import re
import sys

from evidence_runner import verify_evidence

TARGET = pathlib.Path.cwd()
SOURCE = (TARGET / "../FlashDB").resolve()
REPORTS = TARGET / "reports"
COMPLIANCE = REPORTS / "c-to-rust-compliance.tsv"
MODULES = REPORTS / "c-module-coverage.tsv"

RULE_IDS = [
    "BASE-01",
    "PROF-01",
    "IMM-01",
    "COV-01",
    "API-01",
    "TDD-01",
    "INT-01",
    "LAY-01",
    "STA-01",
    "PST-01",
    "XIO-01",
    "ABI-01",
    "MEM-01",
    "ERR-01",
    "CBK-01",
    "GLB-01",
    "EVD-01",
    "LOG-01",
    "VER-01",
]

REQUIRED_REPORTS = [
    "source-inventory.md",
    "layout-probe.md",
    "progress.md",
    "c-test-coverage-required.tsv",
    "c-test-coverage.tsv",
]

RULE_HINTS = {
    "BASE-01": ("source_guard.py", "config_profile_check.py"),
    "PROF-01": ("config_profile_check.py",),
    "IMM-01": ("source_guard.py",),
    "COV-01": ("api_surface_check.py", "c_coverage_check.py"),
    "API-01": ("api_surface_check.py", "c_link_test.sh", "c_interop_test.sh"),
    "TDD-01": ("c_coverage_check.py",),
    "INT-01": ("layout", "config_profile_check.py"),
    "LAY-01": ("c_interop_test.sh", "layout"),
    "STA-01": ("c_link_test.sh", "c_interop_test.sh"),
    "PST-01": ("c_interop_test.sh",),
    "XIO-01": ("c_interop_test.sh",),
    "ABI-01": ("api_surface_check.py", "c_link_test.sh"),
    "MEM-01": ("rust_policy_check.py",),
    "ERR-01": ("c_link_test.sh", "api_surface_check.py"),
    "CBK-01": ("api_surface_check.py", "c_interop_test.sh"),
    "GLB-01": ("rust_policy_check.py", "c_interop_test.sh"),
    "EVD-01": ("c_coverage_check.py", "api_surface_check.py", "translation_spec_check.py"),
    "LOG-01": ("trace_capture.py",),
    "VER-01": ("final_verify.sh", "build_check.sh"),
}


def fail(message: str) -> None:
    print(f"[translation_spec_check] FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def source_modules() -> list[str]:
    source_dir = SOURCE / "src"
    if not source_dir.is_dir():
        fail(f"missing C source directory: {source_dir}")
    modules = [path.relative_to(SOURCE).as_posix() for path in sorted(source_dir.rglob("*.c"))]
    if not modules:
        fail("no C source modules found")
    return modules


def read_tsv(path: pathlib.Path, fields: list[str]) -> list[dict[str, str]]:
    if not path.is_file():
        fail(f"missing report: {path}")
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if reader.fieldnames != fields:
            fail(f"{path} must have columns in this order: {', '.join(fields)}")
        return list(reader)


def write_tsv(path: pathlib.Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def reconcile_rows(
    path: pathlib.Path,
    fields: list[str],
    key: str,
    required: list[dict[str, str]],
) -> None:
    existing: dict[str, dict[str, str]] = {}
    if path.exists():
        for row in read_tsv(path, fields):
            row_key = row[key].strip()
            if row_key and row_key not in existing:
                existing[row_key] = row
    rows = []
    for default in required:
        row = existing.get(default[key], default)
        rows.append({field: row.get(field, default.get(field, "")) for field in fields})
    write_tsv(path, fields, rows)


def initialize() -> int:
    REPORTS.mkdir(parents=True, exist_ok=True)

    reconcile_rows(
        COMPLIANCE,
        ["rule_id", "status", "evidence"],
        "rule_id",
        [{"rule_id": rule_id, "status": "PENDING", "evidence": ""} for rule_id in RULE_IDS],
    )

    reconcile_rows(
        MODULES,
        ["c_file", "c_symbols", "rust_files", "rust_tests", "evidence", "status"],
        "c_file",
        [
            {
                "c_file": module,
                "c_symbols": "",
                "rust_files": "",
                "rust_tests": "",
                "evidence": "",
                "status": "PENDING",
            }
            for module in source_modules()
        ],
    )

    print(f"initialized {COMPLIANCE}")
    print(f"initialized {MODULES}")
    return 0


def split_values(text: str) -> list[str]:
    return [value.strip() for value in text.split(";") if value.strip()]


def check_evidence(text: str, hints: tuple[str, ...]) -> list[str]:
    references = split_values(text)
    if not references:
        return ["at least one structured evidence record is required"]
    failures = []
    for reference in references:
        try:
            verify_evidence(TARGET, reference, hints)
        except (OSError, ValueError) as exc:
            failures.append(str(exc))
    return failures


def rust_test_names() -> set[str]:
    names: set[str] = set()
    for root_name in ["src", "tests"]:
        root = TARGET / root_name
        if not root.exists():
            continue
        for path in root.rglob("*.rs"):
            text = path.read_text(errors="replace")
            names.update(re.findall(r"#\s*\[\s*test\s*\][\s\S]{0,200}?\bfn\s+([A-Za-z_][A-Za-z0-9_]*)", text))
    return names


def verify_reports(failures: list[str], allow_missing: bool) -> None:
    minimum_sizes = {
        "source-inventory.md": 100,
        "layout-probe.md": 100,
        "progress.md": 20,
        "c-test-coverage-required.tsv": 20,
        "c-test-coverage.tsv": 20,
    }
    for name in REQUIRED_REPORTS:
        path = REPORTS / name
        if not path.is_file() and allow_missing:
            continue
        if not path.is_file() or path.stat().st_size < minimum_sizes[name]:
            failures.append(f"required report is missing or too small: reports/{name}")

    traces = REPORTS / "c-oracle-traces"
    traces_present = traces.is_dir() and any(
        path.is_file() and path.stat().st_size > 0 for path in traces.rglob("*")
    )
    if not traces_present and not allow_missing:
        failures.append("reports/c-oracle-traces must contain at least one non-empty C oracle trace")


def verify_compliance(failures: list[str], allow_pending: bool) -> None:
    rows = read_tsv(COMPLIANCE, ["rule_id", "status", "evidence"])
    by_id: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        by_id.setdefault(row["rule_id"].strip(), []).append(row)

    for rule_id in RULE_IDS:
        matches = by_id.get(rule_id, [])
        if len(matches) != 1:
            failures.append(f"{rule_id}: expected exactly one compliance row")
            continue
        row = matches[0]
        status = row["status"].strip()
        if allow_pending and status == "PENDING":
            continue
        if status != "PASS":
            failures.append(f"{rule_id}: status must be PASS")
        for error in check_evidence(row["evidence"], RULE_HINTS[rule_id]):
            failures.append(f"{rule_id}: {error}")

    for rule_id in sorted(set(by_id) - set(RULE_IDS)):
        failures.append(f"unknown compliance rule id: {rule_id}")


def verify_modules(failures: list[str], allow_pending: bool) -> None:
    fields = ["c_file", "c_symbols", "rust_files", "rust_tests", "evidence", "status"]
    rows = read_tsv(MODULES, fields)
    expected = set(source_modules())
    by_file: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        by_file.setdefault(row["c_file"].strip(), []).append(row)

    tests = rust_test_names()
    for c_file in sorted(expected):
        matches = by_file.get(c_file, [])
        if len(matches) != 1:
            failures.append(f"{c_file}: expected exactly one module coverage row")
            continue
        row = matches[0]
        status = row["status"].strip()
        if allow_pending and status == "PENDING":
            continue
        if status != "PASS":
            failures.append(f"{c_file}: status must be PASS")
        c_symbols = split_values(row["c_symbols"])
        if not c_symbols:
            failures.append(f"{c_file}: list concrete C symbols")
        else:
            c_text = (SOURCE / c_file).read_text(errors="replace")
            for symbol in c_symbols:
                if not re.search(rf"\b{re.escape(symbol)}\b", c_text):
                    failures.append(f"{c_file}: C symbol not found in source: {symbol}")

        rust_files = split_values(row["rust_files"])
        if not rust_files:
            failures.append(f"{c_file}: rust_files must not be empty")
        for rust_file in rust_files:
            path = TARGET / rust_file
            if not rust_file.startswith("src/") or path.suffix != ".rs" or not path.is_file():
                failures.append(f"{c_file}: Rust source does not exist: {rust_file}")

        module_tests = split_values(row["rust_tests"])
        if not module_tests:
            failures.append(f"{c_file}: rust_tests must not be empty")
        for test in module_tests:
            if test not in tests:
                failures.append(f"{c_file}: Rust test function not found: {test}")

        for error in check_evidence(
            row["evidence"], ("c_coverage_check.py", "c_link_test.sh", "c_interop_test.sh")
        ):
            failures.append(f"{c_file}: {error}")

    for c_file in sorted(set(by_file) - expected):
        failures.append(f"module coverage references unknown C source: {c_file}")


def verify_static_mut(failures: list[str]) -> None:
    pattern = re.compile(r"\bstatic\s+mut\b")
    for path in sorted((TARGET / "src").rglob("*.rs")):
        text = re.sub(r"/\*.*?\*/", "", path.read_text(errors="replace"), flags=re.S)
        text = re.sub(r"(?m)//.*$", "", text)
        if pattern.search(text):
            failures.append(f"{path.relative_to(TARGET)}: static mut is forbidden by MEM-01")


def verify(allow_pending: bool = False) -> int:
    failures: list[str] = []
    verify_reports(failures, allow_missing=allow_pending)
    verify_compliance(failures, allow_pending)
    verify_modules(failures, allow_pending)
    verify_static_mut(failures)

    if failures:
        print("TRANSLATION_SPEC_CHECK_FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1

    status = "PROGRESS" if allow_pending else "FINAL"
    print(f"TRANSLATION_SPEC_CHECK_{status}_PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--init", action="store_true")
    parser.add_argument("--progress", action="store_true")
    args = parser.parse_args()
    if args.init:
        return initialize()
    return verify(allow_pending=args.progress)


if __name__ == "__main__":
    sys.exit(main())
