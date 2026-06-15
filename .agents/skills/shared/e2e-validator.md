# E2E Validation Framework

## Core Principle (from Taibai L003)

> E2E validation is a DESIGN REQUIREMENT, not a post-completion verification step.
> Run E2E after the FIRST functional module, not after ALL modules are done.
> Early E2E catches architectural gaps when they're cheap to fix.

## Validation Flow (6 Steps)

```
Step 0: Build target (cargo build --release)
  ↓
Step 1: Setup environment (cluster/server/database)
  ↓
Step 2: Baseline E2E (original component, record results)
  ↓
Step 3: Hot-swap (replace original with translated component)
  ↓
Step 4: Target E2E (same tests after swap)
  ↓
Step 5: Compare report (baseline vs target, determine PASS/FAIL)
  ↓
Step 6: Optional cleanup
```

## When to Run E2E

| Trigger | Action |
|---------|--------|
| First functional module complete | MANDATORY — E2E gate |
| Each wave complete | Recommended |
| Component complete | Required for sign-off |
| Bug fix applied | Re-run failed tests |

## Swap Strategies

### Strategy A: Process-level replacement
- Kill original process → start translated binary on same port
- Best for: servers, daemons, long-running services
- Risk: downtime during swap

### Strategy B: Library-level replacement
- Link against translated .so/.dylib instead of original
- Best for: library translations
- Risk: ABI compatibility

### Strategy C: Side-by-side comparison
- Run both original and translated simultaneously
- Compare responses for same inputs
- Best for: stateless services, CLI tools

## E2E Failure Handling

| Failure Count | Action |
|---------------|--------|
| 0 | ✅ Component verified |
| 1-5 | Run `/e2e-debugger` for automated diagnosis |
| 5+ | Manual triage, run debugger per-test |

## Smoke Test Checklist (Minimum E2E)

For any translated component, verify at minimum:
- [ ] Process starts without crash
- [ ] Health endpoint responds
- [ ] Basic CRUD operation works
- [ ] Error responses match source format
- [ ] Graceful shutdown works

## Integration with DI (from Taibai L001/L004)

**Critical**: E2E WILL FAIL if only Mock DI implementations exist.
Every DI trait must have BOTH:
1. `InMemory`/`Mock` implementation (for unit tests)
2. `Real`/`KubeBacked` implementation (for production/E2E)

A component with only Mock DI impls is NOT ready for E2E — it will compile and pass unit tests but fail functionally.
