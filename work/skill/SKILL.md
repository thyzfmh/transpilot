---
name: c-to-rust-migration-intake
description: Use when the user asks to translate, rewrite, migrate, port, or reimplement a C/C++ project or source directory into Rust, especially when they provide a source path and want a Rust target project, tests, compile repair workflow, unsafe audit, or OpenCode execution flow.
---

# C to Rust Migration Intake

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
- project name: `flashdb_rust`
- migration scope: `src/` and `tests/`
- validation: Rust build, Rust tests, unsafe ratio under 10%

Normalize the Rust crate name to lowercase snake_case.

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

   接下来我会先初始化 Rust 工程和执行脚本，不会立即改写源码。
   ```

6. Run the deterministic initializer from the repository root:

   ```bash
   bash work/scripts/init-c-to-rust-project.sh "<source>" "<target>" "<project_name>"
   ```

7. After initialization, run a quick self-check inside the generated project:

   ```bash
   ./harness/analyze_flashdb.sh "<source>"
   ./harness/build_check.sh
   ./harness/test_all.sh
   ./harness/unsafe_audit.sh 10
   ```

8. Report the generated path and next action:

   ```text
   已生成 Rust 迁移工程：<target>

   下一步我会分析源码结构，生成第一批迁移任务，然后逐步实现和验证。
   ```

## Execution rule

Never claim success without running the verification commands. If a command fails, summarize the exact failing command and point OpenCode to the generated report under `reports/`.

