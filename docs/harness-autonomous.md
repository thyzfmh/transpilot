# Harness 自驱指南：让 AI 端到端完成翻译

> 目标读者：希望最少人工介入、让 AI 自主推进数十个 Wave 的项目负责人
> 核心理念：**目标定一次，交付看一次，中间全自动**

---

## 1. 什么是 Harness 模式

传统对话式：每个 Wave 都来问"接下来做什么？"——人类成了瓶颈。

Harness 模式：把 AI 当成一个有**自检能力**和**升级触发器**的子进程，
- 输入：一份目标 + 一份预算
- 输出：一份验收报告
- 中间过程：AI 自己写代码、自己跑 parity、自己开 OpenSpec 提案、自己 commit
- **只在 4 种情况升级到人类**

---

## 2. 三层闭环设计

让 AI 自驱的关键不是"prompt 写得多详细"，而是给它**三层闭环**：

### 第一层：自验证闭环（每个 Wave 内）
AI 自己产出，自己验证，自己修复。

```
翻译模块 → cargo build → cargo test → parity 工具 → 通过？
                                                 ├─ 是 → 进入下一模块
                                                 └─ 否 → 自我修复（≤3 次）
```

**关键工具**：
- `cargo build` / `cargo test`：编译/单测自检
- `parity-checker` skill：行为对齐自检
- `e2e-debugger` skill：当 parity 卡住时自我深挖

**防死循环**：单 Wave 内最多 3 次自我修复，超过则触发升级。

### 第二层：状态持久化（跨 Wave/跨会话）
AI 自己读、自己写"项目记忆"，会话中断后能从断点恢复。

```
会话开始 → 读 translation-state.jsonc → 找到 in_progress 模块 → 继续
会话结束 → 更新 translation-state.jsonc + decisions.md + commit
```

**三件套**：
- `translation-state.jsonc` — 哪些模块完成、parity 多少、blockers
- `decisions.md` — 本次会话做了哪些技术决策（追加式）
- `openspec/changes/<wave-id>/` — 当前 Wave 的提案/任务/进度

无需人工同步，AI 在每个 Wave 结束时**强制写入**。

### 第三层：升级触发器（必须问人类的 5 种情况）
其他全部场景，AI **不准**问人类。

| 触发器 | 表现 | 为什么需要人类 |
|--------|------|----------------|
| **设计歧义** | 同一行为有 2 种合理实现，且影响下游 ≥3 个模块 | 架构方向决策 |
| **Parity 反复 < 80%** | 同一模块连续 3 次自修复后 parity 仍低于 80% | 可能源代码本身有 bug 或测试用例错 |
| **外部依赖缺失** | 需要新增 crate 但选项有 5+ 个/无明显胜出者 | 长期技术债选择 |
| **源码本身有 bug** | 翻译过程中发现源项目逻辑错误 | 是否同步修复需要业务判断 |
| **幻觉指数高** | anti-hallucination 连续 3 个 wave 抓出 ≥3 处"无源码引用断言"，或单 wave hallucination_score > 0.3 | AI 出现结构性幻觉倾向，retry 解决不了 |

不在这 5 种内 → AI 自己定，写进 `decisions.md` 备查。

---

## 3. 自驱脚本：harness/run-autonomous.sh

把三层闭环串成一个可循环的脚本。

```bash
#!/usr/bin/env bash
# harness/run-autonomous.sh
# 用法: ./harness/run-autonomous.sh <target-parity> <max-waves>
# 例:  ./harness/run-autonomous.sh 95 20

set -euo pipefail
TARGET=${1:-95}
MAX_WAVES=${2:-20}
WAVE=0

while [ $WAVE -lt $MAX_WAVES ]; do
  WAVE=$((WAVE+1))
  echo "=== Wave $WAVE ==="

  # 1. 让 AI 选择下一个 Wave 范围（基于 codegraph 依赖图）
  agent run --skill translator --task "select-next-wave" \
    --input ".opencode/translation-state.jsonc" \
    --output ".opencode/wave-${WAVE}.jsonc"

  # 2. 让 AI 执行翻译
  agent run --skill translator --task "execute-wave" \
    --input ".opencode/wave-${WAVE}.jsonc" \
    --max-self-fix 3

  # 3. 索引新鲜度门控（防过期数据导致幻觉）
  ./scripts/check-codegraph-freshness.sh . 24 || { echo "ESCALATE: stale index"; exit 4; }

  # 4. parity 验证
  agent run --skill parity-checker --task "verify-wave-${WAVE}"
  PARITY=$(jq -r ".waves[\"${WAVE}\"].parity" .opencode/translation-state.jsonc)

  # 5. 幻觉审计（深度核验）
  agent run --skill anti-hallucination --task "audit-wave-${WAVE}"
  HSCORE=$(jq -r ".hallucination_score" .opencode/halluc-${WAVE}.jsonc)
  VERDICT=$(jq -r ".verdict" .opencode/halluc-${WAVE}.jsonc)

  # 6. 占位符门控（零容忍）
  ./scripts/forbid-placeholders.sh src 0 || { echo "ESCALATE: placeholders left"; exit 5; }

  # 7. 升级判断
  if [ "$PARITY" -lt 80 ] && [ "$RETRY_COUNT" -ge 3 ]; then
    echo "ESCALATE: parity stuck at $PARITY"; exit 2
  fi
  if [ "$VERDICT" = "escalate" ]; then
    echo "ESCALATE: hallucination_score=$HSCORE"; exit 6
  fi

  # 8. 状态持久化
  git add -A && git commit -m "wave-${WAVE}: parity=${PARITY} halluc=${HSCORE}"

  # 6. 终止条件
  OVERALL=$(jq -r '.overall_parity' .opencode/translation-state.jsonc)
  [ "$OVERALL" -ge "$TARGET" ] && { echo "DONE"; exit 0; }
done

echo "ESCALATE: max waves reached"; exit 3
```

