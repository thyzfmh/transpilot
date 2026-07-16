# 执行入口

请加载并执行以下 Skill 文件：

```text
work/skills/flashdb-rust-autonomous/SKILL.md
```

Skill 名称：flashdb-rust-autonomous

执行规则：

- 禁止使用 subagent 或 task agent
- 源项目固定为 `code/FlashDB`
- Rust 目标固定为 `code/flashDB_rust`
- 不询问用户，不中断执行
- 失败就按 Skill 内的循环修复并重新验证
- 不执行 Git 提交、推送或工作区清理
- 完整交互记录和验证日志输出到 `logs/trace`
- 直到 `work/skills/flashdb-rust-autonomous/scripts/final_verify_target.sh` 通过
- 最后必须更新 `result/output.md`
