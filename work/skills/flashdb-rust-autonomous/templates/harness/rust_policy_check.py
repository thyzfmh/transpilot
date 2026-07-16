#!/usr/bin/env python3
from __future__ import annotations

import pathlib
import re
import sys

TARGET = pathlib.Path.cwd()

PROHIBITED = {
    "static mut": re.compile(r"\bstatic\s+mut\b"),
    "unwrap": re.compile(r"\.\s*unwrap\s*\("),
    "expect": re.compile(r"\.\s*expect\s*\("),
    "todo macro": re.compile(r"\btodo\s*!\s*(?:\(|\{|\[)"),
    "unimplemented macro": re.compile(r"\bunimplemented\s*!\s*(?:\(|\{|\[)"),
    "panic macro": re.compile(r"\bpanic\s*!\s*(?:\(|\{|\[)"),
}
SHORTCUT_COMMENT = re.compile(
    r"(?im)//[^\n]*(simplified|no[- ]?op for tests|stub|fake implementation|placeholder implementation)"
)


def sanitize(text: str) -> str:
    def blanks(match: re.Match[str]) -> str:
        return "".join("\n" if char == "\n" else " " for char in match.group(0))

    text = re.sub(r"/\*.*?\*/", blanks, text, flags=re.S)
    text = re.sub(r"(?m)//.*$", blanks, text)
    text = re.sub(r'br?"(?:\\.|[^"\\])*"', blanks, text)
    text = re.sub(r"b?'(?:\\.|[^'\\])'", blanks, text)
    return text


def matching_brace(text: str, start: int) -> int:
    depth = 0
    for index in range(start, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return index
    return len(text) - 1


def check_file(path: pathlib.Path) -> list[str]:
    original = path.read_text(errors="replace")
    clean = sanitize(original)
    relative = path.relative_to(TARGET).as_posix()
    failures: list[str] = []

    for label, pattern in PROHIBITED.items():
        for match in pattern.finditer(clean):
            line = clean.count("\n", 0, match.start()) + 1
            failures.append(f"{relative}:{line}: prohibited production {label}")
    for match in SHORTCUT_COMMENT.finditer(original):
        line = original.count("\n", 0, match.start()) + 1
        failures.append(f"{relative}:{line}: shortcut implementation comment is forbidden")

    original_lines = original.splitlines()
    for index, line_text in enumerate(clean.splitlines()):
        if not re.search(r"\bunsafe\b", line_text):
            continue
        safety_window = "\n".join(original_lines[max(0, index - 3) : index + 1])
        if "SAFETY:" not in safety_window:
            failures.append(f"{relative}:{index + 1}: unsafe requires a nearby SAFETY: justification")

    ffi_pattern = re.compile(r"\bpub\s+(?:unsafe\s+)?extern\s+\"C\"\s+fn\s+([A-Za-z_][A-Za-z0-9_]*)")
    for match in ffi_pattern.finditer(clean):
        body_start = clean.find("{", match.end())
        if body_start < 0:
            failures.append(f"{relative}: extern C function has no body: {match.group(1)}")
            continue
        body = clean[body_start : matching_brace(clean, body_start) + 1]
        if "catch_unwind" not in body and "ffi_guard" not in body:
            line = clean.count("\n", 0, match.start()) + 1
            failures.append(
                f"{relative}:{line}: extern C function {match.group(1)} lacks catch_unwind/ffi_guard panic containment"
            )
    return failures


def check_test_file(path: pathlib.Path) -> list[str]:
    original = path.read_text(errors="replace")
    clean = sanitize(original)
    relative = path.relative_to(TARGET).as_posix()
    failures: list[str] = []
    for label in ["todo macro", "unimplemented macro"]:
        for match in PROHIBITED[label].finditer(clean):
            line = clean.count("\n", 0, match.start()) + 1
            failures.append(f"{relative}:{line}: prohibited test {label}")
    for match in SHORTCUT_COMMENT.finditer(original):
        line = original.count("\n", 0, match.start()) + 1
        failures.append(f"{relative}:{line}: shortcut test comment is forbidden")
    return failures


def main() -> int:
    src = TARGET / "src"
    files = sorted(src.rglob("*.rs")) if src.is_dir() else []
    if not files:
        print("RUST_POLICY_CHECK_FAIL: no production Rust files", file=sys.stderr)
        return 1
    failures = [failure for path in files for failure in check_file(path)]
    test_root = TARGET / "tests"
    test_files = sorted(test_root.rglob("*.rs")) if test_root.is_dir() else []
    failures.extend(failure for path in test_files for failure in check_test_file(path))
    if failures:
        print("RUST_POLICY_CHECK_FAIL")
        for failure in failures:
            print(f"- {failure}")
        return 1
    print("RUST_POLICY_CHECK_PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
