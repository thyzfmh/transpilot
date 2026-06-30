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
- 工程名称：默认 `<源码目录名>_rust`，例如 `FlashDB` 默认生成 `FlashDB_rust`

## 执行方式

加载并执行 Skill：

```text
work/skill/c-to-rust/SKILL.md
```

该 Skill 包含完整的初始化步骤和验证流程，无需依赖外部脚本。

## 初始化后的用户说明

初始化完成后，告诉用户：

```text
我已经生成 Rust 迁移工程，里面包含：
- Rust 项目结构
- 构建和测试脚本
- 编译错误修复流程
- unsafe 检查
- 最终验证报告

下一步会先分析源码结构，再生成第一批迁移任务，然后逐步实现和验证。
```

## 生成工程后的验证命令

进入生成的 Rust 工程目录后运行：

```bash
./harness/build_check.sh
./harness/test_all.sh
./harness/unsafe_audit.sh 10
./harness/final_verify.sh
```

验证不通过则持续修复直到全部通过。
