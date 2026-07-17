#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import sys

from evidence_runner import requirements, run_evidence


def main() -> int:
    target = pathlib.Path.cwd().resolve()
    gates = requirements(target)
    if "final-spec" in gates and list(gates)[-1] != "final-spec":
        raise ValueError("final-spec must be the last required evidence gate")
    for evidence_id, command in gates.items():
        print(f"FINAL_GATE_START: {evidence_id}")
        status = run_evidence(target, evidence_id, command)
        if status != 0:
            print(f"FINAL_GATE_FAIL: {evidence_id} exit={status}", file=sys.stderr)
            return status
        print(f"FINAL_GATE_PASS: {evidence_id}")
    print(f"FINAL_GATE_SET_PASS: count={len(gates)}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError) as exc:
        print(f"FINAL_GATE_FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
