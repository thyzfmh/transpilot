#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import re
import sys

TARGET = pathlib.Path.cwd()
CONFIG = (TARGET / "../FlashDB/tests/fdb_cfg.h").resolve()
REPORT = TARGET / "reports/config-profile.md"


def main() -> int:
    if not CONFIG.is_file():
        print(f"CONFIG_PROFILE_FAIL: missing {CONFIG}", file=sys.stderr)
        return 1
    text = re.sub(r"/\*.*?\*/", "", CONFIG.read_text(errors="replace"), flags=re.S)
    required = {
        "FDB_USING_KVDB": r"(?m)^\s*#define\s+FDB_USING_KVDB\b",
        "FDB_USING_TSDB": r"(?m)^\s*#define\s+FDB_USING_TSDB\b",
        "FDB_USING_FILE_POSIX_MODE": r"(?m)^\s*#define\s+FDB_USING_FILE_POSIX_MODE\b",
        "FDB_WRITE_GRAN=1": r"(?m)^\s*#define\s+FDB_WRITE_GRAN\s+1\s*$",
    }
    failures = [name for name, pattern in required.items() if not re.search(pattern, text)]
    if re.search(r"(?m)^\s*#define\s+FDB_USING_TIMESTAMP_64BIT\b", text):
        failures.append("FDB_USING_TIMESTAMP_64BIT must be disabled for the fixed profile")

    REPORT.parent.mkdir(parents=True, exist_ok=True)
    REPORT.write_text(
        "\n".join(
            [
                "# Supported Configuration Profile",
                "",
                "- Backend: POSIX file mode",
                "- Databases: KVDB and TSDB",
                "- Write granularity: 1 bit",
                "- Timestamp: signed 32 bit",
                "- Scope: the profile selected by code/FlashDB/tests/fdb_cfg.h",
                f"- Status: {'FAILED' if failures else 'PASSED'}",
                "",
                *(f"- Failure: {failure}" for failure in failures),
                "",
            ]
        )
    )
    if failures:
        print("CONFIG_PROFILE_FAIL", file=sys.stderr)
        for failure in failures:
            print(f"- {failure}", file=sys.stderr)
        return 1
    print("CONFIG_PROFILE_PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
