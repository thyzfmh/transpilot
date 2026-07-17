from __future__ import annotations

import json
import pathlib
from typing import Any


SCHEMA = "source-translation-adapter-v2"


def adapter_path(target: pathlib.Path) -> pathlib.Path:
    candidates = [
        target.resolve() / "harness/project-adapter.json",
        pathlib.Path(__file__).resolve().with_name("project-adapter.json"),
    ]
    path = next((candidate for candidate in candidates if candidate.is_file()), None)
    if path is None:
        raise ValueError("missing project-adapter.json")
    return path


def load_adapter(target: pathlib.Path) -> dict[str, Any]:
    path = adapter_path(target)
    data = json.loads(path.read_text())
    if data.get("schema") != SCHEMA:
        raise ValueError("project adapter schema mismatch")
    return data


def source_root(target: pathlib.Path, adapter: dict[str, Any]) -> pathlib.Path:
    value = adapter.get("source_root")
    if not isinstance(value, str) or not value:
        raise ValueError("project adapter source_root is missing")
    return (target.resolve() / value).resolve()


def require_list(adapter: dict[str, Any], key: str) -> list[Any]:
    value = adapter.get(key)
    if not isinstance(value, list) or not value:
        raise ValueError(f"project adapter {key} must be a non-empty list")
    return value


def expand_command(
    command: list[Any],
    target: pathlib.Path,
    adapter: dict[str, Any],
) -> list[str]:
    source = source_root(target, adapter)
    artifact = target / str(adapter.get("target_artifact", ""))
    values = {
        "source": source.as_posix(),
        "target": target.resolve().as_posix(),
        "artifact": artifact.resolve().as_posix(),
    }
    if not command or not all(isinstance(part, str) for part in command):
        raise ValueError("adapter command must be a non-empty string list")
    return [part.format(**values) for part in command]
