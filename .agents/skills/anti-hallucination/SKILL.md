---
name: anti-hallucination
description: 翻译过程中的幻觉防御网 — 当 AI 即将基于"印象"而非"证据"做断言时强制核验，特别是引用源码行为/目标语言 API/常量值/调用关系时
prerequisites:
  - codegraph 已索引源/目标项目
  - 目标语言文档可访问（cargo doc / docs.rs）
---

# Anti-Hallucination 翻译核验器

## 何时使用
- 翻译任何**非平凡函数**前（叶子工具函数除外）
- 引用源码行为、常量、API、调用关系前
- parity-checker 报 100% 但你不放心时（深度核验）

## 不用于
- 单纯重命名/格式化
- 已有 codegraph 直接返回的代码搬运

## 核验决策树
- "我说的源码行为对吗？" → `codegraph_node` 取原文 + 5 问检查
- "我用的目标 API 存在吗？" → 写最小 cargo check 片段或查 docs.rs
- "这个常量是不是对的？" → grep 源码 + 行号引用
- "调用方向对吗？" → `codegraph_callers` 双向核对

## 5 条铁律
1. **无证据不断言** — 任何"源码这样写"必带 codegraph_node 行号
2. **未见过的 API 必先 check** — cargo check 通过才允许写进翻译
3. **常量必引用** — 端口/超时/重试次数零容忍臆测
4. **调用方双向核对** — 翻译前查源、翻译后查译，数量必须一致
5. **想得出反例 → 测试不够** — 想不出说明覆盖未到边界

## 详细参考
- 5 类幻觉与对治 → `reference.md`
- 函数级强制清单 → `checklist.md`
