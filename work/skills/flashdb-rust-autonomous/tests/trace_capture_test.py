#!/usr/bin/env python3
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile

SKILL = pathlib.Path(__file__).resolve().parents[1]
HARNESS = SKILL / "templates/harness"
sys.path.insert(0, str(HARNESS))

import evidence_runner  # noqa: E402
import trace_capture  # noqa: E402
import completion  # noqa: E402
from run_identity import current_identity, sha256  # noqa: E402


def machine_result(payload: dict[str, object]) -> str:
    return (
        "# Execution Result\n\n- Status: PASSED\n\n"
        "<!-- machine-result-begin -->\n```json\n"
        + json.dumps(payload, sort_keys=True)
        + "\n```\n<!-- machine-result-end -->\n"
    )


def build_fixture(root: pathlib.Path) -> tuple[pathlib.Path, bytes]:
    (root / "INSTRUCTION.md").write_text("fixture\n")
    source = root / "code/FlashDB"
    (source / "inc").mkdir(parents=True)
    (source / "inc/fixture.h").write_text("int fixture(void);\n")
    target = root / "code/flashDB_rust"
    (target / "src").mkdir(parents=True)
    (target / "tests").mkdir()
    (target / "harness").mkdir()
    (target / "reports/evidence").mkdir(parents=True)
    (target / "reports/source-acceptance-logs").mkdir()
    (target / "Cargo.toml").write_text("[package]\nname='fixture'\nversion='0.0.0'\n")
    (target / "src/lib.rs").write_text("pub fn fixture() {}\n")
    (target / "libfixture.a").write_bytes(b"fixture archive")
    command = [sys.executable, "-c", "print('verified fixture')"]
    adapter = {
        "schema": "source-translation-adapter-v2",
        "source_root": "../FlashDB",
        "target_artifact": "libfixture.a",
        "source_hash_globs": ["inc/**/*.h"],
        "target_hash_globs": [
            "Cargo.toml",
            "src/**/*.rs",
            "harness/project-adapter.json",
        ],
        "runtime_timeout_seconds": 5,
        "required_evidence": {
            "final-source": command,
            "final-build": command,
        },
        "required_trace_reports": [
            "checkpoint.json",
            "source-acceptance.json",
            "final-report.md",
            "tool-versions.json",
            "build-artifacts.json",
        ],
        "required_trace_artifact_globs": [
            "reports/source-acceptance-logs/*.log"
        ],
        "trace_provider": "opencode",
    }
    (target / "harness/project-adapter.json").write_text(json.dumps(adapter) + "\n")

    log = target / "reports/source-acceptance-logs/sample.log"
    log.write_text("Running: fixture ...\n=== fixture: PASSED ===\n")
    identity = current_identity(target)
    acceptance = {
        "schema": "source-native-acceptance-v2",
        "identity": identity,
        "total": 1,
        "passed": 1,
        "failed": 0,
        "not_run": 0,
        "suites": [
            {
                "name": "sample",
                "source_file": "tests/sample.c",
                "log": log.relative_to(target).as_posix(),
                "log_sha256": sha256(log),
                "exit_code": 0,
                "pass_regex": "PASSED",
                "protocol_complete": True,
                "protocol_errors": [],
                "total": 1,
                "passed": 1,
            }
        ],
        "cases": [
            {
                "case_id": "tests/sample.c::fixture#1",
                "name": "fixture",
                "occurrence": 1,
                "status": "PASS",
                "failure": "",
                "suite": "sample",
                "source_file": "tests/sample.c",
            }
        ],
    }
    (target / "reports/source-acceptance.json").write_text(json.dumps(acceptance) + "\n")
    (target / "reports/final-report.md").write_text("# Final\n\n- Status: PASSED\n")
    (target / "reports/tool-versions.json").write_text(
        json.dumps(
            {
                "schema": "source-translation-tool-versions-v1",
                "tools": [{"tool": "python3", "version": "fixture"}],
            }
        )
        + "\n"
    )
    (target / "reports/build-artifacts.json").write_text(
        json.dumps(
            {
                "schema": "source-translation-build-artifacts-v1",
                "artifacts": [
                    {
                        "path": "libfixture.a",
                        "sha256": sha256(target / "libfixture.a"),
                        "bytes": (target / "libfixture.a").stat().st_size,
                    }
                ],
                "llvm_ir": [],
            }
        )
        + "\n"
    )
    (root / "result").mkdir()
    (root / "result/output.md").write_text(
        machine_result(
            {
                "schema": "source-translation-result-v2",
                "status": "TECHNICAL_GATES_PASSED",
                "identity": identity,
            }
        )
    )
    for evidence_id in adapter["required_evidence"]:
        (target / "reports/evidence" / f"{evidence_id}.json").write_text("{}\n")
        (target / "reports/evidence" / f"{evidence_id}.log").write_text("forged\n")

    chat = {
        "info": {"id": "ses_fixture", "directory": root.as_posix()},
        "messages": [
            {"info": {"role": "user"}, "parts": [{"type": "text", "text": "execute"}]},
            {"info": {"role": "assistant"}, "parts": [{"type": "text", "text": "working"}]},
        ],
    }
    return target, json.dumps(chat, ensure_ascii=False).encode()


