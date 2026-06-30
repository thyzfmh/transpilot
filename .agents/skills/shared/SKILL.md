---
name: shared-translation-engine
description: Cross-language shared translation infrastructure. Provides project governance (three-pillar documentation), parity verification protocol, E2E validation framework, and universal anti-patterns. Used as foundation by go2rust and c2rust skills.
---

# Shared Translation Engine

## Overview

This skill provides the universal infrastructure shared by all language-specific translation skills. It covers project governance, verification protocols, and accumulated anti-patterns from real-world large-scale translation projects.

## When to Use

- Starting a new translation project (any source language → Rust)
- Setting up project governance (state tracking, decision logging)
- Verifying translation correctness (parity checking)
- Planning E2E validation strategy
- Reviewing translation work for common anti-patterns

## Three-Pillar Documentation System

Every translation project needs three persistent documents:

| Pillar | File | Purpose | Update Frequency |
|--------|------|---------|-----------------|
| State | `.opencode/translation-state.jsonc` | Single source of truth for component status, parity scores, blockers | After every module |
| Decisions | `.opencode/decisions.md` | Every non-obvious translation decision with rationale | On every decision |
| Changes | `openspec/changes/<name>/` | Per-component change proposals | Per wave or phase |

**Critical rule**: NEVER modify translation-state.jsonc based on memory — only update after verifying actual file state.

## Translation Order

```
Phase 0: Shared infrastructure (API types, shared crates)
Phase 1: Leaf packages (no internal deps) — validate patterns
Phase 2: Core packages (depend on leaf packages)
Phase 3: Integration packages (depend on core + external)
```

## Wave Pattern

For large components (>10 modules), break into waves of 3-5 modules:
- Each wave gets a dedicated change proposal
- Each task within a wave ≤ 200 lines of code
- Last task of each wave = integration verification
- E2E gate: first wave MUST include E2E validation

## Probe-Before-Implement Rule

Before implementing any task:
1. `grep` for the target type/function name
2. Check if 90% already exists (common in incremental projects)
3. If found, scope the actual delta (often 10% of estimate)
4. Saves average 70% of estimated work (verified 3× in Taibai)

## Related Files

- `governance.md` — Detailed three-pillar documentation system
- `openspec-workflow.md` — OpenSpec 变更治理工作流（propose/apply/archive/sync）
- `parity-checker.md` — Four-layer equivalence verification protocol
- `e2e-validator.md` — E2E validation framework
- `anti-patterns.md` — Eleven universal translation anti-patterns (AP-001 to AP-011)
- `lessons-flashdb.md` — FlashDB translation lessons (L-001 to L-008)
- `interfaces.md` — Skill 间数据流契约（v1.0）

## Unwrap Classification

Not all `unwrap()` is equal. Classify before removing:

| Pattern | Safety | Action |
|---------|--------|--------|
| `buf[offset..offset+4].try_into().unwrap()` (compile-time-known size) | ✅ Safe | Keep — can never fail |
| `option.unwrap()` after `if option.is_none() { return }` guard | ✅ Safe | Keep — provably Some |
| `result.unwrap()` on IO / user input / dynamic size | ❌ Unsafe | Replace with `?` or `map_err` |
| `result.unwrap()` on external dependency output | ❌ Unsafe | Replace with proper error propagation |

## Verification Script Ordering

The order of checks in verification scripts matters:

```
1. cargo fmt --check   ← cheapest, catches style issues first
2. cargo check         ← type correctness
3. cargo test          ← functional correctness
4. unsafe audit        ← safety compliance
5. placeholder audit   ← completeness
```

Rationale: Formatting issues indicate hasty code. Catch them early before deeper analysis.

## Clean-Room Verification Rule

Any deliverable (init script, build script, verify script) MUST be tested in a clean/temporary environment before claiming it works. "Works on my machine" is not a delivery standard.

Test command: run the script in `/tmp/` or equivalent, verify `cargo check` passes on generated output.
