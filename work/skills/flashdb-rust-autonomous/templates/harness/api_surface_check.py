#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import pathlib
import re
import shutil
import subprocess
import sys

from adapter import load_adapter, source_root
from run_identity import sha256

TARGET = pathlib.Path.cwd()
ADAPTER = load_adapter(TARGET)
SOURCE = source_root(TARGET, ADAPTER)
REPORTS = TARGET / "reports"
REQUIRED = REPORTS / "c-api-required.tsv"
COVERAGE = REPORTS / "c-api-coverage.tsv"
SUMMARY = REPORTS / "c-api-coverage-check.md"


def strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"(?m)//.*$", "", text)


def required_items() -> list[dict[str, str]]:
    public_header = SOURCE / str(ADAPTER.get("public_header", ""))
    definitions = SOURCE / str(ADAPTER.get("definitions_header", ""))
    if not public_header.is_file() or not definitions.is_file():
        raise ValueError("missing public C headers")
    function_pattern = str(ADAPTER.get("public_function_regex", ""))
    control_pattern = str(ADAPTER.get("control_value_regex", ""))
    if not function_pattern or not control_pattern:
        raise ValueError("project adapter API extraction patterns are missing")
    functions = sorted(
        set(re.findall(function_pattern, strip_comments(public_header.read_text(errors="replace"))))
    )
    matches = re.findall(
        control_pattern,
        strip_comments(definitions.read_text(errors="replace")),
    )
    if not all(isinstance(match, tuple) and len(match) == 2 for match in matches):
        raise ValueError("control_value_regex must capture control name and value")
    control_values: dict[str, str] = {}
    for name, value in matches:
        if name in control_values and control_values[name] != value:
            raise ValueError(f"conflicting C control definitions: {name}")
        control_values[name] = value
    if not functions:
        raise ValueError("no public C functions discovered")
    return [
        *({"kind": "function", "name": name, "source": public_header.relative_to(SOURCE).as_posix(), "expected": ""} for name in functions),
        *(
            {
                "kind": "control",
                "name": name,
                "source": definitions.relative_to(SOURCE).as_posix(),
                "expected": value,
            }
            for name, value in sorted(control_values.items())
        ),
    ]


