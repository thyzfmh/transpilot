# FlashDB C-to-Rust 转换 - 参赛作品说明

## 1. 作品概述

本作品将 FlashDB 的 C 实现转换为 Rust，并输出可被原始 C 测试程序链接
的 Rust 静态库。转换流程由 OpenCode Skill 驱动，Rust 实现需要通过原始
C 测试用例约束，而不是仅通过围绕 Rust 实现编写的自测。

## 2. 输入

| 输入项 | 说明 |
|--------|------|
| 原始 C 项目 | 含 FlashDB C 源码、头文件和原始 C 测试用例（如 kvdb_main.c、tsdb_main.c）的项目目录 |
| Rust 项目 | 转换后的 Rust 项目，含 Cargo.toml，并能产出供 C 测试链接的静态库 |
| 执行代理 | 能读取本仓库并执行本作品 Skill 的 OpenCode 环境 |

## 3. 执行工作流

### Step 0：生成或更新 Rust 项目

在仓库根目录中让 OpenCode 加载并执行：

```text
work/skills/flashdb-rust-autonomous/SKILL.md
```

Skill 名称：flashdb-rust-autonomous

预期输出：OpenCode 读取原始 C 项目，生成或更新转换后的 Rust 项目。

本步产物：转换后的 Rust 项目、转换过程报告和结果摘要。

### Step 1：编译 Rust 项目

```bash
cd code/flashDB_rust/
RUSTC_BOOTSTRAP=1 cargo build --release
```

预期产物：`code/flashDB_rust/target/release/libflashdb_rust.a`

成功标志：编译无错误，静态库文件存在且非空。

### Step 2：编译 C 测试并链接 Rust 静态库

```bash
cd code/FlashDB/tests/
gcc -c kvdb_main.c -I. -I../inc -I../src -o kvdb_main.o
gcc -c tsdb_main.c -I. -I../inc -I../src -o tsdb_main.o
gcc -o kvdb_test kvdb_main.o -L../../flashDB_rust/target/release -lflashdb_rust -lpthread -ldl -lm
gcc -o tsdb_test tsdb_main.o -L../../flashDB_rust/target/release -lflashdb_rust -lpthread -ldl -lm
```

预期产物：`code/FlashDB/tests/kvdb_test`、`code/FlashDB/tests/tsdb_test`
可执行文件。

成功标志：C 测试程序链接无错误。

### Step 3：运行 C 测试

```bash
cd code/FlashDB/tests/
rm -rf fdb_kvdb1/ fdb_tsdb1/ storage_* fdb_tsdb1 storage_tsdb
./kvdb_test
./tsdb_test
```

预期输出：KVDB 和 TSDB 测试程序逐项打印测试用例执行结果。

成功标志：原始 C 测试中的 24 个测试场景全部通过。

## 4. 产物清单

| 产物 | 位置 | 格式 | 用途 |
|------|------|------|------|
| Rust 静态库 | `code/flashDB_rust/target/release/libflashdb_rust.a` | 静态库 | 供原始 C 测试程序链接 |
| 转换后的 Rust 项目 | `code/flashDB_rust/` | Cargo 项目目录 | Scorer 编译 Rust 静态库的主目标 |
| C 测试可执行文件 | `code/FlashDB/tests/kvdb_test`、`code/FlashDB/tests/tsdb_test` | 二进制 | 执行原始 C 测试场景 |
| Rust acceptance tests | `code/flashDB_rust/tests/` | Rust 测试源码 | 用 C-derived 测试约束 Rust 行为 |
| C 测试覆盖表 | `code/flashDB_rust/reports/c-test-coverage.tsv` | TSV | 记录 C 测试场景到 Rust acceptance test 的映射 |
| Oracle 证据 | `code/flashDB_rust/reports/c-oracle-traces/` | 多文件 | 保存 C 源码、宏、运行输出或探针得到的期望值证据 |
| 转换报告 | `code/flashDB_rust/reports/` | Markdown/TSV | 记录转换方案、源码盘点、布局探针、进度和覆盖结果 |
| 作品 Skill | `work/skills/flashdb-rust-autonomous/SKILL.md` | Markdown | OpenCode 执行入口 |
| 结果摘要 | `result/output.md` | Markdown | 汇总转换状态、主要产物和执行结果 |
