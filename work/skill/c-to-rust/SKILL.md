---
name: c-to-rust
description: Translate the FlashDB C project to Rust. Executes the full migration flow automatically — init, translate, verify, fix — until final_verify.sh passes.
---

# FlashDB C → Rust Migration

This skill translates the FlashDB C project to Rust. The source and target paths are fixed.

## Fixed Paths

- **Source**: `code/FlashDB` (C)
- **Target**: `code/flashDB_rust` (Rust)
- **Project name**: `flashDB_rust`
- **Crate name**: `flashdb_rust` (lowercase snake_case for Cargo)

## Core Rule

**Execute the ENTIRE flow below without stopping. Do NOT ask the user any questions. Do NOT pause between phases. Keep going until `final_verify.sh` passes.**

If a verification step fails, fix it immediately and re-verify. Keep fixing until it passes.

Only escalate to the user if:
1. The source project cannot compile and no Oracle fallback exists
2. The same module fails 3 consecutive Waves
3. A bug is found in the source code itself

## Phase 0: Intake

1. Verify `code/FlashDB` exists and contains `src/`. If not, report the problem and stop.
2. Tell the user what will happen:

   ```text
   我会按 C→Rust 迁移流程处理 FlashDB：

   - 源项目：code/FlashDB
   - Rust 工程：code/flashDB_rust
   - 工程名称：flashDB_rust
   - 迁移范围：src 和 tests
   - 验证方式：Rust 编译、Rust 测试、unsafe 占比检查

   接下来我会自动完成翻译，直到最终验证通过。
   ```

3. Proceed to **Phase 1** immediately.

## Phase 1: Project Initialization

In the target directory, create the following structure. Adjust `<CRATE_NAME>` to the lowercase snake_case version of the project name.

### 1. Create directory structure

```
<target>/
  .cargo/
  src/
  tests/
  harness/
  plans/
  reports/
```

### 2. Cargo.toml

```toml
[package]
name = "<CRATE_NAME>"
version = "0.1.0"
edition = "2021"

[lib]
name = "<CRATE_NAME>"
path = "src/lib.rs"

[[bin]]
name = "<CRATE_NAME>"
path = "src/main.rs"

[dependencies]
thiserror = "2"

[dev-dependencies]
tempfile = "3"
proptest = "1"
```

### 3. src/lib.rs

```rust
//! Rust reimplementation workspace.
//!
//! Replace this module with real behavior as task plans are completed.

pub fn harness_ready() -> bool {
    true
}
```

### 4. src/main.rs

```rust
fn main() {
    println!("<CRATE_NAME> ready");
}
```

### 5. tests/harness_smoke.rs

```rust
#[test]
fn harness_starts_from_a_compiling_crate() {
    assert!(<CRATE_NAME>::harness_ready());
}
```

### 6. .cargo/config.toml

```toml
[build]
rustflags = ["-Dwarnings"]
```

### 7. .gitignore

```
/target
/reports/*.log
/reports/*.tmp
.DS_Store
```

### 8. Harness Scripts

Create these scripts under `harness/`:

**harness/build_check.sh**
```bash
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
```

**harness/test_all.sh**
```bash
#!/usr/bin/env bash
set -euo pipefail
mkdir -p reports
{
  echo "# Test Report"
  echo ""
  cargo test --all-targets -- --nocapture
} 2>&1 | tee reports/test-report.log
```

**harness/unsafe_audit.sh**
```bash
#!/usr/bin/env bash
set -euo pipefail
THRESHOLD="${1:-10}"
mkdir -p reports

python3 - "$THRESHOLD" <<'PYEOF'
import pathlib, re, sys

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
```

**harness/final_verify.sh**
```bash
#!/usr/bin/env bash
set -euo pipefail
mkdir -p reports

./harness/build_check.sh
./harness/test_all.sh
./harness/unsafe_audit.sh 10

PLACEHOLDERS="$(grep -RInE 'todo!\(|unimplemented!\(|panic!\("TODO|TODO: fake|placeholder' src tests 2>/dev/null || true)"
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
  echo "- Build: passed"
  echo "- Tests: passed"
  echo "- Unsafe audit: passed"
  echo "- Placeholder audit: passed"
} > reports/final-report.md

echo "Final verification passed. Wrote reports/final-report.md"
```

After creating all harness scripts, run `chmod +x harness/*.sh`.

### 9. Initialize git and verify

```bash
cd <target> && git init
cargo check --all-targets
cargo test
```

Verification must pass. If it fails, fix it before proceeding.

