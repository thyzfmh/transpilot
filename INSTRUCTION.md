# OpenCode 执行入口

请 OpenCode 加载以下 Skill 文件：

```text
work/skills/flashdb-rust-autonomous/SKILL.md
```

Skill 名称：flashdb-rust-autonomous

执行规则：

- 源项目固定为 `code/FlashDB`
- Rust 目标固定为 `code/flashDB_rust`
- 不询问用户，不中断执行
- 失败就按 Skill 内的循环修复并重新验证
- 直到 `code/flashDB_rust/harness/final_verify.sh` 通过
- 最后必须更新 `result/output.md`
