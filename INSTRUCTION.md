# C 项目翻译为 Rust：运行入口

## 作品目标

当用户提出类似下面的需求时，启动本作品：

```text
帮我把 /path/to/source 翻译成 Rust
把 /path/to/project 用 Rust 重写
迁移这个 C 项目到 Rust
```

本作品会先初始化一个 Rust 迁移工程，并生成后续执行所需的脚本、任务计划、验证命令和报告目录。源码目录本身即为迁移基准，不再额外询问 commit 或比赛信息。

## 输入信息

如果用户已经给出源码目录，只需要继续确认缺失的必要信息：

- 源码目录：用户提供的 C 项目目录，目录内应包含 `src/`
- Rust 工程目录：默认 `<源码目录>_rust`
- 工程名称：默认 `<源码目录名>_rust`，例如 `FlashDB` 默认生成 `flashdb_rust`

## 推荐执行方式

优先加载并执行 Skill：

```text
work/skill/SKILL.md
```

如果平台不支持 Skill，可直接执行脚本：

```bash
bash work/scripts/init-c-to-rust-project.sh <source_path> <target_path> [project_name]
```

示例：

```bash
bash work/scripts/init-c-to-rust-project.sh ./code/FlashDB ./flashdb_rust flashdb_rust
```

## 初始化后的用户说明

初始化完成后，告诉用户：

```text
我已经生成 Rust 迁移工程，里面包含：
- Rust 项目结构
- 源码分析脚本
- 构建和测试脚本
- 编译错误修复流程
- unsafe 检查
- 最终验证报告

下一步会先分析源码结构，再生成第一批迁移任务，然后逐步实现和验证。
```

## 生成工程后的验证命令

进入生成的 Rust 工程目录后运行：

```bash
./harness/analyze_flashdb.sh <source_path>
./harness/plan_next_task.sh task-001 "Translate the first C-to-Rust source slice" "<source_path>/src"
./harness/build_check.sh
./harness/test_all.sh
./harness/unsafe_audit.sh 10
./harness/final_verify.sh
```

如果编译失败，运行：

```bash
./harness/repair_loop.sh
```

然后让 OpenCode 根据 `reports/repair-request.md` 中的 error stack 精准打补丁。
