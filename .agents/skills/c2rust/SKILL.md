---
name: c2rust
description: Universal C→Rust translation skill. Covers system-level (Linux kernel, embedded) and application-level (Redis, Nginx, SQLite) C projects. Core challenges - memory management, pointer safety, preprocessor, global mutable state, FFI interop. Triggers - C to Rust, C translation, memory safety, unsafe audit, FFI.
---

# C → Rust Translation Skill

## Overview

C→Rust translation's core goal is **eliminating undefined behavior**, not mere syntax conversion. Every malloc/free, pointer dereference, and type cast is a potential safety gap.

**Strategy**: First create unsafe 1:1 port, then systematically push unsafe to boundary layers.

## When to Use

- Translating any C codebase to Rust
- System-level projects (kernel modules, embedded, drivers)
- Application-level projects (Redis, Nginx, SQLite-like)
- Creating safe Rust wrappers around C libraries
- Auditing unsafe code usage

## Translation Phases

### Phase 0: Analysis & Planning
- Static analysis: global variables, function pointers, macro usage statistics
- Dependency graph: `.h` include relationships → module dependency DAG
- unsafe budget: estimate what MUST remain unsafe (FFI, inline asm)
- Safety boundary: define where safe Rust wrapper layer sits

### Phase 1: FFI Layer (for incremental migration)
- `bindgen` generates C header bindings
- Thin unsafe wrapper layer
- Safe Rust API wraps unsafe calls
- This layer shrinks as pure Rust implementations replace C modules

### Phase 2: Leaf Modules (pure computation, no I/O deps)
- Data structure translation
- Pure function translation
- Unit test porting

### Phase 3: Core Modules
- Memory management subsystem replacement
- Error handling unification
- Concurrency model replacement

### Phase 4: Integration
- Event loop / main loop replacement
- I/O subsystem replacement
- Full E2E testing

## Difficulty Classification

| Difficulty | C Pattern | Rust Equivalent | Example |
|---|---|---|---|
| Easy | struct + functions | struct + impl | Data containers |
| Easy | #define CONST | const CONST: Type | Constants |
| Medium | linked list + malloc/free | Vec/VecDeque/BTreeMap | Containers |
| Medium | return code errors | Result<T, E> | Error propagation |
| Hard | pointer arithmetic | safe abstractions (index/iter/slice) | Buffer ops |
| Hard | function pointer tables | trait object / enum dispatch | Vtables |
| Hard | global mutable state | OnceLock/Mutex/thread_local | Config/cache |
| Very Hard | setjmp/longjmp | Result + ? operator | Error recovery |
| Very Hard | preprocessor metaprogramming | const/cfg/macro_rules!/proc_macro | Conditional compile |
| Very Hard | void* generics | real generics <T> | Generic containers |
| Very Hard | inline assembly | asm! macro + cfg(target_arch) | Perf-critical paths |

## unsafe Budget Rules

- Target: unsafe code < 5% of total lines
- Every `unsafe` block MUST have `// SAFETY:` comment explaining invariants
- Every `unsafe` block MUST have a corresponding safe test
- unsafe is ONLY acceptable for: FFI calls, verified raw pointer ops, verified transmute
- Prefer `unsafe` elimination hierarchy:
  1. Can it be done with safe Rust? → Do it safely
  2. Can it use a safe wrapper crate (bytemuck, zerocopy)? → Use the crate
  3. Must it be unsafe? → Isolate in smallest possible scope with SAFETY comment

## Key Differentiation Decisions

### D1: malloc/free → Ownership System
C's manual memory management → Rust's ownership + Drop.
Decision tree: see `memory-patterns.md` Pattern M-008.

### D2: Pointer Arithmetic → Safe Abstractions
C's ptr++ → Rust's iterators, slice indexing, or offset calculations.
Raw pointers only at FFI boundary.

### D3: Preprocessor → Type System + cfg
C's #define/#ifdef → Rust's const, type aliases, cfg attributes, feature flags.
Complex macros → macro_rules! or proc_macro.

### D4: Global Mutable State → Safe Patterns
C's global variables → OnceLock (init-once), Mutex (mutable), thread_local (per-thread).
static mut is FORBIDDEN — always use safe wrappers.

### D5: Error Handling → Result<T, E>
C's return codes + errno → Rust's Result with typed errors.
Never leave error codes as-is — always wrap in Result.

## Common Mistakes

| Mistake | Consequence | Fix |
|---------|-------------|-----|
| Translate malloc literally as unsafe alloc | Memory unsafety preserved | Use Box/Vec/Arc |
| Keep void* as *const c_void | No type safety | Use generics <T> |
| Leave global mutable state as static mut | Data races | OnceLock/Mutex/thread_local |
| Large unsafe blocks | Difficult to audit | Minimize unsafe scope |
| No SAFETY comments | Unverifiable correctness | Document invariants |
| Skip FFI wrapper layer | Unsafe leaks everywhere | Always wrap unsafe in safe API |
| Copy preprocessor logic verbatim | Unidiomatic Rust | Use cfg/const/macro |

## Related Files

- `memory-patterns.md` — 9 memory management patterns
- `pointer-patterns.md` — 7 pointer translation patterns
- `preprocessor-patterns.md` — 9 preprocessor translation patterns
- `ffi-patterns.md` — FFI interop strategies
- `unsafe-audit.md` — unsafe usage audit guide