def main() -> int:
    original_run = trace_capture.run
    original_export = trace_capture.export_session
    try:
        with tempfile.TemporaryDirectory() as temporary:
            root = pathlib.Path(temporary).resolve()
            target, chat = build_fixture(root)

            def fake_run(command: list[str]) -> subprocess.CompletedProcess[bytes]:
                if command == ["opencode", "--version"]:
                    return subprocess.CompletedProcess(command, 0, b"test-version\n", b"")
                raise AssertionError(f"unexpected command: {command}")

            def fake_export(session_id: str, output: pathlib.Path) -> None:
                if session_id != "ses_fixture":
                    raise AssertionError(f"unexpected session: {session_id}")
                output.write_bytes(chat)

            trace_capture.run = fake_run
            trace_capture.export_session = fake_export
            try:
                trace_capture.export_trace(target, "ses_fixture")
            except ValueError as exc:
                if "evidence" not in str(exc):
                    raise
            else:
                raise AssertionError("forged evidence records were accepted")

            for evidence_id, command in evidence_runner.requirements(target).items():
                if evidence_runner.run_evidence(target, evidence_id, command) != 0:
                    raise AssertionError(f"fixture evidence failed: {evidence_id}")
            gate_evidence = {
                evidence_id: json.loads(
                    (target / f"reports/evidence/{evidence_id}.json").read_text()
                )["log_sha256"]
                for evidence_id in evidence_runner.requirements(target)
            }
            checkpoint = {
                "schema": "source-translation-checkpoint-v3",
                "identity": current_identity(target),
                "stage": "ready_for_final",
                "last_exit_code": 0,
                "counts": {"passed": 1, "failed": 0, "not_run": 0, "total": 1},
                "gate_evidence": gate_evidence,
            }
            (target / "reports/checkpoint.json").write_text(json.dumps(checkpoint) + "\n")
            completion.stage_result(target)

            trace_capture.export_trace(target, "ses_fixture")
            trace_capture.verify_trace(target)
            completion.finalize_result(target)
            trace_capture.refresh_result(target)
            trace_capture.verify_trace(target)
            completion.verify_result(target, require_trace=True)

            manifest_path = root / "logs/trace/trace-manifest.json"
            manifest_text = manifest_path.read_text()
            manifest = json.loads(manifest_text)
            manifest["verification_artifacts"].pop(next(iter(manifest["verification_artifacts"])))
            manifest_path.write_text(json.dumps(manifest) + "\n")
            try:
                trace_capture.verify_trace(target)
            except ValueError as exc:
                if "artifact set" not in str(exc):
                    raise
            else:
                raise AssertionError("incomplete trace artifact index was accepted")
            manifest_path.write_text(manifest_text)

            chat_path = root / "logs/trace/llm_chat_log.json"
            chat_path.write_bytes(chat_path.read_bytes() + b" ")
            try:
                trace_capture.verify_trace(target)
            except ValueError as exc:
                if "hash mismatch" not in str(exc):
                    raise
            else:
                raise AssertionError("tampered AI interaction log was accepted")
    finally:
        trace_capture.run = original_run
        trace_capture.export_session = original_export
    print("trace_capture_test.py: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
