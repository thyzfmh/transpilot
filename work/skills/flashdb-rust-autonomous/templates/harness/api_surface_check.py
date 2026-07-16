#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import pathlib
import re
import subprocess
import sys

from evidence_runner import verify_evidence

TARGET = pathlib.Path.cwd()
SOURCE = (TARGET / "../FlashDB").resolve()
REPORTS = TARGET / "reports"
REQUIRED = REPORTS / "c-api-required.tsv"
COVERAGE = REPORTS / "c-api-coverage.tsv"
SUMMARY = REPORTS / "c-api-coverage-check.md"
FIELDS = ["kind", "name", "rust_symbol", "rust_test", "evidence", "status"]


def fail(message: str) -> None:
    print(f"[api_surface_check] FAIL: {message}", file=sys.stderr)
    raise SystemExit(1)


def strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"(?m)//.*$", "", text)


def required_items() -> list[dict[str, str]]:
    public_header = SOURCE / "inc/flashdb.h"
    definitions = SOURCE / "inc/fdb_def.h"
    if not public_header.is_file() or not definitions.is_file():
        fail("missing FlashDB public headers")

    public_text = strip_comments(public_header.read_text(errors="replace"))
    functions = sorted(set(re.findall(r"\b(fdb_[A-Za-z0-9_]+)\s*\(", public_text)))
    control_text = strip_comments(definitions.read_text(errors="replace"))
    controls = sorted(
        set(re.findall(r"(?m)^\s*#define\s+(FDB_(?:KVDB|TSDB)_CTRL_[A-Z0-9_]+)\b", control_text))
    )
    if not functions or not controls:
        fail("could not extract public functions or control commands")
    return [
        *({"kind": "function", "name": name, "source": "inc/flashdb.h"} for name in functions),
        *({"kind": "control", "name": name, "source": "inc/fdb_def.h"} for name in controls),
    ]


def write_required(items: list[dict[str, str]]) -> None:
    REPORTS.mkdir(parents=True, exist_ok=True)
    with REQUIRED.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["kind", "name", "source"], delimiter="\t")
        writer.writeheader()
        writer.writerows(items)


