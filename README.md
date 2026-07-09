# Transpilot FlashDB Competition Package

This repository is packaged for one task: translate FlashDB from C to Rust with
OpenCode.

## Entry

Use the repository root entry file:

```text
INSTRUCTION.md
```

It tells OpenCode to load and execute:

```text
work/skills/flashdb-rust-autonomous/SKILL.md
```

`transpilot init` is not a skill and is not part of this competition package.

## Fixed Task

- Source: `code/FlashDB`
- Target: `code/flashDB_rust`
- Skill name: `flashdb-rust-autonomous`
- Final gate: `code/flashDB_rust/harness/final_verify.sh`
- Result file: `result/output.md`

The skill owns the full loop: source inspection, Rust design, implementation,
test porting, repair, final verification, and result update.

## Directory Layout

```text
transpilot/
├── INSTRUCTION.md
├── AGENTS.md
├── code/
│   └── FlashDB/
├── work/
│   └── skills/
│       └── flashdb-rust-autonomous/
│           ├── SKILL.md
│           ├── scripts/
│           │   └── self_check.sh
│           └── tests/
│               └── package_check.sh
├── result/
│   └── output.md
├── logs/
└── docs/
```

## Local Checks

The repository-level checks for this package are:

```bash
work/skills/flashdb-rust-autonomous/scripts/self_check.sh
```

`code/flashDB_rust` is created and completed by the skill during the OpenCode
competition run. Once present, the required final verification command is:

```bash
cd code/flashDB_rust && ./harness/final_verify.sh
```
