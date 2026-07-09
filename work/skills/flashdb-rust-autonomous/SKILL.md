---
name: flashdb-rust-autonomous
description: Use when OpenCode is running this repository's FlashDB C-to-Rust competition task from INSTRUCTION.md and must translate code/FlashDB into code/flashDB_rust without user interaction.
---

# FlashDB Rust Autonomous Translation

## Fixed Contract

- Source: `code/FlashDB`
- Target: `code/flashDB_rust`
- Crate package/name: `flashdb_rust`
- Scope: translate FlashDB `src/`, `inc/`, and source-backed behavior from `tests/`
- Completion gate: `cd code/flashDB_rust && ./harness/final_verify.sh` exits 0
- Result gate: `result/output.md` records the final pass

Do not ask the user questions. Make reasonable source-backed decisions and keep
executing until the completion and result gates pass.

## Non-Stop Loop

Use this loop for the whole task and for every failure:

```text
inspect source and current Rust state
  -> choose the smallest missing behavior slice
  -> design the Rust representation from C evidence
  -> implement the slice
  -> port or add source-backed Rust tests
  -> run verification
  -> if anything fails, patch from the exact error and rerun
  -> repeat until final_verify.sh passes
  -> update result/output.md
```

Never end with a plan, partial translation, failing verification, TODO marker,
or "needs user confirmation." If the same approach fails three times, change the
approach by shrinking the slice, adding a narrower test, or replacing the
translation strategy. Do not stop merely because the work is long.

Only stop before success if `code/FlashDB/src` is missing or unreadable. Record
that blocker in `result/output.md`.

## Phase 0: Normalize Workspace

1. Verify `code/FlashDB/src` exists.
2. Create `code/flashDB_rust` if it does not exist.
3. If the target already exists, continue from it. Do not delete working Rust
   code just to restart.
4. Ensure the target has:

```text
code/flashDB_rust/
  .cargo/config.toml
  Cargo.toml
  src/
  tests/
  harness/
  reports/
```

5. Copy fixed target templates from this skill before writing translation code.
   Resolve paths relative to this `SKILL.md` file:

```bash
SKILL_DIR="work/skills/flashdb-rust-autonomous"
TARGET="code/flashDB_rust"
mkdir -p "$TARGET/.cargo" "$TARGET/src" "$TARGET/tests" "$TARGET/harness" "$TARGET/reports"
cp "$SKILL_DIR/templates/cargo-config.toml" "$TARGET/.cargo/config.toml"
if [ ! -f "$TARGET/Cargo.toml" ]; then
  cp "$SKILL_DIR/templates/Cargo.toml" "$TARGET/Cargo.toml"
fi
cp "$SKILL_DIR/templates/harness/"*.sh "$TARGET/harness/"
chmod +x "$TARGET/harness/"*.sh
```

The harness scripts are fixed verification assets. Do not rewrite them unless a
script itself fails because of a real local environment issue; if changed,
preserve the same checks.

6. Ensure `.cargo/config.toml` denies warnings:

```toml
[build]
rustflags = ["-Dwarnings"]
```

7. Ensure the harness scripts below exist and are executable:

- `harness/build_check.sh`
- `harness/test_all.sh`
- `harness/unsafe_audit.sh`
- `harness/final_verify.sh`

`build_check.sh` must run `cargo fmt --check` when rustfmt exists and then
`cargo check --all-targets`. If rustfmt is missing, warn and continue to
`cargo check`.

`test_all.sh` must run `cargo test --all-targets -- --nocapture`.

`unsafe_audit.sh 10` must count production Rust `unsafe` keyword hits under
`src/` and fail when the ratio is greater than or equal to 10%.

`final_verify.sh` must run build, tests, unsafe audit, and a placeholder audit
for `todo!(`, `unimplemented!(`, `panic!("TODO`, `TODO: fake`, and
`placeholder` under `src` and `tests`. It must also fail if no production Rust
source or no Rust tests exist, so an empty crate cannot pass.

## Phase 1: Source Design

Create or refresh `code/flashDB_rust/reports/source-inventory.md` with:

- all C source and header files under `code/FlashDB/src` and `code/FlashDB/inc`
- all C tests under `code/FlashDB/tests`
- source file sizes
- module dependency notes based on `#include`
- translation order

Use this FlashDB order unless source evidence proves a different dependency:

1. configuration, constants, statuses, structs, alignment macros
2. CRC/status/write-granularity helpers from `fdb_utils.c`
3. flash backend and file behavior from `fdb_file.c`
4. shared init/deinit behavior from `fdb.c`
5. KVDB behavior from `fdb_kvdb.c`
6. TSDB behavior from `fdb_tsdb.c`
7. Rust tests ported from `tests/fdb_kvdb_tc.c` and `tests/fdb_tsdb_tc.c`

Try to run the C tests:

```bash
cd code/FlashDB/tests && make test
```

If they pass, treat the C tests and C execution as the primary oracle. If they
cannot run because of environment issues, use source tests, constants, and
source code as static oracle evidence and continue.

