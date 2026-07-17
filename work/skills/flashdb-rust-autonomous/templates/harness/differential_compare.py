#!/usr/bin/env python3
from __future__ import annotations

import json
import pathlib
import sys
from typing import Any

from adapter import load_adapter, require_list
from run_identity import require_identity
from run_identity import sha256 as file_sha256
from runtime_snapshot import SCHEMA as SNAPSHOT_SCHEMA
from source_acceptance import SCHEMA as ACCEPTANCE_SCHEMA


def load_json(path: pathlib.Path) -> dict[str, Any]:
    if not path.is_file():
        raise ValueError(f"required differential input is missing: {path}")
    data = json.loads(path.read_text())
    if not isinstance(data, dict):
        raise ValueError(f"differential input is not an object: {path}")
    return data


def acceptance_cases(target: pathlib.Path, name: str) -> list[tuple[str, str]]:
    data = load_json(target / "reports" / name)
    if data.get("schema") != ACCEPTANCE_SCHEMA:
        raise ValueError(f"acceptance schema mismatch: {name}")
    require_identity(data.get("identity"), target)
    total = int(data.get("total", 0))
    if (
        total <= 0
        or int(data.get("passed", -1)) != total
        or int(data.get("failed", -1)) != 0
        or int(data.get("not_run", -1)) != 0
    ):
        raise ValueError(f"acceptance is incomplete: {name}")
    cases = data.get("cases")
    if not isinstance(cases, list) or not all(isinstance(case, dict) for case in cases):
        raise ValueError(f"acceptance cases are invalid: {name}")
    return [(str(case.get("case_id", "")), str(case.get("status", ""))) for case in cases]


def snapshot(target: pathlib.Path, implementation: str, suite: str) -> dict[str, Any]:
    data = load_json(
        target / "reports/runtime-snapshots" / implementation / f"{suite}.json"
    )
    if (
        data.get("schema") != SNAPSHOT_SCHEMA
        or data.get("suite") != suite
        or data.get("implementation") != implementation
    ):
        raise ValueError(f"runtime snapshot metadata is invalid: {implementation}/{suite}")
    require_identity(data.get("identity"), target)
    changed = data.get("changed")
    deleted = data.get("deleted")
    if (
        not isinstance(changed, list)
        or not all(isinstance(item, dict) for item in changed)
        or not isinstance(deleted, list)
        or not all(isinstance(item, str) for item in deleted)
    ):
        raise ValueError(f"runtime snapshot payload is invalid: {implementation}/{suite}")
    changed_map: dict[str, dict[str, Any]] = {}
    for item in changed:
        relative = str(item.get("path", ""))
        if (
            not relative
            or pathlib.Path(relative).is_absolute()
            or ".." in pathlib.Path(relative).parts
            or relative in changed_map
        ):
            raise ValueError(
                f"runtime snapshot path is invalid: {implementation}/{suite}/{relative}"
            )
        copied = (
            target
            / "reports/runtime-snapshots"
            / implementation
            / f"{suite}-files"
            / relative
        )
        if (
            not copied.is_file()
            or copied.stat().st_size != item.get("bytes")
            or file_sha256(copied) != item.get("sha256")
        ):
            raise ValueError(
                f"runtime snapshot content is invalid: {implementation}/{suite}/{relative}"
            )
        changed_map[relative] = {
            "sha256": item.get("sha256"),
            "bytes": item.get("bytes"),
            "file": copied,
        }
    files_root = (
        target
        / "reports/runtime-snapshots"
        / implementation
        / f"{suite}-files"
    )
    copied_paths = (
        {
            path.relative_to(files_root).as_posix()
            for path in files_root.rglob("*")
            if path.is_file()
        }
        if files_root.is_dir()
        else set()
    )
    if copied_paths != set(changed_map):
        raise ValueError(
            f"runtime snapshot file set is invalid: {implementation}/{suite}"
        )
    return {"changed": changed_map, "deleted": sorted(deleted)}


