---
name: translator
description: 统一翻译驱动器 — 检测源语言，加载技能，驱动完整翻译流程
prerequisites:
  - codegraph-navigator (CodeGraph 已安装并索引)
---

# 翻译驱动器

## 何时使用
- 开始翻译新组件/模块
- 恢复翻译会话（读 translation-state.jsonc 续上）

## 核心原则
1. **CodeGraph First** — 探索代码用图查询，不暴力 grep
2. **准确性 > 效率** — 理解完再翻译，不猜不蒙
3. **Wave 模式** — 3-5 模块/批，叶子优先
4. **零占位符** — Wave 结束时 `todo!()` 归零

## 支持的源语言
| 语言 | 技能 | 检测方式 |
|------|------|---------|
| Go | `go2rust` | `go.mod` / `*.go` |
| C | `c2rust` | `Makefile` / `CMakeLists.txt` / `*.c` |

## 工作流（简版）
```
分析 → 初始化 → [Wave: 翻译→验证→归档] × N → 完成
```

## 升级触发器（仅以下情况问人类）
- 设计决策歧义（2+ 等价译法，影响公开 API）
- 反复 3 次 parity < 80%
- 外部依赖缺失
- 源代码本身有 bug

## 详细参考
- 完整工作流状态机 → `workflow.md`
- 详细前置条件与规则 → `reference.md`
