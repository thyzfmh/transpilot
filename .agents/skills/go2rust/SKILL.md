---
name: go2rust
description: Universal Go→Rust translation skill. Covers type mapping, concurrency patterns, error handling, serialization compatibility, DI patterns. Applicable to any Go project. Triggers - Go to Rust, Go translation, 1:1 porting, wire-compatibility, behavioral equivalence.
---

# Go → Rust Translation Skill

## Overview

Lessons from translating Kubernetes v1.36 (~500K Go LOC) to Rust across 7 components. These practices apply to any large Go→Rust porting project where behavioral equivalence is required.

**Core principle**: 1:1 replication means matching Go's *behavior*, not Go's *API shape*. Rust has fundamentally different concurrency, ownership, and error handling models — adapt the API shape to Rust idioms while preserving wire behavior.

## When to Use

- Translating any Go codebase to Rust
- Any Go→Rust project requiring wire/behavioral compatibility
- Setting up governance for a multi-component translation project
- Making Go-Rust differentiation decisions

## Translation Strategy

### Incremental Translation Order

```
Phase 0: Shared infrastructure (API types, shared crates)
Phase 1: Leaf packages (no internal deps) — validate pattern
Phase 2: Core packages (depend on leaf packages)
Phase 3: Integration packages (depend on core + external)
```

**Start with leaf packages** to validate type mapping patterns before tackling complex dependencies.

### Placeholder Stub Strategy

When a dependency type doesn't exist yet:
1. Define local placeholder struct with `#[derive(Default, Clone, Debug, Serialize, Deserialize)]`
2. Use `Option<PlaceholderType>` with `#[serde(default, skip_serializing_if = "Option::is_none")]`
3. Add TODO comment linking to the gap
4. Replace incrementally when dependency becomes available

**Never block on missing types.** Local stubs allow forward motion.

### Wave Pattern

For components with many sub-modules (>10), create wave proposals (3-5 modules per wave):
- Keeps task lists manageable
- Allows incremental verification
- Last task per wave = integration verification

## Key Differentiation Decisions

### D1: OnceLock Lazy Init vs Go's Immediate Registration

Go's global variables initialize immediately in `init()`. Rust's `OnceLock<T>` delays until first access.

**Impact**: Resources invisible until first use (e.g., metrics show 0 items in /metrics).
**Solution**: Every module with lazy globals MUST have an `init()` / `warm_up()` function called at startup.

### D2: Send + Sync Bounds on Trait Objects

Go interfaces are inherently goroutine-safe. Rust trait objects used across threads MUST have `Send + Sync` bounds.

**Rule**: Every trait stored in `Arc`/shared across threads needs `: Send + Sync` supertrait.
**Example**: `trait Controller: Send + Sync { fn run(&self); }`

### D3: trait object → Arc<struct> for Shared State

Go interface values have reference semantics (pointer internally). Rust `Box<dyn Trait>` has ownership semantics.

**Rule**: When multiple consumers share a value → `Arc<ConcreteStruct>`, not `Box<dyn Trait>`.

### D4: serde(default) vs Go encoding/json Zero-Value Initialization

Go's `json.Unmarshal` silently zero-initializes missing struct fields. Rust's serde REJECTS missing non-Option fields.

**Rule**: Struct fields that may be absent in JSON MUST have `#[serde(default)]` or be `Option<T>`.
**Real bug from Taibai**: webhook responses omit `spec`, Go accepts silently, Rust rejects with "missing field 'spec'".

### D5: Goroutine → OS Thread for Long-Running Controllers

Go goroutines are lightweight. But for long-running infinite loops (controllers), `tokio::spawn` is wrong — blocking loops starve the tokio scheduler.

**Rule**: Long-running controller loops → `std::thread::spawn()`. Controller trait MUST be `Send`.
**When to use tokio::spawn**: Short-lived async operations, I/O-bound work.

### D6: tokio::spawn Must Be Called Within Runtime Context

`tokio::spawn()` outside `rt.block_on()` panics with "no reactor running".

**Rule**: All tokio operations MUST be inside `block_on()` or an existing async context.
**Pattern for sync→async bridge**: Create dedicated `tokio::runtime::Runtime` instance, use `runtime.block_on()`.

## Common Mistakes

| Mistake | Consequence | Fix |
|---------|-------------|-----|
| Copy Go's API shape directly | Runtime crashes | Use Rust idioms (Result, Arc, OnceLock) |
| Only Mock DI implementations | Green CI Trap (L001) | Create both Mock AND Real impls |
| Block on missing types | Progress stalls weeks | Local placeholder stubs |
| Use `unwrap()` in production | Runtime panics | Result propagation + thiserror |
| Skip parity check after module | Silent behavioral drift | Run parity-checker every module |
| Monolithic proposal for 25+ modules | Unmanageable task list | Wave pattern (3-5 per wave) |
| Delay E2E until all complete | Expensive architectural gaps | E2E after first module (L003) |
| Use `todo!()` in production | Runtime panics on untested paths | Return Ok(default) with TODO comment |
| Redefine shared types locally | Type divergence | Always use shared types crate |

## Related Files

- `type-mapping.md` — Complete type mapping reference
- `concurrency-patterns.md` — 6 concurrency patterns
- `error-handling.md` — Error translation patterns
- `serde-patterns.md` — Serialization differences
