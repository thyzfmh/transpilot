#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import subprocess
import sys

from adapter import expand_command, load_adapter, require_list


def main() -> int:
    target = pathlib.Path.cwd().resolve()
    adapter = load_adapter(target)
    command = expand_command(require_list(adapter, "target_test_command"), target, adapter)
    timeout = int(adapter.get("runtime_timeout_seconds", 180))
    result = subprocess.run(command, cwd=target, check=False, timeout=timeout)
    if result.returncode != 0:
        print(
            f"CONFIGURED_TARGET_TEST_FAIL: exit={result.returncode} command={command}",
            file=sys.stderr,
        )
        return result.returncode
    print("CONFIGURED_TARGET_TEST_PASS")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        print(f"CONFIGURED_TARGET_TEST_FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
