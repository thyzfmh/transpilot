# Transpilot CLI

`scripts/transpilot` is the public P1 entry point for OpenCode users. It is intentionally thin: it wraps existing scripts, enforces acceptance confirmation, and prints user-facing status. It does not replace OpenCode skills.

## Commands

```bash
./scripts/transpilot install [--prefix DIR]
./scripts/transpilot init <source_path> <target_path> [--name NAME] [--lang go|c]
./scripts/transpilot analyze <source_path> [--goal TEXT] [--scope a,b,c]
./scripts/transpilot acceptance review
./scripts/transpilot acceptance confirm
./scripts/transpilot acceptance verify
./scripts/transpilot plan new <wave-id> [--goal TEXT] [--scope a,b,c]
./scripts/transpilot plan review <wave-id>
./scripts/transpilot run --dry-run
./scripts/transpilot status
./scripts/transpilot status --expert
./scripts/transpilot doctor
./scripts/transpilot check
```

## OpenCode Flow

0. Optional: install the wrapper:

   ```bash
   ./scripts/transpilot install
   ```

   This links `transpilot` into `~/.local/bin`. Each target project still receives its own local scripts and skills through `transpilot init`.

1. Initialize the target project:

   ```bash
   transpilot init /path/to/source /path/to/target
   ```

2. Open `/path/to/target` in OpenCode.

3. Analyze the source and start the early interaction:

   ```bash
   ./scripts/transpilot analyze /path/to/source
   ```

   The output includes a user sync section, questions to ask before Wave 1, and an OpenCode prompt. The agent should summarize findings and ask the user about scope, Oracle strategy, E2E smoke, and acceptance priorities before editing the plan.

4. Review and confirm the acceptance plan:

   ```bash
   ./scripts/transpilot acceptance review
   ./scripts/transpilot acceptance confirm
   ```

5. Ask OpenCode to continue with the next Wave:

   ```bash
   ./scripts/transpilot plan new wave-1 \
     --goal "migrate the user-confirmed slice" \
     --scope "path/a,path/b"
   ./scripts/transpilot plan review wave-1
   ```

   The Wave writing plan lives in `.opencode/plans/wave-001.md`. It is the minimum executable contract for the Wave: goal, behavior requirements, atomic tasks, test matrix, acceptance criteria, verification commands, and review gate.

6. Hand the plan to OpenCode:

   ```bash
   ./scripts/transpilot run --dry-run
   ```

   The command prints the handoff prompt. The actual translation work remains in OpenCode skills.

7. Track progress:

   ```bash
   ./scripts/transpilot status
   ./scripts/transpilot status --expert
   ```

## Acceptance Gate

`transpilot run` refuses to start until `acceptance-plan.yaml` is confirmed. Confirmation writes `.opencode/acceptance-confirmation.json` with the plan hash. If the plan changes, the confirmation is invalidated and must be renewed.

This protects the product quality red line: verification scope, Oracle mode, E2E command, and must-pass cases cannot silently change after T0.

## Complex C/C++ Projects

`transpilot analyze` warns when C++ files are present. The current stable path covers Go/C and C API slices. Full C++ core migration requires explicit scope and additional migration skills.

For a partial migration, pass a goal and scope:

```bash
./scripts/transpilot analyze /path/to/libzmq \
  --goal "migrate zmq_msg_t message lifecycle" \
  --scope "include/zmq.h,src/msg.cpp,src/metadata.cpp"
```

OpenCode should summarize the analysis, ask the user to confirm the proposed slice, then update `acceptance-plan.yaml` only after confirmation.

## Direct OpenCode Prompt

If you start from chat instead of the CLI, use:

```text
Please start Transpilot analysis only. Do not translate yet.

Read AGENTS.md, acceptance-plan.yaml, and .opencode/translation-state.jsonc.
Run ./scripts/transpilot analyze <source_path> with my goal/scope if provided.
Synchronize the findings with me in user language.
Ask me to confirm scope, Oracle strategy, E2E smoke command, and acceptance priorities.
Only after I confirm, update acceptance-plan.yaml and ask me to run:
  ./scripts/transpilot acceptance review
  ./scripts/transpilot acceptance confirm

Then create a Wave writing plan:
  ./scripts/transpilot plan new wave-1 --goal "<goal>" --scope "<scope>"

Fill the plan with source evidence, precise input/output behavior, boundary cases, full test matrix, and verification commands.
Execute one atomic task at a time.
After implementation, hand the Wave to a review agent.
If the review agent says tests, evidence, or behavior are insufficient, continue the same Wave with that feedback until the review gate passes.
```
