# Transpilot — Source Code Translation Toolkit

## Overview

Transpilot is a standalone, reusable toolkit for translating large codebases from Go or C to Rust.
Born from Taibai (Rust reimplementation of Kubernetes v1.36), generalizing 30+ translation decisions and 8 critical lessons.

## Supported Languages

| Source | Target | Skill Path |
|--------|--------|------------|
| Go | Rust | `.agents/skills/go2rust/` |
| C | Rust | `.agents/skills/c2rust/` |

## Key Paths

- Skills: `.agents/skills/`
- Templates: `templates/`
- Config: `config/`
- Scripts: `scripts/`

## Core Rules

1. 1:1 replication — match source *behavior*, not *API shape*
2. Rust idioms — adapt to ownership, Result, traits
3. No unwrap() in production code
4. Update translation-state.jsonc after each module
5. E2E Gate — run E2E after FIRST module, not after ALL
6. Dual DI — both Mock and Real implementations
7. Probe first — check if code exists before writing
8. Wave pattern — 3-5 modules per batch
9. Leaf first — translate leaf packages before core
10. Zero placeholders at wave end — `scripts/forbid-placeholders.sh` must pass
11. Evidence-based translation — no assertion without `codegraph_node` citation; every non-trivial function passes anti-hallucination 6-questions
12. Fresh index — `scripts/check-codegraph-freshness.sh` runs before each wave
13. **Oracle independence** — expected values come from `src_run()`, fixtures, or static codegraph; never from AI. Enforced by `scripts/check-oracle-independence.sh`
14. **T0 acceptance plan** — every project starts with `acceptance-plan.yaml` (template at `templates/acceptance-plan.yaml.template`), user-confirmed before wave-1
15. **Analyze sync before Wave 1** — after project analysis, summarize findings to the user and ask scope/Oracle/E2E questions before planning the first Wave

## Skill Usage

| I want to... | Run |
|---|---|
| Initialize a target project | `./scripts/transpilot init <source> <target>` |
| Review acceptance gate | `./scripts/transpilot acceptance review` |
| Confirm acceptance gate | `./scripts/transpilot acceptance confirm` |
| Start/continue translating | `./scripts/transpilot run --dry-run` then follow the OpenCode handoff |
| Check progress | `./scripts/transpilot status` |
| Check expert progress | `./scripts/transpilot status --expert` |
| Diagnose setup | `./scripts/transpilot doctor` |
| Audit hallucinations | `/anti-hallucination <wave>` |
| Verify parity | `/parity-checker <component> [module]` |
| Run E2E validation | `/e2e-validator <component>` |
| Diagnose E2E failures | `/e2e-debugger <component>` |
| Diff-test behavior (Oracle = source project) | `/differential-tester <wave>` |
| Check index freshness | `./scripts/check-codegraph-freshness.sh` |
| Check placeholders | `./scripts/forbid-placeholders.sh src` |
| Check Oracle independence | `./scripts/check-oracle-independence.sh tests` |

## Cross-Skill Contract

All skills exchange data via `.opencode/*.jsonc` files — schema locked in
`.agents/skills/shared/interfaces.md` (v1.0). Schema changes require OpenSpec
proposal.

Key data flows:
- `wave-N.jsonc` (translator) → `parity-N.jsonc` (parity-checker)
  → `halluc-N.jsonc` (anti-hallucination) → `diff-N.jsonc` (differential-tester)
  → `translation-state.jsonc` (harness, single source of truth)
- `acceptance-plan.yaml` is read-only after T0 confirmation — only OpenSpec
  proposal can amend it.
