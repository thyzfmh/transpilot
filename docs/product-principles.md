# Product Principles

Transpilot automates migration work, but it must not hide delivery risk from the user.

## Quality Red Lines

1. **No silent trust downgrade**
   - If source execution is unavailable, Oracle mode is downgraded, E2E is missing, or parity ceiling drops, the user must see and confirm it before Wave 1.

2. **Simple defaults, honest status**
   - Default status output uses user language: progress, trust, risks, blockers, and next action.
   - Expert terms such as `oracle_mode`, `hallucination_score`, and `diff_verdict` remain available through expert reports.

3. **Acceptance before automation**
   - `acceptance-plan.yaml` must be reviewed and confirmed before `transpilot run` or the harness can start a wave.
   - The confirmation lock records the plan hash and becomes invalid if the plan changes.

4. **Automation must be explainable**
   - Every automatic handoff must leave evidence in `.opencode/`, `decisions.md`, or a report.
   - A user should be able to ask why a wave stopped and get a concrete reason.

5. **Never overstate completion**
   - A translated codebase with weak Oracle evidence is not reported as production-ready.
   - Trust ceilings must affect the language used in status and final reports.

6. **Recovery is part of quality**
   - Large migrations must survive interruptions.
   - State lives in `.opencode/translation-state.jsonc`; decisions live in `.opencode/decisions.md`.

7. **Analysis must start a conversation**
   - After `transpilot analyze`, the agent must synchronize findings with the user before Wave 1.
   - Early interaction is expected: scope, Oracle strategy, E2E command, and acceptance priorities should be clarified before automation starts.
   - Superpowers-style brainstorming/planning is appropriate at this stage; it should reduce risk, not expose unnecessary internals.

8. **Every Wave needs a writing plan**
   - Before implementation, OpenCode must produce `.opencode/plans/wave-NNN.md`.
   - The plan must describe the goal, functional requirements, exact inputs/outputs, boundaries, atomic tasks, test matrix, verification commands, and review gate.
   - Tests must be sufficient. Happy-path-only tests are not acceptable.
   - A review agent must inspect the completed Wave. If the review finds weak tests, missing evidence, or behavior drift, OpenCode continues the same Wave with that feedback until the gate passes.

## OpenCode Product Shape

The public entry point is the thin CLI wrapper:

```bash
./scripts/transpilot init <source> <target>
./scripts/transpilot acceptance review
./scripts/transpilot acceptance confirm
./scripts/transpilot run --dry-run
./scripts/transpilot status
./scripts/transpilot status --expert
```

OpenCode and the skills remain the expert execution layer. The CLI reduces user workload; it does not replace the evidence chain.