## Phase 2: Source Analysis

1. Read the C source directory structure under `<source>/src/`.
2. Identify all `.c` and `.h` files.
3. Determine module dependencies: which files include which headers.
4. Produce a topological sort: translate leaf modules (no internal deps) first.
5. Write a brief `reports/source-inventory.md` listing source files, their sizes, and recommended translation order.
6. Try to compile the C source project. If it compiles, note that C Oracle is available for differential testing.

Proceed to **Phase 3** immediately.

## Phase 3: Wave Translation Loop

Repeat the following until ALL C source modules have been translated to Rust:

### Wave Planning

1. Pick the next 3-5 leaf modules (dependencies already translated or no dependencies).
2. Write a brief wave plan to `plans/wave-NNN.md` listing the modules and expected deliverables.

### Module Translation (for each module in the wave)

1. **Read the C source file** thoroughly. Understand every function, constant, type, and macro.
2. **Translate types and constants** first. Map C structs/enums/defines to Rust types/consts.
3. **Translate function signatures**. Apply C→Rust mapping rules:
   - `malloc/free` → `Box`/`Vec`/`Arc`
   - `*T` (owned) → `Box<T>`
   - `*T` (borrowed) → `&T`/`&mut T`
   - `*T` (nullable) → `Option<&T>`
   - `#define CONST` → `const`/`static`
   - `#define MACRO(x)` → `macro_rules!` or inline function
   - `#ifdef` → `#[cfg(...)]`
   - `int cmd + void* arg` → Rust enum
   - `fn pointer + void*` → `&mut dyn FnMut`
   - `static char buffer` → `String`/`Vec<u8>`
4. **Translate function bodies**. Preserve behavior, not API shape.
5. **Port C tests** to Rust. Use `#[test]` + `cargo test`. Rules:
   - Test counters: use `thread_local! { Cell<T> }` instead of `static mut`
   - GC test values: compute from C macros, not round numbers
   - Cover happy path, boundary, error, and regression cases
6. **Verify immediately**:
   ```bash
   cargo fmt
   cargo check --all-targets
   cargo test
   ```
   If any command fails, read the error, fix precisely, and re-verify. Max 3 fix rounds per module. If still failing, narrow the translation scope and retry.

### Wave Verification

After all modules in the wave are translated:

1. Run:
   ```bash
   cargo fmt
   cargo check --all-targets
   cargo test --all-targets
   ./harness/unsafe_audit.sh 10
   ```
2. Check for placeholders:
   ```bash
   grep -RInE 'todo!\(|unimplemented!\(|panic!\("TODO|placeholder' src tests
   ```
   If any found, replace with real implementation.
3. Compare C test list against Rust test list. Fill any coverage gaps.
4. If this is Wave 1: build C Oracle programs for differential testing (see Phase 4).

If verification fails, fix and re-verify until it passes. Then proceed to the next wave.

## Phase 4: C Oracle Differential Testing (after Wave 1)

If the C source compiles, build C Oracle programs to verify behavioral equivalence:

1. Write small C programs that exercise key behaviors (basic CRUD, GC, multi-sector, reboot persistence).
2. Each program outputs results to stdout in a parseable format (JSONL or key=value).
3. Build them: `gcc -I<source>/inc <source>/src/*.c oracle_<test>.c -o oracle/oracle_<test>`
4. Write Rust differential tests that:
   - Run the C Oracle program, parse its output
   - Replay the same operations in Rust
   - Compare results
   - Mark with `#[ignore]`, run with `cargo test -- --ignored`
5. All differential tests must pass. If any fails, investigate the behavioral difference and fix the Rust implementation.

## Phase 5: Final Verification

After ALL modules are translated and ALL waves pass:

1. Run:
   ```bash
   ./harness/final_verify.sh
   ```
2. Run all differential tests:
   ```bash
   cargo test --test diff_* -- --ignored
   ```
3. Add rustdoc to all public APIs.
4. Update README.md with project documentation.

**If `final_verify.sh` fails, fix the failure and re-run. Keep going until it passes.**

## Summary: The Loop

```
Phase 0 (Intake)
  → Phase 1 (Init project)
    → Phase 2 (Analyze source)
      → Phase 3 (Wave loop: translate → verify → fix → next wave)
        → Phase 4 (C Oracle diff tests, after Wave 1)
          → Phase 5 (Final verify)
```

**DO NOT STOP between phases. DO NOT ask the user questions. Keep executing until `final_verify.sh` passes.**
