---
name: status-dashboard
description: 翻译进度仪表盘 — 生成组件级进度报告和风险预警
---

# 进度仪表盘

## 何时使用
- 查看翻译整体进度
- 生成进度报告
- 识别风险和瓶颈

## 数据源
- `translation-state.jsonc` — 模块状态和 parity 分数
- `decisions.md` — 决策数量和类型
- `openspec/changes/` — 活跃提案数

## 输出格式
```
组件 A: ████████░░ 80% (Wave 4/5, parity 96%)
组件 B: ███░░░░░░░ 30% (Wave 2/4, blocker: 外部依赖)
```

## 关键规则
- 只读取状态文件，不修改
- 风险标记：parity < 85% 或 blocker 未解决 > 3 天

## 详细参考
- 完整报告模板 → `reference.md`
