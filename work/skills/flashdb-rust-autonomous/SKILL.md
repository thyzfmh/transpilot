---
name: flashdb-rust-autonomous
description: Autonomously translate code/FlashDB to code/flashDB_rust with C-test-first development, source-bound evidence, C ABI compatibility, and bidirectional persistence verification.
---

# FlashDB Rust Autonomous Translation

## Fixed Contract

- C source: `code/FlashDB`
- Rust target: `code/flashDB_rust`
- Crate and static library name: `flashdb_rust`
- Release library: `code/flashDB_rust/target/release/libflashdb_rust.a`
- Supported profile: POSIX file mode, KVDB and TSDB enabled,
  `FDB_WRITE_GRAN=1`, signed 32-bit timestamp
- Trusted completion command:
  `work/skills/flashdb-rust-autonomous/scripts/final_verify_target.sh`
- Result file: `result/output.md`
- Complete AI interaction and verification trace: `logs/trace/`

Do not ask the user questions. Keep inspecting, testing, implementing, and
repairing until the trusted completion command passes and the result file is
updated.

Read `references/c-to-rust-translation-spec.md` completely before changing the
target. It is mandatory for design, implementation, testing, and verification.
The scripts are enforcement tools, not a replacement for understanding C.

## Trust Boundary

During translation:

- do not edit files under `code/FlashDB`; compiler objects and temporary test
  output are allowed, but C source, headers, tests, and Makefiles are immutable;
- do not edit `INSTRUCTION.md` or anything under
  `work/skills/flashdb-rust-autonomous`;
- do not weaken, skip, replace, or locally patch a harness check;
- never use the current Rust behavior as the oracle for a Rust test;
- never claim success from a report row, process exit alone, or a worker result.

`references/source-manifest.sha256` binds the accepted C input. The trusted
launcher checks both the source manifest and the copied target harness before
and after final verification.

## Autonomous Loop

Use one main-agent loop:

```text
preflight and restore checkpoint
  -> inspect the next C case or public API item
  -> record a C-derived oracle
  -> add the Rust acceptance test first
  -> observe the focused test fail for the missing behavior
  -> implement the smallest source-equivalent behavior
  -> run the focused test and progressive gates
  -> record source-bound evidence and checkpoint
  -> repeat until all queues are closed
  -> freeze Rust source and rebuild final evidence
  -> run the trusted completion command
  -> update result/output.md and run the trusted command again
```

For a behavior failure, never stop after a fixed retry count. After three
failures with the same approach, change the approach: reduce the slice, add a C
probe, inspect a lower-level call path, or replace the implementation strategy.

An environment blocker is different from a behavior failure. If preflight exits
with code `2`, retry the exact blocker after one repair attempt. Only when the
same external blocker occurs three consecutive times may execution stop. Record
the command, three logs, and required external action in `result/output.md` with
status `BLOCKED`. Missing tools, unreadable fixed source, unwritable workspace,
or exhausted disk are blockers; failing builds and tests are not.

## Phase 0: Install Fixed Harness

From the repository root, create or resume the target and replace only its
harness with the fixed template:

```bash
SKILL_DIR="work/skills/flashdb-rust-autonomous"
TARGET="code/flashDB_rust"
mkdir -p "$TARGET/.cargo" "$TARGET/src" "$TARGET/tests" "$TARGET/reports"
cp "$SKILL_DIR/templates/cargo-config.toml" "$TARGET/.cargo/config.toml"
if [ ! -f "$TARGET/Cargo.toml" ]; then
  cp "$SKILL_DIR/templates/Cargo.toml" "$TARGET/Cargo.toml"
fi
python3 - "$SKILL_DIR" "$TARGET" <<'PY'
import pathlib
import shutil
import sys

skill = pathlib.Path(sys.argv[1])
target = pathlib.Path(sys.argv[2])
destination = target / "harness"
if destination.exists():
    shutil.rmtree(destination)
shutil.copytree(skill / "templates/harness", destination)
PY
chmod +x "$TARGET/harness/"*.sh
```

Do not delete valid Rust implementation work when resuming. The fixed
`.cargo/config.toml` must deny warnings, and `Cargo.toml` must contain:

```toml
[lib]
name = "flashdb_rust"
path = "src/lib.rs"
crate-type = ["rlib", "staticlib"]
```

Initialize and validate the queues:

