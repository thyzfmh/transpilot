#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
import pathlib
import subprocess
import sys
import tempfile


SKILL = pathlib.Path(__file__).resolve().parents[1]
HARNESS = SKILL / "templates/harness"


def run(command: list[str], cwd: pathlib.Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=False)


def write_adapter(target: pathlib.Path) -> None:
    (target / "harness").mkdir(parents=True, exist_ok=True)
    (target / "harness/project-adapter.json").write_text(
        json.dumps(
            {
                "schema": "source-translation-adapter-v2",
                "source_root": "../FlashDB",
                "target_artifact": "libfixture.a",
                "target_rlib": "libfixture.rlib",
                "source_hash_globs": ["Makefile", "**/*.c"],
                "target_hash_globs": [
                    "Cargo.toml",
                    "src/**/*.rs",
                    "harness/project-adapter.json",
                ],
                "runtime_timeout_seconds": 5,
                "required_evidence": {
                    "final-fixture": [
                        sys.executable,
                        "-c",
                        "print('fixture pass')",
                    ],
                    "final-api": [
                        sys.executable,
                        "-c",
                        "print('fixture api pass')",
                    ],
                },
                "native_suites": [
                    {"name": "sample", "source_file": "tests/sample.c"}
                ],
            }
        )
        + "\n"
    )


