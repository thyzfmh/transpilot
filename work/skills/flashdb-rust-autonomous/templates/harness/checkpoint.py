#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import pathlib
import sys

TARGET = pathlib.Path.cwd()
SOURCE = (TARGET / "../FlashDB").resolve()
CHECKPOINT = TARGET / "reports/checkpoint.json"
SCHEMA = "flashdb-checkpoint-v1"


def source_hash() -> str:
    digest = hashlib.sha256()
    files = []
    for root in [SOURCE / "inc", SOURCE / "src", SOURCE / "tests"]:
        if root.is_dir():
            files.extend(
                path
                for path in root.rglob("*")
                if path.is_file() and (path.suffix in {".c", ".h"} or path.name == "Makefile")
            )
    for path in sorted(files):
        digest.update(path.relative_to(SOURCE).as_posix().encode())
        digest.update(b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).hexdigest().encode())
        digest.update(b"\n")
    return digest.hexdigest()


def target_hash() -> str:
    digest = hashlib.sha256()
    files = [
        TARGET / "Cargo.toml",
        TARGET / "Cargo.lock",
        TARGET / "build.rs",
        TARGET / ".cargo/config.toml",
    ]
    for root in [TARGET / "src", TARGET / "tests"]:
        if root.is_dir():
            files.extend(path for path in root.rglob("*") if path.is_file())
    for path in sorted(path for path in files if path.is_file()):
        digest.update(path.relative_to(TARGET).as_posix().encode())
        digest.update(b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).hexdigest().encode())
        digest.update(b"\n")
    return digest.hexdigest()


def load() -> dict[str, object]:
    if not CHECKPOINT.is_file():
        raise ValueError(f"missing checkpoint: {CHECKPOINT}")
    data = json.loads(CHECKPOINT.read_text())
    if data.get("schema") != SCHEMA:
        raise ValueError("invalid checkpoint schema")
    if data.get("source_hash") != source_hash():
        raise ValueError("checkpoint source hash does not match current C baseline")
    if data.get("target_hash") != target_hash():
        raise ValueError("checkpoint target hash does not match current Rust source")
    return data


def write(data: dict[str, object]) -> None:
    CHECKPOINT.parent.mkdir(parents=True, exist_ok=True)
    data["schema"] = SCHEMA
    data["source_hash"] = source_hash()
    data["target_hash"] = target_hash()
    data["updated_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    CHECKPOINT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("init")
    record = sub.add_parser("record")
    record.add_argument("--case", required=True)
    record.add_argument("--stage", required=True)
    record.add_argument("--command", required=True)
    record.add_argument("--exit-code", required=True, type=int)
    sub.add_parser("verify-final")
    args = parser.parse_args()

    if args.action == "init":
        if CHECKPOINT.exists():
            load()
            print("CHECKPOINT_RESUME_PASS")
        else:
            write({"case_id": "workspace", "stage": "initialized", "last_command": "preflight", "last_exit_code": 0})
            print("CHECKPOINT_INIT_PASS")
        return 0
    if args.action == "record":
        if CHECKPOINT.exists():
            load()
        write(
            {
                "case_id": args.case,
                "stage": args.stage,
                "last_command": args.command,
                "last_exit_code": args.exit_code,
            }
        )
        print("CHECKPOINT_RECORDED")
        return 0

    data = load()
    if data.get("stage") != "ready_for_final" or data.get("last_exit_code") != 0:
        raise ValueError("checkpoint must record ready_for_final with exit code 0")
    print("CHECKPOINT_FINAL_PASS")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"CHECKPOINT_FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
