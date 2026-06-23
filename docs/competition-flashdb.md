# FlashDB Competition Harness

This branch adds a thin C-to-Rust competition profile for the FlashDB rewrite task.

The goal is not to expose the full Transpilot toolchain. The goal is to generate a practical harness project that OpenCode can use to migrate FlashDB one verified slice at a time.

## Why This Profile Is Thin

The competition asks for a harness engineering deliverable:

- rewrite `./code/FlashDB/src` as Rust;
- rewrite `./code/FlashDB/tests` as Rust tests;
- keep the Rust crate buildable and executable;
- keep production `unsafe` below 10%;
- use compile errors and test failures as a repair loop.

For this scenario, a heavy orchestration layer is counterproductive. The generated project keeps only what the competition can evaluate:

- a Rust crate named `flashdb_rust`;
- `AGENTS.md` with OpenCode execution rules;
- task plans under `plans/`;
- deterministic harness scripts under `harness/`;
- reports under `reports/`;
- compile, test, repair, unsafe audit, and final verification commands.

## Usage

Prepare the competition source:

```bash
git clone https://gitcode.com/xwxf/FlashDB ./code/FlashDB
cd ./code/FlashDB
git checkout -b competition f9d0421315c564fb890a1b14eee77b290e0d7bbe
```

Generate the harness:

```bash
transpilot competition flashdb init ./code/FlashDB ./flashdb_rust
```

Open `./flashdb_rust` in OpenCode.

Then run:

```bash
./harness/analyze_flashdb.sh ./code/FlashDB
./harness/plan_next_task.sh task-001 "Translate the first FlashDB behavior slice" "./code/FlashDB/src"
```

Ask OpenCode to follow:

- `AGENTS.md`;
- `acceptance-plan.yaml`;
- `reports/source-inventory.md`;
- the current `plans/task-*.md`.

## Generated Harness Commands

```bash
./harness/analyze_flashdb.sh [source]
./harness/plan_next_task.sh <task-id> <goal> <scope>
./harness/build_check.sh
./harness/repair_loop.sh
./harness/test_all.sh
./harness/unsafe_audit.sh 10
./harness/final_verify.sh
```

## OpenCode Loop

```text
read task plan
  -> cite source evidence
  -> implement the smallest C-to-Rust slice
  -> port or generate Rust tests from FlashDB source behavior
  -> run build/test/unsafe audit
  -> if failing, run repair_loop and patch from compiler/test output
  -> update plans and reports
  -> continue with the next task only after verification passes
```

## Design Bias

This profile intentionally favors boring, auditable engineering over broad automation:

- one language path: C to Rust;
- one benchmark project shape: FlashDB;
- one target crate: `flashdb_rust`;
- one verification path: Cargo build/test plus unsafe audit;
- one product promise: OpenCode can keep repairing from concrete error stacks.