```bash
cd code/flashDB_rust
python3 harness/source_guard.py --target .
./harness/preflight.sh
python3 harness/checkpoint.py init
python3 harness/c_coverage_check.py --init
python3 harness/api_surface_check.py --init
python3 harness/translation_spec_check.py --init
python3 harness/c_coverage_check.py --progress
python3 harness/api_surface_check.py --progress
python3 harness/translation_spec_check.py --progress
```

The three `--init` commands reconcile current required rows, preserve valid
current work, and remove stale rows. They do not turn unfinished rows into
passes.

## Phase 1: Source Design and C Oracle

Create or refresh these target reports from C source evidence:

- `reports/source-inventory.md`: every C source/header/test, size, includes,
  key public and static symbols, module dependencies, translation order;
- `reports/config-profile.md`: output of `config_profile_check.py`;
- `reports/layout-probe.md`: measured C sizes, alignments, offsets, endian and
  write-granularity facts;
- `reports/c-oracle-traces/`: original C test and focused C probe output;
- `reports/progress.md`: checkpoint, current queue item, latest command, next
  action.

Use this dependency order unless source evidence proves otherwise:

1. configuration, types, constants, status tables, alignment, layout;
2. `fdb_utils.c` CRC and low-level helpers;
3. `fdb_file.c` POSIX storage backend;
4. `fdb.c` shared initialization/deinitialization;
5. `fdb_kvdb.c` KV state machine and recovery;
6. `fdb_tsdb.c` time-series state machine and recovery;
7. C ABI, controls, callbacks, iteration, output, and all C test cases.

Run the original C suite before translating behavior and save its complete
output as an oracle trace. If the original suite cannot run, build a focused C
probe for the affected behavior and save its source, compile command, and
output. A static oracle must cite the exact C file, function, branch, macro, and
expected value.

The required work queues are:

- `reports/c-test-coverage-required.tsv`: every `TEST_RUN(...)` occurrence;
- `reports/c-api-required.tsv`: every public function and KVDB/TSDB control;
- `reports/c-module-coverage.tsv`: every C source module;
- `reports/c-to-rust-compliance.tsv`: every Chinese specification rule.

## Phase 2: C-Test-First Translation

For each row in `c-test-coverage-required.tsv`, in file order:

1. Read the complete C test body, helpers, macros, and production call path.
2. Record the exact case id, such as
   `fdb_kvdb_tc.c::test_fdb_kvdb_init#1`.
3. Run the original C case or focused probe where needed.
4. Add one distinct Rust `#[test]` under `tests/c_kvdb_cases.rs` or
   `tests/c_tsdb_cases.rs` before changing production Rust.
5. Put the exact C case id inside the test body and reproduce C setup,
   operation order, assertions, restart context, and expected values.
6. Run the focused Rust test and confirm it fails for the missing behavior.
7. Implement the smallest equivalent behavior in the safe Rust core and narrow
   FFI boundary.
8. Run the focused test successfully through `evidence_runner.py`.
9. Add its `reports/evidence/*.json` path to the coverage row and update the
   checkpoint.

Example successful focused-test evidence:

```bash
python3 harness/evidence_runner.py run \
  --id ccase-kvdb-init-1 -- \
  cargo test --release test_fdb_kvdb_init_first_pass -- --exact --nocapture
```

The coverage row's `oracle` must name the exact C test file and function. Its
`evidence` must reference successful structured evidence for that exact Rust
test. Repeated C cases require distinct Rust tests and distinct evidence.

After each slice run:

```bash
cargo fmt
./harness/build_check.sh
./harness/test_all.sh
python3 harness/c_coverage_check.py --progress
python3 harness/api_surface_check.py --progress
python3 harness/translation_spec_check.py --progress
python3 harness/rust_policy_check.py
```

After any C ABI, persistent-format, callback, control, or iterator change, also
run:

```bash
./harness/c_link_test.sh
./harness/c_interop_test.sh
```

Update `reports/progress.md` and record the case and last successful command:

```bash
python3 harness/checkpoint.py record \
  --case '<case-id>' --stage slice_passed \
  --command '<focused command>' --exit-code 0
```

## Mandatory Semantic Areas

Closing the C test queue alone is insufficient. The implementation must also
close every row in the public API, module, and specification queues.

The following are mandatory:

- exact persistent byte layout, status transitions, CRC, erased values,
  padding, sector movement, GC, recovery, and restart behavior;
- all public symbols from `inc/flashdb.h` exported by the release static
  library with exact C signatures;
- every KVDB/TSDB control command, including lock/unlock callbacks, getters,
  rollover, file mode, max size, and not-formatable mode;
- callback invocation count, ordering, early stop, user context, and lock
  balance;
