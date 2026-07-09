# Autonomous Harness

Autonomous execution for this competition lives inside:

```text
work/skills/flashdb-rust-autonomous/SKILL.md
```

The skill owns the loop:

```text
inspect source
  -> design Rust representation from C evidence
  -> implement one behavior slice
  -> port source-backed tests
  -> run verification
  -> repair from exact failures
  -> repeat until final_verify.sh passes
```

There is no separate harness workflow that OpenCode must load before this skill.