def write_tsv(path: pathlib.Path, fields: list[str], rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t")
        writer.writeheader()
        writer.writerows(rows)


def initialize(items: list[dict[str, str]]) -> int:
    write_tsv(REQUIRED, ["kind", "name", "source", "expected"], items)
    write_tsv(
        COVERAGE,
        ["kind", "name", "status", "evidence"],
        [{"kind": item["kind"], "name": item["name"], "status": "PENDING", "evidence": ""} for item in items],
    )
    print(f"C_API_DISCOVERY_PASS: required={len(items)}")
    return 0


def expand_flags(values: object) -> list[str]:
    if not isinstance(values, list) or not all(isinstance(value, str) for value in values):
        raise ValueError("adapter C flags must be string lists")
    replacements = {
        "source": SOURCE.as_posix(),
        "target": TARGET.resolve().as_posix(),
        "artifact": (TARGET / str(ADAPTER.get("target_artifact", ""))).as_posix(),
    }
    return [value.format(**replacements) for value in values]


def split_llvm_params(text: str) -> list[str]:
    values: list[str] = []
    start = 0
    depth = 0
    pairs = {"(": ")", "[": "]", "{": "}", "<": ">"}
    closing = set(pairs.values())
    for index, char in enumerate(text):
        if char in pairs:
            depth += 1
        elif char in closing:
            depth -= 1
        elif char == "," and depth == 0:
            values.append(text[start:index].strip())
            start = index + 1
    tail = text[start:].strip()
    if tail:
        values.append(tail)
    return values


def llvm_type_at_start(value: str) -> str:
    value = value.strip()
    if value == "...":
        return value
    if value[:1] in {"[", "{", "<"}:
        opener = value[0]
        closer = {"[": "]", "{": "}", "<": ">"}[opener]
        depth = 0
        for index, char in enumerate(value):
            if char == opener:
                depth += 1
            elif char == closer:
                depth -= 1
                if depth == 0:
                    return re.sub(r"\s+", " ", value[: index + 1])
    match = re.match(r'(?:i\d+|void|half|float|double|fp128|ptr|%["A-Za-z0-9_.$]+)', value)
    if not match:
        raise ValueError(f"cannot parse LLVM parameter type: {value}")
    return match.group(0)


def llvm_signature(text: str, name: str) -> tuple[str, tuple[str, ...]]:
    marker = f"@{name}("
    position = text.find(marker)
    if position < 0:
        raise ValueError(f"LLVM IR does not contain function: {name}")
    line_start = text.rfind("\n", 0, position) + 1
    prefix = text[line_start:position].strip()
    if not (prefix.startswith("define ") or prefix.startswith("declare ")):
        raise ValueError(f"LLVM symbol is not a function declaration: {name}")
    return_tokens = re.findall(
        r'(?:i\d+|void|half|float|double|fp128|ptr|%["A-Za-z0-9_.$]+)',
        prefix,
    )
    if not return_tokens:
        raise ValueError(f"cannot parse LLVM return type: {name}")
    depth = 1
    index = position + len(marker)
    while index < len(text) and depth:
        if text[index] == "(":
            depth += 1
        elif text[index] == ")":
            depth -= 1
        index += 1
    if depth:
        raise ValueError(f"unterminated LLVM function signature: {name}")
    params_text = text[position + len(marker) : index - 1]
    params = tuple(
        llvm_type_at_start(param)
        for param in split_llvm_params(params_text)
        if param.strip()
    )
    return return_tokens[-1], params


def build_artifacts() -> tuple[list[pathlib.Path], pathlib.Path]:
    report = REPORTS / "build-artifacts.json"
    if not report.is_file():
        raise ValueError("build artifact manifest is missing; run the configured build gate")
    data = json.loads(report.read_text())
    if data.get("schema") != "source-translation-build-artifacts-v1":
        raise ValueError("build artifact manifest schema mismatch")
    entries = data.get("artifacts")
    llvm_names = data.get("llvm_ir")
    if (
        not isinstance(entries, list)
        or not isinstance(llvm_names, list)
        or not llvm_names
        or not all(isinstance(name, str) for name in llvm_names)
    ):
        raise ValueError("build artifact manifest is incomplete")
    indexed: dict[str, pathlib.Path] = {}
    for entry in entries:
        if not isinstance(entry, dict) or not isinstance(entry.get("path"), str):
            raise ValueError("build artifact entry is invalid")
        path = (TARGET / entry["path"]).resolve()
        try:
            path.relative_to(TARGET.resolve())
        except ValueError as exc:
            raise ValueError("build artifact path escapes target") from exc
        if (
            not path.is_file()
            or path.stat().st_size != entry.get("bytes")
            or sha256(path) != entry.get("sha256")
        ):
            raise ValueError(f"build artifact is stale or changed: {entry['path']}")
        indexed[entry["path"]] = path
    llvm_files = [indexed.get(name) for name in llvm_names]
    if any(path is None for path in llvm_files):
        raise ValueError("LLVM IR is not indexed by the build artifact manifest")
    current_llvm = {
        path.relative_to(TARGET).as_posix()
        for path in (TARGET / "target/release/deps").glob("*.ll")
        if path.is_file()
    }
    if current_llvm != set(llvm_names):
        raise ValueError("LLVM IR set differs from the current build artifact manifest")
    rlib_name = str(ADAPTER.get("target_rlib", ""))
    rlib = indexed.get(rlib_name)
    if rlib is None:
        raise ValueError("configured Rust rlib is not indexed by the build artifact manifest")
    return [path for path in llvm_files if path is not None], rlib


def parse_probe_output(text: str, expected_prefix: str) -> dict[tuple[int, str], int]:
    values: dict[tuple[int, str], int] = {}
    for line in text.splitlines():
        parts = line.split("\t")
        if len(parts) != 4 or parts[0] != expected_prefix:
            continue
        key = (int(parts[1]), parts[2])
        if key in values:
            raise ValueError(f"duplicate probe value: {expected_prefix} {key}")
        values[key] = int(parts[3], 10)
    return values


def probe_mismatches(
    c_values: dict[tuple[int, str], int],
    rust_values: dict[tuple[int, str], int],
    expected: set[tuple[int, str]],
    label: str,
) -> list[str]:
    if set(c_values) != expected or set(rust_values) != expected:
        raise ValueError(f"{label} probe output is incomplete")
    return [
        f"{label}={index}:{key} C={c_values[(index, key)]} Rust={rust_values[(index, key)]}"
        for index, key in sorted(expected)
        if c_values[(index, key)] != rust_values[(index, key)]
    ]


def layout_and_constant_probe(
    controls: list[str],
    rlib: pathlib.Path,
) -> tuple[dict[str, tuple[int, int]], int]:
    contracts = ADAPTER.get("layout_contracts")
    if not isinstance(contracts, list) or not contracts:
        raise ValueError("layout_contracts must be a non-empty list")
    crate_name = str(ADAPTER.get("rust_crate_name", ""))
    if not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", crate_name):
        raise ValueError("rust_crate_name is invalid")
    reports = REPORTS / "abi-probe"
    reports.mkdir(parents=True, exist_ok=True)
    public_header = SOURCE / str(ADAPTER.get("public_header", ""))
    c_lines = [
        "#include <stddef.h>",
        "#include <stdint.h>",
        "#include <stdio.h>",
        f'#include "{public_header.as_posix()}"',
        "int main(void) {",
    ]
    rust_lines = [
        f"extern crate {crate_name};",
        "use std::mem::{align_of, offset_of, size_of};",
        "fn main() {",
    ]
    expected_keys: set[tuple[int, str]] = set()
    for index, raw in enumerate(contracts):
        if not isinstance(raw, dict):
            raise ValueError("layout contract must be an object")
        c_type = str(raw.get("c_type", ""))
        rust_type = str(raw.get("rust_type", ""))
        fields = raw.get("fields")
        if not c_type or not rust_type or not isinstance(fields, dict) or not fields:
            raise ValueError(f"layout contract is incomplete at index {index}")
        c_lines.extend(
            [
                f'  printf("L\\t{index}\\tsize\\t%zu\\n", sizeof({c_type}));',
                f'  printf("L\\t{index}\\talign\\t%zu\\n", _Alignof({c_type}));',
            ]
        )
        rust_lines.extend(
            [
                f'  println!("L\\t{index}\\tsize\\t{{}}", size_of::<{rust_type}>());',
                f'  println!("L\\t{index}\\talign\\t{{}}", align_of::<{rust_type}>());',
            ]
        )
        expected_keys.update({(index, "size"), (index, "align")})
        for field_index, (c_field, rust_field) in enumerate(fields.items()):
            if not isinstance(c_field, str) or not isinstance(rust_field, str):
                raise ValueError("layout field mapping must contain strings")
            key = f"field-{field_index}"
            c_lines.append(
                f'  printf("L\\t{index}\\t{key}\\t%zu\\n", offsetof({c_type}, {c_field}));'
            )
            rust_lines.append(
                f'  println!("L\\t{index}\\t{key}\\t{{}}", offset_of!({rust_type}, {rust_field}));'
            )
            expected_keys.add((index, key))
    for index, name in enumerate(controls):
        c_lines.append(f'  printf("K\\t{index}\\tvalue\\t%lld\\n", (long long)({name}));')
        rust_lines.append(
            f'  println!("K\\t{index}\\tvalue\\t{{}}", {crate_name}::{name} as i128);'
        )
    c_lines.extend(["  return 0;", "}", ""])
    rust_lines.extend(["}", ""])
    c_probe = reports / "layout_probe.c"
    rust_probe = reports / "layout_probe.rs"
    c_probe.write_text("\n".join(c_lines))
    rust_probe.write_text("\n".join(rust_lines))
    cc = shutil.which(str(ADAPTER.get("c_compiler", ""))) or shutil.which("cc")
    rustc = shutil.which("rustc")
    if not cc or not rustc:
        raise ValueError("layout verification requires a C compiler and rustc")
    c_binary = reports / "layout_probe_c"
    rust_binary = reports / "layout_probe_rust"
    c_compile = subprocess.run(
        [cc, "-std=c11", "-Werror", *expand_flags(ADAPTER.get("c_compile_flags", [])), str(c_probe), "-o", str(c_binary)],
        cwd=TARGET,
        capture_output=True,
        text=True,
        check=False,
    )
    (reports / "layout-c.log").write_text(c_compile.stdout + c_compile.stderr)
    if c_compile.returncode != 0:
        raise ValueError("C layout probe did not compile; see reports/abi-probe/layout-c.log")
    rust_compile = subprocess.run(
        [
            rustc,
            "--edition=2021",
            str(rust_probe),
            "--extern",
            f"{crate_name}={rlib}",
            "-L",
            f"dependency={TARGET / 'target/release/deps'}",
            "-o",
            str(rust_binary),
        ],
        cwd=TARGET,
        capture_output=True,
        text=True,
        check=False,
    )
    (reports / "layout-rust.log").write_text(rust_compile.stdout + rust_compile.stderr)
    if rust_compile.returncode != 0:
        raise ValueError("Rust layout probe did not compile; see reports/abi-probe/layout-rust.log")
    c_run = subprocess.run([str(c_binary)], cwd=TARGET, capture_output=True, text=True, check=False)
    rust_run = subprocess.run([str(rust_binary)], cwd=TARGET, capture_output=True, text=True, check=False)
    (reports / "layout-c-output.log").write_text(c_run.stdout + c_run.stderr)
    (reports / "layout-rust-output.log").write_text(rust_run.stdout + rust_run.stderr)
    if c_run.returncode != 0 or rust_run.returncode != 0:
        raise ValueError("compiled layout probe failed at runtime")
    c_layout = parse_probe_output(c_run.stdout, "L")
    rust_layout = parse_probe_output(rust_run.stdout, "L")
    mismatches = probe_mismatches(c_layout, rust_layout, expected_keys, "layout")
    c_controls = parse_probe_output(c_run.stdout, "K")
    rust_controls = parse_probe_output(rust_run.stdout, "K")
    control_values: dict[str, tuple[int, int]] = {}
    control_keys = {(index, "value") for index in range(len(controls))}
    mismatches.extend(
        probe_mismatches(c_controls, rust_controls, control_keys, "control")
    )
    for index, name in enumerate(controls):
        key = (index, "value")
        control_values[name] = (c_controls[key], rust_controls[key])
    values_report = {
        "schema": "source-translation-layout-values-v1",
        "contracts": [
            {
                "index": index,
                "c_type": contracts[index]["c_type"],
                "rust_type": contracts[index]["rust_type"],
                "values": {
                    key: c_layout[(index, key)]
                    for contract_index, key in sorted(expected_keys)
                    if contract_index == index
                },
            }
            for index in range(len(contracts))
        ],
        "controls": {
            name: {"c": values[0], "rust": values[1]}
            for name, values in control_values.items()
        },
    }
    (reports / "layout-values.json").write_text(
        json.dumps(values_report, ensure_ascii=False, indent=2) + "\n"
    )
    (REPORTS / "layout-probe.md").write_text(
        "\n".join(
            [
                "# ABI And Layout Probe",
                "",
                f"- Public C layouts compared: {len(contracts)}",
                f"- Compared size/alignment/field offsets: {len(expected_keys)}",
                f"- Compiled control values compared: {len(controls)}",
                f"- Status: {'FAILED' if mismatches else 'PASSED'}",
                "",
                "## Mismatches",
                "",
                *(f"- {item}" for item in mismatches),
                *(["- none"] if not mismatches else []),
                "",
            ]
        )
    )
    if mismatches:
        raise ValueError("C/Rust compiled contract mismatch: " + "; ".join(mismatches[:4]))
    return control_values, len(expected_keys)


def compiled_runtime_calls() -> set[str]:
    raw_sources = ADAPTER.get("api_runtime_sources")
    if (
        not isinstance(raw_sources, list)
        or not raw_sources
        or not all(isinstance(entry, dict) for entry in raw_sources)
    ):
        raise ValueError("api_runtime_sources must be a non-empty object list")
    clang = shutil.which("clang")
    if not clang:
        raise ValueError("compiled API call-site verification requires clang")
    reports = REPORTS / "abi-probe"
    reports.mkdir(parents=True, exist_ok=True)
    combined: list[str] = []
    for index, entry in enumerate(raw_sources):
        root_name = entry.get("root")
        relative = entry.get("path")
        if root_name not in {"source", "target"} or not isinstance(relative, str):
            raise ValueError(f"invalid API runtime source at index {index}")
        root = SOURCE if root_name == "source" else TARGET
        source = (root / relative).resolve()
        try:
            source.relative_to(root.resolve())
        except ValueError as exc:
            raise ValueError("API runtime source escapes configured root") from exc
        if not source.is_file():
            raise ValueError(f"API runtime source is missing: {source}")
        output = reports / f"runtime-calls-{index}.ll"
        result = subprocess.run(
            [
                clang,
                "-S",
                "-emit-llvm",
                "-O0",
                *expand_flags(ADAPTER.get("c_compile_flags", [])),
                str(source),
                "-o",
                str(output),
            ],
            cwd=TARGET,
            capture_output=True,
            text=True,
            check=False,
        )
        (reports / f"runtime-calls-{index}.log").write_text(
            result.stdout + result.stderr
        )
        if result.returncode != 0:
            raise ValueError(
                f"API runtime call source did not compile: {source}; "
                f"see reports/abi-probe/runtime-calls-{index}.log"
            )
        combined.append(output.read_text(errors="replace"))
    text = "\n".join(combined)
    return set(
        re.findall(
            r"\b(?:call|invoke)\b[^\n@]*@([A-Za-z_][A-Za-z0-9_]*)\(",
            text,
        )
    )


def abi_probe(
    functions: list[str],
    rust_ir_files: list[pathlib.Path],
) -> dict[str, tuple[str, tuple[str, ...]]]:
    clang = shutil.which("clang")
    cc = shutil.which(str(ADAPTER.get("c_compiler", ""))) or shutil.which("cc")
    if not clang or not cc:
        raise ValueError("ABI verification requires clang and a C linker")
    public_header = SOURCE / str(ADAPTER.get("public_header", ""))
    archive = TARGET / str(ADAPTER.get("target_artifact", ""))
    reports = TARGET / "reports/abi-probe"
    reports.mkdir(parents=True, exist_ok=True)
    probe_c = reports / "api_probe.c"
    probe_c.write_text(
        "\n".join(
            [
                "#include <stdint.h>",
                f'#include "{public_header.as_posix()}"',
                "static const void *const api_refs[] = {",
                *(f"    (const void *)(uintptr_t)&{name}," for name in functions),
                "};",
                "int main(void) { return api_refs[0] == 0; }",
                "",
            ]
        )
    )
    c_flags = expand_flags(ADAPTER.get("c_compile_flags", []))
    link_flags = expand_flags(ADAPTER.get("c_link_flags", []))
    c_ir = reports / "api_probe.ll"
    compile_ir = subprocess.run(
        [clang, "-S", "-emit-llvm", "-O0", "-Werror", *c_flags, str(probe_c), "-o", str(c_ir)],
        cwd=TARGET,
        capture_output=True,
        text=True,
        check=False,
    )
    (reports / "c-llvm.log").write_text(compile_ir.stdout + compile_ir.stderr)
    if compile_ir.returncode != 0:
        raise ValueError("C ABI probe did not compile; see reports/abi-probe/c-llvm.log")
    link = subprocess.run(
        [cc, *c_flags, str(probe_c), str(archive), *link_flags, "-o", str(reports / "api_probe")],
        cwd=TARGET,
        capture_output=True,
        text=True,
        check=False,
    )
    (reports / "link.log").write_text(link.stdout + link.stderr)
    if link.returncode != 0:
        raise ValueError("C ABI probe did not link; see reports/abi-probe/link.log")
    rust_text = "\n".join(path.read_text(errors="replace") for path in rust_ir_files)
    c_text = c_ir.read_text(errors="replace")
    signatures: dict[str, tuple[str, tuple[str, ...]]] = {}
    for name in functions:
        c_signature = llvm_signature(c_text, name)
        rust_signature = llvm_signature(rust_text, name)
        if c_signature != rust_signature:
            raise ValueError(
                f"ABI signature mismatch for {name}: C={c_signature} Rust={rust_signature}"
            )
        signatures[name] = c_signature
    return signatures


def verify(progress: bool) -> int:
    items = required_items()
    write_tsv(REQUIRED, ["kind", "name", "source", "expected"], items)

    runtime_paths = list(sorted((SOURCE / "tests").rglob("*.c")))
    runtime_text = "\n".join(
        strip_comments(path.read_text(errors="replace"))
        for path in runtime_paths
        if path.is_file()
    )
    functions = [item["name"] for item in items if item["kind"] == "function"]
    controls = [item["name"] for item in items if item["kind"] == "control"]
    try:
        llvm_files, rlib = build_artifacts()
        abi_signatures = abi_probe(functions, llvm_files)
        control_values, layout_values = layout_and_constant_probe(controls, rlib)
        runtime_calls = compiled_runtime_calls()
    except ValueError:
        if progress:
            abi_signatures = {}
            control_values = {}
            layout_values = 0
            runtime_calls = set()
        else:
            raise

    rows: list[dict[str, str]] = []
    failures: list[str] = []
    behavior_covered = 0
    for item in items:
        name = item["name"]
        required_checks: list[tuple[bool, str]] = []
        observations: list[str] = []
        if item["kind"] == "function":
            required_checks.append(
                (
                    name in abi_signatures,
                    "generated C address/link probe and LLVM ABI signature",
                )
            )
            if name in runtime_calls:
                observations.append("behavior covered by compiled source call site")
                behavior_covered += 1
            else:
                observations.append("ABI-only; no original source-test call site")
        else:
            values = control_values.get(name)
            required_checks.append(
                (
                    values is not None and values[0] == values[1],
                    f"compiled control value={values[0]}" if values else "compiled C/Rust control value",
                )
            )
            if re.search(rf"\b{re.escape(name)}\b", runtime_text):
                observations.append("used by original source tests")
                behavior_covered += 1
            else:
                observations.append("compiled value only; no original source-test use")
        missing = [label for ok, label in required_checks if not ok]
        status = "PASS" if not missing else "PENDING"
        rows.append(
            {
                "kind": item["kind"],
                "name": name,
                "status": status,
                "evidence": "; ".join(
                    [
                        *(
                            label
                            for ok, label in required_checks
                            if ok
                        ),
                        *observations,
                    ]
                ),
            }
        )
        if missing:
            failures.append(f"{item['kind']} {name}: missing {', '.join(missing)}")

    write_tsv(COVERAGE, ["kind", "name", "status", "evidence"], rows)
    passed = len(items) - len(failures)
    SUMMARY.write_text(
        "\n".join(
            [
                "# C API Surface Check",
                "",
                f"- Passed: {passed}",
                f"- Required: {len(items)}",
                f"- Original source-test runtime uses: {behavior_covered}",
                f"- ABI/value-only items: {len(items) - behavior_covered}",
                f"- Status: {'PASSED' if not failures else 'IN_PROGRESS'}",
                "",
                "## First Failure",
                "",
                f"- {failures[0] if failures else 'none'}",
                "",
            ]
        )
    )
    if failures and not progress:
        print("C_API_SURFACE_CHECK_FAIL")
        for failure in failures[:10]:
            print(f"- {failure}")
        return 1
    marker = "C_API_PROGRESS" if progress else "C_API_SURFACE_CHECK_PASS"
    print(f"{marker}: passed={passed} total={len(items)} layout_values={layout_values}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--init", action="store_true")
    parser.add_argument("--progress", action="store_true")
    args = parser.parse_args()
    items = required_items()
    if args.init:
        return initialize(items)
    return verify(args.progress)


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (OSError, ValueError) as exc:
        print(f"C_API_SURFACE_CHECK_FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
