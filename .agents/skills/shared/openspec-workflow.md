# OpenSpec 翻译治理工作流

## 概述

OpenSpec 是翻译项目的**变更治理系统**，为每个组件/阶段提供结构化的变更提案流程。
它与 CodeGraph 和翻译驱动器协同工作，确保大规模翻译的可追踪性和一致性。

## 核心命令

| 命令 | 用途 | 时机 |
|------|------|------|
| `/opsx-propose` | 创建变更提案 | 开始新组件/新 Wave 时 |
| `/opsx-apply` | 执行提案中的任务 | 实施翻译时 |
| `/opsx-archive` | 归档已完成提案 | Wave/组件完成后 |
| `/opsx-sync` | 同步主规格文件 | 重大进展后 |

## 目录结构

```
project-root/
├── openspec/
│   ├── config.yaml          # OpenSpec 配置
│   ├── specs/               # 主规格文件（组件级）
│   │   ├── <component>/
│   │   │   └── spec.md      # 组件规格：状态、约定、架构
│   │   └── translation-conventions/
│   │       └── spec.md      # 全局翻译约定
│   └── changes/             # 活跃变更提案
│       ├── <component>-wave-1/
│       │   ├── proposal.md  # 问题 + 高层方案
│       │   ├── design.md    # 详细设计 + 权衡
│       │   ├── specs/       # 行为规格
│       │   └── tasks.md     # 可实施的任务分解
│       └── archive/         # 已完成的变更
│           └── ...
```

## 工作流详解

### Phase 1: 提案（`/opsx-propose`）

**触发时机:**
- 开始翻译一个新组件
- 开始一个新 Wave（3-5 模块的批次）
- 发现需要架构变更时

**创建的四个文件:**

#### proposal.md
```markdown
# <Component> Wave N Translation

## Problem Statement
- Source: <go/c module path>
- Target: <rust crate path>
- Scope: N modules, ~XXXX lines of Go/C code
- Dependencies: [已翻译的前置模块]

## Approach
- Strategy: [direct|refactor|hybrid]
- Risk: [low|medium|high]
- Estimated effort: N sessions
```

#### design.md
```markdown
# Design: <Component> Wave N

## Architecture Decisions
- [使用 CodeGraph 分析的结果]
- 依赖图: codegraph impact <entry_point>
- 调用关系: codegraph callers <public_api>

## Type Mappings
| Go/C Type | Rust Type | Rationale |
|-----------|-----------|-----------|

## Trade-offs
- Option A vs Option B: [analysis]
- Chosen: [decision with rationale]
```

#### tasks.md
```markdown
# Tasks: <Component> Wave N

## Prerequisites
- [ ] CodeGraph 索引就绪: `codegraph status`
- [ ] 前置模块已翻译: [list]
- [ ] 依赖图已分析: `codegraph impact <entry>`

## Implementation Tasks
- [ ] Task 1: Translate <module_a> (~50 lines)
  - Source: <path>
  - Target: <path>
  - Depends on: [none|task N]
- [ ] Task 2: Translate <module_b> (~80 lines)
  ...

## Verification Tasks
- [ ] Unit tests pass: `cargo test -p <crate>`
- [ ] Parity check: source vs target API surface
- [ ] Integration: callers of translated modules work
- [ ] E2E (if first wave): basic functional test

## Post-Wave
- [ ] Update translation-state.jsonc
- [ ] Record decisions to decisions.md
- [ ] Archive this change: `/opsx-archive`
```

### Phase 2: 执行（`/opsx-apply`）

**与 CodeGraph 的集成:**

```
执行每个任务前:
1. codegraph_explore → 理解源模块完整上下文
2. codegraph_callers → 确认公开接口的所有调用者
3. 翻译
4. codegraph_node → 在目标项目验证结构

执行后:
5. 标记 tasks.md 中的任务为完成
6. 更新 translation-state.jsonc
```

**任务粒度规则:**
- 每个任务 ≤ 200 行代码变更
- 每个任务可独立验证（`cargo check` + `cargo test`）
- 避免跨模块依赖的单个任务

### Phase 3: 归档（`/opsx-archive`）

**触发时机:**
- Wave 中所有任务完成
- 所有验证任务通过
- translation-state.jsonc 已更新

**操作:**
```bash
# 将 changes/<name>/ 移动到 changes/archive/<name>/
/opsx-archive <change-name>
```

**归档前检查清单:**
- [ ] tasks.md 中所有任务已勾选
- [ ] parity score ≥ 95%
- [ ] E2E 通过（如适用）
- [ ] 无未解决的 blockers

### Phase 4: 同步（`/opsx-sync`）

**触发时机:**
- 归档变更后
- 重大架构决策后
- 定期（每 5 个 Wave 或每周）

**操作:**
```bash
# 更新 openspec/specs/<component>/spec.md
/opsx-sync
```

**同步内容:**
- 组件整体 parity score
- 已完成模块列表
- 剩余工作量估算
- 关键决策摘要

---

## 与翻译驱动器的集成

```
翻译驱动器 (translator/SKILL.md)
│
├── 开始新组件 → /opsx-propose
│     └── CodeGraph 分析 → design.md
│
├── 执行 Wave → /opsx-apply
│     ├── 每个 task → codegraph_explore → 翻译 → 验证
│     └── Wave 完成 → 更新 state + decisions
│
├── Wave 验证通过 → /opsx-archive
│     └── 移入 archive/
│
└── 重大进展 → /opsx-sync
      └── 更新 specs/<component>/spec.md
```

## 典型翻译项目生命周期

```
组件 A (20 模块):
├── Wave 1 (5 模块): propose → apply × 5 → verify → archive → sync
├── Wave 2 (5 模块): propose → apply × 5 → verify → archive → sync  
├── Wave 3 (5 模块): propose → apply × 5 → verify → archive → sync
└── Wave 4 (5 模块): propose → apply × 5 → verify → archive → sync ✓

组件 B (8 模块):
├── Wave 1 (4 模块): propose → apply × 4 → verify → archive → sync
└── Wave 2 (4 模块): propose → apply × 4 → verify → archive → sync ✓
```

## 为什么需要 OpenSpec

| 问题 | 无 OpenSpec | 有 OpenSpec |
|------|-----------|-----------|
| 上下文丢失 | 新会话不知道在做什么 | 读 tasks.md 立即恢复 |
| 决策遗忘 | 重复讨论相同问题 | design.md 记录了决策 |
| 范围蔓延 | 翻译中不断扩大范围 | proposal.md 约束了边界 |
| 进度不可见 | 不知道完成了多少 | tasks.md + state 精确追踪 |
| 大型项目失控 | 100+ 模块无从下手 | Wave 模式 + 依赖图 = 清晰路径 |

## 配置

### openspec/config.yaml

```yaml
# 项目级 OpenSpec 配置
project:
  name: "<project-name>"
  type: "translation"
  
translation:
  source_language: "go"  # 或 "c"
  target_language: "rust"
  wave_size: 3-5          # 每 Wave 模块数
  task_max_lines: 200     # 每任务最大行数
  parity_threshold: 95    # 归档前最低 parity %
  
governance:
  state_file: ".opencode/translation-state.jsonc"
  decisions_file: ".opencode/decisions.md"
  
codegraph:
  required: true          # 强制要求 CodeGraph 就绪
  pre_task_explore: true  # 每个任务前自动 explore
```
