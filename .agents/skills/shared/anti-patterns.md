# Universal Translation Anti-Patterns

Extracted from Taibai (K8s → Rust) project lessons L001-L008. These apply to ANY large-scale source-to-Rust translation project.

## AP-001: Green CI Trap

**Source**: Taibai L001, L005
**Description**: All tests pass (2459 green), but system doesn't work. Every DI trait only has Mock implementations — tests prove structure, not function.
**Detection**: Search for `impl XxxTrait for` — if only InMemory/Mock found, violation.
**Rule**: Every DI trait MUST have BOTH Mock (test) AND Real (production) implementations.
**Cost of ignoring**: Entire component appears "done" but is functionally hollow.

## AP-002: Late E2E

**Source**: Taibai L003
**Description**: E2E validation postponed until all components complete. Architectural gaps discovered when they're extremely expensive to fix (36 controllers already built on wrong foundation).
**Detection**: No `e2e_first_run` timestamp in translation state despite modules translated.
**Rule**: Run E2E after the FIRST functional module, not after ALL are done.
**Cost of ignoring**: Months of work built on unvalidated architecture.

## AP-003: Stub Accumulation

**Source**: Taibai controller manager experience
**Description**: 36 controllers all have structural code but no real infrastructure connections. Stubs pile up without replacement plan.
**Detection**: Count of `todo!()`, `unimplemented!()`, and placeholder functions trending upward.
**Rule**: Each wave's LAST task must be integration verification. Track stub count explicitly.
**Cost of ignoring**: Technical debt becomes unmanageable.

## AP-004: Copy-Shape-Not-Behavior

**Source**: Taibai k8s-translator-practices §4
**Description**: Directly copying source language API shape into Rust (e.g., Go's panic-style WithLabelValues, C's return-code error handling left as-is).
**Detection**: Non-idiomatic Rust patterns that match source language style.
**Rule**: 1:1 replication means matching BEHAVIOR, not API signature. Adapt to Rust idioms.
**Examples**:
- Go `panic("msg")` → should be `return Err(...)`, not `panic!("msg")`
- Go interface reference semantics → should be `Arc<Struct>`, not `Box<dyn Trait>` for shared state
- C `return -1` → should be `Result<T, Error>`, not `fn() -> i32`

## AP-005: Blind Retry

**Source**: Taibai D-W34-RESOLVED
**Description**: Agent/developer times out (30 min, zero output), then blindly retries the same approach — same result.
**Detection**: Two identical attempts producing same (zero) output.
**Rule**: After timeout/failure, do CODE STATE PROBE first:
1. `grep + wc -l` on target files
2. Determine if ANY progress was made
3. If zero: decompose to smaller surface (one file, one trait, one route)
4. If partial: identify the actual blocking point
**Cost of ignoring**: Repeated wasted cycles.

## AP-006: Probe-Before-Implement (Positive Pattern)

**Source**: Taibai D-W34, D-PHASE2-RBAC, D-PHASE1-CACHE (verified 3× independently)
**Description**: Plan estimates 250 lines of new code; actual probe reveals 90% already exists — only 80 lines needed.
**Rule**: When assigned "implement X":
1. First `grep -r "X"` across the codebase
2. If found: read existing code, scope actual delta
3. If 90% exists: only implement the 10% gap
**Savings**: Average 70% work reduction when prior infrastructure exists.
**When it doesn't help**: True greenfield phases (Phase 2+) — but tight task breakdown compensates.

## AP-007: Shared Mutable Test State

**Source**: FlashDB L-001
**Description**: Tests use `static mut` or `AtomicI32` for counters/timestamps. Under `cargo test` parallel execution, threads share state, causing intermittent failures.
**Detection**: `static mut` or `static ATOMIC` in test files used as mutable counters.
**Rule**: Test counters MUST use `thread_local! { Cell<T> }`. Each test thread gets its own isolated copy.
**Cost of ignoring**: Tests pass in isolation but fail under `cargo test` — classic heisenbug.

## AP-008: Agent Self-Report Trust

**Source**: FlashDB L-002
**Description**: Deep agent runs for 51 minutes, reports "I have bugs in tsl_iter_by_time". Reality: all 107 tests pass — agent fixed its own bugs during the run.
**Detection**: Agent output contains "this might have issues" / "there are bugs" / "needs debugging".
**Rule**: Only `cargo test` exit code is truth. Agent self-reports must be independently verified. Never trust agent's final assessment without running the actual verification.
**Cost of ignoring**: Wasting time "fixing" non-existent bugs, or ignoring real bugs because agent said "it works".

## AP-009: Self-Written Test Assertions (Oracle Independence Violation)

**Source**: FlashDB L-003, differential-tester skill
**Description**: AI writes both the code AND the expected values in `assert_eq!(result, 42)`. The 42 is AI-derived, not independently verified.
**Detection**: String/number literal expected values in test assertions. `assert_eq!(foo(), "expected")` where "expected" is not from source execution.
**Rule**: Expected values MUST come from: (1) source project runtime output, (2) static codegraph analysis, (3) user confirmation. AI-derived expected values are banned.
**Cost of ignoring**: Tests pass but prove nothing — self-verification is circular.

## AP-010: Guessed Sector Layout

**Source**: FlashDB L-004
**Description**: GC test fails because KV value sizes don't match the C test's computed sizes. Picking "round number" values (256, 512) instead of computing from the same formulas as C.
**Detection**: Test constants that look "nice" (powers of 2, round numbers) in GC/overflow/sector-boundary tests.
**Rule**: For tests depending on sector layout (GC, overflow, allocation), value sizes MUST be computed from the same formulas as the C test. Port the `_TKV_*` macro computation exactly.
**Cost of ignoring**: GC never triggers, or triggers at wrong time — test proves nothing about GC correctness.

## AP-011: Missing Post-Wave Coverage Gap

**Source**: FlashDB L-006
**Description**: Wave 3 completed with 26 TSDB tests. But C test's `test_fdb_tsl_iter_by_time_1` (multi-sector iteration) had no Rust equivalent. Gap only discovered when building C Oracle diff test.
**Detection**: After Wave completion, no explicit comparison of Rust test list vs C test function list.
**Rule**: After each Wave, list all C test functions and verify each has a Rust equivalent. Any missing = mandatory addition before next Wave.
**Cost of ignoring**: Entire categories of edge cases untested until late in the project.

## Anti-Pattern Decision Matrix

| Situation | Anti-Pattern Risk | Mitigation |
|-----------|-------------------|------------|
| All tests green, no E2E | AP-001 + AP-002 | Add Real DI + immediate E2E |
| 10+ modules translated, 0 E2E runs | AP-002 | Stop translating, run E2E |
| stub_count > real_count | AP-003 | Pause, clear stubs first |
| Rust code looks like Go/C | AP-004 | Code review for idioms |
| Same task fails twice | AP-005 | Decompose + probe |
| "Implement X" task received | AP-006 | grep X first |
| `static mut` in test file | AP-007 | Replace with thread_local! |
| Agent says "this is broken" | AP-008 | Run cargo test independently |
| `assert_eq!(result, 42)` in test | AP-009 | Get 42 from source project |
| Nice round numbers in GC test | AP-010 | Compute from C test macros |
| Wave done, no coverage gap check | AP-011 | List C tests, find missing Rust equivalents |
