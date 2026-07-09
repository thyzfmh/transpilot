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

`transpilot init` is not a skill. It is an older local CLI bootstrap command in
this source tree and is not part of the competition execution path.

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
│           └── SKILL.md
├── result/
│   └── output.md
├── logs/
├── scripts/
├── harness/
├── tests/
└── docs/
```

## Local Checks

The repository-level checks for this package are:

```bash
tests/test_flashdb_competition.sh
tests/test_transpilot_cli.sh
python3 /Users/tanghui/.codex/skills/.system/skill-creator/scripts/quick_validate.py work/skills/flashdb-rust-autonomous
cd code/FlashDB/tests && make test
```

`code/flashDB_rust` is created and completed by the skill during the OpenCode
competition run. Once present, the required final verification command is:

```bash
cd code/flashDB_rust && ./harness/final_verify.sh
```
