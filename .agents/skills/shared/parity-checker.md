# Equivalence Verification Protocol

## Four-Layer Verification Model

### Layer 1: Structural Parity

**What**: Source exported functions/methods vs target pub functions/methods
**Formula**: `parity = real_implementations / (total_source_functions - autogen_excluded) × 100`
**Threshold**: ≥ 95% = structurally complete
**How**: Automated function counting

Definitions:
- `real_implementations`: Rust functions with actual matching logic
- `stubs`: Functions returning placeholder values (count against parity)
- `missing`: Source functions with no Rust equivalent (count against parity)
- `autogen_excluded`: Auto-generated code (excluded from denominator)

### Layer 2: Functional Parity

**What**: Key algorithms produce same output for same input
**Checks**:
- Error handling paths consistent
- Edge case behavior matches
- Default values match
- Control flow equivalent (branches, loops, early returns)
**How**: Cross-testing — same test cases drive both source and target

### Layer 3: Interface Parity

**What**: Wire-level compatibility
**Checks**:
- HTTP/gRPC endpoints: same response format
- Serialization: JSON field names, protobuf tags match exactly
- CLI: same flags, same output format
- Error responses: same format and codes
**How**: Record-replay testing — record source requests/responses, replay against target

### Layer 4: Behavioral Parity (Most Critical)

**What**: Runtime behavior equivalence
**Checks**:
- Concurrency: race conditions, deadlocks, liveness
- Resource management: memory leaks, file handles, connections
- Performance: comparable characteristics
- Side effects: same external observable effects
**How**: E2E testing — swap component in real environment

## Verification Cadence

| Trigger | Layers | Action |
|---------|--------|--------|
| After each module | 1 + 2 | Structural + functional check |
| After each wave | 1 + 2 + 3 | Add interface check |
| After component complete | All 4 | Full verification |
| First functional module done | 4 | E2E gate (L003) |

## Parity Report Format

```markdown
# Parity Report: <component>/<module>

| Dimension | Source Count | Target Count | Parity | Status |
|-----------|-------------|--------------|--------|--------|
| Types | N | N | 100% | ✅ |
| Functions | N | N | 95% | ✅ |
| Tests | N | N | 90% | ⚠️ |
| **Overall** | **N** | **N** | **95%** | **✅** |

## Missing Items
- ❌ <function_name> (reason)

## Stubs
- ⚠️ <function_name> (blocked by: <reason>)

## Decisions Made
- [DXXX] <title>
```

## Definition of Done

A module is NOT verified until:
1. Layer 1 parity ≥ 95%
2. Layer 2: all source tests have Rust equivalents
3. No `todo!()` macros in production code
4. No `unwrap()` in production code
5. All shared types come from shared crate (not locally redefined)
