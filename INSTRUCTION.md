# C 项目翻译为 Rust：运行入口

## 翻译目标

- **源码**: `code/FlashDB` (C)
- **目标**: `code/flashDB_rust` (Rust)

## 执行方式

加载并执行 Skill：

```text
work/skills/c-to-rust/SKILL.md
```

按 SKILL.md 中的 Phase 0-5 依次执行，不中断，不提问，直到 `final_verify.sh` 通过。

## 核心规则

- 全程自动执行，不询问用户
- 验证不通过则立即修复，持续修复直到通过
- **执行完成后必须将运行结果写入 `result/output.md`**
- 仅在以下情况升级给用户：源码无法编译且无 Oracle 降级、同模块连续 3 Wave 失败、发现源码 bug

## 完成条件

全部满足才算完成：

1. `final_verify.sh` 通过（exit code 0）
2. Rust 测试全部通过
3. unsafe 占比 < 10%
4. **`result/output.md` 已更新执行结果**
