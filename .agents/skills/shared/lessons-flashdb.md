# FlashDB Translation Lessons

> Crystallized from the complete FlashDB C→Rust translation (3 Waves, 4730 LOC, 107 tests, 0.12% unsafe).
> These lessons supplement the universal anti-patterns in `anti-patterns.md`.

## L-001: `static mut` in Tests → Thread-Local

**Trigger**: Test passes in isolation but fails under `cargo test` (parallel execution).

**Root cause**: `static mut COUNTER: i32 = 0` is shared across test threads. Thread A writes, Thread B reads stale/wrong value.

**First attempt fails**: `AtomicI32` is genuinely shared across threads — Thread A's `fetch_add(2)` affects Thread B's counter.

**Fix**: `thread_local! { static COUNTER: Cell<i32> = Cell::new(0); }` — each thread gets its own isolated counter.

**Rule**: In any test that uses a mutable global counter/timestamp:
```
❌ static mut CUR_TIME: i32 = 0;
❌ static CUR_TIME: AtomicI32 = AtomicI32::new(0);  // cross-thread contamination
✅ thread_local! { static CUR_TIME: Cell<i32> = Cell::new(0); }
```

**When this applies**: Any C test that uses `static int cur_time = 0;` with incrementing `get_time()`.

## L-002: Agent Self-Report ≠ Ground Truth

**Trigger**: Deep agent reports "I have bugs in tsl_iter_by_time" after 51-minute run.

**Reality**: `cargo test` showed all 107 tests pass. Agent had found and fixed its own bugs during the run.

**Rule**: Only `cargo test` exit code is truth. Agent self-reports ("I have bugs" / "this is broken") must be independently verified. Never assume the agent's final assessment is accurate.

**Pattern**:
```
Agent says: "tsl_iter_by_time has issues"
Your action: Run cargo test → all pass → ignore agent's self-report
```

## L-003: C Oracle is the Highest-Credibility Verification

**Trigger**: Need to prove Rust implementation matches C behavior, not just passes self-written tests.

**Solution**: Build C Oracle programs that:
1. Perform a fixed sequence of operations
2. Output results as JSONL to stdout
3. Rust test parses C output, replays same operations, compares

**Why it works**: C code is compiled and run — AI cannot fabricate runtime output. AI only writes input generators, never expected values.

**Credibility**: ★★★★★ (vs ★ for AI-written assertions)

**Oracle variants needed** (based on FlashDB experience):
| Oracle | Scenario | Why needed |
|--------|----------|------------|
| Basic CRUD | set/get/del/iter/append | Core functionality |
| GC trigger | Fill sectors, overwrite, trigger GC | GC is the hardest path to get right |
| Multi-sector iteration | Span 3+ sectors with iter_by_time | Sector boundary edge cases |
| Reboot persistence |_deinit + reinit, check state | Flash I/O round-trip |

## L-004: GC Test Values Must Be Computed, Not Guessed

**Trigger**: KVDB GC diff test needs GC to actually trigger.

**Problem**: If KV value sizes are wrong, either:
- Too small → too many KVs per sector, GC doesn't trigger when expected
- Too large → can't fit enough KVs to create the required garbage pattern

**Solution**: Port the C test's `_TKV_*` macro computation exactly:
```c
_TKV_BASE = KV_HDR_SZ + aligned_name_len  // per-KV overhead
_TKV_USABLE = sector_size - sector_hdr_sz  // usable data space
TEST_KV_VALUE_LEN = (USABLE - 3*BASE + 3) / 4  // exact fit constraint
```

**Rule**: For any test that depends on sector layout (GC, overflow, allocation failure), the value sizes MUST be computed from the same formulas as the C test. Do NOT pick round numbers.

## L-005: `try_into().unwrap()` in Binary Parsing is Safe

**Trigger**: Code review found ~15 `unwrap()` calls in tsdb.rs.

**Analysis**: All follow the same pattern: slicing a known-size buffer at compile-time constant offsets.
```rust
let time_bytes: [u8; 4] = buf[OFFSET..OFFSET + 4].try_into().unwrap();
```
This can never fail — 4-byte slice → `[u8; 4]` is always valid when offset + 4 ≤ buf.len().

**Classification**:
- ✅ Compile-time-known-size array conversion → `unwrap()` is safe
- ✅ `if let Some` / `is_none()` guard above → `unwrap()` is safe
- ❌ IO operations / user input / dynamic sizes → must use `?` or `map_err`

## L-006: Post-Wave Coverage Gap Analysis is Mandatory

**Trigger**: Wave 3 completed with 26 TSDB tests, but multi-sector iter_by_time was untested.

**Problem**: Tests use small configs (4 sectors, MemFlash). C tests use 16 sectors, PosixFlash, and span sector boundaries. The gap was only found when building the C Oracle diff test.

**Rule**: After each Wave, compare Rust test coverage against C test coverage:
1. List all C test functions (e.g., `test_fdb_gc`, `test_fdb_gc2`, `test_fdb_tsl_iter_by_time_1`)
2. Check if each has a Rust equivalent
3. Any missing = mandatory addition before next Wave

## L-007: `cargo fmt --check` is the Cheapest Lint

**Trigger**: Wave 3 deep agent's output had formatting issues caught by `build_check.sh`.

**Rule**: Format check should be the FIRST gate in any verification script, before `cargo check`. Formatting inconsistency = code written in haste, may have quality issues.

```
build_check.sh order:
1. cargo fmt --check   ← cheapest, catches style issues
2. cargo check         ← type correctness
3. cargo test          ← functional correctness
```

## L-008: End-to-End Verification in Clean Environment

**Trigger**: Competition deliverable must work from scratch, not just on developer's machine.

**Test**: Run `init-c-to-rust-project.sh` in `/tmp/` → verify `cargo check` passes on generated project.

**Rule**: Any deliverable (init script, build script, verify script) MUST be tested in a clean/temporary environment. "Works on my machine" is not a delivery standard.

## Lesson-to-Anti-Pattern Mapping

| Lesson | Anti-Pattern | New AP ID |
|--------|-------------|-----------|
| L-001 | Test-time shared mutable state | AP-007 |
| L-002 | Trusting agent self-report | AP-008 |
| L-003 | Self-written test assertions | AP-009 |
| L-004 | Guessed sector layout | AP-010 |
| L-006 | Missing coverage gap analysis | AP-011 |

## Lesson-to-Skill Updates

| Lesson | Skill File | Update |
|--------|-----------|--------|
| L-001 | `c2rust/SKILL.md` | Add test template with thread_local! |
| L-003 | `differential-tester/reference.md` | Add Oracle variant table |
| L-004 | `c2rust/SKILL.md` | Add GC sizing rule |
| L-005 | `shared/SKILL.md` | Add unwrap classification |
| L-006 | `translator/workflow.md` | Add post-wave coverage gap step |
| L-007 | `shared/SKILL.md` | Add verification order rule |
| L-008 | `shared/SKILL.md` | Add clean-room verification rule |
