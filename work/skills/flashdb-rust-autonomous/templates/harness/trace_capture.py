#!/usr/bin/env python3
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import shutil
import subprocess
import sys
from typing import Any

from adapter import adapter_path, load_adapter
from completion import read_result
from evidence_runner import SCHEMA as EVIDENCE_SCHEMA
from evidence_runner import requirements, verify_evidence
from run_identity import current_identity, require_identity, sha256
from source_acceptance import SCHEMA as ACCEPTANCE_SCHEMA


SCHEMA = "source-translation-trace-v2"


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
        if (candidate / "INSTRUCTION.md").is_file():
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


def required_reports(target: pathlib.Path) -> list[str]:
    raw = load_adapter(target).get("required_trace_reports")
    if not isinstance(raw, list) or not raw or not all(isinstance(name, str) for name in raw):
        raise ValueError("adapter required_trace_reports must be a non-empty string list")
    if len(raw) != len(set(raw)):
        raise ValueError("adapter required_trace_reports contains duplicates")
    return raw


def supporting_artifacts(target: pathlib.Path) -> list[pathlib.Path]:
    raw = load_adapter(target).get("required_trace_artifact_globs")
    if not isinstance(raw, list) or not raw or not all(isinstance(item, str) for item in raw):
        raise ValueError("adapter required_trace_artifact_globs must be a non-empty string list")
    files: set[pathlib.Path] = set()
    for pattern in raw:
        matches = sorted(path.resolve() for path in target.glob(pattern) if path.is_file())
        if not matches:
            raise ValueError(f"required trace artifact glob matched no files: {pattern}")
        for path in matches:
            try:
                path.relative_to(target.resolve())
            except ValueError as exc:
                raise ValueError(f"trace artifact escapes target: {path}") from exc
            files.add(path)
    return sorted(files)


def copy_verification(target: pathlib.Path, trace: pathlib.Path) -> dict[str, dict[str, object]]:
    destination = trace / "verification"
    if destination.exists():
        shutil.rmtree(destination)
    (destination / "evidence").mkdir(parents=True)
    (destination / "reports").mkdir(parents=True)
    (destination / "config").mkdir(parents=True)
    (destination / "result").mkdir(parents=True)

    sources: list[tuple[pathlib.Path, pathlib.Path]] = []
    for evidence_id in requirements(target):
        verify_evidence(target, f"reports/evidence/{evidence_id}.json", evidence_id)
        for suffix in [".json", ".log"]:
            source = target / "reports/evidence" / f"{evidence_id}{suffix}"
            sources.append((source, destination / "evidence" / source.name))
    for name in required_reports(target):
        source = target / "reports" / name
        if not source.is_file() or source.stat().st_size == 0:
            raise ValueError(f"missing required verification report: {source}")
        sources.append((source, destination / "reports" / name))
    sources.append(
        (
            adapter_path(target),
            destination / "config/project-adapter.json",
        )
    )
    for source in supporting_artifacts(target):
        sources.append((source, destination / source.relative_to(target)))
    result = repo_root(target) / "result/output.md"
    result_payload = read_result(target, {"TECHNICAL_GATES_PASSED"})
    if result_payload.get("identity") != current_identity(target):
        raise ValueError("result/output.md identity is stale")
    sources.append((result, destination / "result/output.md"))

    artifacts: dict[str, dict[str, object]] = {}
    for source, output in sources:
        output.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, output)
        relative = output.relative_to(trace).as_posix()
        if relative in artifacts:
            raise ValueError(f"duplicate trace artifact path: {relative}")
        artifacts[relative] = {"sha256": sha256(output), "bytes": output.stat().st_size}
    return artifacts


def expected_artifacts(target: pathlib.Path, trace: pathlib.Path) -> set[str]:
    expected = {
        f"verification/evidence/{evidence_id}{suffix}"
        for evidence_id in requirements(target)
        for suffix in [".json", ".log"]
    }
    expected.update(f"verification/reports/{name}" for name in required_reports(target))
    expected.add("verification/config/project-adapter.json")
    expected.update(
        f"verification/{path.relative_to(target).as_posix()}"
        for path in supporting_artifacts(target)
    )
    expected.add("verification/result/output.md")
    return expected


