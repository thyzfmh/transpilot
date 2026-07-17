#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import re
import sys

from adapter import load_adapter, source_root


TARGET = pathlib.Path.cwd().resolve()
ADAPTER = load_adapter(TARGET)
SOURCE = source_root(TARGET, ADAPTER)
REPORT = TARGET / "reports/config-profile.md"


def main() -> int:
    profile = ADAPTER.get("configuration_profile")
    if not isinstance(profile, dict):
        raise ValueError("adapter configuration_profile is missing")
    config = SOURCE / str(profile.get("source_file", ""))
    if not config.is_file():
        raise ValueError(f"configuration source is missing: {config}")
    text = re.sub(r"/\*.*?\*/", "", config.read_text(errors="replace"), flags=re.S)
    required = profile.get("required_regex")
    forbidden = profile.get("forbidden_regex")
    if not isinstance(required, dict) or not isinstance(forbidden, dict):
        raise ValueError("configuration profile regex maps are invalid")
    failures = [
        f"required setting is absent: {name}"
        for name, pattern in required.items()
        if not isinstance(pattern, str) or not re.search(pattern, text)
    ]
    failures.extend(
        f"forbidden setting is enabled: {name}"
        for name, pattern in forbidden.items()
        if isinstance(pattern, str) and re.search(pattern, text)
    )
    description = profile.get("description")
    if not isinstance(description, list) or not all(isinstance(item, str) for item in description):
        raise ValueError("configuration profile description is invalid")
    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(
        "\n".join(
            [
                "# Supported Configuration Profile",
                "",
                *(f"- {item}" for item in description),
                f"- Scope: {config.relative_to(SOURCE)}",
                f"- Status: {'FAILED' if failures else 'PASSED'}",
                "",
                *(f"- Failure: {failure}" for failure in failures),
                "",
            ]
        )
    )
    if failures:
        for failure in failures:
            print(f"CONFIG_PROFILE_FAIL: {failure}", file=sys.stderr)
        return 1
    print("CONFIG_PROFILE_PASS")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError) as exc:
        print(f"CONFIG_PROFILE_FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
