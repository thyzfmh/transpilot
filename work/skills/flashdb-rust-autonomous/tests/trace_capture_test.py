#!/usr/bin/env python3
from __future__ import annotations

import json
import pathlib
import subprocess
import sys
import tempfile

SKILL = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SKILL / "templates/harness"))

import trace_capture  # noqa: E402


def build_fixture(root: pathlib.Path) -> tuple[pathlib.Path, bytes]:
    (root / "INSTRUCTION.md").write_text("fixture\n")
    (root / "code/FlashDB/inc").mkdir(parents=True)
    target = root / "code/flashDB_rust"
    (target / "src").mkdir(parents=True)
    (target / "tests").mkdir()
    (target / "reports/evidence").mkdir(parents=True)
    (target / "Cargo.toml").write_text("[package]\nname='fixture'\nversion='0.0.0'\n")
    (target / "src/lib.rs").write_text("pub fn fixture() {}\n")
    for evidence_id in trace_capture.REQUIRED_EVIDENCE_IDS:
        (target / "reports/evidence" / f"{evidence_id}.json").write_text("{}\n")
        (target / "reports/evidence" / f"{evidence_id}.log").write_text("PASS\n")
    for report in trace_capture.REQUIRED_REPORTS:
        (target / "reports" / report).write_text("fixture report\n")

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
            trace_capture.export_trace(target, "ses_fixture")
            trace_capture.verify_trace(target)

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
