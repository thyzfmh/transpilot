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
11. Evidence-based translation — no assertion without `codegraph_node` citation; every non-trivial function passes anti-hallucination 5-questions
12. Fresh index — `scripts/check-codegraph-freshness.sh` runs before each wave

## Skill Usage

| I want to... | Run |
|---|---|
| Start/continue translating | `/translator <lang> <component>` |
| Audit hallucinations | `/anti-hallucination <wave>` |
| Verify parity | `/parity-checker <component> [module]` |
| Run E2E validation | `/e2e-validator <component>` |
| Diagnose E2E failures | `/e2e-debugger <component>` |
| Check progress | `/status [component]` |
| Check index freshness | `./scripts/check-codegraph-freshness.sh` |
| Check placeholders | `./scripts/forbid-placeholders.sh src` |

## Cross-Skill Contract

All skills exchange data via `.opencode/*.jsonc` files — schema locked in
`.agents/skills/shared/interfaces.md` (v1.0). Schema changes require OpenSpec
proposal.
