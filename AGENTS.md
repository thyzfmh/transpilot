# Transpilot — FlashDB C→Rust Translation

## Your Task

**Translate FlashDB from C to Rust.** Execute the skill at `work/skill/c-to-rust/SKILL.md` and follow it to completion.

- **Source**: `code/FlashDB` (C)
- **Target**: `code/flashDB_rust` (Rust)
- **Do not stop** until `final_verify.sh` passes in the target project
- **Do not ask the user questions** — make reasonable decisions autonomously
- **If verification fails, fix it immediately and re-verify** — keep fixing until it passes

## Entry Point

1. Read and follow `INSTRUCTION.md`
2. Load and execute `work/skill/c-to-rust/SKILL.md`
3. Keep going until Phase 5 (Final Verification) passes

## Core Rules

1. 1:1 replication — match source *behavior*, not *API shape*
2. Rust idioms — adapt to ownership, Result, traits
3. No `unwrap()` in production code
4. Wave pattern — 3-5 modules per batch
5. Leaf first — translate leaf modules before core
6. Zero placeholders — no `todo!()`, `unimplemented!()`, or `panic!("TODO")`
7. Evidence-based translation — no assertion without source code citation
8. Oracle independence — expected values come from C source execution, never from AI
9. `thread_local!` for test counters — `static mut` causes parallel test failures
10. GC/sector tests need computed sizes — value sizes from C macros, not round numbers
11. Coverage gap analysis after each Wave — every C test must have a Rust equivalent
12. Autonomous mode — run full translation without asking questions until `final_verify.sh` passes; only escalate on 3× Wave failure or source bugs

## Additional Skills

- `work/skill/superpowers/` — general development skills (brainstorming, TDD, debugging, writing plans, etc.)
- `work/skill/openspec-*/` — structured change management (propose, apply, explore, archive, sync)
