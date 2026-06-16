---
name: codegraph-navigator
description: 基于 CodeGraph 知识图谱的翻译导航器 — 用预索引图替代暴力搜索，减少 ~50% token
prerequisites:
  - codegraph CLI 已安装且对源/目标项目执行了 `codegraph init`
---

# CodeGraph 翻译导航器

## 何时使用
- 翻译任何代码前需要理解上下文
- 确定模块翻译顺序（依赖图）
- 验证翻译完整性（调用方覆盖）

## 工具选择（决策树）
- "X 怎么工作？" → `codegraph_explore`（首选，一次到位）
- "谁调用了 X？" → `codegraph_callers`
- "X 完整源码" → `codegraph_node`
- "查找符号" → `codegraph_search`
- 以上不适用 → 退回 grep/Read

## 关键规则
1. **CodeGraph First** — 任何代码探索优先用图查询
2. **信任结果** — 不要对返回的源码再 Read 一次
3. **翻译前必查** — 非叶子函数先 `codegraph_callers`
4. **两侧对照** — 翻译后在目标项目运行相同查询验证

## 详细参考
- 查询策略与示例 → `reference.md`
- 安装配置 → `docs/codegraph-integration.md`
