---
name: self-improving-translator
description: 从翻译经验中自动学习模式，积累到语义记忆库，持续提升翻译准确性
triggers:
  - 翻译会话结束时自动触发
  - 翻译错误被修正后触发
  - 新模式被发现时手动触发
---

# 自我改进系统

## 三层记忆
- **语义记忆** (`memory/semantic-patterns.json`) — 可复用的翻译模式
- **情节记忆** (`memory/episodes/`) — 具体翻译会话的经验
- **工作记忆** — 当前会话中临时积累的模式

## 自动触发点
| Hook | 时机 | 动作 |
|------|------|------|
| `pre-translate.sh` | 翻译前 | 加载相关模式到工作记忆 |
| `post-translate.sh` | 翻译后 | 提取新模式候选 |
| `post-fix.sh` | 修正后 | 记录纠正模式（高优先级） |
| `session-end.sh` | 会话结束 | 合并工作记忆→语义记忆 |

## 关键规则
1. 纠正模式 confidence 直接设为 0.9（已验证）
2. 新发现模式初始 confidence = 0.5，使用 3 次后提升
3. 模式冲突时：新 > 旧，纠正 > 发现

## 详细参考
- 完整架构与流程 → `reference.md`
- 模式模板 → `templates/pattern-template.md`
- 纠正模板 → `templates/correction-template.md`
