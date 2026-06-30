---
name: translator
description: 统一翻译驱动器 — 检测源语言，加载技能，驱动完整翻译流程
prerequisites:
  - codegraph-navigator (CodeGraph 已安装并索引)
  - anti-hallucination (非平凡函数翻译前必过 6 问)
  - 索引新鲜度 (scripts/check-codegraph-freshness.sh 通过)
---

# 翻译驱动器

## 何时使用
- 开始翻译新组件/模块
- 恢复翻译会话（读 translation-state.jsonc 续上）
- 用户给出源项目路径，要求翻译（→ 进入自主模式）

## 核心原则
1. **CodeGraph First** — 探索代码用图查询，不暴力 grep
2. **无证据不断言** — 每个非平凡函数过 anti-hallucination 6 问
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

## 自主模式

当用户说"帮我把 /path/to/project 翻译成 Rust"时，进入自主模式。
**全程不问用户任何问题，直到最终验证通过。**

### 自主决策默认值

所有原本需要问用户的问题，按以下默认值自动决定：

| 问题 | 默认决策 | 理由 |
|------|---------|------|
| 翻译范围？ | `src/` + `tests/` | 标准范围 |
| 是否包含 KV 缓存？ | 先不包含 | 先翻译核心，后加功能 |
| E2E 何时跑？ | 第一个功能模块后立即跑 | AP-002 防范 |
| WRITE_GRAN？ | 检测 C 源的 `FDB_WRITE_GRAN` 定义，默认 1 | 最常见值 |
| 文件模式？ | 检测 C 源是否有 `FDB_USING_FILE_POSIX_MODE`，有则启用 | 匹配源配置 |
| Oracle 模式？ | 优先 run-source（C 可编译运行时） | 最高可信度 |
| unsafe 阈值？ | 10% | 竞赛标准 |
| 并行翻译？ | Wave 内独立模块可并行 | 提高吞吐 |

### 自主流程（从源项目路径到最终验证通过）

```
Phase 0: 检测与初始化（~5 min）
  ├─ 检测源语言 → 加载对应技能
  ├─ 运行 init 脚本创建 Rust 骨架
  ├─ 运行 analyze 脚本生成 source-inventory.md
  ├─ 编译 C 源项目（如果可能）→ 确认 Oracle 可用
  └─ 生成 acceptance-plan.yaml（自动确认）

Phase 1: 规划（~10 min）
  ├─ 分析源码结构 → 拓扑排序 → 叶子优先
  ├─ 规划 Wave 1（3-5 个最简单的叶子模块）
  └─ 写 wave plan 到 .opencode/plans/wave-001.md

Phase 2: 翻译循环（每个 Wave）
  ├─ Wave N 开始
  │   ├─ 按计划逐模块翻译
  │   │   ├─ 接口翻译（types + traits）
  │   │   ├─ 实现翻译（函数体）
  │   │   ├─ 测试翻译（port C tests + thread_local! 计数器）
  │   │   ├─ cargo fmt && cargo check && cargo test
  │   │   └─ 修复编译/测试失败（最多 3 轮，超过则缩小范围）
  │   ├─ Wave 完成后
  │   │   ├─ 运行 unsafe_audit.sh
  │   │   ├─ 运行 forbid-placeholders.sh
  │   │   ├─ 对照 C 测试列表做覆盖率差距分析
  │   │   ├─ 补齐缺失的 Rust 测试
  │   │   └─ 更新 translation-state + decisions
  │   └─ 如果 Wave 1 完成 → 立即建 C Oracle + 差分测试
  └─ 所有模块翻译完成 → 进入 Phase 3

Phase 3: 最终验证（~15 min）
  ├─ 建全部 C Oracle 程序（basic + GC + multi-sector + reboot）
  ├─ 跑全部差分测试 vs C Oracle
  ├─ cargo fmt && cargo check && cargo test (全量)
  ├─ unsafe_audit.sh
  ├─ forbid-placeholders.sh
  ├─ final_verify.sh
  ├─ 更新 README.md 和 reports/
  └─ 添加 rustdoc 到所有公开 API
```

### 自主模式失败恢复

| 失败类型 | 自动处理 |
|---------|---------|
| 编译错误 | 读取 error stack → 精准打补丁 → 最多 3 轮 |
| 3 轮编译修复失败 | 缩小翻译范围（拆分模块）→ 重试 |
| 测试失败 | 对比 C 测试预期 → 修复 → 最多 3 轮 |
| 3 轮测试修复失败 | 回退到上一个通过状态 → 缩小范围重试 |
| C Oracle 编译失败 | 降级到 static-codegraph Oracle（签名/调用图对照） |
| unsafe 超标 | 审计 unsafe 块 → 逐个消除 → 重验 |
| Deep agent 超时/无输出 | AP-005: 不盲目重试，先 probe 代码状态 |

### 自主模式唯一升级条件

以下情况才暂停并报告用户：
1. 源项目无法编译且无法降级到 static-codegraph（缺少依赖）
2. 同一模块连续 3 个 Wave 都翻译失败
3. 发现源代码本身有 bug（C 代码运行结果不符合其测试预期）

### 自主模式输出格式

每完成一个 Phase/Wave，输出进度报告：
```
## Wave N 完成
- 翻译模块: [列表]
- LOC: X (累计 Y)
- 测试: X passed (累计 Y)
- unsafe: X%
- 差分测试: X/Y passed vs C Oracle
- 覆盖率差距: [缺失的 C 测试对应的 Rust 测试]
- 下一步: Wave N+1 计划
```

## 工作流（简版）
```
分析 → 初始化 → [Wave: 翻译→验证→归档] × N → 完成
```

自主模式下：
```
用户给路径 → [自动执行上述流程] → 最终验证通过 → 报告完成
```

## 升级触发器（自主模式下不问用户，除非触发以下条件）
- 设计决策歧义（2+ 等价译法，影响公开 API）
- 反复 3 次 parity < 80%
- 外部依赖缺失
- 源代码本身有 bug

## 详细参考
- 完整工作流状态机 → `workflow.md`
- 详细前置条件与规则 → `reference.md`
