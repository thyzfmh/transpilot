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

## Anti-Pattern Decision Matrix

| Situation | Anti-Pattern Risk | Mitigation |
|-----------|-------------------|------------|
| All tests green, no E2E | AP-001 + AP-002 | Add Real DI + immediate E2E |
| 10+ modules translated, 0 E2E runs | AP-002 | Stop translating, run E2E |
| stub_count > real_count | AP-003 | Pause, clear stubs first |
| Rust code looks like Go/C | AP-004 | Code review for idioms |
| Same task fails twice | AP-005 | Decompose + probe |
| "Implement X" task received | AP-006 | grep X first |