def validate_copied_evidence(
    target: pathlib.Path,
    trace: pathlib.Path,
    evidence_id: str,
    identity: dict[str, Any],
) -> None:
    record_path = trace / f"verification/evidence/{evidence_id}.json"
    log_path = trace / f"verification/evidence/{evidence_id}.log"
    data = json.loads(record_path.read_text())
    if (
        data.get("schema") != EVIDENCE_SCHEMA
        or data.get("id") != evidence_id
        or data.get("exit_code") != 0
        or data.get("command") != requirements(target)[evidence_id]
        or data.get("identity") != identity
        or pathlib.Path(str(data.get("cwd", ""))).resolve() != target.resolve()
        or data.get("log") != f"reports/evidence/{evidence_id}.log"
        or not isinstance(data.get("timeout_seconds"), int)
        or int(data.get("timeout_seconds", 0)) <= 0
        or not isinstance(data.get("started_at"), str)
        or not isinstance(data.get("finished_at"), str)
    ):
        raise ValueError(f"copied evidence record is invalid: {evidence_id}")
    before = data.get("identity_before")
    if not isinstance(before, dict):
        raise ValueError(f"copied evidence pre-run identity is missing: {evidence_id}")
    for field in ["adapter_sha256", "source_hash", "target_hash"]:
        if before.get(field) != identity.get(field):
            raise ValueError(f"copied evidence inputs changed: {evidence_id}")
    if evidence_id != "final-build" and before.get("artifact") != identity.get("artifact"):
        raise ValueError(f"copied evidence artifact changed: {evidence_id}")
    if not log_path.is_file() or sha256(log_path) != data.get("log_sha256"):
        raise ValueError(f"copied evidence log hash mismatch: {evidence_id}")


def validate_copied_reports(
    target: pathlib.Path,
    trace: pathlib.Path,
    identity: dict[str, Any],
) -> None:
    acceptance_path = trace / "verification/reports/source-acceptance.json"
    acceptance = json.loads(acceptance_path.read_text())
    if acceptance.get("schema") != ACCEPTANCE_SCHEMA or acceptance.get("identity") != identity:
        raise ValueError("copied source acceptance identity is invalid")
    total = int(acceptance.get("total", 0))
    if (
        total <= 0
        or int(acceptance.get("passed", -1)) != total
        or int(acceptance.get("failed", -1)) != 0
        or int(acceptance.get("not_run", -1)) != 0
    ):
        raise ValueError("copied source acceptance is incomplete")
    for suite in acceptance.get("suites", []):
        if not isinstance(suite, dict):
            raise ValueError("copied source acceptance suite is invalid")
        log = trace / "verification" / str(suite.get("log", ""))
        if not log.is_file() or sha256(log) != suite.get("log_sha256"):
            raise ValueError("copied source acceptance log hash mismatch")
    copied_adapter = trace / "verification/config/project-adapter.json"
    if sha256(copied_adapter) != identity.get("adapter_sha256"):
        raise ValueError("copied project adapter hash mismatch")
    tool_versions = json.loads(
        (trace / "verification/reports/tool-versions.json").read_text()
    )
    if (
        tool_versions.get("schema") != "source-translation-tool-versions-v1"
        or not isinstance(tool_versions.get("tools"), list)
        or not tool_versions["tools"]
    ):
        raise ValueError("copied tool version report is invalid")
    build_artifacts = json.loads(
        (trace / "verification/reports/build-artifacts.json").read_text()
    )
    if (
        build_artifacts.get("schema") != "source-translation-build-artifacts-v1"
        or not isinstance(build_artifacts.get("artifacts"), list)
        or not build_artifacts["artifacts"]
    ):
        raise ValueError("copied build artifact report is invalid")
    checkpoint = json.loads((trace / "verification/reports/checkpoint.json").read_text())
    copied_gates = {
        evidence_id: json.loads(
            (trace / f"verification/evidence/{evidence_id}.json").read_text()
        ).get("log_sha256")
        for evidence_id in requirements(target)
    }
    if (
        checkpoint.get("schema") != "source-translation-checkpoint-v3"
        or checkpoint.get("identity") != identity
        or checkpoint.get("stage") != "ready_for_final"
        or checkpoint.get("gate_evidence") != copied_gates
    ):
        raise ValueError("copied checkpoint is stale or incomplete")
    final_report = trace / "verification/reports/final-report.md"
    if "- Status: PASSED" not in final_report.read_text(errors="replace"):
        raise ValueError("copied final report is not PASSED")
    copied_result = trace / "verification/result/output.md"
    if copied_result.read_bytes() != (repo_root(target) / "result/output.md").read_bytes():
        raise ValueError("copied result/output.md is not current")
    if read_result(target).get("identity") != identity:
        raise ValueError("result/output.md identity differs from the trace")


