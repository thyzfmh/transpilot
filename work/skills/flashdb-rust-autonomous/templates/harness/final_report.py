#!/usr/bin/env python3
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

from adapter import load_adapter
from evidence_runner import requirements
from run_identity import current_identity, identity_token
from source_acceptance import SCHEMA as ACCEPTANCE_SCHEMA


def main() -> int:
    target = pathlib.Path.cwd().resolve()
    checkpoint = subprocess.run(
        [sys.executable, "harness/checkpoint.py", "verify-final"],
        cwd=target,
        capture_output=True,
        text=True,
        check=False,
    )
    if checkpoint.returncode != 0:
        raise ValueError(checkpoint.stderr.strip() or checkpoint.stdout.strip())
    acceptance = json.loads((target / "reports/source-acceptance.json").read_text())
    if acceptance.get("schema") != ACCEPTANCE_SCHEMA:
        raise ValueError("source acceptance schema mismatch")
    total = int(acceptance.get("total", 0))
    passed = int(acceptance.get("passed", -1))
    if total <= 0 or passed != total:
        raise ValueError("source acceptance is incomplete")
    oracle = json.loads((target / "reports/source-oracle.json").read_text())
    oracle_total = int(oracle.get("total", 0))
    oracle_passed = int(oracle.get("passed", -1))
    if (
        oracle.get("schema") != ACCEPTANCE_SCHEMA
        or oracle_total <= 0
        or oracle_passed != oracle_total
    ):
        raise ValueError("source oracle baseline is incomplete")
    identity = current_identity(target)
    adapter = load_adapter(target)
    capabilities = adapter.get("capabilities")
    if not isinstance(capabilities, dict):
        raise ValueError("adapter capabilities are missing")
    artifact = identity["artifact"]
    capability_lines = []
    if capabilities.get("public_c_abi") is True:
        capability_lines.append("- C ABI signatures: PASSED")
    if capabilities.get("layout_contract") is True:
        capability_lines.append("- C/Rust layout contracts: PASSED")
    if capabilities.get("source_target_differential") is True:
        capability_lines.append("- Source/target behavioral and side-effect differential: PASSED")
    report = target / "reports/final-report.md"
    report.write_text(
        "\n".join(
            [
                "# Final Verification Report",
                "",
                "- Status: PASSED",
                f"- Run identity: `{identity_token(identity)}`",
                f"- Source-native tests: {passed}/{total} PASSED",
                f"- Original source baseline: {oracle_passed}/{oracle_total} PASSED",
                f"- Target artifact: {artifact['path']}",
                f"- Artifact SHA-256: `{artifact['sha256']}`",
                f"- Verified evidence records: {len(requirements(target))}",
                f"- Applicable capabilities: {', '.join(sorted(key for key, value in capabilities.items() if value is True))}",
                *capability_lines,
                "- Translation contracts: PASSED",
                "- Rust safety policy: PASSED",
                "",
            ]
        )
    )
    print("FINAL_REPORT_PASS")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"FINAL_REPORT_FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
