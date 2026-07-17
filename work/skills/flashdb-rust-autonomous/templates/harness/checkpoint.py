#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import sys

from adapter import load_adapter
from evidence_runner import requirements, verify_evidence
from run_identity import current_identity, require_identity
from source_acceptance import SCHEMA as ACCEPTANCE_SCHEMA


TARGET = pathlib.Path.cwd()
ADAPTER = load_adapter(TARGET)
CHECKPOINT = TARGET / "reports/checkpoint.json"
ACCEPTANCE = TARGET / "reports/source-acceptance.json"
SCHEMA = "source-translation-checkpoint-v3"


def load(require_current_target: bool = False) -> dict[str, object]:
    if not CHECKPOINT.is_file():
        raise ValueError(f"missing checkpoint: {CHECKPOINT}")
    data = json.loads(CHECKPOINT.read_text())
    if data.get("schema") != SCHEMA:
        raise ValueError("invalid checkpoint schema")
    identity = data.get("identity")
    if not isinstance(identity, dict):
        raise ValueError("checkpoint identity is missing")
    current = current_identity(TARGET, require_artifact=require_current_target)
    for field in ["adapter_sha256", "source_hash"]:
        if identity.get(field) != current.get(field):
            raise ValueError(f"checkpoint {field} does not match current run")
    if require_current_target and identity != current:
        raise ValueError("checkpoint target or artifact identity is stale")
    return data


def write(data: dict[str, object]) -> None:
    CHECKPOINT.parent.mkdir(parents=True, exist_ok=True)
    data["schema"] = SCHEMA
    data["identity"] = current_identity(TARGET, require_artifact=False)
    data["updated_at"] = dt.datetime.now(dt.timezone.utc).isoformat()
    CHECKPOINT.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def acceptance_counts(require_complete: bool = False) -> dict[str, int]:
    if not ACCEPTANCE.is_file():
        if require_complete:
            raise ValueError("source acceptance has not been generated")
        return {"passed": 0, "failed": 0, "not_run": 0, "total": 0}
    data = json.loads(ACCEPTANCE.read_text())
    if data.get("schema") != ACCEPTANCE_SCHEMA:
        raise ValueError("source acceptance schema mismatch")
    try:
        require_identity(data.get("identity"), TARGET)
    except ValueError:
        if require_complete:
            raise
        return {"passed": 0, "failed": 0, "not_run": 0, "total": 0}
    counts = {
        key: int(data.get(key, -1))
        for key in ["passed", "failed", "not_run", "total"]
    }
    if require_complete and (
        counts["total"] <= 0
        or counts["passed"] != counts["total"]
        or counts["failed"] != 0
        or counts["not_run"] != 0
    ):
        raise ValueError(f"source acceptance is incomplete: {counts}")
    return counts


def verified_gates() -> dict[str, str]:
    gates: dict[str, str] = {}
    for evidence_id in requirements(TARGET):
        reference = f"reports/evidence/{evidence_id}.json"
        data = verify_evidence(TARGET, reference, evidence_id)
        gates[evidence_id] = str(data.get("log_sha256"))
    return gates


def concise(data: dict[str, object]) -> str:
    counts = data.get("counts", {})
    return (
        f"stage={data.get('stage')} item={data.get('item')} "
        f"exit={data.get('last_exit_code')} counts={counts} "
        f"next={data.get('next_action')}"
    )


def initial_state() -> dict[str, object]:
    return {
        "item": "project-discovery",
        "stage": "initialized",
        "last_command": "preflight",
        "last_exit_code": 0,
        "failure": "",
        "next_action": "run source baseline and first source-native target gate",
        "counts": acceptance_counts(),
        "attempts": [],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="action", required=True)
    sub.add_parser("init")
    sub.add_parser("show")
    record = sub.add_parser("record")
    record.add_argument("--item", "--case", dest="item", required=True)
    record.add_argument("--stage", required=True)
    record.add_argument("--command", required=True)
    record.add_argument("--exit-code", required=True, type=int)
    record.add_argument("--failure", default="")
    record.add_argument("--next-action", required=True)
    record.add_argument("--approach", default="")
    sub.add_parser("seal-final")
    sub.add_parser("verify-final")
    args = parser.parse_args()

    if args.action == "init":
        if CHECKPOINT.exists():
            try:
                data = load()
            except (ValueError, json.JSONDecodeError) as exc:
                write(initial_state())
                print(f"CHECKPOINT_REINITIALIZED: {exc}")
            else:
                print(f"CHECKPOINT_RESUME: {concise(data)}")
        else:
            write(initial_state())
            print("CHECKPOINT_INIT_PASS")
        return 0
    if args.action == "show":
        print(f"CHECKPOINT: {concise(load())}")
        return 0
    if args.action == "record":
        if args.stage == "ready_for_final":
            raise ValueError("ready_for_final can only be created by seal-final")
        previous: dict[str, object] = {}
        if CHECKPOINT.exists():
            previous = load()
        attempts = list(previous.get("attempts", []))
        attempts.append(
            {
                "recorded_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                "item": args.item,
                "stage": args.stage,
                "command": args.command,
                "exit_code": args.exit_code,
                "failure": args.failure,
                "approach": args.approach,
            }
        )
        write(
            {
                "item": args.item,
                "stage": args.stage,
                "last_command": args.command,
                "last_exit_code": args.exit_code,
                "failure": args.failure,
                "next_action": args.next_action,
                "counts": acceptance_counts(),
                "attempts": attempts,
            }
        )
        print("CHECKPOINT_RECORDED")
        return 0

    if args.action == "seal-final":
        counts = acceptance_counts(require_complete=True)
        gates = verified_gates()
        previous = load() if CHECKPOINT.exists() else {}
        write(
            {
                "item": "all",
                "stage": "ready_for_final",
                "last_command": "machine-verified final evidence set",
                "last_exit_code": 0,
                "failure": "",
                "next_action": "write result, export trace, and verify completion",
                "counts": counts,
                "attempts": list(previous.get("attempts", [])),
                "gate_evidence": gates,
            }
        )
        print("CHECKPOINT_SEALED")
        return 0

    data = load(require_current_target=True)
    if data.get("stage") != "ready_for_final" or data.get("last_exit_code") != 0:
        raise ValueError("checkpoint must record ready_for_final with exit code 0")
    if data.get("counts") != acceptance_counts(require_complete=True):
        raise ValueError("checkpoint acceptance counts are stale")
    if data.get("gate_evidence") != verified_gates():
        raise ValueError("checkpoint evidence set is stale or incomplete")
    print("CHECKPOINT_FINAL_PASS")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"CHECKPOINT_FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
