#!/usr/bin/env bash
# init-flashdb-competition.sh — generate a thin C->Rust competition harness for FlashDB.
set -euo pipefail

SOURCE_PATH="${1:?usage: $0 <flashdb_source_path> <target_path>}"
TARGET_PATH="${2:?usage: $0 <flashdb_source_path> <target_path>}"

if [ ! -d "$SOURCE_PATH" ]; then
  echo "ERROR: source path does not exist: $SOURCE_PATH" >&2
  exit 1
fi
if [ ! -d "$SOURCE_PATH/src" ]; then
  echo "ERROR: FlashDB source must contain src/: $SOURCE_PATH/src" >&2
  exit 1
fi

TODAY="$(date +%Y-%m-%d)"
mkdir -p "$TARGET_PATH"
cd "$TARGET_PATH"

if [ ! -d .git ]; then
  git init >/dev/null
fi

mkdir -p .opencode plans reports harness src tests .cargo

cat > Cargo.toml <<'EOF'
[package]
name = "flashdb_rust"
version = "0.1.0"
edition = "2021"

[lib]
name = "flashdb_rust"
path = "src/lib.rs"

[[bin]]
name = "flashdb_rust"
path = "src/main.rs"

[dependencies]
thiserror = "2"

[dev-dependencies]
tempfile = "3"
proptest = "1"
EOF

cat > src/lib.rs <<'EOF'
//! Rust reimplementation workspace for FlashDB.
//!
//! The competition harness starts with a compiling shell so OpenCode can migrate
//! one source-backed slice at a time. Replace this module with real FlashDB
//! behavior as task plans are completed.

pub fn harness_ready() -> bool {
    true
}
EOF

cat > src/main.rs <<'EOF'
fn main() {
    println!("flashdb_rust harness ready");
}
EOF

cat > tests/harness_smoke.rs <<'EOF'
#[test]
fn harness_starts_from_a_compiling_crate() {
    assert!(flashdb_rust::harness_ready());
}
EOF

cat > .cargo/config.toml <<'EOF'
[build]
rustflags = ["-Dwarnings"]
EOF

