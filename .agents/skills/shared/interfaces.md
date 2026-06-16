# Skill 间握手协议（接口契约）

> 锁定 skill 之间传递的字段格式，防止 AI 改格式导致流水线断裂。
> 任何对本协议的变更，必须先开 OpenSpec 提案。

---

## 总览：数据流

```
translator → [wave-N.jsonc]            → parity-checker
parity-checker → [parity-N.jsonc]      → anti-hallucination
anti-hallucination → [halluc-N.jsonc]  → differential-tester
differential-tester → [diff-N.jsonc]   → harness 升级判断
acceptance-plan.yaml (T0 锁定)          → harness / parity-checker / differential-tester
self-improving ← 所有 skill 的输出
status-dashboard ← 所有 *.jsonc
```

所有交换文件统一放 `.opencode/`。

---

## 1. translator → parity-checker

**文件**：`.opencode/wave-${N}.jsonc`

```jsonc
{
  "wave_id": "string, 必填, e.g. 'wave-3'",
  "modules": [
    {
      "module": "crates::foo::bar",
      "src_path": "k8s.io/foo/bar",
      "src_files": ["bar.go", "types.go"],
      "dst_files": ["src/foo/bar.rs"],
      "status": "in_progress|done|blocked",
      "translated_functions": ["Bar::new", "Bar::process"],
      "skipped_functions": [],
      "notes": "free text"
    }
  ],
  "started_at": "ISO-8601",
  "completed_at": "ISO-8601 or null"
}
```

**契约**：
- `wave_id` 全局唯一，递增
- `modules[].status` 仅允许 3 值
- 写入方：translator；读取方：parity-checker / status-dashboard

---

## 2. parity-checker → anti-hallucination

**文件**：`.opencode/parity-${N}.jsonc`

```jsonc
{
  "wave_id": "wave-3",
  "overall_parity": 0.92,
  "modules": [
    {
      "module": "crates::foo::bar",
      "parity": 0.95,
      "tests_total": 47,
      "tests_passed": 45,
      "behavior_diffs": [
        { "case": "empty_input", "src": "panic", "dst": "Err(...)", "severity": "low" }
      ]
    }
  ]
}
```

**契约**：
- `parity` ∈ [0.0, 1.0]
- `behavior_diffs[].severity` 仅 `low|medium|high`
- 写入方：parity-checker；读取方：anti-hallucination / harness

---

## 3. anti-hallucination → harness

**文件**：`.opencode/halluc-${N}.jsonc`

```jsonc
{
  "wave_id": "wave-3",
  "audited_modules": ["crates::foo::bar"],
  "findings": [
    {
      "severity": "high|medium|low",
      "type": "api_fabrication|behavior_assumption|constant_drift|caller_inversion|coverage_thin",
      "loc": "src/foo/bar.rs:42",
      "evidence": "string"
    }
  ],
  "hallucination_score": 0.15,
  "verdict": "pass|retry|escalate"
}
```

**契约**：
- `hallucination_score` ∈ [0.0, 1.0]，越低越好
- `verdict` 决定 harness 下一步：
  - `pass` → 进入下一 wave
  - `retry` → 同 wave 自我修复（≤3 次）
  - `escalate` → 升级人类
- `type` 必须是 5 个枚举之一（与 reference.md 5 类幻觉对齐）

---

## 3.5 differential-tester → harness

**文件**：`.opencode/diff-${N}.jsonc`

```jsonc
{
  "wave_id": "wave-3",
  "oracle_mode": "run-source|record-replay|static-codegraph|dual-ai",
  "cases_total": 142,
  "cases_passed": 138,
  "cases_failed": [
    { "case_id": "AC-bar-001", "input": "...", "src_out": "...", "dst_out": "...", "diff": "..." }
  ],
  "ai_derived_oracles": 0,
  "parity_ceiling": 0.95,
  "verdict": "pass|retry|escalate"
}
```

**契约**：
- `ai_derived_oracles` 必须为 0；> 0 → harness 强制 escalate
- `oracle_mode` 影响 `parity_ceiling`：run-source 0.99 / record-replay 0.95 / dual-ai 0.85 / static-codegraph 0.75
- `verdict` 语义与 halluc-N.jsonc 相同
- 写入方：differential-tester；读取方：harness / status-dashboard

---

## 4. 全局状态：translation-state.jsonc

**文件**：`.opencode/translation-state.jsonc`（持久化）

```jsonc
{
  "project": "string",
  "src_lang": "go|c",
  "dst_lang": "rust",
  "overall_parity": 0.65,
  "current_wave": "wave-3",
  "waves": {
    "wave-1": { "status": "done", "parity": 1.0, "halluc_score": 0.05 },
    "wave-2": { "status": "done", "parity": 0.98, "halluc_score": 0.10 },
    "wave-3": { "status": "in_progress", "parity": null, "halluc_score": null }
  },
  "blockers": [
    { "module": "...", "reason": "...", "since": "wave-2" }
  ],
  "session_history": [
    { "wave": "wave-3", "started": "...", "ended": null }
  ]
}
```

**契约**：
- 所有 skill 都可读，**只有 translator 可写顶层字段**
- parity-checker 只更新 `waves[].parity`
- anti-hallucination 只更新 `waves[].halluc_score`
- harness 只更新 `current_wave` 和 `session_history`

---

## 5. 决策记录

**文件**：`.opencode/decisions.md`（追加式，纯文本）

每条决策格式：

```markdown
## YYYY-MM-DD wave-N <topic>

**Context**: 为什么需要决策
**Options**: 备选方案
**Decision**: 选了哪个，理由
**Consequences**: 影响下游什么
```

**契约**：
- 所有 skill 都可追加，**禁止删除/修改历史条目**
- 升级触发时人类决策也要写一条

---

## 6. 协议变更流程

如需变更上述任何字段：

1. 开 OpenSpec 提案：`openspec/changes/iface-vN-to-vN+1/`
2. 在 proposal.md 列出：旧字段、新字段、迁移脚本
3. 实现时**先**升 schema，**再**改 skill
4. 归档前确认所有 skill 已用新协议

---

## 版本

当前协议版本：**v1.0**
最后更新：见 git log