- real behavior for integrity checking, printing, iteration, reverse
  iteration, status updates, cleanup, and capacity calculations;
- error-code distinctions and output-parameter behavior;
- panic containment at every C ABI entry;
- no `static mut`, production `unwrap`, `expect`, `panic`, unfinished macro,
  placeholder path, or unjustified `unsafe`;
- C-produced databases readable by Rust, Rust-produced databases readable by
  C, and byte-identical deterministic KVDB/TSDB fixtures.

`harness/c_interop_test.sh` is the fixed cross-implementation gate. It must not
be replaced by a Rust-only round trip or by C tests whose writer and reader both
link the Rust implementation.

## Phase 3: Freeze and Rebuild Evidence

Structured evidence is bound to the current C source hash and current Rust
Cargo files, build configuration, `src/`, and `tests/` hash. Any later Rust
source, test, or build-input change makes old evidence stale. Once all behavior
is implemented:

1. Run `cargo fmt` and stop changing Rust source/tests.
2. Regenerate successful focused `cargo test` evidence for every C coverage
   row.
3. Generate final build, source guard, profile, C link, interop, and Rust policy
   evidence with `evidence_runner.py`.
4. Update API/module rows with the relevant C link or interop evidence.
5. Run strict C coverage and API checks through `evidence_runner.py`.
6. Update every compliance row with evidence whose command matches that rule.
7. Run the strict specification check.

Recommended final evidence commands:

```bash
python3 harness/evidence_runner.py run --id final-source -- python3 harness/source_guard.py --target .
python3 harness/evidence_runner.py run --id final-profile -- python3 harness/config_profile_check.py
python3 harness/evidence_runner.py run --id final-build -- ./harness/build_check.sh
python3 harness/evidence_runner.py run --id final-c-link -- ./harness/c_link_test.sh
python3 harness/evidence_runner.py run --id final-interop -- ./harness/c_interop_test.sh
python3 harness/evidence_runner.py run --id final-rust-policy -- python3 harness/rust_policy_check.py
python3 harness/evidence_runner.py run --id final-c-coverage -- python3 harness/c_coverage_check.py
python3 harness/evidence_runner.py run --id final-api -- python3 harness/api_surface_check.py
python3 harness/trace_capture.py export --target .
python3 harness/evidence_runner.py run --id final-trace -- python3 harness/trace_capture.py verify --target .
python3 harness/translation_spec_check.py
```

Evidence records live under `reports/evidence/`. A `PASS` ledger row without a
valid structured record is a failure. Do not manually fabricate JSON or logs.
Use `reports/evidence/final-trace.json` for `LOG-01`.

After all strict checks pass, record readiness:

```bash
python3 harness/checkpoint.py record \
  --case all --stage ready_for_final \
  --command 'strict pre-final gates' --exit-code 0
```

## Phase 4: Trusted Completion

Run from the repository root:

```bash
work/skills/flashdb-rust-autonomous/scripts/final_verify_target.sh
```

The trusted launcher automatically exports the latest active OpenCode session
for this repository, without `--sanitize`, to `logs/trace/llm_chat_log.json`.
It also snapshots the machine-generated verification JSON and raw logs under
`logs/trace/verification/` before rerunning every code-level gate. The trace is
an audit record only; statements in it never satisfy a gate.

If any command fails, return to the exact failed queue item, repair it, freeze
again, and regenerate stale evidence. Do not report partial completion.

After the trusted command passes, update `result/output.md`:

```markdown
## Execution Result

- Status: COMPLETED
- Source: code/FlashDB (C)
- Target: code/flashDB_rust (Rust)
- Supported profile: POSIX file mode, KVDB+TSDB, FDB_WRITE_GRAN=1, 32-bit timestamp
- Trusted final verification: PASSED
- Date: <current date>

### Verification Summary
- C-derived Rust cases: <passed>/<required>
- Public C API items: <passed>/<required>
- Original C-linked tests: PASSED
- C/Rust bidirectional persistence: PASSED
- Rust safety policy: PASSED
- Placeholders: NONE
```

Then run the trusted command once more. Only the second pass permits a final
success response.

## Subagent Policy

Do not delegate implementation or queue ownership. The main agent must continue
working and must remain responsible for all edits and verification.

A subagent may be used only for a read-only review of one named C function when
the platform can enforce a hard timeout of at most 10 minutes. Record start,
deadline, result, and acceptance in `reports/progress.md`. At timeout, abandon
the subagent and continue immediately. A subagent statement is never evidence
and never completion.
