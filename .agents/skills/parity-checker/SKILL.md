---
name: parity-checker
description: 四层等价性验证 — 确认翻译后代码与源代码行为一致
---

# 等价性验证器

## 何时使用
- Wave 翻译完成后验证
- 接口变更后快速检查
- 最终验收前全量验证

## 四层检查
| 层级 | 检查内容 | 工具 |
|------|---------|------|
| 结构 | API 签名匹配 | `codegraph_explore` 对比 |
| 功能 | 单元测试通过 | `cargo test` |
| 接口 | 调用方兼容 | `codegraph_callers` |
| 行为 | E2E 输出一致 | 对比测试 |

## 关键规则
- parity ≥ 95% 才算通过
- 结构层失败 → 立即修复（阻塞后续）
- 行为层差异 → 记录到 decisions.md

## 详细参考
- 完整验证流程 → `reference.md`
- 共享验证协议 → `../shared/parity-checker.md`
