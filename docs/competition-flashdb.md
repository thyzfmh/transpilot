# FlashDB Competition Harness

This repository is currently shaped as a FlashDB C-to-Rust competition package.

## Platform Entry

The execution agent should start from the root file:

```text
INSTRUCTION.md
```

That file names the executable skill:

```text
work/skills/flashdb-rust-autonomous/SKILL.md
```

`transpilot init` is not a skill and is not required for the competition run.
Any package self-check scripts live under the skill directory.
The target harness scripts are also prebuilt under the skill directory and are
copied into `code/flashDB_rust/harness/` during Phase 0.

## Fixed Contract

- Source: `code/FlashDB`
- Target: `code/flashDB_rust`
- Rust crate name: `flashdb_rust`
- Trusted final verification: `work/skills/flashdb-rust-autonomous/scripts/final_verify_target.sh`
- Result report: `result/output.md`

## Skill Responsibilities

The skill must close the whole loop:

1. inspect FlashDB C source and tests;
2. design the Rust representation from source evidence;
3. implement FlashDB behavior in Rust;
4. port source-backed Rust tests;
5. run build, tests, unsafe audit, and placeholder audit;
6. fix failures from concrete compiler or test output;
7. repeat until every code-level and contract gate passes;
8. update `result/output.md`.

The Skill applies reusable C-to-Rust constraints for ABI layout, integer
semantics, persistent bytes, state machines, callbacks, errors, ownership and
unsafe auditing. FlashDB paths, build commands and configuration remain data
in the project adapter rather than business-specific logic in the reusable
method.

## Final Gate

The competition run is not complete until this command exits successfully:

```bash
work/skills/flashdb-rust-autonomous/scripts/final_verify_target.sh
```