## Phase 2: Development Rules

Translate behavior, not C API shape. Prefer safe Rust ownership and explicit
results over raw pointer emulation.

Mapping rules:

| C pattern | Rust pattern |
|---|---|
| `#define` constants | `pub const` |
| status enums/macros | Rust enums plus conversion helpers |
| owned buffers | `Vec<u8>` |
| borrowed buffers | `&[u8]` / `&mut [u8]` |
| nullable references | `Option<&T>` / `Option<&mut T>` |
| flash storage callbacks | trait methods |
| `void *` control arguments | typed Rust enums |
| global test counters | `thread_local!` with `Cell` |

C-to-Rust tactics for FlashDB:

- Model flash as a `FlashBackend` trait. Keep KVDB/TSDB generic over the backend
  so memory and POSIX-file storage share the same behavior tests.
- Treat on-flash metadata as byte layout, not Rust struct layout. Use explicit
  little-endian read/write helpers for magic words, CRCs, lengths, timestamps,
  and addresses. Avoid relying on `repr(C)` unless an actual FFI boundary is
  introduced.
- Translate FlashDB status tables as bit-pattern helpers. Preserve the C
  meaning of erased bytes, write granularity, status index order, and monotonic
  state transitions.
- Keep sector/KV/TSL addresses as `u32` offsets and convert to `usize` only at
  backend slice boundaries. Validate bounds at that boundary.
- Replace C output-pointer APIs with return values such as `Result<T, FdbErr>`
  or `Option<T>`, but preserve the source error behavior.
- Translate `void *` controls into enums such as typed control arguments instead
  of accepting untyped bytes.
- Preserve C allocation behavior with `Vec<u8>` and fixed-size arrays. Use
  computed aligned lengths for names, values, blobs, headers, and log bodies.
- Make garbage collection and sector iteration state-machine driven. Do not
  shortcut by rebuilding maps from high-level collections unless tests prove the
  same on-flash behavior.
- Port macros into `const fn` where values participate in layout calculations,
  especially alignment and status-table-size formulas.
- Use `unsafe` only where a safe replacement would change required behavior;
  every remaining unsafe use must stay under the audit threshold.

Rules that must not be violated:

- No production `unwrap()`, `expect()`, `todo!()`, `unimplemented!()`, or
  placeholder implementation.
- No fake tests that only assert the harness starts.
- Expected values must come from C tests, C constants/macros, C execution, or
  mechanically computed source formulas.
- GC and sector-size tests must compute sizes from FlashDB macros and on-flash
  layout, not round numbers.
- Every public behavior added in Rust must have a Rust test.
- Preserve persistence, sector state transitions, write granularity, CRC checks,
  KV overwrite/delete semantics, TSDB timestamp ordering, and iteration order.

## Phase 3: Verification Loop

After each slice, run from `code/flashDB_rust`:

```bash
cargo fmt
./harness/build_check.sh
./harness/test_all.sh
./harness/unsafe_audit.sh 10
```

If a command fails:

1. Read the exact error span or failing assertion.
2. Identify whether the cause is translation logic, test oracle, API mismatch,
   missing type mapping, or harness script behavior.
3. Patch the smallest affected code.
4. Re-run the failed command, then re-run the full slice verification.

Before moving to another behavior area, compare the C test function names in
`code/FlashDB/tests` with Rust test names and add missing equivalents.

For critical behavior, add differential or oracle-backed tests when practical:

- basic KV set/get/delete/default
- KV overwrite and garbage collection
- multi-sector KV movement
- TSDB append/query/count/clean
- TSDB reboot or reinitialization behavior

## Phase 4: Final Gate

When all source modules and tests have Rust equivalents, run:

```bash
cd code/flashDB_rust
./harness/final_verify.sh
```

If any part fails, continue the verification loop. Do not report completion.

After `final_verify.sh` passes, update `result/output.md` with:

```markdown
## Execution Result

- Status: COMPLETED
- Source: code/FlashDB (C)
- Target: code/flashDB_rust (Rust)
- Final verification: PASSED
- Date: <current date>

### Translation Summary
- Modules translated: <list>
- Rust tests: <number and pass count>
- C tests: <passed / not run with reason>
- Unsafe ratio: <value>
- Placeholders: NONE
```

Then run a final readback:

```bash
test -f result/output.md
cd code/flashDB_rust && ./harness/final_verify.sh
```

Only after both commands pass may OpenCode answer that the work is complete.

## Optional Subagent Use

Do not depend on separate subagent files. If OpenCode supports subagents, the
main agent may dispatch internal review prompts copied from this section, but
the main agent remains responsible for edits and final verification.

Use these internal roles only after the main agent has enough source evidence:

- Source reviewer: check that each behavior claim cites C source or C tests.
- Rust reviewer: check for placeholders, unsafe overuse, unwraps, and behavior
  gaps.
- Verification reviewer: check that `final_verify.sh`, Rust tests, and
  `result/output.md` all prove completion.

Subagents may report findings; they must not replace the non-stop loop.
