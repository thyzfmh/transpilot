#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re
import subprocess
import sys
from typing import Any

from adapter import load_adapter
from run_identity import current_identity, require_identity, sha256


SCHEMA = "source-translation-evidence-v2"
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")


def evidence_dir(target: pathlib.Path) -> pathlib.Path:
    path = target / "reports/evidence"
    path.mkdir(parents=True, exist_ok=True)
    return path


def requirements(target: pathlib.Path) -> dict[str, list[str]]:
    raw = load_adapter(target).get("required_evidence")
    if not isinstance(raw, dict) or not raw:
        raise ValueError("adapter required_evidence is missing")
    result: dict[str, list[str]] = {}
    for evidence_id, command in raw.items():
        if (
            not isinstance(evidence_id, str)
            or not isinstance(command, list)
            or not command
            or not all(isinstance(part, str) for part in command)
        ):
            raise ValueError("adapter required_evidence entry is invalid")
        result[evidence_id] = command
    return result


def run_evidence(target: pathlib.Path, evidence_id: str, command: list[str]) -> int:
    if not ID_RE.fullmatch(evidence_id):
        raise ValueError(f"invalid evidence id: {evidence_id}")
    if not command:
        raise ValueError("evidence command is empty")
    expected = requirements(target).get(evidence_id)
    if expected is None:
        raise ValueError(f"evidence id is not required by the adapter: {evidence_id}")
    if command != expected:
        raise ValueError(
            f"evidence command mismatch for {evidence_id}: expected {expected}, got {command}"
        )

    identity_before = current_identity(target, require_artifact=False)
    out_dir = evidence_dir(target)
    log_path = out_dir / f"{evidence_id}.log"
    json_path = out_dir / f"{evidence_id}.json"
    started = dt.datetime.now(dt.timezone.utc).isoformat()

    timeout = int(load_adapter(target).get("runtime_timeout_seconds", 180))
    with log_path.open("w") as log:
        try:
            process = subprocess.run(
                command,
                cwd=target,
                stdout=log,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
                timeout=timeout,
            )
            exit_code = process.returncode
        except subprocess.TimeoutExpired:
            log.write(f"\nEVIDENCE_TIMEOUT after {timeout} seconds\n")
            exit_code = 124

    identity = current_identity(target, require_artifact=exit_code == 0)
    for field in ["adapter_sha256", "source_hash", "target_hash"]:
        if identity_before.get(field) != identity.get(field):
            exit_code = 125
            with log_path.open("a") as log:
                log.write(f"\nEVIDENCE_INPUT_MUTATION: {field} changed while command ran\n")
    if (
        evidence_id != "final-build"
        and identity_before.get("artifact") != identity.get("artifact")
    ):
        exit_code = 125
        with log_path.open("a") as log:
            log.write("\nEVIDENCE_INPUT_MUTATION: target artifact changed while command ran\n")
    record = {
        "schema": SCHEMA,
        "id": evidence_id,
        "command": command,
        "cwd": target.as_posix(),
        "started_at": started,
        "finished_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "exit_code": exit_code,
        "timeout_seconds": timeout,
        "identity_before": identity_before,
        "identity": identity,
        "log": log_path.relative_to(target).as_posix(),
        "log_sha256": sha256(log_path),
    }
    json_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
    print(f"EVIDENCE_WRITTEN: {json_path.relative_to(target)}")
    if exit_code != 0:
        tail = log_path.read_text(errors="replace").splitlines()[-12:]
        for line in tail:
            print(line)
    return exit_code


def load_evidence(target: pathlib.Path, reference: str) -> dict[str, Any]:
    path = (target / reference).resolve()
    evidence_root = (target / "reports/evidence").resolve()
    try:
        path.relative_to(evidence_root)
    except ValueError as exc:
        raise ValueError(f"evidence must be under reports/evidence: {reference}") from exc
    if not path.is_file():
        raise ValueError(f"evidence record does not exist: {reference}")
    data = json.loads(path.read_text())
    if data.get("schema") != SCHEMA or data.get("exit_code") != 0:
        raise ValueError(f"evidence is not a successful {SCHEMA} record: {reference}")
    evidence_id = str(data.get("id", ""))
    expected_command = requirements(target).get(evidence_id)
    if expected_command is None:
        raise ValueError(f"evidence id is not required by current adapter: {reference}")
    command = data.get("command")
    if command != expected_command:
        raise ValueError(f"evidence command does not match adapter: {reference}")
    if pathlib.Path(str(data.get("cwd", ""))).resolve() != target.resolve():
        raise ValueError(f"evidence working directory mismatch: {reference}")
    log = (target / str(data.get("log", ""))).resolve()
    try:
        log.relative_to(evidence_root)
    except ValueError as exc:
        raise ValueError(f"evidence log escapes reports/evidence: {reference}") from exc
    if not log.is_file() or sha256(log) != data.get("log_sha256"):
        raise ValueError(f"evidence log hash mismatch: {reference}")
    for field in ["started_at", "finished_at"]:
        if not isinstance(data.get(field), str) or not data[field]:
            raise ValueError(f"evidence field missing: {field}: {reference}")
    require_identity(data.get("identity"), target)
    before = data.get("identity_before")
    if not isinstance(before, dict):
        raise ValueError(f"evidence pre-run identity is missing: {reference}")
    for field in ["adapter_sha256", "source_hash", "target_hash"]:
        if before.get(field) != data["identity"].get(field):
            raise ValueError(f"evidence inputs changed while command ran: {reference}")
    return data


def verify_evidence(
    target: pathlib.Path,
    reference: str,
    expected_id: str | None = None,
) -> dict[str, Any]:
    data = load_evidence(target, reference)
    if expected_id is not None and data.get("id") != expected_id:
        raise ValueError(f"evidence id mismatch: expected {expected_id}: {reference}")
    return data


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="action", required=True)
    run_parser = sub.add_parser("run")
    run_parser.add_argument("--id", required=True)
    run_parser.add_argument("command", nargs=argparse.REMAINDER)
    verify_parser = sub.add_parser("verify")
    verify_parser.add_argument("reference")
    args = parser.parse_args()

    target = pathlib.Path.cwd().resolve()
    if args.action == "run":
        command = args.command[1:] if args.command and args.command[0] == "--" else args.command
        return run_evidence(target, args.id, command)
    verify_evidence(target, args.reference)
    print("EVIDENCE_VERIFY_PASS")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"EVIDENCE_ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
