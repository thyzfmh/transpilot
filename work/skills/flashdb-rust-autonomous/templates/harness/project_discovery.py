#!/usr/bin/env python3
from __future__ import annotations

import argparse
import collections
import datetime as dt
import hashlib
import json
import pathlib
import re
import sys

from adapter import load_adapter, source_root
from run_identity import current_identity


SCHEMA = "source-translation-project-v1"
LANGUAGES = {
    ".c": "C",
    ".h": "C header",
    ".cc": "C++",
    ".cpp": "C++",
    ".hpp": "C++ header",
    ".rs": "Rust",
    ".py": "Python",
    ".go": "Go",
    ".java": "Java",
    ".js": "JavaScript",
    ".ts": "TypeScript",
}
BUILD_NAMES = {
    "Makefile",
    "CMakeLists.txt",
    "Cargo.toml",
    "pyproject.toml",
    "setup.py",
    "package.json",
    "pom.xml",
    "build.gradle",
    "go.mod",
}
IGNORED_PARTS = {".git", "target", "node_modules", "__pycache__"}


def digest_files(root: pathlib.Path, files: list[pathlib.Path]) -> str:
    digest = hashlib.sha256()
    for path in files:
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(b"\0")
        digest.update(hashlib.sha256(path.read_bytes()).digest())
        digest.update(b"\n")
    return digest.hexdigest()


def discover_tests(
    path: pathlib.Path,
    text: str,
    patterns: dict[str, str] | None = None,
) -> list[str]:
    suffix = path.suffix.lower()
    if patterns and suffix in patterns:
        return re.findall(patterns[suffix], text)
    if suffix in {".c", ".cc", ".cpp"}:
        return re.findall(r"\bTEST_RUN\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)", text)
    if suffix == ".rs":
        return re.findall(r"#\s*\[\s*test\s*\][\s\S]{0,200}?\bfn\s+([A-Za-z_][A-Za-z0-9_]*)", text)
    if suffix == ".py":
        return re.findall(r"(?m)^\s*def\s+(test_[A-Za-z0-9_]+)\s*\(", text)
    if suffix in {".js", ".ts"}:
        return re.findall(r"\b(?:it|test)\s*\(\s*['\"]([^'\"]+)", text)
    return []


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source")
    parser.add_argument("--target", default=".")
    args = parser.parse_args()

    target = pathlib.Path(args.target).resolve()
    adapter = None
    if args.source:
        source = pathlib.Path(args.source).resolve()
    else:
        adapter = load_adapter(target)
        source = source_root(target, adapter)
    if not source.is_dir():
        print(f"PROJECT_DISCOVERY_FAIL: source directory is missing: {source}", file=sys.stderr)
        return 1

    discovered_files = sorted(
        path
        for path in source.rglob("*")
        if path.is_file() and not any(part in IGNORED_PARTS for part in path.relative_to(source).parts)
    )
    files = [
        path
        for path in discovered_files
        if path.suffix.lower() in LANGUAGES or path.name in BUILD_NAMES
    ]
    language_counts: collections.Counter[str] = collections.Counter()
    build_files: list[str] = []
    test_files: list[dict[str, object]] = []
    public_headers: list[str] = []

    for path in files:
        relative = path.relative_to(source).as_posix()
        language = LANGUAGES.get(path.suffix.lower())
        if language:
            language_counts[language] += 1
        if path.name in BUILD_NAMES:
            build_files.append(relative)
        if path.suffix.lower() in {".h", ".hpp"} and any(
            part.lower() in {"inc", "include", "api"} for part in path.relative_to(source).parts[:-1]
        ):
            public_headers.append(relative)
        if language:
            text = path.read_text(errors="replace")
            configured_patterns = adapter.get("test_discovery_patterns") if adapter else None
            if configured_patterns is not None and not isinstance(configured_patterns, dict):
                raise ValueError("adapter test_discovery_patterns must be an object")
            tests = discover_tests(path, text, configured_patterns)
            if tests:
                test_files.append({"path": relative, "tests": tests, "count": len(tests)})

    reports = target / "reports"
    reports.mkdir(parents=True, exist_ok=True)
    profile = {
        "schema": SCHEMA,
        "source_root": source.as_posix(),
        "source_hash": digest_files(source, files),
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "file_count": len(files),
        "languages": dict(sorted(language_counts.items())),
        "build_files": build_files,
        "public_headers": public_headers,
        "test_files": test_files,
        "discovered_test_count": sum(int(item["count"]) for item in test_files),
    }
    if adapter is not None:
        identity = current_identity(target, require_artifact=False)
        profile["adapter_sha256"] = identity["adapter_sha256"]
        profile["oracle_source_hash"] = identity["source_hash"]
    (reports / "project-profile.json").write_text(
        json.dumps(profile, ensure_ascii=False, indent=2) + "\n"
    )
    lines = [
        "# Source Project Inventory",
        "",
        f"- Files: {profile['file_count']}",
        f"- Source hash: `{profile['source_hash']}`",
        f"- Discovered native tests: {profile['discovered_test_count']}",
        f"- Build files: {', '.join(build_files) if build_files else 'none discovered'}",
        f"- Public headers: {', '.join(public_headers) if public_headers else 'none discovered'}",
        "",
        "## Languages",
        "",
        *(f"- {name}: {count}" for name, count in sorted(language_counts.items())),
        "",
        "## Native Test Files",
        "",
        *(
            f"- {item['path']}: {item['count']}"
            for item in test_files
        ),
        "",
    ]
    (reports / "source-inventory.md").write_text("\n".join(lines))
    print(
        "PROJECT_DISCOVERY_PASS: "
        f"files={profile['file_count']} tests={profile['discovered_test_count']}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
