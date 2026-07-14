# FlashDB C-to-Rust 转换 - 参赛作品说明

## 1. 作品概述

本作品将 FlashDB 的 C 实现转换为 Rust，并输出可被原始 C 测试程序链接
的 Rust 静态库。转换流程由作品 Skill 驱动，Rust 实现需要通过原始 C
测试用例约束，而不是仅通过围绕 Rust 实现编写的自测。

## 2. 输入

| 输入项 | 说明 |
|--------|------|
| 原始 C 项目 | 含 FlashDB C 源码、头文件和原始 C 测试用例（如 kvdb_main.c、tsdb_main.c）的项目目录 |
| Rust 项目 | 转换后的 Rust 项目，含 Cargo.toml，并能产出供 C 测试链接的静态库 |
| 执行环境 | 能读取本仓库、执行 Shell 命令并加载本作品 Skill 的环境 |

## 3. 执行工作流

### Step 0：加载转换 Skill

在仓库根目录加载并执行：

```text
work/skills/flashdb-rust-autonomous/SKILL.md
```

Skill 名称：flashdb-rust-autonomous

预期输出：进入从 C 源码到 Rust 项目的自动转换流程。

本步产物：`code/flashDB_rust/` 工作目录、转换报告目录和验证脚本。

### Step 1：读取输入并建立翻译基线

执行流程读取 `code/FlashDB` 中的源码、头文件和测试文件，建立模块清单、
结构布局、宏常量、状态编码和 C `TEST_RUN(...)` 测试队列。

预期产物：

- `code/flashDB_rust/reports/source-inventory.md`
- `code/flashDB_rust/reports/layout-probe.md`
- `code/flashDB_rust/reports/c-test-coverage-required.tsv`
- `code/flashDB_rust/reports/c-oracle-traces/`

成功标志：所有原始 C 测试场景被枚举，并能追溯到源码、宏或 C 运行证据。

### Step 2：生成 Rust 项目和测试约束

执行流程创建或更新 `code/flashDB_rust`，写入 Cargo 配置、Rust 模块骨架、
验证脚本，并从 C 测试队列生成 Rust acceptance tests。每个 Rust 测试的
期望值来自 C 源码、C 宏、C 测试或 C 运行证据。

预期产物：

- `code/flashDB_rust/Cargo.toml`
- `code/flashDB_rust/src/`
- `code/flashDB_rust/tests/c_kvdb_cases.rs`
- `code/flashDB_rust/tests/c_tsdb_cases.rs`
- `code/flashDB_rust/tests/layout_oracle.rs`
- `code/flashDB_rust/reports/c-test-coverage.tsv`

成功标志：24 个 C 测试场景均有对应的 Rust acceptance test 和覆盖记录。

### Step 3：按测试驱动翻译 Rust 实现

执行流程按 C 测试队列逐项闭环：

```text
读取 C 测试和依赖源码
-> 写入对应 Rust acceptance test
-> 运行测试并观察失败
-> 实现最小 Rust 行为
-> 重新运行测试
-> 修复失败并更新报告
```

翻译范围包括 FlashDB 的布局、错误码、CRC、状态表、文件后端、KVDB、
TSDB 和 C ABI 兼容层。

预期产物：`code/flashDB_rust/src/` 下完整 Rust 源码，以及持续更新的转换
报告。

成功标志：Rust 单元测试、Rust acceptance tests 和覆盖检查均通过。

### Step 4：编译 Rust 项目

```bash
cd code/flashDB_rust/
RUSTC_BOOTSTRAP=1 cargo build --release
```

预期产物：`code/flashDB_rust/target/release/libflashdb_rust.a`

成功标志：编译无错误，静态库文件存在且非空。

### Step 5：编译 C 测试并链接 Rust 静态库

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

### Step 6：运行 C 测试

```bash
cd code/FlashDB/tests/
rm -rf fdb_kvdb1/ fdb_tsdb1/ storage_* fdb_tsdb1 storage_tsdb
./kvdb_test
./tsdb_test
```

预期输出：KVDB 和 TSDB 测试程序逐项打印测试用例执行结果。

成功标志：原始 C 测试中的 24 个测试场景全部通过。

### Step 7：输出结果摘要

执行流程将最终转换状态、测试结果和关键产物路径写入：

```text
result/output.md
```

预期输出：结果摘要记录转换完成状态、Rust 项目位置、静态库位置、测试通过
情况、覆盖情况和安全审计结果。

成功标志：`result/output.md` 标记转换完成，并列出已通过的构建、测试和
链接验证。

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
| 作品 Skill | `work/skills/flashdb-rust-autonomous/SKILL.md` | Markdown | 执行入口 |
| 结果摘要 | `result/output.md` | Markdown | 汇总转换状态、主要产物和执行结果 |