def export_trace(target: pathlib.Path, session_id: str | None) -> int:
    target = target.resolve()
    adapter = load_adapter(target)
    if adapter.get("trace_provider") != "opencode":
        raise ValueError("configured trace provider is not supported by this adapter")
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
    identity = current_identity(target)
    manifest = {
        "schema": SCHEMA,
        "session_id": selected,
        "repository": repo.as_posix(),
        "target": target.relative_to(repo).as_posix(),
        "provider": "opencode",
        "export_command": ["opencode", "export", selected],
        "sanitized": False,
        "provider_version": version.stdout.decode(errors="replace").strip(),
        "exported_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "chat": {
            "path": "llm_chat_log.json",
            "sha256": sha256(chat),
            "bytes": chat.stat().st_size,
            "messages": len(data["messages"]),
            "user_messages": user_count,
            "assistant_messages": assistant_count,
        },
        "identity": identity,
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
    if (
        manifest.get("schema") != SCHEMA
        or manifest.get("sanitized") is not False
        or manifest.get("provider") != load_adapter(target).get("trace_provider")
    ):
        raise ValueError("trace manifest schema, provider, or sanitization flag is invalid")
    if pathlib.Path(str(manifest.get("repository", ""))).resolve() != repo.resolve():
        raise ValueError("trace manifest repository mismatch")
    chat_info = manifest.get("chat")
    if not isinstance(chat_info, dict):
        raise ValueError("trace manifest chat metadata is missing")
    chat = trace / str(chat_info.get("path", ""))
    if not chat.is_file() or sha256(chat) != chat_info.get("sha256"):
        raise ValueError("AI interaction log hash mismatch")
    data = json.loads(chat.read_bytes())
    user_count, assistant_count = validate_chat(data, repo, str(manifest.get("session_id", "")))
    if (
        chat_info.get("messages") != len(data["messages"])
        or chat_info.get("user_messages") != user_count
        or chat_info.get("assistant_messages") != assistant_count
    ):
        raise ValueError("AI interaction log counts mismatch")
    identity = current_identity(target)
    if manifest.get("identity") != identity:
        raise ValueError("trace identity is stale")
    artifacts = manifest.get("verification_artifacts")
    if not isinstance(artifacts, dict):
        raise ValueError("verification artifact index is invalid")
    expected = expected_artifacts(target, trace)
    if set(artifacts) != expected:
        raise ValueError("trace artifact set is incomplete or contains unexpected files")
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
    for evidence_id in requirements(target):
        validate_copied_evidence(target, trace, evidence_id, identity)
    validate_copied_reports(target, trace, identity)
    print(f"TRACE_VERIFY_PASS: session={manifest['session_id']} artifacts={len(artifacts)}")
    return 0


def refresh_result(target: pathlib.Path) -> int:
    target = target.resolve()
    repo = repo_root(target)
    trace = repo / "logs/trace"
    manifest_path = trace / "trace-manifest.json"
    if not manifest_path.is_file():
        raise ValueError("trace manifest is missing")
    manifest = json.loads(manifest_path.read_text())
    if manifest.get("identity") != current_identity(target):
        raise ValueError("trace identity is stale")
    result_payload = read_result(target, {"PASSED"})
    if result_payload.get("identity") != manifest.get("identity"):
        raise ValueError("final result identity differs from trace")
    source = repo / "result/output.md"
    output = trace / "verification/result/output.md"
    shutil.copyfile(source, output)
    artifacts = manifest.get("verification_artifacts")
    if not isinstance(artifacts, dict):
        raise ValueError("trace artifact index is invalid")
    key = "verification/result/output.md"
    if key not in artifacts:
        raise ValueError("trace result artifact entry is missing")
    artifacts[key] = {"sha256": sha256(output), "bytes": output.stat().st_size}
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n")
    print("TRACE_RESULT_REFRESH_PASS")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="action", required=True)
    export = sub.add_parser("export")
    export.add_argument("--target", default=".")
    export.add_argument("--session-id")
    verify = sub.add_parser("verify")
    verify.add_argument("--target", default=".")
    session = sub.add_parser("session")
    session.add_argument("--target", default=".")
    refresh = sub.add_parser("refresh-result")
    refresh.add_argument("--target", default=".")
    args = parser.parse_args()
    target = pathlib.Path(args.target)
    if args.action == "export":
        return export_trace(target, args.session_id)
    if args.action == "session":
        selected = discover_session(repo_root(target))
        print(f"TRACE_SESSION_PASS: {selected}")
        return 0
    if args.action == "refresh-result":
        return refresh_result(target)
    return verify_trace(target)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"TRACE_CAPTURE_FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
