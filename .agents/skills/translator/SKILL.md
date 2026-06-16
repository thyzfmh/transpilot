---
name: translator
description: 统一翻译驱动器 — 检测源语言，加载技能，驱动完整翻译流程
prerequisites:
  - codegraph-navigator (CodeGraph 已安装并索引)
  - anti-hallucination (非平凡函数翻译前必过 5 问)
  - 索引新鲜度 (scripts/check-codegraph-freshness.sh 通过)
---

# 翻译驱动器

## 何时使用
- 开始翻译新组件/模块
- 恢复翻译会话（读 translation-state.jsonc 续上）

## 核心原则
1. **CodeGraph First** — 探索代码用图查询，不暴力 grep
2. **无证据不断言** — 每个非平凡函数过 anti-hallucination 5 问
3. **Wave 模式** — 3-5 模块/批，叶子优先
4. **零占位符** — Wave 结束时 `forbid-placeholders.sh` 必须通过

## 三层核验（防幻觉）
- **源头层** — 未见过的目标 API 必先 cargo check 最小示例
- **双向层** — 翻译前/后各跑一次 codegraph_callers，调用方数对齐
- **差分层** — parity 100% 不够，必须想出反例或跑 property test

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
