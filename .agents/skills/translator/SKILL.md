---
name: translator
description: 统一翻译驱动器 — 自动检测源语言，加载对应技能，驱动完整翻译流程
prerequisites:
  - codegraph-navigator (CodeGraph 必须已安装并对源/目标项目索引)
---

# 翻译驱动器 (Translator)

## 概述

统一入口点，协调所有翻译相关技能，驱动从源语言到 Rust 的完整翻译流程。

## 前置条件

> 本技能要求 `codegraph-navigator` 已就绪。翻译开始前，驱动器会执行：
> ```bash
> codegraph status  # 确认源项目索引可用
> ```
> 如果 CodeGraph 未安装或未索引，将提示用户先完成配置。

## 核心原则：CodeGraph First

翻译的两个目标按优先级排列：
1. **准确性** — 完整理解源代码的调用图和类型关系后再翻译
2. **Token 效率** — 优先使用 CodeGraph 图查询，避免暴力 grep/Read

**规则:**
- 任何代码探索 → 先尝试 `codegraph_explore`（1 次 call 替代 5-20 次）
- 翻译非叶子函数前 → 必须 `codegraph_callers` 确认调用方
- 信任 CodeGraph 结果 → 不重复 Read 已返回的源码
- CodeGraph 无法回答时 → 退回 grep/Read（仅限动态分发/反射/宏展开场景）

## 支持的源语言

| 语言 | 技能 | 检测方式 |
|------|------|---------|
| Go | `go2rust` | `go.mod` / `*.go` 文件 |
| C | `c2rust` | `Makefile` / `CMakeLists.txt` / `*.c` + `*.h` |

## 翻译工作流

### Phase 0: 项目分析
```
输入: 源项目路径
输出: 分析报告（语言、规模、依赖、复杂度评估）

1. 检测项目语言和构建系统
2. 分析目录结构和模块划分
3. 构建依赖图
4. 评估翻译难度（按模块）
5. 生成翻译计划（Wave 分组）
```

### Phase 1: 项目初始化
```
输入: 分析报告
输出: Rust 项目骨架 + 翻译状态文件

1. 创建 Cargo workspace
2. 按模块划分 crate
3. 初始化 translation-state.jsonc
4. 初始化 decisions.md
5. 设置 CI（cargo check + clippy + test）
```

### Phase 2: 逐模块翻译（Wave 模式）
```
每个 Wave（3-5 模块）:
  1. 选择本 Wave 模块（叶子优先）
  2. 对每个模块:
     a. 翻译接口（types + traits）
     b. 翻译实现（函数体）
     c. 翻译测试
     d. 运行 parity-checker
     e. 更新 translation-state
  3. Wave 完成后运行 E2E 验证
  4. 诊断 + 修复 E2E 失败
  5. 记录决策到 decisions.md
```

### Phase 3: 集成验证
```
1. 运行完整测试套件
2. 运行 E2E 场景
3. 性能基准对比
4. unsafe 审计
5. 生成最终报告
```

## 关键规则

### R1: 恢复优先
每次会话开始前，先读取 `translation-state.jsonc` 恢复上下文。
绝不从头开始——翻译项目跨越多个会话。

### R2: 叶子优先策略
```
翻译顺序 = 拓扑排序(依赖图).reverse()
即：先翻译没有项目内依赖的模块
```

### R3: Wave 纪律
- 每 Wave 3-5 个模块
- Wave 内模块应互不依赖
- Wave 结束必须通过 E2E
- 不通过不开始下一 Wave

### R4: 占位符规则
```
翻译中允许占位符，但必须:
- 标记为 todo!("PLACEHOLDER: 原因")
- 在 translation-state 中记录
- 本 Wave 结束前消除
- 绝不让占位符积累超过一个 Wave
```

### R5: 决策记录
任何非平凡翻译选择（>1 种合理方案时）必须记录到 decisions.md。
格式: D-XXX: 标题 | 上下文 | 决策 | 后果

## 自动检测逻辑

```python
def detect_language(project_path):
    if exists(project_path / "go.mod") or glob("**/*.go"):
        return "go", load_skill("go2rust")
    elif exists(project_path / "CMakeLists.txt") or exists(project_path / "Makefile"):
        return "c", load_skill("c2rust")
    elif glob("**/*.c") or glob("**/*.h"):
        return "c", load_skill("c2rust")
    else:
        raise Error("Unsupported source language")
```

## 调用其他技能

| 阶段 | 技能 | 用途 |
|------|------|------|
| 分析 | `shared` | 治理规则 |
| 翻译 | `go2rust` / `c2rust` | 语言特定翻译 |
| 验证 | `parity-checker` | 等价性检查 |
| E2E | `e2e-debugger` | 失败诊断 |
| 监控 | `status-dashboard` | 进度报告 |
| 改进 | `self-improving` | 经验积累 |

## 会话模板

每次翻译会话的标准流程：
```
1. [恢复] 读取 translation-state.jsonc → 确定当前位置
2. [计划] 确定本次会话目标（通常 1 Wave）
3. [执行] 逐模块翻译
4. [验证] parity-check + E2E
5. [记录] 更新状态 + 决策
6. [改进] 触发自我改进 hooks
```
