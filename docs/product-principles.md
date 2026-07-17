# Product Principles

The active product shape for this branch is a narrow autonomous translation
package:

- a fixed FlashDB C source at `code/FlashDB`;
- a fixed Rust target at `code/flashDB_rust`;
- one executable skill at `work/skills/flashdb-rust-autonomous/SKILL.md`;
- a trusted final gate at
  `work/skills/flashdb-rust-autonomous/scripts/final_verify_target.sh`.

Keep platform-facing instructions direct. Do not require users or the
execution agent to discover legacy local tooling before running the Skill.