def main() -> int:
    with tempfile.TemporaryDirectory() as temporary:
        root = pathlib.Path(temporary)
        source = root / "FlashDB"
        target = root / "flashDB_rust"
        (source / "tests").mkdir(parents=True)
        (source / "src").mkdir()
        (target / "src").mkdir(parents=True)
        (target / "reports").mkdir()
        (source / "Makefile").write_text("test:\n\t@true\n")
        test_source = source / "tests/sample.c"
        test_source.write_text(
            "void suite(void) {\n"
            "  TEST_RUN(test_alpha);\n"
            "  TEST_RUN(test_beta);\n"
            "}\n"
        )
        (source / "src/module.c").write_text("int module(void) { return 0; }\n")
        (target / "Cargo.toml").write_text("[package]\nname='fixture'\nversion='0.0.0'\n")
        (target / "src/lib.rs").write_text("pub fn fixture() {}\n")
        (target / "libfixture.a").write_bytes(b"fixture archive")
        (target / "libfixture.rlib").write_bytes(b"fixture rlib")
        write_adapter(target)

        discovery = run(
            [
                sys.executable,
                str(HARNESS / "project_discovery.py"),
                "--source",
                str(source),
                "--target",
                str(target),
            ],
            root,
        )
        if discovery.returncode != 0:
            raise AssertionError(discovery.stderr or discovery.stdout)
        profile = json.loads((target / "reports/project-profile.json").read_text())
        if profile["discovered_test_count"] != 2:
            raise AssertionError(f"unexpected test count: {profile}")

        log = target / "reports/sample.log"
        log.write_text(
            "Running: test_alpha ...\n"
            "Running: test_beta ...\n"
            "FAIL test_beta: expected value mismatch\n"
        )
        acceptance = run(
            [
                sys.executable,
                str(HARNESS / "source_acceptance.py"),
                "--source",
                str(source),
                "--target",
                str(target),
                "--suite",
                f"sample|{test_source}|{log}|1|=== sample: PASSED ===",
            ],
            target,
        )
        if acceptance.returncode != 1:
            raise AssertionError(acceptance.stderr or acceptance.stdout)
        result = json.loads((target / "reports/source-acceptance.json").read_text())
        if (result["passed"], result["failed"], result["not_run"]) != (1, 1, 0):
            raise AssertionError(f"unexpected acceptance result: {result}")
        if result["cases"][1]["case_id"] != "tests/sample.c::test_beta#1":
            raise AssertionError(f"unexpected case id: {result['cases'][1]}")

        early_log = target / "reports/early-exit.log"
        early_log.write_text(
            "Running: test_alpha ...\n"
            "Running: test_beta ...\n"
        )
        early = run(
            [
                sys.executable,
                str(HARNESS / "source_acceptance.py"),
                "--source",
                str(source),
                "--target",
                str(target),
                "--output",
                "reports/early-acceptance.json",
                "--suite",
                f"sample|{test_source}|{early_log}|0|=== sample: PASSED ===",
            ],
            target,
        )
        if early.returncode != 1:
            raise AssertionError("suite without completion marker was accepted")
        early_result = json.loads((target / "reports/early-acceptance.json").read_text())
        if early_result["cases"][1]["status"] == "PASS":
            raise AssertionError("last started case passed without suite completion")

        checkpoint = run([sys.executable, str(HARNESS / "checkpoint.py"), "init"], target)
        if checkpoint.returncode != 0:
            raise AssertionError(checkpoint.stderr or checkpoint.stdout)
        (target / "src/lib.rs").write_text("pub fn fixture() { let _changed = true; }\n")
        record = run(
            [
                sys.executable,
                str(HARNESS / "checkpoint.py"),
                "record",
                "--item",
                "tests/sample.c::test_beta#1",
                "--stage",
                "implementing",
                "--command",
                "source acceptance",
                "--exit-code",
                "1",
                "--failure",
                "expected value mismatch",
                "--next-action",
                "repair beta behavior",
            ],
            target,
        )
        if record.returncode != 0:
            raise AssertionError(record.stderr or record.stdout)
        state = json.loads((target / "reports/checkpoint.json").read_text())
        if state["item"] != "tests/sample.c::test_beta#1" or state["next_action"] != "repair beta behavior":
            raise AssertionError(f"unexpected checkpoint: {state}")

        forged_ready = run(
            [
                sys.executable,
                str(HARNESS / "checkpoint.py"),
                "record",
                "--item",
                "all",
                "--stage",
                "ready_for_final",
                "--command",
                "claimed success",
                "--exit-code",
                "0",
                "--next-action",
                "finish",
            ],
            target,
        )
        if forged_ready.returncode == 0:
            raise AssertionError("checkpoint accepted self-asserted ready_for_final")

        abi_check = run(
            [
                sys.executable,
                "-c",
                (
                    "import os,sys;"
                    f"os.chdir({str(target)!r});"
                    f"sys.path.insert(0,{str(HARNESS)!r});"
                    "import api_surface_check as a;"
                    "c='declare i32 @fdb_bad(ptr noundef)\\n';"
                    "r='define void @fdb_bad() { ret void }\\n';"
                    "assert a.llvm_signature(c,'fdb_bad') != a.llvm_signature(r,'fdb_bad');"
                    "assert a.probe_mismatches({(0,'value'):1},{(0,'value'):2},{(0,'value')},'control')"
                ),
            ],
            root,
        )
        if abi_check.returncode != 0:
            raise AssertionError(abi_check.stderr or abi_check.stdout)

        differential_files = target / "reports/differential-fixture"
        differential_files.mkdir()
        source_one = differential_files / "source-one.bin"
        source_two = differential_files / "source-two.bin"
        translated_ok = differential_files / "translated-ok.bin"
        translated_bad = differential_files / "translated-bad.bin"
        source_one.write_bytes(b"stable-A-tail")
        source_two.write_bytes(b"stable-B-tail")
        translated_ok.write_bytes(b"stable-Z-tail")
        translated_bad.write_bytes(b"broken-Z-tail")
        differential_check = run(
            [
                sys.executable,
                "-c",
                (
                    "import os,sys;"
                    f"os.chdir({str(target)!r});"
                    f"sys.path.insert(0,{str(HARNESS)!r});"
                    "import differential_compare as d;"
                    f"s1={{'changed':{{'state.bin':{{'file':__import__('pathlib').Path({str(source_one)!r})}}}},'deleted':['old.bin']}};"
                    f"s2={{'changed':{{'state.bin':{{'file':__import__('pathlib').Path({str(source_two)!r})}}}},'deleted':['old.bin']}};"
                    f"ok={{'changed':{{'state.bin':{{'file':__import__('pathlib').Path({str(translated_ok)!r})}}}},'deleted':['old.bin']}};"
                    f"bad={{'changed':{{'state.bin':{{'file':__import__('pathlib').Path({str(translated_bad)!r})}}}},'deleted':['old.bin']}};"
                    "assert d.compare_suite([s1,s2],ok)[0] == [];"
                    "assert d.compare_suite([s1,s2],ok)[2] == 1;"
                    "assert d.compare_suite([s1,s2],bad)[0]"
                ),
            ],
            root,
        )
        if differential_check.returncode != 0:
            raise AssertionError(
                differential_check.stderr or differential_check.stdout
            )

        llvm_dir = target / "target/release/deps"
        llvm_dir.mkdir(parents=True)
        llvm = llvm_dir / "fixture.ll"
        llvm.write_text("define void @fixture() { ret void }\n")
        artifacts = [target / "libfixture.a", target / "libfixture.rlib", llvm]
        (target / "reports/build-artifacts.json").write_text(
            json.dumps(
                {
                    "schema": "source-translation-build-artifacts-v1",
                    "artifacts": [
                        {
                            "path": path.relative_to(target).as_posix(),
                            "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                            "bytes": path.stat().st_size,
                        }
                        for path in artifacts
                    ],
                    "llvm_ir": [llvm.relative_to(target).as_posix()],
                }
            )
            + "\n"
        )
        artifact_check = run(
            [
                sys.executable,
                "-c",
                (
                    "import os,sys;"
                    f"os.chdir({str(target)!r});"
                    f"sys.path.insert(0,{str(HARNESS)!r});"
                    "import api_surface_check as a;"
                    "a.build_artifacts()"
                ),
            ],
            root,
        )
        if artifact_check.returncode != 0:
            raise AssertionError(artifact_check.stderr or artifact_check.stdout)
        (llvm_dir / "stale.ll").write_text("define void @stale() { ret void }\n")
        stale_check = run(
            [
                sys.executable,
                "-c",
                (
                    "import os,sys;"
                    f"os.chdir({str(target)!r});"
                    f"sys.path.insert(0,{str(HARNESS)!r});"
                    "import api_surface_check as a;"
                    "a.build_artifacts()"
                ),
            ],
            root,
        )
        if stale_check.returncode == 0 or "LLVM IR set differs" not in stale_check.stderr:
            raise AssertionError("stale LLVM IR was accepted")

        module_check = run(
            [
                sys.executable,
                "-c",
                (
                    "import os,sys;"
                    f"os.chdir({str(target)!r});"
                    f"sys.path.insert(0,{str(HARNESS)!r});"
                    "import translation_spec_check as t;"
                    "assert set(t.module_contracts()) == {'src/module.c'}"
                ),
            ],
            root,
        )
        if module_check.returncode != 0:
            raise AssertionError(module_check.stderr or module_check.stdout)
        (source / "src/unmapped.c").write_text("int unmapped(void) { return 0; }\n")
        discovered_module_check = run(
            [
                sys.executable,
                "-c",
                (
                    "import os,sys;"
                    f"os.chdir({str(target)!r});"
                    f"sys.path.insert(0,{str(HARNESS)!r});"
                    "import translation_spec_check as t;"
                    "assert set(t.module_contracts()) == {'src/module.c','src/unmapped.c'}"
                ),
            ],
            root,
        )
        if discovered_module_check.returncode != 0:
            raise AssertionError(
                discovered_module_check.stderr or discovered_module_check.stdout
            )

        python_source = root / "python-project"
        python_target = root / "python-target"
        (python_source / "tests").mkdir(parents=True)
        (python_target / "reports").mkdir(parents=True)
        (python_source / "pyproject.toml").write_text("[project]\nname='fixture'\nversion='0.0.0'\n")
        (python_source / "tests/test_sample.py").write_text(
            "def test_value():\n"
            "    assert 1 == 1\n"
        )
        python_discovery = run(
            [
                sys.executable,
                str(HARNESS / "project_discovery.py"),
                "--source",
                str(python_source),
                "--target",
                str(python_target),
            ],
            root,
        )
        if python_discovery.returncode != 0:
            raise AssertionError(python_discovery.stderr or python_discovery.stdout)
        python_profile = json.loads((python_target / "reports/project-profile.json").read_text())
        if python_profile["languages"] != {"Python": 1} or python_profile["discovered_test_count"] != 1:
            raise AssertionError(f"generic discovery failed: {python_profile}")

        custom_source = root / "custom-c-source"
        custom_target = root / "custom-c-target"
        (custom_source / "tests").mkdir(parents=True)
        (custom_target / "harness").mkdir(parents=True)
        (custom_target / "reports").mkdir()
        (custom_source / "tests/cases.c").write_text(
            "void suite(void) { CASE(test_custom_alpha); CASE(test_custom_beta); }\n"
        )
        (custom_target / "harness/project-adapter.json").write_text(
            json.dumps(
                {
                    "schema": "source-translation-adapter-v2",
                    "source_root": "../custom-c-source",
                    "target_artifact": "libfixture.a",
                    "source_hash_globs": ["tests/**/*.c"],
                    "target_hash_globs": ["harness/project-adapter.json"],
                    "native_test_protocol": {
                        "case_regex": r"\bCASE\s*\(\s*([A-Za-z_][A-Za-z0-9_]*)\s*\)"
                    },
                    "native_suites": [
                        {
                            "name": "custom",
                            "source_file": "tests/cases.c",
                        }
                    ],
                }
            )
            + "\n"
        )
        custom_coverage = run(
            [
                sys.executable,
                str(HARNESS / "c_coverage_check.py"),
                "--init",
            ],
            custom_target,
        )
        if custom_coverage.returncode != 0:
            raise AssertionError(custom_coverage.stderr or custom_coverage.stdout)
        required_text = (custom_target / "reports/source-test-required.tsv").read_text()
        if "test_custom_alpha" not in required_text or "test_custom_beta" not in required_text:
            raise AssertionError("configured source case regex was not used by coverage")

    print("general_method_test.py: PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
