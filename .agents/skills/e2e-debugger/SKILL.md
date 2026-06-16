---
name: e2e-debugger
description: E2E 测试失败时的自动诊断器 — 定位失败根因到具体模块/函数
---

# E2E 诊断器

## 何时使用
- E2E 测试失败时自动触发
- 集成测试报错但原因不明
- 需要二分定位问题模块

## 诊断流程
```
失败 → 缩小范围(二分) → 定位模块 → 定位函数 → 修复建议
```

## 工具链
- `codegraph_explore` — 追踪调用路径
- `cargo test -- <specific>` — 隔离验证
- 对比源/目标行为差异

## 关键规则
- 先隔离再修复（不盲猜）
- 修复后重跑完整 E2E（防回归）
- 记录失败模式到 anti-patterns

## 详细参考
- 完整诊断决策树 → `reference.md`
- E2E 框架 → `../shared/e2e-validator.md`
