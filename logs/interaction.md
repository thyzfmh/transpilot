# 人工交互记录

## 翻译目标

- **源码目录**: `/Users/tanghui/code/FlashDB` (C)
- **目标目录**: `/Users/tanghui/code/FlashDB_rust` (Rust)
- **源码项目**: FlashDB — 嵌入式 Flash 数据库，支持 KVDB 和 TSDB 两种模式
- **翻译方向**: C → Rust

## 交互时间线

### T0: 项目初始化

用户要求按照平台交付目录整理作品，并希望自然语言入口为"帮我把 /xx/xx 翻译成 Rust"这类表达。

本次整理中没有额外要求用户提供新的源码目录；交付件以通用 C→Rust 迁移初始化能力为入口。

### T1: FlashDB 翻译执行

用户指定源码目录 `/Users/tanghui/code/FlashDB`，要求翻译为 Rust。

- Wave 1: types.rs, config.rs, lowlevel.rs, utils.rs, flash.rs, lib.rs — 53 tests
- Wave 2: kvdb.rs (1909 lines) — 71 total tests
- Wave 3: tsdb.rs (1558 lines) — 107 total tests, 0.12% unsafe
- 修复 `static mut` → `thread_local! { Cell<i32> }` 并行测试竞争
- 添加 rustdoc 到所有公开 API (8 doctests)
- 构建 4 个 C Oracle 程序用于差分测试
- 4 个差分测试全部通过 vs C Oracle
- final_verify.sh 通过

### T2: 竞赛交付整理

用户指出 result/output.md 和 logs/ 缺失，竞赛交付不完整。

- 生成 result/output.md 包含完整运行输出
- 生成 logs/ 目录包含执行日志
- 晶炼 8 条教训到 lessons-flashdb.md (L-001 to L-008)
- 添加 5 个反模式到 anti-patterns.md (AP-007 to AP-011)
- 更新 c2rust/SKILL.md、shared/SKILL.md、translator/SKILL.md
- 验证 init-c-to-rust-project.sh 在干净 /tmp/ 环境中工作

### T3: 提交与推送

用户要求提交代码。7 个原子 commit 提交到 FlashDB_rust 本地仓库。

用户要求创建 GitHub 私有仓库推送整个 transpilot 目录（非仅 FlashDB_rust），命名为 competition。

- 创建私有仓库 github.com/thyzfmh/competition
- 推送 main + competition-flashdb-harness 分支

### T4: 日志整理

用户要求 logs/ 也需提交：
- logs/interaction.md 记录用户与 OpenCode 的交互记录
- logs/trace/ 存放推理过程日志（.gitignore 排除）
- 翻译源目录固定为 code/FlashDB → Rust

## 关键决策记录

| 决策 | 选择 | 理由 |
|------|------|------|
| FlashBackend 抽象 | `KvDb<F: FlashBackend>` 泛型 | 可测试性：Mock vs Real 双实现 |
| C 的 int cmd + void* arg | `KvControlArg`/`TslControlArg` 枚举 | 类型安全，消除裸指针 |
| kv_get 返回值 | `Option<String>` | 消除 C 的静态 buffer |
| 回调机制 | `&mut dyn FnMut` 闭包 | 替代 C 的 fn pointer + void* |
| 测试计数器 | `thread_local! { Cell<i32> }` | `static mut` 导致并行测试竞争 |
| 差分测试 Oracle | C 源项目编译运行 | AI 不写预期值，Oracle 独立 |
| GC 测试数据 | 从 C 宏计算大小 | 不用整数凑数 (AP-010) |
