# FlashDB Competition Harness

This repository is currently shaped as a FlashDB C-to-Rust competition package.

## Platform Entry

OpenCode should start from the root file:

```text
INSTRUCTION.md
```

That file names the executable skill:

```text
work/skills/flashdb-rust-autonomous/SKILL.md
```

`transpilot init` is not a skill and is not required for the competition run.
Any package self-check scripts live under the skill directory.

## Fixed Contract

- Source: `code/FlashDB`
- Target: `code/flashDB_rust`
- Rust crate name: `flashdb_rust`
- Final verification: `code/flashDB_rust/harness/final_verify.sh`
- Result report: `result/output.md`

## Skill Responsibilities

The skill must close the whole loop:

1. inspect FlashDB C source and tests;
2. design the Rust representation from source evidence;
3. implement FlashDB behavior in Rust;
4. port source-backed Rust tests;
5. run build, tests, unsafe audit, and placeholder audit;
6. fix failures from concrete compiler or test output;
7. repeat until `final_verify.sh` passes;
8. update `result/output.md`.

The skill includes the FlashDB-specific C-to-Rust tactics: byte-layout
translation, explicit endian helpers, flash backend traits, status table
bit-pattern helpers, aligned length formulas, GC and sector state machines, and
unsafe auditing.

## Final Gate

The competition run is not complete until this command exits successfully:

```bash
cd code/flashDB_rust && ./harness/final_verify.sh
```
