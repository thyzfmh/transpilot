#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import pathlib
import shutil
import subprocess
import sys
from typing import Any

from evidence_runner import current_source_hash, current_target_hash

SCHEMA = "flashdb-trace-v1"
REQUIRED_EVIDENCE_IDS = [
    "final-source",
    "final-profile",
    "final-build",
    "final-c-link",
    "final-interop",
    "final-rust-policy",
    "final-c-coverage",
    "final-api",
]
REQUIRED_REPORTS = [
    "checkpoint.json",
    "c-test-coverage.tsv",
    "c-api-coverage.tsv",
    "c-module-coverage.tsv",
    "c-to-rust-compliance.tsv",
    "config-profile.md",
]


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run(command: list[str]) -> subprocess.CompletedProcess[bytes]:
    return subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)


def export_session(session_id: str, output: pathlib.Path) -> None:
    with output.open("wb") as handle:
        process = subprocess.run(
            ["opencode", "export", session_id],
            stdout=handle,
            stderr=subprocess.PIPE,
            check=False,
        )
    if process.returncode != 0:
        raise ValueError(
            f"OpenCode export failed: {process.stderr.decode(errors='replace').strip()}"
        )


def repo_root(target: pathlib.Path) -> pathlib.Path:
    target = target.resolve()
    for candidate in [target.parent, *target.parents]:
        if (candidate / "INSTRUCTION.md").is_file() and (candidate / "code/FlashDB").is_dir():
            return candidate
    raise ValueError(f"cannot locate repository root from target: {target}")


def discover_session(repo: pathlib.Path) -> str:
    directory = repo.as_posix().replace("'", "''")
    query = (
        "SELECT id FROM session "
        f"WHERE directory = '{directory}' AND time_archived IS NULL "
        "ORDER BY time_updated DESC LIMIT 1;"
    )
    process = run(["opencode", "db", query, "--format", "json"])
    if process.returncode != 0:
        raise ValueError(f"cannot query OpenCode sessions: {process.stderr.decode(errors='replace').strip()}")
    rows = json.loads(process.stdout)
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0].get("id"), str):
        raise ValueError("no active OpenCode session found for this repository")
    return rows[0]["id"]


def validate_chat(data: Any, repo: pathlib.Path, session_id: str) -> tuple[int, int]:
    if not isinstance(data, dict) or not isinstance(data.get("info"), dict):
        raise ValueError("OpenCode export is not a session object")
    info = data["info"]
    if info.get("id") != session_id:
        raise ValueError("OpenCode export session id mismatch")
    directory = pathlib.Path(str(info.get("directory", ""))).resolve()
    if directory != repo.resolve():
        raise ValueError(f"OpenCode session belongs to another directory: {directory}")
    messages = data.get("messages")
    if not isinstance(messages, list) or not messages:
        raise ValueError("OpenCode export contains no messages")
    roles = [message.get("info", {}).get("role") for message in messages if isinstance(message, dict)]
    user_count = roles.count("user")
    assistant_count = roles.count("assistant")
    if user_count == 0 or assistant_count == 0:
        raise ValueError("OpenCode export must contain both user and assistant messages")
    return user_count, assistant_count


def copy_verification(target: pathlib.Path, trace: pathlib.Path) -> dict[str, dict[str, object]]:
    destination = trace / "verification"
    if destination.exists():
        shutil.rmtree(destination)
    (destination / "evidence").mkdir(parents=True)
    (destination / "reports").mkdir(parents=True)

    sources: list[tuple[pathlib.Path, pathlib.Path]] = []
    for evidence_id in REQUIRED_EVIDENCE_IDS:
        for suffix in [".json", ".log"]:
            source = target / "reports/evidence" / f"{evidence_id}{suffix}"
            if not source.is_file():
                raise ValueError(f"missing required verification evidence: {source}")
            sources.append((source, destination / "evidence" / source.name))
    for name in REQUIRED_REPORTS:
        source = target / "reports" / name
        if not source.is_file():
            raise ValueError(f"missing required verification report: {source}")
        sources.append((source, destination / "reports" / name))
    final_report = target / "reports/final-report.md"
    if final_report.is_file():
        sources.append((final_report, destination / "reports/final-report.md"))

    artifacts: dict[str, dict[str, object]] = {}
    for source, output in sources:
        shutil.copyfile(source, output)
        relative = output.relative_to(trace).as_posix()
        artifacts[relative] = {"sha256": sha256(output), "bytes": output.stat().st_size}
    return artifacts


