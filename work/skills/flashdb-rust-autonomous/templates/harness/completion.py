#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import pathlib
import sys
from typing import Any

from evidence_runner import requirements, verify_evidence
from run_identity import current_identity, identity_token, require_identity, sha256
from source_acceptance import SCHEMA as ACCEPTANCE_SCHEMA


SCHEMA = "source-translation-result-v2"
STAGED = "TECHNICAL_GATES_PASSED"
FINAL = "PASSED"
BEGIN = "<!-- machine-result-begin -->"
END = "<!-- machine-result-end -->"


def repo_root(target: pathlib.Path) -> pathlib.Path:
    for candidate in [target.parent, *target.parents]:
        if (candidate / "INSTRUCTION.md").is_file():
            return candidate
    raise ValueError(f"cannot locate repository root from target: {target}")


def checkpoint_verify(target: pathlib.Path) -> None:
    path = target / "reports/checkpoint.json"
    if not path.is_file():
        raise ValueError("checkpoint is missing")
    data = json.loads(path.read_text())
    if (
        data.get("schema") != "source-translation-checkpoint-v3"
        or data.get("stage") != "ready_for_final"
        or data.get("last_exit_code") != 0
    ):
        raise ValueError("checkpoint is not sealed for final completion")
    require_identity(data.get("identity"), target)
    gates: dict[str, str] = {}
    for evidence_id in requirements(target):
        record = verify_evidence(
            target,
            f"reports/evidence/{evidence_id}.json",
            evidence_id,
        )
        gates[evidence_id] = str(record.get("log_sha256"))
    if data.get("gate_evidence") != gates:
        raise ValueError("checkpoint evidence set is stale or incomplete")


def acceptance(target: pathlib.Path) -> dict[str, Any]:
    path = target / "reports/source-acceptance.json"
    if not path.is_file():
        raise ValueError("source acceptance result is missing")
    data = json.loads(path.read_text())
    if data.get("schema") != ACCEPTANCE_SCHEMA:
        raise ValueError("source acceptance schema mismatch")
    require_identity(data.get("identity"), target)
    total = int(data.get("total", 0))
    counts = {
        key: int(data.get(key, -1))
        for key in ["passed", "failed", "not_run", "total"]
    }
    if total <= 0 or counts != {"passed": total, "failed": 0, "not_run": 0, "total": total}:
        raise ValueError(f"source acceptance is incomplete: {counts}")
    return counts


def final_report(target: pathlib.Path) -> pathlib.Path:
    report = target / "reports/final-report.md"
    if not report.is_file() or "- Status: PASSED" not in report.read_text(errors="replace"):
        raise ValueError("machine final report is missing or not PASSED")
    return report


def result_path(target: pathlib.Path) -> pathlib.Path:
    return repo_root(target) / "result/output.md"


def trace_summary(target: pathlib.Path) -> dict[str, Any]:
    manifest_path = repo_root(target) / "logs/trace/trace-manifest.json"
    if not manifest_path.is_file():
        raise ValueError("trace manifest is missing")
    manifest = json.loads(manifest_path.read_text())
    identity = current_identity(target)
    if manifest.get("identity") != identity:
        raise ValueError("trace identity is stale")
    chat = manifest.get("chat")
    artifacts = manifest.get("verification_artifacts")
    if not isinstance(chat, dict) or not isinstance(artifacts, dict):
        raise ValueError("trace manifest is incomplete")
    return {
        "schema": str(manifest.get("schema", "")),
        "session_id": str(manifest.get("session_id", "")),
        "exported_at": str(manifest.get("exported_at", "")),
        "chat_sha256": str(chat.get("sha256", "")),
        "artifact_count": len(artifacts),
    }


def payload_for(
    target: pathlib.Path,
    status: str,
    *,
    include_trace: bool = False,
) -> dict[str, Any]:
    checkpoint_verify(target)
    identity = current_identity(target)
    report = final_report(target)
    payload = {
        "schema": SCHEMA,
        "status": status,
        "identity": identity,
        "identity_token": identity_token(identity),
        "counts": acceptance(target),
        "final_report": {
            "path": report.relative_to(target).as_posix(),
            "sha256": sha256(report),
        },
        "trusted_command": "work/skills/flashdb-rust-autonomous/scripts/final_verify_target.sh",
    }
    if include_trace:
        payload["trace"] = trace_summary(target)
    return payload