def read_rows() -> list[dict[str, str]]:
    if not COVERAGE.is_file():
        return []
    with COVERAGE.open(newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        if reader.fieldnames != FIELDS:
            fail(f"{COVERAGE} must have columns in this order: {', '.join(FIELDS)}")
        return list(reader)


def write_rows(rows: list[dict[str, str]]) -> None:
    with COVERAGE.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def initialize(items: list[dict[str, str]]) -> int:
    existing = {(row["kind"].strip(), row["name"].strip()): row for row in read_rows()}
    rows = []
    for item in items:
        key = (item["kind"], item["name"])
        rows.append(
            existing.get(
                key,
                {
                    "kind": item["kind"],
                    "name": item["name"],
                    "rust_symbol": item["name"] if item["kind"] == "function" else item["name"],
                    "rust_test": "",
                    "evidence": "",
                    "status": "PENDING",
                },
            )
        )
    write_rows(rows)
    print(f"initialized {COVERAGE} with {len(rows)} public API items")
    return 0


def rust_tests() -> set[str]:
    names: set[str] = set()
    pattern = re.compile(
        r"#\s*\[\s*test\s*\]\s*(?:\n\s*#\[[^\]]+\]\s*)*\n\s*fn\s+([A-Za-z_][A-Za-z0-9_]*)"
    )
    for root_name in ["src", "tests"]:
        root = TARGET / root_name
        if root.is_dir():
            for path in root.rglob("*.rs"):
                names.update(pattern.findall(path.read_text(errors="replace")))
    return names


def exported_symbols() -> str:
    archive = TARGET / "target/release/libflashdb_rust.a"
    if not archive.is_file() or archive.stat().st_size == 0:
        fail(f"missing release static library: {archive}")
    process = subprocess.run(
        ["nm", "-g", "--defined-only", str(archive)],
        capture_output=True,
        text=True,
    )
    if process.returncode != 0:
        fail(f"GNU nm failed: {process.stderr.strip()}")
    return process.stdout


def source_text() -> str:
    return "\n".join(path.read_text(errors="replace") for path in sorted((TARGET / "src").rglob("*.rs")))


def c_runtime_call_text() -> str:
    paths = list(sorted((SOURCE / "tests").rglob("*.c")))
    paths.append(TARGET / "harness/interop/interop_driver.c")
    return "\n".join(path.read_text(errors="replace") for path in paths if path.is_file())


def verify(allow_pending: bool) -> int:
    items = required_items()
    write_required(items)
    rows = read_rows()
    required = {(item["kind"], item["name"]): item for item in items}
    by_key: dict[tuple[str, str], list[dict[str, str]]] = {}
    for row in rows:
        by_key.setdefault((row["kind"].strip(), row["name"].strip()), []).append(row)

    tests = rust_tests()
    pass_function_exists = any(
        row["status"].strip() == "PASS" and row["kind"].strip() == "function" for row in rows
    )
    symbols = exported_symbols() if pass_function_exists or not allow_pending else ""
    rust_source = source_text()
    runtime_calls = c_runtime_call_text()
    failures: list[str] = []
    pending = 0
    for key, item in required.items():
        matches = by_key.get(key, [])
        if len(matches) != 1:
            failures.append(f"{item['kind']} {item['name']}: expected exactly one coverage row")
            continue
        row = matches[0]
        status = row["status"].strip()
        if allow_pending and status == "PENDING":
            pending += 1
            continue
        if status != "PASS":
            failures.append(f"{item['kind']} {item['name']}: status must be PASS")
            continue

        rust_symbol = row["rust_symbol"].strip()
        if rust_symbol != item["name"]:
            failures.append(f"{item['name']}: rust_symbol must preserve the public C name")
        if item["kind"] == "function":
            if not re.search(rf"(?m)(?:^|\s)_?{re.escape(item['name'])}(?:$|\s)", symbols):
                failures.append(f"{item['name']}: symbol not exported by libflashdb_rust.a")
            if not re.search(rf"\b{re.escape(item['name'])}\s*\(", runtime_calls):
                failures.append(f"{item['name']}: no C runtime test call found")
        elif not re.search(rf"\b{re.escape(item['name'])}\b", rust_source):
            failures.append(f"{item['name']}: control constant not present in production Rust source")
        elif not re.search(rf"\b{re.escape(item['name'])}\b", runtime_calls):
            failures.append(f"{item['name']}: no C runtime test use found")

        test_name = row["rust_test"].strip()
        if test_name not in tests:
            failures.append(f"{item['name']}: Rust test function not found: {test_name}")
        references = [value.strip() for value in row["evidence"].split(";") if value.strip()]
        if not references:
            failures.append(f"{item['name']}: structured evidence is required")
        for reference in references:
            try:
                verify_evidence(
                    TARGET,
                    reference,
                    ("api_surface_check.py", "c_link_test.sh", "c_interop_test.sh"),
                )
            except (OSError, ValueError) as exc:
                failures.append(f"{item['name']}: {exc}")

    for key in sorted(set(by_key) - set(required)):
        failures.append(f"coverage row references unknown API item: {key[0]} {key[1]}")

    SUMMARY.write_text(
        "\n".join(
            [
                "# C API Surface Check",
                "",
                f"- Required items: {len(required)}",
                f"- Pending items: {pending}",
                f"- Status: {'FAILED' if failures else ('IN_PROGRESS' if pending else 'PASSED')}",
                "",
                "## Failures",
                "",
                *(f"- {failure}" for failure in failures),
                "",
            ]
        )
    )
    if failures:
        print("C_API_SURFACE_CHECK_FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("C_API_SURFACE_PROGRESS_PASS" if pending else "C_API_SURFACE_CHECK_PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--init", action="store_true")
    parser.add_argument("--progress", action="store_true")
    args = parser.parse_args()
    items = required_items()
    write_required(items)
    if args.init:
        return initialize(items)
    return verify(allow_pending=args.progress)


if __name__ == "__main__":
    sys.exit(main())
