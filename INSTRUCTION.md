# C 项目翻译为 Rust：运行入口

## 翻译目标

- **源码**: `code/FlashDB` (C)
- **目标**: `code/flashDB_rust` (Rust)

## 执行方式

加载并执行 Skill：

```text
work/skills/c-to-rust/SKILL.md
```

该 Skill 包含从项目初始化到最终验证的完整自主流程。源码路径和目标路径已固定，加载后按步骤执行，不中断，不提问，直到 `final_verify.sh` 通过。

## 核心规则

- 全程自动执行，不询问用户
- 验证不通过则立即修复，持续修复直到通过
- 仅在以下情况升级给用户：源码无法编译且无 Oracle 降级、同模块连续 3 Wave 失败、发现源码 bug
