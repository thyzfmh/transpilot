#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import pathlib
import sys

from adapter import load_adapter, source_root
from run_identity import matched_files

SKILL_REL = pathlib.Path("work/skills/flashdb-rust-autonomous")


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def fail(messages: list[str]) -> int:
    print("SOURCE_GUARD_FAIL", file=sys.stderr)
    for message in messages:
        print(f"- {message}", file=sys.stderr)
    return 1


def find_repo(target: pathlib.Path) -> pathlib.Path:
    for candidate in [target.parent, *target.parents]:
        if (candidate / SKILL_REL / "SKILL.md").is_file():
            return candidate
    raise RuntimeError(f"cannot locate repository root from target: {target}")


def read_manifest(path: pathlib.Path) -> dict[str, str]:
    entries: dict[str, str] = {}
    for line in path.read_text().splitlines():
        if not line.strip():
            continue
        digest, relative = line.split(None, 1)
        entries[relative.strip()] = digest
    return entries


def source_files(repo: pathlib.Path, target: pathlib.Path) -> set[str]:
    adapter = load_adapter(target)
    source = source_root(target, adapter)
    patterns = adapter.get("source_hash_globs")
    if not isinstance(patterns, list):
        raise ValueError("adapter source_hash_globs is missing")
    return {
        path.relative_to(repo).as_posix()
        for path in matched_files(source, patterns)
    }


def harness_files(root: pathlib.Path) -> dict[str, pathlib.Path]:
    return {
        path.relative_to(root).as_posix(): path
        for path in root.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts and not path.name.endswith(".pyc")
    }


def verify(target: pathlib.Path) -> int:
    try:
        repo = find_repo(target)
    except RuntimeError as exc:
        return fail([str(exc)])

    skill = repo / SKILL_REL
    manifest_path = skill / "references/source-manifest.sha256"
    expected = read_manifest(manifest_path)
    actual_files = source_files(repo, target)
    failures: list[str] = []

    missing = sorted(set(expected) - actual_files)
    extra = sorted(actual_files - set(expected))
    failures.extend(f"source baseline file missing: {path}" for path in missing)
    failures.extend(f"unrecognized source baseline file: {path}" for path in extra)
    for relative, expected_hash in expected.items():
        path = repo / relative
        if path.is_file() and sha256(path) != expected_hash:
            failures.append(f"source baseline changed: {relative}")

    template_root = skill / "templates/harness"
    target_root = target / "harness"
    template_files = harness_files(template_root)
    target_files = harness_files(target_root)
    for relative in sorted(set(template_files) - set(target_files)):
        failures.append(f"target harness file missing: harness/{relative}")
    for relative in sorted(set(target_files) - set(template_files)):
        failures.append(f"unrecognized target harness file: harness/{relative}")
    for relative in sorted(set(template_files) & set(target_files)):
        if sha256(template_files[relative]) != sha256(target_files[relative]):
            failures.append(f"target harness drifted from skill template: harness/{relative}")

    if failures:
        return fail(failures)
    print("SOURCE_GUARD_PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--target", default=".")
    args = parser.parse_args()
    return verify(pathlib.Path(args.target).resolve())


if __name__ == "__main__":
    sys.exit(main())
