---
name: differential-tester
description: Oracle 独立的差分测试器 — 当需要验证译码行为时，禁止 AI 自己写预期值，必须用源项目运行结果做 Oracle
prerequisites:
  - 源项目可编译运行（首选 Oracle）
  - 或：CodeGraph 已索引（fallback 静态 Oracle）
---

# 差分测试器

## 何时使用
- 单测覆盖不足，但源项目能跑
- 翻译完成后需要"行为对齐"验证（非签名对齐）
- parity-checker 拿不到现成测试用例时

## 不用于
- 源项目跑不起来（→ 改用静态对照 + 双 AI）
- 性能基准（→ 用 bench，不是 diff）

## Oracle 选择决策树
- 源项目能跑 + 函数纯净 → **run-source**（首选）
- 源项目能跑 + 涉及 I/O → **record-replay**（录回放）
- 源项目跑不起来 → **static-codegraph**（签名/调用图对照）
- 以上都不行 → 升级人类（不要自己编预期值）

## 5 条铁律
1. **禁止硬编码预期值** — `assert_eq!(result, "literal")` 一律拒绝
2. **预期值必须来自 src_run()** — 同一输入同时喂源/译，diff 断言
3. **AI 只写输入生成器** — 不写预期；input 可随机/property
4. **跑测试 AI 与写代码 AI 隔离** — 双 AI 模式，tester 看不到译码
5. **Oracle 缺失即升级** — 不允许 fallback 到"AI 直觉"

## 详细参考
- 4 种 Oracle 模式与代码模板 → `reference.md`