**退出码语义**（让上层 CI/cron 能判断）：
- `0`：达成目标，等人类验收
- `2`：升级——parity 卡住
- `3`：升级——预算耗尽

---

## 4. 让 AI 自驱的 5 条隐性规则

这些不是脚本，是写进 SKILL.md 的**行为约束**。

### 规则 1：默认不问，先做再说
模糊场景下 AI 应**自己定一个合理方案 + 写进 decisions.md**，而不是停下来问。
人类在最终验收时翻 decisions.md 即可。

### 规则 2：所有自修复都有上限
单文件 ≤3 次、单 Wave ≤10 次、单会话 ≤30 次。超限即升级。

### 规则 3：每个 Wave 必须 commit
即使没完成全部，也 commit 进度并打 tag `wave-N-WIP`。
**理由**：会话崩溃/超时不丢工作。

### 规则 4：CodeGraph First, Always
任何"我去看看 X"的冲动，先变成 `codegraph_explore` 调用。
**节省 ~50% token = 多翻 ~50% 模块**。

### 规则 5：占位符必须当 Wave 清零
不准留 `todo!()` / `unimplemented!()` 跨 Wave。
**理由**：占位符滚雪球后，最后一个 Wave 会成无底洞。

---

## 5. 对话最少化：人类只需 3 个时刻

完整自驱项目，人类只需出现 3 次：

### T0：启动会议（一次性，~30 分钟）
- 给 AI 项目目标（语言、范围、parity 目标、deadline）
- 让 AI 跑 `codegraph index` + 生成 `inventory.md`
- 让 AI 用 `openspec/specs/` 起个总章程（项目宪法）
- 人类审阅一次，确认无误后说"开始"

### T1：升级响应（按需，每次 ~5 分钟）
当 AI 触发上面 4 种升级时，看决策、给方向、放回去继续。

### T2：最终验收（一次性，~1 小时）
- AI 跑 `harness/final-acceptance.sh` 出报告
- 人类抽查 `decisions.md` + 跑一次完整 E2E
- 通过则归档所有 OpenSpec 变更

中间的几十/上百个 Wave，**完全不用对话**。

---

## 6. 与现有 Skill 的协同

| 角色 | Skill | 何时被自动触发 |
|------|-------|----------------|
| 调度员 | translator | 每个 Wave 入口 |
| 探索器 | codegraph-navigator | 翻译前理解上下文 |
| 验证器 | parity-checker | 每个模块完成后 |
| 调试器 | e2e-debugger | parity 不达标时 |
| 进化器 | self-improving | 每次升级后归纳教训 |
| 看板 | status-dashboard | T2 验收时 |

所有 skill 已经在 SKILL.md 里声明了**触发条件**（frontmatter description），
AI 会按场景自动调用，无需人类指令。

---

## 7. 常见误区

- "我把 prompt 写得超详细就能自驱"
  → 不行。详细 prompt 只解决"怎么做"，不解决"做完怎么验证"和"卡住怎么办"。

- "让 AI 每个 Wave 都汇报给我"
  → 反模式。汇报本身就是对话成本。让它自己写 `decisions.md`，你按需翻。

- "AI 自驱就是放养，不管它"
  → 不对。是给**清晰的边界**（4 种升级 + 3 类预算上限）后再放手。

正确姿势：
> 给目标 + 给边界 + 给闭环 → 让它跑 → 升级时介入 → 最终验收

---

## 8. 下一步

- 实操新手教程见 [GETTING_STARTED.md](./GETTING_STARTED.md)
- Skill 编写细节见 [skill-cookbook.md](./skill-cookbook.md)
- CodeGraph 配置见 [codegraph-integration.md](./codegraph-integration.md)
