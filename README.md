# Transpilot FlashDB Competition Package

This repository configures one source-to-Rust translation task. Its execution
Skill uses a reusable source-translation method and isolates current-project
facts in a project adapter.

## Entry

Use the repository root entry file:

```text
INSTRUCTION.md
```

It tells the execution agent to load and execute:

```text
work/skills/flashdb-rust-autonomous/SKILL.md
```

`transpilot init` is not a skill and is not part of this competition package.

## Fixed Task

- Source: `code/FlashDB`
- Target: `code/flashDB_rust`
- Skill name: `flashdb-rust-autonomous`
- Trusted final gate: `work/skills/flashdb-rust-autonomous/scripts/final_verify_target.sh`
- Result file: `result/output.md`

The skill owns the full loop: source inspection, Rust design, implementation,
test porting, repair, final verification, and result update. Fixed target
harness scripts are prebuilt under the skill and copied into
`code/flashDB_rust/harness/` during Phase 0.

## Method Layers

- `references/autonomous-source-translation-method.md`: project-independent
  discovery, source-oracle, repair, checkpoint, and completion loop.
- `references/c-to-rust-translation-spec.md`: reusable C-to-Rust constraints.
- `references/project-adapter.md` and `harness/project-adapter.json`: current
  source path, target artifact, native tests, headers, and commands.

The source-native test total is discovered from source. It is not encoded in
the general workflow.

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
│           │   ├── install_target_harness.sh
│           │   ├── final_verify_target.sh
│           │   └── self_check.sh
│           ├── templates/
│           │   ├── Cargo.toml
│           │   ├── cargo-config.toml
│           │   └── harness/
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

`code/flashDB_rust` is created and completed by the Skill during execution.
The trusted final verification command is run from the repository root:

```bash
work/skills/flashdb-rust-autonomous/scripts/final_verify_target.sh
```

The target-local `./harness/final_verify.sh` is an internal code-level gate.
It does not replace trace export, result finalization, and the trusted
completion checks performed by the command above.
