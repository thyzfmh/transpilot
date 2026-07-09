# OpenCode Trial Analysis - 2026-07-09

Command used:

```bash
opencode run --dangerously-skip-permissions --title "FlashDB Rust autonomous trial with embedded harness" "请读取 INSTRUCTION.md，加载并执行 work/skills/flashdb-rust-autonomous/SKILL.md。按该 skill 的规则，从 code/FlashDB 翻译到 code/flashDB_rust，不询问用户，持续实现、测试、修复，直到 code/flashDB_rust/harness/final_verify.sh 通过，并更新 result/output.md。"
```

Observed good behavior:

- OpenCode loaded `INSTRUCTION.md`, `work/skills/flashdb-rust-autonomous/SKILL.md`, and `AGENTS.md`.
- Phase 0 copied `Cargo.toml`, `.cargo/config.toml`, and all `harness/*.sh` from the skill templates into `code/flashDB_rust`.
- Copied harness files matched the skill templates exactly.
- C KVDB/TSDB tests passed and were treated as oracle evidence.
- Layout probes were written under `/tmp`, not into `code/FlashDB`, avoiding source pollution.

Observed problem:

- After reading full source and running layout probes, OpenCode spent several minutes without writing `reports/source-inventory.md`, Rust source, or tests.
- The target still contained only copied templates when interrupted.
- Root cause: the skill allowed too much hidden all-at-once design after Phase 1.

Follow-up change:

- Added mandatory durable Phase 1 reports: `reports/source-inventory.md` and `reports/layout-probe.md`.
- Added a mandatory first Rust slice for layout helpers and layout oracle tests before KVDB/TSDB implementation.
