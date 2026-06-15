# Translation Project Governance System

## Three-Pillar Documentation

### Pillar 1: translation-state.jsonc

**Location**: `.opencode/translation-state.jsonc`
**Purpose**: Single source of truth — component status, parity scores, blockers, current module

**Rules**:
- NEVER modify based on memory — only update after verifying actual file state
- Every module translation MUST update this file
- New sessions MUST read this file first
- Use JSONC (JSON with Comments) for inline context

**Structure**:
```jsonc
{
  "project": { "name", "source_language", "source_root", "target_root" },
  "components": {
    "<name>": {
      "status": "not_started|in_progress|e2e_validated|complete",
      "source_modules_total": N,
      "source_modules_translated": N,
      "parity_score": N,
      "current_module": "<context>",
      "next_modules": [],
      "blockers": []
    }
  }
}
```

### Pillar 2: decisions.md

**Location**: `.opencode/decisions.md`
**Purpose**: Record every non-obvious translation decision with rationale

**Entry Format**:
```markdown
### [DXXX] Short Title
- **Date**: YYYY-MM-DD
- **Component**: <component>
- **Source Module**: <source path>
- **Target Module**: <rust path>
- **Context**: What problem necessitated this decision
- **Decision**: What was decided
- **Rationale**: Why this over alternatives
- **Impact**: What this affects downstream
- **Alternatives Considered**: What else was evaluated
```

**Categories**:
- `[D-TYPE-xxx]` — Type mapping decisions
- `[D-MEM-xxx]` — Memory management (C→Rust specific)
- `[D-CONC-xxx]` — Concurrency decisions
- `[D-ARCH-xxx]` — Architecture decisions
- `[D-COMPAT-xxx]` — Compatibility decisions
- `[D-UNSAFE-xxx]` — Unsafe usage (C→Rust specific)
- `[L-xxx]` — Lessons learned (process changes)

### Pillar 3: OpenSpec Changes

**Location**: `openspec/changes/<name>/`
**Purpose**: Per-component/feature change proposals

**Four Artifacts**:
1. `proposal.md` — Problem statement + high-level approach
2. `design.md` — Detailed design with trade-offs
3. `specs/` — Behavioral specifications
4. `tasks.md` — Implementable task breakdown

**Wave Pattern**:
- Large components → break into waves (3-5 modules/wave)
- Each wave = one OpenSpec change proposal
- Wave lifecycle: propose → apply → archive → sync

## Session Resumption Protocol

Every new session starts with:
1. Read `translation-state.jsonc` → restore context
2. Read last 10 decisions from `decisions.md` → understand history
3. Check `current_module` and `next_modules`
4. Check `blockers`
5. Verify source code path is accessible
6. Begin work

Every session ends with:
1. Update `translation-state.jsonc` with progress
2. Record new decisions to `decisions.md`
3. Update OpenSpec tasks if applicable
