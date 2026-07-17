#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import pathlib
import re
import sys

from adapter import load_adapter, require_list, source_root
from evidence_runner import requirements, verify_evidence
from project_discovery import SCHEMA as PROFILE_SCHEMA
from run_identity import current_identity, require_identity
from source_acceptance import SCHEMA as ACCEPTANCE_SCHEMA


TARGET = pathlib.Path.cwd().resolve()
ADAPTER = load_adapter(TARGET)
SOURCE = source_root(TARGET, ADAPTER)
REPORTS = TARGET / "reports"
COMPLIANCE = REPORTS / "c-to-rust-compliance.tsv"
MODULES = REPORTS / "c-module-coverage.tsv"

KNOWN_RULES = {
    "BASE-01", "PROF-01", "IMM-01", "COV-01", "API-01", "TDD-01",
    "INT-01", "LAY-01", "STA-01", "PST-01", "XIO-01", "ABI-01",
    "MEM-01", "ERR-01", "CBK-01", "GLB-01", "EVD-01", "LOG-01", "VER-01",
}
RULE_EVIDENCE = {
    "BASE-01": ["final-source", "final-source-oracle"],
    "PROF-01": ["final-profile"],
    "IMM-01": ["final-source"],
    "COV-01": ["final-c-coverage", "final-api"],
    "API-01": ["final-api", "final-c-link"],
    "TDD-01": ["final-source-oracle", "final-c-link", "final-c-coverage"],
    "INT-01": ["final-c-link", "final-api"],
    "LAY-01": ["final-api", "final-differential"],
    "STA-01": ["final-c-link", "final-differential"],
    "PST-01": ["final-differential"],
    "XIO-01": ["final-differential"],
    "ABI-01": ["final-api"],
    "MEM-01": ["final-rust-policy"],
    "ERR-01": ["final-c-link", "final-api"],
    "CBK-01": ["final-api", "final-differential"],
    "GLB-01": ["final-rust-policy", "final-differential"],
    "EVD-01": ["final-source", "final-c-link", "final-api"],
    "LOG-01": ["final-c-link"],
    "VER-01": [],
}