def export_trace(target: pathlib.Path, session_id: str | None) -> int:
    target = target.resolve()
    repo = repo_root(target)
    trace = repo / "logs/trace"
    trace.mkdir(parents=True, exist_ok=True)
    selected = session_id or discover_session(repo)
    temporary = trace / ".llm_chat_log.json.tmp"
    export_session(selected, temporary)
    data = json.loads(temporary.read_bytes())
    user_count, assistant_count = validate_chat(data, repo, selected)

    chat = trace / "llm_chat_log.json"
    temporary.replace(chat)
    artifacts = copy_verification(target, trace)
    version = run(["opencode", "--version"])
    if version.returncode != 0:
        raise ValueError("cannot read OpenCode version")
    manifest = {
        "schema": SCHEMA,
        "session_id": selected,
        "repository": repo.as_posix(),
        "target": target.relative_to(repo).as_posix(),
        "export_command": ["opencode", "export", selected],
        "sanitized": False,
        "opencode_version": version.stdout.decode(errors="replace").strip(),
        "exported_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "chat": {
            "path": "llm_chat_log.json",
            "sha256": sha256(chat),
            "bytes": chat.stat().st_size,
            "messages": len(data["messages"]),
            "user_messages": user_count,
            "assistant_messages": assistant_count,
        },
        "source_hash": current_source_hash(target),
        "target_hash": current_target_hash(target),
        "verification_artifacts": artifacts,
    }
    (trace / "trace-manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    )
    print(f"TRACE_EXPORT_PASS: session={selected} messages={len(data['messages'])}")
    return 0


def verify_trace(target: pathlib.Path) -> int:
    target = target.resolve()
    repo = repo_root(target)
    trace = repo / "logs/trace"
    manifest_path = trace / "trace-manifest.json"
    if not manifest_path.is_file():
        raise ValueError(f"missing trace manifest: {manifest_path}")
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("schema") != SCHEMA or manifest.get("sanitized") is not False:
        raise ValueError("trace manifest schema or sanitization flag is invalid")
    if pathlib.Path(str(manifest.get("repository", ""))).resolve() != repo.resolve():
        raise ValueError("trace manifest repository mismatch")
    chat_info = manifest.get("chat")
    if not isinstance(chat_info, dict):
        raise ValueError("trace manifest chat metadata is missing")
    chat = trace / str(chat_info.get("path", ""))
    if not chat.is_file() or sha256(chat) != chat_info.get("sha256"):
        raise ValueError("AI interaction log hash mismatch")
    data = json.loads(chat.read_bytes())
    validate_chat(data, repo, str(manifest.get("session_id", "")))
    if manifest.get("source_hash") != current_source_hash(target):
        raise ValueError("trace was captured for a different C source hash")
    if manifest.get("target_hash") != current_target_hash(target):
        raise ValueError("trace was captured for a different Rust target hash")
    artifacts = manifest.get("verification_artifacts")
    if not isinstance(artifacts, dict) or not artifacts:
        raise ValueError("verification artifact index is empty")
    for relative, metadata in artifacts.items():
        path = (trace / relative).resolve()
        try:
            path.relative_to(trace.resolve())
        except ValueError as exc:
            raise ValueError(f"trace artifact escapes logs/trace: {relative}") from exc
        if not isinstance(metadata, dict) or not path.is_file():
            raise ValueError(f"trace artifact is missing: {relative}")
        if sha256(path) != metadata.get("sha256") or path.stat().st_size != metadata.get("bytes"):
            raise ValueError(f"trace artifact hash mismatch: {relative}")
    print(
        "TRACE_VERIFY_PASS: "
        f"session={manifest['session_id']} artifacts={len(artifacts)}"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="action", required=True)
    export = sub.add_parser("export")
    export.add_argument("--target", default="code/flashDB_rust")
    export.add_argument("--session-id")
    verify = sub.add_parser("verify")
    verify.add_argument("--target", default="code/flashDB_rust")
    session = sub.add_parser("session")
    session.add_argument("--target", default="code/flashDB_rust")
    args = parser.parse_args()
    target = pathlib.Path(args.target)
    if args.action == "export":
        return export_trace(target, args.session_id)
    if args.action == "session":
        selected = discover_session(repo_root(target))
        print(f"TRACE_SESSION_PASS: {selected}")
        return 0
    return verify_trace(target)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"TRACE_CAPTURE_FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