def render_result(payload: dict[str, Any]) -> str:
    final = payload["status"] == FINAL
    status_text = "PASSED" if final else STAGED
    counts = payload["counts"]
    artifact = payload["identity"]["artifact"]
    return "\n".join(
        [
            "# Execution Result",
            "",
            f"- Status: {status_text}",
            f"- Source-native tests: {counts['passed']}/{counts['total']} PASSED",
            f"- Target artifact: {artifact['path']}",
            f"- Artifact SHA-256: `{artifact['sha256']}`",
            f"- Run identity: `{payload['identity_token']}`",
            f"- Trusted final verification: {'PASSED' if final else 'PENDING TRACE'}",
            "",
            BEGIN,
            "```json",
            json.dumps(payload, ensure_ascii=False, sort_keys=True),
            "```",
            END,
            "",
        ]
    )


def stage_result(target: pathlib.Path) -> int:
    payload = payload_for(target, STAGED)
    output = result_path(target)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(render_result(payload))
    print(f"RESULT_STAGE_PASS: {output}")
    return 0


def finalize_result(target: pathlib.Path) -> int:
    staged = read_result(target, {STAGED})
    expected = payload_for(target, STAGED)
    if staged != expected:
        raise ValueError("staged result is stale")
    trace = repo_root(target) / "logs/trace"
    copied = trace / "verification/result/output.md"
    manifest = json.loads((trace / "trace-manifest.json").read_text())
    if (
        manifest.get("identity") != expected["identity"]
        or not copied.is_file()
        or copied.read_bytes() != result_path(target).read_bytes()
    ):
        raise ValueError("verified trace does not contain the staged result")
    payload = payload_for(target, FINAL, include_trace=True)
    result_path(target).write_text(render_result(payload))
    print("RESULT_FINALIZE_PASS")
    return 0


def read_result(
    target: pathlib.Path,
    allowed_statuses: set[str] | None = None,
) -> dict[str, Any]:
    output = result_path(target)
    if not output.is_file():
        raise ValueError("result/output.md is missing")
    text = output.read_text()
    if BEGIN not in text or END not in text:
        raise ValueError("result/output.md has no machine result payload")
    block = text.split(BEGIN, 1)[1].split(END, 1)[0]
    match = block.split("```json", 1)
    if len(match) != 2 or "```" not in match[1]:
        raise ValueError("result/output.md machine payload is malformed")
    data = json.loads(match[1].split("```", 1)[0])
    statuses = allowed_statuses or {STAGED, FINAL}
    if data.get("schema") != SCHEMA or data.get("status") not in statuses:
        raise ValueError("result/output.md status or schema is invalid")
    return data


def verify_result(target: pathlib.Path, require_trace: bool) -> int:
    expected = payload_for(target, FINAL, include_trace=require_trace)
    actual = read_result(target, {FINAL})
    if actual != expected:
        raise ValueError("result/output.md is stale or inconsistent with current verification")
    if require_trace:
        repo = repo_root(target)
        manifest_path = repo / "logs/trace/trace-manifest.json"
        if not manifest_path.is_file():
            raise ValueError("trace manifest is missing")
        manifest = json.loads(manifest_path.read_text())
        if manifest.get("identity") != expected["identity"]:
            raise ValueError("trace and result identities differ")
        copied = repo / "logs/trace/verification/result/output.md"
        if not copied.is_file() or sha256(copied) != sha256(result_path(target)):
            raise ValueError("trace does not contain the current result/output.md")
    print("RESULT_VERIFY_PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("stage")
    sub.add_parser("finalize")
    verify = sub.add_parser("verify")
    verify.add_argument("--require-trace", action="store_true")
    args = parser.parse_args()
    target = pathlib.Path.cwd().resolve()
    if args.action == "stage":
        return stage_result(target)
    if args.action == "finalize":
        return finalize_result(target)
    return verify_result(target, args.require_trace)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"COMPLETION_FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
