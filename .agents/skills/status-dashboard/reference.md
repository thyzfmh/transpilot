# status-dashboard 详细参考

> 按需加载。


# 进度仪表盘 (Status Dashboard)

## 概述

从翻译状态文件生成人类可读的进度报告，帮助跟踪翻译进展、
识别瓶颈、预估完成时间。

## 数据源

主要数据源: `translation-state.jsonc`

```jsonc
{
  "project": {
    "name": "project-name",
    "source_language": "go",  // or "c"
    "total_modules": 42,
    "started_at": "2024-01-15"
  },
  "modules": {
    "module-a": {
      "status": "verified",      // pending | in_progress | translated | verified
      "parity_score": 98.5,
      "wave": 1,
      "difficulty": "medium",
      "lines_source": 1200,
      "lines_rust": 1450,
      "tests_total": 45,
      "tests_passing": 45,
      "unsafe_count": 2,
      "started_at": "2024-01-20",
      "completed_at": "2024-01-22"
    }
  },
  "waves": {
    "1": { "status": "complete", "modules": ["module-a", "module-b"] },
    "2": { "status": "in_progress", "modules": ["module-c", "module-d"] }
  }
}
```

## 报告类型

### 1. 概览报告 (Summary)

```
═══════════════════════════════════════════════════
  TRANSPILOT — [项目名] 翻译进度
═══════════════════════════════════════════════════

  源语言: Go          开始: 2024-01-15
  总模块: 42          当前 Wave: 3/8

  ┌─────────────────────────────────────────────┐
  │ 进度: ████████████░░░░░░░░░ 58% (24/42)     │
  └─────────────────────────────────────────────┘

  状态分布:
    ✅ 已验证:    20 (48%)
    🔄 翻译中:     4 (10%)
    ⏳ 待开始:    18 (42%)

  等价性: 97.2% (综合)
  unsafe: 3.1% (预算内)
  测试:   892/905 通过 (98.6%)

  预估完成: 2024-03-20 (±2 weeks)
═══════════════════════════════════════════════════
```

### 2. Wave 报告 (Wave Detail)

```
Wave 3 — 进行中
───────────────────────────────────────────
模块          状态        Parity  测试
───────────────────────────────────────────
module-c      translated  95.2%   38/42
module-d      in_progress  —      12/30
module-e      in_progress  —       0/28
───────────────────────────────────────────

阻塞项:
  - module-d: 3 个函数使用了 module-f（未翻译）
  - module-e: 等待 module-d 的接口稳定

预计完成: 3-5 天
```

### 3. 模块详情 (Module Detail)

```
module-c — 详情
───────────────────────────────────────────
状态: translated (待验证)
难度: Hard
Wave: 3
源码行: 2,100
Rust 行: 2,450 (+17%)
───────────────────────────────────────────

等价性:
  L1 结构: 98% (2 个函数待翻译)
  L2 功能: 95% (2 个测试失败)
  L3 接口: 100%
  L4 行为: 待验证

未解决问题:
  1. [P1] serialize_config() — serde 属性不匹配
  2. [P2] handle_timeout() — 测试超时

决策记录:
  D-012: 选择 tokio::time 替代 std::thread::sleep
```

### 4. 风险报告 (Risk Assessment)

```
风险评估
═══════════════════════════════════════════════════

🔴 高风险:
  - module-x: unsafe 占比 12% (超标)
  - module-y: 0 测试覆盖

🟡 中风险:
  - module-z: 依赖 3 个未翻译模块
  - Wave 5: 含 2 个 "Very Hard" 模块

🟢 低风险:
  - Wave 4: 全部 Easy/Medium 模块

建议:
  1. 优先处理 module-x 的 unsafe 消除
  2. 为 module-y 补充测试后再翻译
  3. 考虑拆分 Wave 5 中的 Very Hard 模块
```

## 指标定义

| 指标 | 计算方式 | 健康阈值 |
|------|---------|---------|
| 总进度 | verified_modules / total_modules | — |
| 综合 Parity | avg(verified_module.parity_score) | ≥ 95% |
| unsafe 比例 | total_unsafe_lines / total_rust_lines | < 5% |
| 测试通过率 | passing_tests / total_tests | ≥ 98% |
| Wave 速度 | modules_per_week (移动平均) | — |
| 预估完成 | remaining / wave_velocity | — |
| 技术债务 | placeholders + known_issues | 递减趋势 |

## 报告生成命令

```bash
# 概览
./scripts/progress-report.sh summary

# Wave 详情
./scripts/progress-report.sh wave 3

# 模块详情
./scripts/progress-report.sh module module-c

# 风险评估
./scripts/progress-report.sh risk

# 完整报告（含所有内容）
./scripts/progress-report.sh full > report.md
```

## 告警规则

| 条件 | 告警级别 | 行动 |
|------|---------|------|
| Parity < 90% | 🔴 CRITICAL | 停止翻译，修复现有问题 |
| unsafe > 10% | 🔴 CRITICAL | 启动 unsafe 审计 |
| Wave 超时 (> 2x 预估) | 🟡 WARNING | 分析瓶颈，考虑拆分 |
| 测试通过率 < 95% | 🟡 WARNING | 优先修复失败测试 |
| 占位符积累 > 10 个 | 🟡 WARNING | 消除占位符 |
| 连续 3 天无进展 | 🟡 WARNING | 检查阻塞项 |
