# FlashDB C-to-Rust 转换 - 参赛作品说明

## 1. 作品概述

本作品提供一个 OpenCode Skill，用于将 FlashDB 的 C 实现转换为 Rust
项目。执行流程由 Skill 自动完成，包括读取原始 C 源码和测试、生成
C-derived Rust acceptance tests、实现 Rust 行为、记录过程产物，并输出
转换后的 Rust 项目。

## 2. 输入

| 输入项 | 说明 |
|--------|------|
| 原始 C 项目 | 含 FlashDB C 源码、头文件和原始 C 测试用例的项目目录 |
| 执行代理 | 能读取本仓库并执行本作品 Skill 的 OpenCode 环境 |
| 可写工作区 | 用于生成 Rust 项目、测试、报告、日志和结果摘要 |

## 3. 执行工作流

### Step 1：加载作品 Skill

在仓库根目录中让 OpenCode 加载并执行：

```text
work/skills/flashdb-rust-autonomous/SKILL.md
```

Skill 名称：flashdb-rust-autonomous

预期输出：OpenCode 进入自动转换流程，开始读取原始 C 项目并创建或更新
Rust 项目。

本步产物：执行过程记录写入 `logs/`，中间报告写入 Rust 项目的 `reports/`
目录。

### Step 2：生成 C-derived acceptance tests

Skill 会从原始 C 测试中提取测试队列，并先生成对应的 Rust acceptance
tests。每个 Rust acceptance test 的期望值来自 C 源码、C 宏、C 测试或 C
运行证据，而不是来自当前 Rust 实现。

预期输出：每个原始 C 测试场景都有对应的 Rust acceptance test 和覆盖记录。

本步产物：Rust 测试文件、C 测试覆盖表和 oracle 证据报告。

### Step 3：执行转换和修复循环

Skill 会按测试队列逐项实现 Rust 行为。每个切片遵循：

```text
写入 C-derived Rust test -> 运行并观察失败 -> 实现最小 Rust 行为 -> 重新运行测试
```

预期输出：Rust 项目持续补齐 FlashDB KVDB、TSDB、存储布局、状态迁移、
GC、扩容、删除、时间序列迭代等行为。

本步产物：转换后的 Rust 源码、Rust 测试、过程报告和进度记录。

### Step 4：写入结果摘要

当 Skill 完成转换流程后，更新结果摘要文件。

预期输出：结果摘要记录转换状态、产物位置和执行记录位置。

本步产物：`result/output.md`。

## 4. 产物清单

| 产物 | 位置 | 格式 | 用途 |
|------|------|------|------|
| 作品 Skill | `work/skills/flashdb-rust-autonomous/SKILL.md` | Markdown | OpenCode 执行入口，定义自动转换流程 |
| 转换后的 Rust 项目 | `code/flashDB_rust/` | Cargo 项目目录 | Scorer 读取和执行的 Rust 转换结果 |
| Rust acceptance tests | `code/flashDB_rust/tests/` | Rust 测试源码 | 约束 Rust 行为与原始 C 测试场景一致 |
| C 测试覆盖表 | `code/flashDB_rust/reports/c-test-coverage.tsv` | TSV | 记录 C 测试场景到 Rust acceptance test 的映射 |
| Oracle 证据 | `code/flashDB_rust/reports/c-oracle-traces/` | 多文件 | 保存 C 源码、宏、运行输出或探针得到的期望值证据 |
| 转换报告 | `code/flashDB_rust/reports/` | Markdown/TSV | 记录源码盘点、布局探针、进度和覆盖结果 |
| 执行日志 | `logs/` | 多文件 | 记录 OpenCode 执行过程 |
| 结果摘要 | `result/output.md` | Markdown | 汇总转换状态、主要产物和执行结果 |