cat > .gitignore <<'EOF'
/target
/reports/*.log
/reports/*.tmp
.DS_Store
EOF

cat > acceptance-plan.yaml <<EOF
# FlashDB Rust Rewrite Competition Acceptance Plan
created_at: "$TODAY"

scope:
  source_project: "$SOURCE_PATH"
  source_src: "$SOURCE_PATH/src"
  source_tests: "$SOURCE_PATH/tests"
  target_project: "."
  target_language: rust
  in:
    - "$SOURCE_PATH/src"
    - "$SOURCE_PATH/tests"
  out:
    - "$SOURCE_PATH/docs"
    - "$SOURCE_PATH/samples"
    - "$SOURCE_PATH/port"

requirements:
  executable_crate: true
  rust_tests_required: true
  source_src_rewritten_to_rust: true
  source_tests_rewritten_to_rust: true
  unsafe_ratio_lt_percent: 10

verification:
  primary_commands:
    - "./harness/build_check.sh"
    - "./harness/test_all.sh"
    - "./harness/unsafe_audit.sh 10"
    - "./harness/final_verify.sh"
  oracle_policy:
    - "Expected values must come from FlashDB source tests, source code constants, fixtures, or user-confirmed behavior."
    - "AI-derived expected values are not accepted as semantic equivalence evidence."
  repair_policy:
    max_compile_repair_rounds_per_task: 5
    use_error_stack: true

deliverables:
  - "Cargo project named flashdb_rust"
  - "Rust implementation under src/"
  - "Rust tests under tests/"
  - "Harness scripts under harness/"
  - "Task plans under plans/"
  - "Final report under reports/final-report.md"
EOF

cat > AGENTS.md <<EOF
# FlashDB Rust Rewrite Harness

This project is a competition harness for rewriting FlashDB from C to Rust.

## Source

- FlashDB source: \`$SOURCE_PATH\`
- Required source scope: \`$SOURCE_PATH/src\`
- Required test scope: \`$SOURCE_PATH/tests\`
- Target language: Rust

## OpenCode Execution Rules

1. Work only on C to Rust migration. Do not add Go or generic migration machinery.
2. Read \`acceptance-plan.yaml\`, \`reports/source-inventory.md\`, and the current \`plans/task-*.md\` before editing Rust code.
3. Migrate one atomic task at a time.
4. Preserve FlashDB behavior, not just API shape.
5. Every non-trivial behavior claim needs source evidence from \`$SOURCE_PATH/src\`, \`$SOURCE_PATH/tests\`, or user confirmation.
6. Rust tests must cover happy path, boundary cases, error paths, and source regression cases.
7. If \`cargo check\` or \`cargo test\` fails, read the error stack and patch precisely. Do not blindly rewrite unrelated modules.
8. Keep production \`unsafe\` below 10% by \`./harness/unsafe_audit.sh 10\`.
9. Do not leave \`todo!\`, \`unimplemented!\`, \`panic!("TODO")\`, placeholder modules, or fake tests in completed tasks.
10. After each task, run:

\`\`\`bash
cargo fmt
./harness/build_check.sh
./harness/test_all.sh
./harness/unsafe_audit.sh 10
\`\`\`

## Required Loop

\`\`\`text
read task plan
  -> cite source evidence
  -> implement the smallest Rust slice
  -> port or generate Rust tests from source behavior
  -> run build/test/unsafe audit
  -> if failing, run repair loop and patch from the error stack
  -> update the task plan and reports
  -> move to the next task only after verification passes
\`\`\`

## Final Gate

Before claiming completion, run:

\`\`\`bash
./harness/final_verify.sh
\`\`\`
EOF

cat > README.md <<EOF
# flashdb_rust Competition Harness

This harness is generated for the FlashDB Rust rewrite competition.

## Quick Start

\`\`\`bash
./harness/analyze_flashdb.sh "$SOURCE_PATH"
./harness/plan_next_task.sh task-001 "Inventory FlashDB src/tests and choose the first safe Rust slice" "$SOURCE_PATH/src,$SOURCE_PATH/tests"
\`\`\`

Then open this directory in OpenCode and ask it to follow \`AGENTS.md\` and the current file under \`plans/\`.

## Verification

\`\`\`bash
./harness/build_check.sh
./harness/test_all.sh
./harness/unsafe_audit.sh 10
./harness/final_verify.sh
\`\`\`
EOF

cat > harness/analyze_flashdb.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

SOURCE="${1:-}"
if [ -z "$SOURCE" ]; then
  SOURCE="$(awk -F': ' '/source_project:/ {gsub("\"", "", $2); print $2; exit}' acceptance-plan.yaml)"
fi
if [ -z "$SOURCE" ] || [ ! -d "$SOURCE/src" ]; then
  echo "ERROR: FlashDB source src/ not found. Pass source path explicitly." >&2
  exit 1
fi

mkdir -p reports
SRC_COUNT="$(find "$SOURCE/src" -type f \( -name '*.c' -o -name '*.h' \) | wc -l | tr -d ' ')"
TEST_COUNT="0"
if [ -d "$SOURCE/tests" ]; then
  TEST_COUNT="$(find "$SOURCE/tests" -type f | wc -l | tr -d ' ')"
fi

{
  echo "# FlashDB Source Inventory"
  echo ""
  echo "- Source: \`$SOURCE\`"
  echo "- C/H files under src: $SRC_COUNT"
  echo "- Files under tests: $TEST_COUNT"
  echo ""
  echo "## Source Files"
  echo ""
  find "$SOURCE/src" -type f \( -name '*.c' -o -name '*.h' \) | sort | sed "s#^#- #"
  echo ""
  echo "## Test Files"
  echo ""
  if [ -d "$SOURCE/tests" ]; then
    find "$SOURCE/tests" -type f | sort | sed "s#^#- #"
  else
    echo "- No tests directory found."
  fi
  echo ""
  echo "## Recommended First Slices"
  echo ""
  echo "1. Public constants, result codes, and configuration types."
  echo "2. Flash abstraction traits and in-memory test backend."
  echo "3. KVDB core data model and lookup path."
  echo "4. TSDB record model and append/query path."
  echo "5. Source test cases ported into Rust integration tests."
} > reports/source-inventory.md

echo "Wrote reports/source-inventory.md"
EOF

cat > harness/plan_next_task.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

TASK_ID="${1:-task-001}"
GOAL="${2:-Translate the next smallest FlashDB behavior slice}"
SCOPE="${3:-FlashDB src/tests}"

mkdir -p plans
PLAN="plans/${TASK_ID}.md"

cat > "$PLAN" <<EOF_PLAN
# ${TASK_ID}: ${GOAL}

## Goal

${GOAL}

## Source Scope

${SCOPE}

## Source Evidence

- Fill with exact FlashDB source files, functions, constants, and test cases before implementation.
- No behavior claim may be implemented without source evidence or user confirmation.

## Functional Requirements

| ID | Behavior | Inputs | Outputs | Boundary / Error Cases | Source Evidence |
|---|---|---|---|---|---|
| FR-001 | Define the smallest behavior in this task. | Source-backed input. | Source-backed output. | Include invalid input and boundary case. | Fill before coding. |

## Atomic Implementation Tasks

1. Identify source functions/constants and write evidence bullets above.
2. Add or update Rust types/functions under \`src/\`.
3. Port source-backed tests into \`tests/\`.
4. Run compile/test/unsafe checks.
5. If checks fail, run \`./harness/repair_loop.sh\` and patch from the error stack.

## Test Matrix

- Happy path: required.
- Empty / zero / null-equivalent input: required when applicable.
- Invalid input / error path: required.
- Boundary size or repeated call: required.
- Source regression case: required when source tests exist.

## Verification Commands

\`\`\`bash
cargo fmt
./harness/build_check.sh
./harness/test_all.sh
./harness/unsafe_audit.sh 10
\`\`\`

## Review Gate

- [ ] Source evidence is filled.
- [ ] Every functional requirement has a Rust test.
- [ ] Tests do not use AI-derived expected values.
- [ ] No placeholders remain in completed code.
- [ ] Verification commands ran successfully.
EOF_PLAN

echo "Created $PLAN"
EOF

cat > harness/build_check.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
mkdir -p reports
{
  echo "# Build Check"
  echo ""
  echo "## cargo fmt --check"
  if cargo fmt --version >/dev/null 2>&1; then
    cargo fmt --check
  else
    echo "WARN: rustfmt is not installed; skipping formatting check."
  fi
  echo ""
  echo "## cargo check --all-targets"
  cargo check --all-targets
} 2>&1 | tee reports/build-check.log
EOF

cat > harness/repair_loop.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
mkdir -p reports

set +e
./harness/build_check.sh
CODE=$?
set -e

if [ "$CODE" -eq 0 ]; then
  echo "Build check already passes."
  exit 0
fi

{
  echo "# Compile Repair Request"
  echo ""
  echo "The build failed. Patch from the error stack below; do not rewrite unrelated modules."
  echo ""
  echo "## High-signal errors"
  echo ""
  grep -nE "error(\\[[A-Z0-9]+\\])?:|warning:| --> " reports/build-check.log | tail -80 || true
  echo ""
  echo "## Required OpenCode action"
  echo ""
  echo "1. Read the exact compiler error and file span."
  echo "2. Identify the smallest patch."
  echo "3. Apply the patch."
  echo "4. Re-run ./harness/build_check.sh."
} > reports/repair-request.md

echo "Wrote reports/repair-request.md"
exit "$CODE"
EOF

cat > harness/test_all.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
mkdir -p reports
{
  echo "# Test Report"
  echo ""
  cargo test --all-targets -- --nocapture
} 2>&1 | tee reports/test-report.log
EOF

cat > harness/unsafe_audit.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
THRESHOLD="${1:-10}"
mkdir -p reports

python3 - "$THRESHOLD" <<'PYEOF'
import pathlib
import re
import sys

threshold = float(sys.argv[1])
files = sorted(pathlib.Path("src").rglob("*.rs"))
code_lines = 0
unsafe_hits = 0
details = []

for path in files:
    text = path.read_text()
    local_lines = 0
    local_unsafe = 0
    for line in text.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("//"):
            continue
        local_lines += 1
        local_unsafe += len(re.findall(r"\bunsafe\b", line))
    code_lines += local_lines
    unsafe_hits += local_unsafe
    if local_unsafe:
        details.append((str(path), local_unsafe))

ratio = (unsafe_hits / code_lines * 100.0) if code_lines else 0.0
report = pathlib.Path("reports/unsafe-report.md")
with report.open("w") as f:
    f.write("# Unsafe Audit\n\n")
    f.write(f"- Rust source files: {len(files)}\n")
    f.write(f"- Non-empty production code lines: {code_lines}\n")
    f.write(f"- unsafe keyword hits: {unsafe_hits}\n")
    f.write(f"- unsafe ratio: {ratio:.2f}%\n")
    f.write(f"- threshold: < {threshold:.2f}%\n\n")
    if details:
        f.write("## Files with unsafe\n\n")
        for path, count in details:
            f.write(f"- `{path}`: {count}\n")

print(f"unsafe ratio: {ratio:.2f}% (threshold < {threshold:.2f}%)")
if ratio >= threshold:
    sys.exit(1)
PYEOF
EOF

cat > harness/final_verify.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
mkdir -p reports

SOURCE="$(awk -F': ' '/source_project:/ {gsub("\"", "", $2); print $2; exit}' acceptance-plan.yaml)"
if [ -z "$SOURCE" ] || [ ! -d "$SOURCE/src" ]; then
  echo "ERROR: source_project/src is not available. Check acceptance-plan.yaml." >&2
  exit 1
fi

./harness/analyze_flashdb.sh "$SOURCE" >/dev/null
./harness/build_check.sh
./harness/test_all.sh
./harness/unsafe_audit.sh 10

PLACEHOLDERS="$(grep -RInE 'todo!\\(|unimplemented!\\(|panic!\\("TODO|TODO: fake|placeholder' src tests 2>/dev/null || true)"
if [ -n "$PLACEHOLDERS" ]; then
  {
    echo "# Placeholder Failure"
    echo ""
    echo "$PLACEHOLDERS"
  } > reports/placeholder-failure.md
  echo "ERROR: placeholders found. See reports/placeholder-failure.md" >&2
  exit 1
fi

{
  echo "# Final Verification Report"
  echo ""
  echo "- Source: \`$SOURCE\`"
  echo "- Build: passed"
  echo "- Tests: passed"
  echo "- Unsafe audit: passed"
  echo "- Placeholder audit: passed"
  echo ""
  echo "See:"
  echo "- \`reports/source-inventory.md\`"
  echo "- \`reports/build-check.log\`"
  echo "- \`reports/test-report.log\`"
  echo "- \`reports/unsafe-report.md\`"
} > reports/final-report.md

echo "Final verification passed. Wrote reports/final-report.md"
EOF

cat > plans/task-000-harness-orientation.md <<EOF
# task-000: Harness Orientation

## Goal

Understand the generated FlashDB Rust rewrite harness before implementation.

## Steps

1. Run \`./harness/analyze_flashdb.sh "$SOURCE_PATH"\`.
2. Read \`reports/source-inventory.md\`.
3. Choose the first narrow C-to-Rust slice from \`$SOURCE_PATH/src\`.
4. Generate a concrete task plan:

\`\`\`bash
./harness/plan_next_task.sh task-001 "Translate <specific FlashDB behavior>" "<exact source files>"
\`\`\`

5. Fill source evidence and functional requirements before writing Rust code.
EOF

chmod +x harness/*.sh

echo "FlashDB competition harness initialized at $TARGET_PATH"
echo ""
echo "Next:"
echo "  cd $TARGET_PATH"
echo "  ./harness/analyze_flashdb.sh \"$SOURCE_PATH\""
echo "  ./harness/plan_next_task.sh task-001 \"Translate first FlashDB slice\" \"$SOURCE_PATH/src\""
