#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import re
import subprocess
import sys
from typing import Any

SCHEMA = "flashdb-evidence-v1"
ID_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,79}$")


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def tree_hash(paths: list[pathlib.Path], base: pathlib.Path) -> str:
    digest = hashlib.sha256()
    files: list[pathlib.Path] = []
    for root in paths:
        if root.is_file():
            files.append(root)
        elif root.is_dir():
            files.extend(path for path in root.rglob("*") if path.is_file() and "target" not in path.parts)
    for path in sorted(set(files)):
        try:
            relative = path.resolve().relative_to(base.resolve()).as_posix()
        except ValueError:
            relative = path.resolve().as_posix()
        digest.update(relative.encode())
        digest.update(b"\0")
        digest.update(sha256(path).encode())
        digest.update(b"\n")
    return digest.hexdigest()


def evidence_dir(target: pathlib.Path) -> pathlib.Path:
    path = target / "reports/evidence"
    path.mkdir(parents=True, exist_ok=True)
    return path


def current_source_hash(target: pathlib.Path) -> str:
    source = (target / "../FlashDB").resolve()
    files = [
        path
        for root in [source / "inc", source / "src", source / "tests"]
        if root.is_dir()
        for path in root.rglob("*")
        if path.is_file() and (path.suffix in {".c", ".h"} or path.name == "Makefile")
    ]
    return tree_hash(files, target.parent.parent)


def current_target_hash(target: pathlib.Path) -> str:
    return tree_hash(
        [
            target / "Cargo.toml",
            target / "Cargo.lock",
            target / "build.rs",
            target / ".cargo/config.toml",
            target / "src",
            target / "tests",
        ],
        target,
    )


def run_evidence(target: pathlib.Path, evidence_id: str, command: list[str]) -> int:
    if not ID_RE.fullmatch(evidence_id):
        raise ValueError(f"invalid evidence id: {evidence_id}")
    if not command:
        raise ValueError("evidence command is empty")

    inputs = current_source_hash(target)
    out_dir = evidence_dir(target)
    log_path = out_dir / f"{evidence_id}.log"
    json_path = out_dir / f"{evidence_id}.json"
    started = dt.datetime.now(dt.timezone.utc).isoformat()

    with log_path.open("w") as log:
        process = subprocess.Popen(
            command,
            cwd=target,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            env=os.environ.copy(),
        )
        assert process.stdout is not None
        for line in process.stdout:
            sys.stdout.write(line)
            log.write(line)
        exit_code = process.wait()

    outputs = current_target_hash(target)
    record = {
        "schema": SCHEMA,
        "id": evidence_id,
        "command": command,
        "cwd": target.as_posix(),
        "started_at": started,
        "finished_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "exit_code": exit_code,
        "source_hash": inputs,
        "target_hash": outputs,
        "log": log_path.relative_to(target).as_posix(),
        "log_sha256": sha256(log_path),
    }
    json_path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n")
    print(f"EVIDENCE_WRITTEN: {json_path.relative_to(target)}")
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
    command = data.get("command")
    if not isinstance(command, list) or not command or not all(isinstance(item, str) for item in command):
        raise ValueError(f"evidence command is invalid: {reference}")
    log = (target / str(data.get("log", ""))).resolve()
    try:
        log.relative_to(evidence_root)
    except ValueError as exc:
        raise ValueError(f"evidence log escapes reports/evidence: {reference}") from exc
    if not log.is_file() or sha256(log) != data.get("log_sha256"):
        raise ValueError(f"evidence log hash mismatch: {reference}")
    for field in ["source_hash", "target_hash", "started_at", "finished_at"]:
        if not isinstance(data.get(field), str) or not data[field]:
            raise ValueError(f"evidence field missing: {field}: {reference}")
    if data["source_hash"] != current_source_hash(target):
        raise ValueError(f"evidence source hash is stale: {reference}")
    if data["target_hash"] != current_target_hash(target):
        raise ValueError(f"evidence target hash is stale: {reference}")
    return data


def verify_evidence(target: pathlib.Path, reference: str, hints: tuple[str, ...] = ()) -> dict[str, Any]:
    data = load_evidence(target, reference)
    command_text = " ".join(data["command"])
    if hints and not any(hint in command_text for hint in hints):
        raise ValueError(f"evidence command lacks one of {hints}: {reference}")
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
