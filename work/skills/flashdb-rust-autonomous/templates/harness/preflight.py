#!/usr/bin/env python3
from __future__ import annotations

import datetime as dt
import json
import os
import pathlib
import shutil
import subprocess
import sys

from adapter import load_adapter, source_root


def main() -> int:
    target = pathlib.Path.cwd().resolve()
    adapter = load_adapter(target)
    tools = adapter.get("required_tools")
    if not isinstance(tools, list) or not tools or not all(isinstance(tool, str) for tool in tools):
        raise ValueError("adapter required_tools must be a non-empty string list")
    missing = []
    versions = []
    for tool in tools:
        candidate = os.environ.get("CC", "cc") if tool == "cc" else tool
        resolved = shutil.which(candidate)
        if not resolved:
            missing.append(candidate)
            continue
        result = subprocess.run(
            [candidate, "--version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            check=False,
            timeout=15,
        )
        output = result.stdout.strip()
        if result.returncode != 0 or not output:
            raise ValueError(f"cannot read required tool version: {candidate}")
        versions.append(
            {
                "tool": tool,
                "command": candidate,
                "path": resolved,
                "version": output.splitlines()[0],
            }
        )
    if missing:
        print(f"PREFLIGHT_BLOCKED: required commands not found: {', '.join(missing)}", file=sys.stderr)
        return 2
    probe = source_root(target, adapter) / str(adapter.get("source_probe", ""))
    if not probe.is_file() or not os.access(probe, os.R_OK):
        print(f"PREFLIGHT_BLOCKED: source probe is unreadable: {probe}", file=sys.stderr)
        return 2
    if not os.access(target, os.W_OK):
        print(f"PREFLIGHT_BLOCKED: target directory is not writable: {target}", file=sys.stderr)
        return 2
    free_kib = shutil.disk_usage(target).free // 1024
    minimum = int(adapter.get("minimum_free_kib", 102400))
    if free_kib < minimum:
        print(
            f"PREFLIGHT_BLOCKED: free disk is {free_kib} KiB, required {minimum} KiB",
            file=sys.stderr,
        )
        return 2
    reports = target / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    (reports / "tool-versions.json").write_text(
        json.dumps(
            {
                "schema": "source-translation-tool-versions-v1",
                "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                "tools": versions,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n"
    )
    print("CONFIGURED_PREFLIGHT_PASS")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError) as exc:
        print(f"PREFLIGHT_BLOCKED: {exc}", file=sys.stderr)
        sys.exit(2)