def compare_suite(
    source_runs: list[dict[str, Any]],
    translated: dict[str, Any],
) -> tuple[list[str], int, int]:
    failures: list[str] = []
    source_changed_sets = [set(run["changed"]) for run in source_runs]
    source_deleted_sets = [set(run["deleted"]) for run in source_runs]
    expected_changed = source_changed_sets[0]
    expected_deleted = source_deleted_sets[0]
    if any(paths != expected_changed for paths in source_changed_sets[1:]):
        failures.append("source side-effect file set is not repeatable")
    if any(paths != expected_deleted for paths in source_deleted_sets[1:]):
        failures.append("source deleted-file set is not repeatable")
    if set(translated["changed"]) != expected_changed:
        failures.append("target changed-file set differs from source")
    if set(translated["deleted"]) != expected_deleted:
        failures.append("target deleted-file set differs from source")
    if failures:
        return failures, 0, 0

    stable_bytes = 0
    variable_bytes = 0
    for relative in sorted(expected_changed):
        source_payloads = [
            run["changed"][relative]["file"].read_bytes() for run in source_runs
        ]
        target_payload = translated["changed"][relative]["file"].read_bytes()
        source_sizes = {len(payload) for payload in source_payloads}
        if len(source_sizes) != 1:
            failures.append(f"{relative}: source file size is not repeatable")
            continue
        expected_size = len(source_payloads[0])
        if len(target_payload) != expected_size:
            failures.append(
                f"{relative}: target size {len(target_payload)} != source {expected_size}"
            )
            continue
        mismatches = 0
        for index, expected in enumerate(source_payloads[0]):
            if all(payload[index] == expected for payload in source_payloads[1:]):
                stable_bytes += 1
                if target_payload[index] != expected:
                    mismatches += 1
            else:
                variable_bytes += 1
        if mismatches:
            failures.append(f"{relative}: {mismatches} stable bytes differ")
    return failures, stable_bytes, variable_bytes


def main() -> int:
    target = pathlib.Path.cwd().resolve()
    adapter = load_adapter(target)
    oracle_cases = acceptance_cases(target, "source-oracle.json")
    target_cases = acceptance_cases(target, "source-acceptance.json")
    failures: list[str] = []
    if oracle_cases != target_cases:
        failures.append("source and target acceptance case sequences differ")
    repetitions = int(adapter.get("differential_source_repetitions", 2))
    if repetitions < 2:
        raise ValueError("differential_source_repetitions must be at least 2")
    rows = []
    for raw_suite in require_list(adapter, "native_suites"):
        if not isinstance(raw_suite, dict) or not isinstance(raw_suite.get("name"), str):
            raise ValueError("native suite is invalid")
        name = raw_suite["name"]
        source_runs = [
            snapshot(target, f"source-{repetition}", name)
            for repetition in range(1, repetitions + 1)
        ]
        translated = snapshot(target, "target", name)
        suite_failures, stable_bytes, variable_bytes = compare_suite(
            source_runs, translated
        )
        status = "PASS" if not suite_failures else "FAIL"
        failures.extend(f"{name}: {failure}" for failure in suite_failures)
        rows.append(
            {
                "suite": name,
                "status": status,
                "changed_files": len(source_runs[0]["changed"]),
                "deleted_files": len(source_runs[0]["deleted"]),
                "stable_bytes": stable_bytes,
                "variable_bytes": variable_bytes,
            }
        )
    report = target / "reports/differential-report.md"
    report.write_text(
        "\n".join(
            [
                "# Source And Target Differential",
                "",
                f"- Status: {'PASSED' if not failures else 'FAILED'}",
                f"- Acceptance cases compared: {len(oracle_cases)}",
                f"- Source calibration runs per suite: {repetitions}",
                "",
                "## Suites",
                "",
                *(
                    f"- {row['suite']}: {row['status']}; "
                    f"changed={row['changed_files']}; deleted={row['deleted_files']}; "
                    f"stable_bytes={row['stable_bytes']}; "
                    f"variable_bytes={row['variable_bytes']}"
                    for row in rows
                ),
                "",
                "## Failures",
                "",
                *(f"- {failure}" for failure in failures),
                *(["- none"] if not failures else []),
                "",
            ]
        )
    )
    if failures:
        print("DIFFERENTIAL_COMPARE_FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print(f"DIFFERENTIAL_COMPARE_PASS: suites={len(rows)} cases={len(oracle_cases)}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"DIFFERENTIAL_COMPARE_FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