def write_tsv(path: pathlib.Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def applicable_rules() -> list[str]:
    raw = ADAPTER.get("applicable_contracts")
    if not isinstance(raw, list) or not raw or not all(isinstance(rule, str) for rule in raw):
        raise ValueError("adapter applicable_contracts must be a non-empty string list")
    if len(raw) != len(set(raw)):
        raise ValueError("adapter applicable_contracts contains duplicates")
    unknown = sorted(set(raw) - KNOWN_RULES)
    if unknown:
        raise ValueError(f"adapter contains unknown contract ids: {unknown}")
    return raw


def source_modules() -> list[str]:
    modules = [
        path.relative_to(SOURCE).as_posix()
        for path in sorted((SOURCE / "src").rglob("*.c"))
    ]
    if not modules:
        raise ValueError("no C source modules discovered")
    return modules


def acceptance_complete() -> dict[str, object]:
    path = REPORTS / "source-acceptance.json"
    if not path.is_file():
        raise ValueError("source acceptance result is missing")
    data = json.loads(path.read_text())
    if data.get("schema") != ACCEPTANCE_SCHEMA:
        raise ValueError("source acceptance schema mismatch")
    require_identity(data.get("identity"), TARGET)
    total = int(data.get("total", 0))
    if (
        total <= 0
        or int(data.get("passed", -1)) != total
        or int(data.get("failed", -1)) != 0
        or int(data.get("not_run", -1)) != 0
    ):
        raise ValueError("source-native acceptance is incomplete")
    return data


def verify_project_profile(acceptance: dict[str, object] | None) -> None:
    path = REPORTS / "project-profile.json"
    if not path.is_file():
        raise ValueError("project profile is missing")
    profile = json.loads(path.read_text())
    identity = current_identity(TARGET)
    if (
        profile.get("schema") != PROFILE_SCHEMA
        or pathlib.Path(str(profile.get("source_root", ""))).resolve() != SOURCE.resolve()
        or profile.get("adapter_sha256") != identity["adapter_sha256"]
        or profile.get("oracle_source_hash") != identity["source_hash"]
    ):
        raise ValueError("project profile is stale or not bound to the current adapter/source")
    test_files = profile.get("test_files")
    if not isinstance(test_files, list):
        raise ValueError("project profile test inventory is invalid")
    discovered = []
    for item in test_files:
        if not isinstance(item, dict) or not isinstance(item.get("tests"), list):
            continue
        occurrences: dict[str, int] = {}
        for name in item["tests"]:
            occurrences[str(name)] = occurrences.get(str(name), 0) + 1
            discovered.append(
                f"{item.get('path')}::{name}#{occurrences[str(name)]}"
            )
    if len(discovered) != len(set(discovered)):
        raise ValueError("project profile contains duplicate discovered tests")
    if int(profile.get("discovered_test_count", -1)) != len(discovered):
        raise ValueError("project profile discovered test count is inconsistent")
    if acceptance is not None and len(discovered) != int(acceptance.get("total", -1)):
        raise ValueError("project profile test count differs from source acceptance")


def module_contracts() -> dict[str, dict[str, list[str]]]:
    suites = [
        str(suite.get("name"))
        for suite in require_list(ADAPTER, "native_suites")
        if isinstance(suite, dict) and isinstance(suite.get("name"), str)
    ]
    if not suites:
        raise ValueError("cannot derive module contracts without native suites")
    known_evidence = set(requirements(TARGET))
    evidence = [
        evidence_id
        for evidence_id in [
            "final-source-oracle",
            "final-c-link",
            "final-differential",
            "final-api",
        ]
        if evidence_id in known_evidence
    ]
    if not evidence:
        raise ValueError("cannot derive module contracts without behavioral evidence")
    return {
        module: {"suites": suites, "evidence": evidence}
        for module in source_modules()
    }


def verify_static_mut() -> list[str]:
    failures: list[str] = []
    pattern = re.compile(r"\bstatic\s+mut\b")
    for path in sorted((TARGET / "src").rglob("*.rs")):
        text = re.sub(r"/\*.*?\*/", "", path.read_text(errors="replace"), flags=re.S)
        text = re.sub(r"(?m)//.*$", "", text)
        if pattern.search(text):
            failures.append(f"{path.relative_to(TARGET)}: static mut is forbidden")
    return failures


def evidence_status(evidence_id: str, progress: bool) -> tuple[str, str]:
    reference = f"reports/evidence/{evidence_id}.json"
    try:
        verify_evidence(TARGET, reference, evidence_id)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        if progress:
            return "PENDING", str(exc)
        return "FAIL", str(exc)
    return "PASS", reference


def initialize() -> int:
    rules = applicable_rules()
    write_tsv(
        COMPLIANCE,
        ["rule_id", "status", "evidence"],
        [{"rule_id": rule, "status": "PENDING", "evidence": ""} for rule in rules],
    )
    write_tsv(
        MODULES,
        ["c_file", "status", "suites", "evidence"],
        [
            {
                "c_file": module,
                "status": "PENDING",
                "suites": ",".join(contract["suites"]),
                "evidence": "",
            }
            for module, contract in module_contracts().items()
        ],
    )
    print(f"TRANSLATION_METHOD_INIT_PASS: rules={len(rules)} modules={len(source_modules())}")
    return 0


def verify(progress: bool) -> int:
    failures: list[str] = []
    acceptance: dict[str, object] | None = None
    if not progress:
        acceptance = acceptance_complete()
    required_reports = ["project-profile.json", "source-inventory.md", "config-profile.md", "layout-probe.md"]
    for name in required_reports:
        path = REPORTS / name
        if not path.is_file() or path.stat().st_size == 0:
            failures.append(f"missing generated project artifact: reports/{name}")
    try:
        verify_project_profile(acceptance)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        if not progress:
            failures.append(str(exc))

    evidence_cache: dict[str, tuple[str, str]] = {}
    rows: list[dict[str, str]] = []
    for rule in applicable_rules():
        evidence_ids = (
            [evidence_id for evidence_id in requirements(TARGET) if evidence_id != "final-spec"]
            if rule == "VER-01"
            else RULE_EVIDENCE[rule]
        )
        statuses = []
        details = []
        for evidence_id in evidence_ids:
            evidence_cache.setdefault(evidence_id, evidence_status(evidence_id, progress))
            status, detail = evidence_cache[evidence_id]
            statuses.append(status)
            details.append(f"{evidence_id}={detail}")
        if "FAIL" in statuses:
            status = "FAIL"
        elif "PENDING" in statuses:
            status = "PENDING"
        else:
            status = "PASS"
        rows.append({"rule_id": rule, "status": status, "evidence": "; ".join(details)})
        if status == "FAIL" or (status == "PENDING" and not progress):
            failures.append(f"{rule}: {rows[-1]['evidence']}")

    static_failures = verify_static_mut()
    failures.extend(static_failures)
    acceptance_suites = {}
    if acceptance is not None:
        acceptance_suites = {
            str(suite.get("name")): suite
            for suite in acceptance.get("suites", [])
            if isinstance(suite, dict)
        }
    module_rows: list[dict[str, str]] = []
    for module, contract in module_contracts().items():
        statuses = []
        details = []
        suite_details = []
        for suite_name in contract["suites"]:
            suite = acceptance_suites.get(suite_name)
            suite_pass = (
                suite is not None
                and suite.get("protocol_complete") is True
                and int(suite.get("total", 0)) > 0
                and int(suite.get("passed", -1)) == int(suite.get("total", 0))
                and int(suite.get("exit_code", -1)) == 0
            )
            statuses.append("PASS" if suite_pass else ("PENDING" if progress else "FAIL"))
            suite_details.append(
                f"{suite_name}={'PASS' if suite_pass else ('PENDING' if progress else 'FAIL')}"
            )
        for evidence_id in contract["evidence"]:
            evidence_cache.setdefault(evidence_id, evidence_status(evidence_id, progress))
            status, detail = evidence_cache[evidence_id]
            statuses.append(status)
            details.append(f"{evidence_id}={detail}")
        status = "PASS" if all(value == "PASS" for value in statuses) else (
            "PENDING" if progress and "FAIL" not in statuses else "FAIL"
        )
        module_rows.append(
            {
                "c_file": module,
                "status": status,
                "suites": "; ".join(suite_details),
                "evidence": "; ".join(details),
            }
        )
        if status == "FAIL":
            failures.append(f"{module}: module contract evidence is incomplete")

    write_tsv(COMPLIANCE, ["rule_id", "status", "evidence"], rows)
    write_tsv(MODULES, ["c_file", "status", "suites", "evidence"], module_rows)
    if failures:
        print("TRANSLATION_SPEC_CHECK_FAIL")
        for failure in failures[:12]:
            print(f"- {failure}")
        return 1
    marker = "PROGRESS" if progress else "FINAL"
    print(f"TRANSLATION_SPEC_CHECK_{marker}_PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--init", action="store_true")
    parser.add_argument("--progress", action="store_true")
    args = parser.parse_args()
    if args.init:
        return initialize()
    return verify(args.progress)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"TRANSLATION_SPEC_CHECK_FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
