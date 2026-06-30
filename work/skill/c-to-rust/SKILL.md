---
name: c-to-rust
description: Use when the user asks to translate, rewrite, migrate, port, or reimplement a C/C++ project or source directory into Rust, especially when they provide a source path and want a Rust target project, tests, compile repair workflow, unsafe audit, or OpenCode execution flow.
---

# C to Rust Migration

Use this skill when the user says something like:

- `帮我把 /path/to/project 翻译成 Rust`
- `把这个 C 项目用 Rust 重写`
- `迁移 /path/to/source 到 Rust`

## User-facing principles

- Do not mention competition, pinned commit, harness, profile, Wave, Oracle, or hallucination metrics.
- Treat the provided source directory as the migration baseline.
- Ask only for missing required information.
- If output directory or project name is missing, choose safe defaults and tell the user.

## Defaults

Given source path `/a/b/FlashDB`:

- target path: `/a/b/FlashDB_rust`
- project name: `FlashDB_rust`
- crate name: `flashdb_rust` (lowercase snake_case for Cargo)
- migration scope: `src/` and `tests/`
- validation: Rust build, Rust tests, unsafe ratio under 10%

## Intake flow

1. Extract the source path from the user's request.
2. If no source path is present, ask: `请告诉我要翻译的源码目录。`
3. If source path does not exist or has no `src/`, report the concrete problem.
4. Derive target path and project name from defaults unless user provided them.
5. Tell the user what will happen in plain language:

   ```text
   我会按 C→Rust 迁移流程处理这个项目：

   - 源项目：<source>
   - Rust 工程：<target>
   - 工程名称：<name>
   - 默认迁移范围：src 和 tests
   - 验证方式：Rust 编译、Rust 测试、unsafe 占比检查

   接下来我会先初始化 Rust 工程，不会立即改写源码。
   ```

6. Initialize the Rust project by following the steps in **Project Initialization** below.
7. After initialization, run the verification commands in **Quick Verification**.
8. Report the generated path and next action:

   ```text
   已生成 Rust 迁移工程：<target>

   下一步我会分析源码结构，生成第一批迁移任务，然后逐步实现和验证。
   ```

## Project Initialization

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

### 8. Initialize git

```bash
cd <target> && git init
```

## Harness Scripts

Create these scripts under `harness/` in the target project. They are short shell scripts that wrap standard cargo commands.

### harness/build_check.sh

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

### harness/test_all.sh

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

### harness/unsafe_audit.sh

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

### harness/final_verify.sh

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

## Quick Verification

After initialization, verify the project compiles and the smoke test passes:

```bash
cargo check --all-targets
cargo test
```

## Execution rule

Never claim success without running the verification commands. If a command fails, summarize the exact failure and fix it. Keep fixing until all verifications pass.
