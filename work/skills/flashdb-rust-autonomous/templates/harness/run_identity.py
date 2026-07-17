#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import pathlib
from typing import Any

from adapter import adapter_path, load_adapter, source_root


SCHEMA = "source-translation-identity-v1"


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def matched_files(root: pathlib.Path, patterns: list[Any]) -> list[pathlib.Path]:
    files: set[pathlib.Path] = set()
    for raw in patterns:
        if not isinstance(raw, str) or not raw:
            raise ValueError("identity glob must be a non-empty string")
        for path in root.glob(raw):
            if path.is_file():
                files.add(path.resolve())
    return sorted(files)


def tree_hash(root: pathlib.Path, patterns: list[Any]) -> str:
    files = matched_files(root, patterns)
    if not files:
        raise ValueError(f"identity patterns matched no files under {root}")
    digest = hashlib.sha256()
    for path in files:
        digest.update(path.relative_to(root.resolve()).as_posix().encode())
        digest.update(b"\0")
        digest.update(bytes.fromhex(sha256(path)))
        digest.update(b"\n")
    return digest.hexdigest()


def current_identity(target: pathlib.Path, require_artifact: bool = True) -> dict[str, Any]:
    target = target.resolve()
    adapter = load_adapter(target)
    source = source_root(target, adapter)
    source_patterns = adapter.get("source_hash_globs")
    target_patterns = adapter.get("target_hash_globs")
    if not isinstance(source_patterns, list) or not isinstance(target_patterns, list):
        raise ValueError("adapter identity globs are missing")
    artifact_relative = str(adapter.get("target_artifact", ""))
    artifact = target / artifact_relative
    artifact_info: dict[str, Any] | None = None
    if artifact.is_file() and artifact.stat().st_size > 0:
        artifact_info = {
            "path": artifact_relative,
            "sha256": sha256(artifact),
            "bytes": artifact.stat().st_size,
        }
    elif require_artifact:
        raise ValueError(f"target artifact is missing or empty: {artifact}")
    return {
        "schema": SCHEMA,
        "adapter_sha256": sha256(adapter_path(target)),
        "source_hash": tree_hash(source, source_patterns),
        "target_hash": tree_hash(target, target_patterns),
        "artifact": artifact_info,
    }


def require_identity(
    recorded: Any,
    target: pathlib.Path,
    *,
    require_artifact: bool = True,
) -> dict[str, Any]:
    current = current_identity(target, require_artifact=require_artifact)
    if not isinstance(recorded, dict) or recorded.get("schema") != SCHEMA:
        raise ValueError("recorded run identity schema is invalid")
    if recorded != current:
        raise ValueError("recorded run identity is stale or inconsistent")
    return current


def identity_token(identity: dict[str, Any]) -> str:
    encoded = json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()
