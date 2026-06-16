# Self-Improving 详细参考

> 按需加载。


# 自我改进系统 (Self-Improving)

## 概述

翻译项目是长期工程（数周到数月），过程中会不断发现新模式、新陷阱。
自我改进系统确保这些经验不会丢失，自动积累到技能文件中。

从 Taibai 项目的 `self-improving-agent` 直接复用并针对翻译场景优化。

## 三层记忆架构

### Layer 1: 语义记忆 (Semantic Memory)
**存储位置:** `memory/semantic-patterns.json`
**内容:** 可复用的翻译模式（类型映射、并发模式、错误处理等）
**特征:** 长期稳定，适用于所有会话

### Layer 2: 情节记忆 (Episodic Memory)
**存储位置:** `memory/episodes.jsonl`
**内容:** 具体翻译事件（特定函数的翻译决策、遇到的具体 bug）
**特征:** 时间序列，用于回溯分析

### Layer 3: 工作记忆 (Working Memory)
**存储位置:** 当前会话上下文
**内容:** 当前 Wave 的翻译上下文、正在处理的模块信息
**特征:** 会话内有效，会话结束时提炼为语义/情节记忆

## 演化触发器

### 触发条件

| 事件 | 触发动作 | 目标文件 |
|------|---------|---------|
| 发现新类型映射 | 追加到 type-mapping | `go2rust/type-mapping.md` 或 `c2rust/` |
| 并发翻译出错后修复 | 更新并发模式 | `*/concurrency-patterns.md` |
| unsafe 审计发现新模式 | 更新审计指南 | `c2rust/unsafe-audit.md` |
| E2E 失败的根因是新模式 | 追加失败模式 | `e2e-debugger/SKILL.md` |
| parity check 发现系统性偏差 | 更新反模式 | `shared/anti-patterns.md` |
| 序列化行为不一致 | 更新 serde 模式 | `go2rust/serde-patterns.md` |
| FFI 边界新发现 | 更新 FFI 模式 | `c2rust/ffi-patterns.md` |
| 内存管理新模式 | 更新内存模式 | `c2rust/memory-patterns.md` |

### 优先级矩阵

| 优先级 | 描述 | 自动/手动 |
|--------|------|----------|
| P0 | 导致编译失败的模式 | 自动更新 |
| P1 | 导致测试失败的模式 | 自动更新 |
| P2 | 导致 E2E 失败的模式 | 自动更新 |
| P3 | 性能/惯用性改进 | 手动审核后更新 |
| P4 | 代码风格偏好 | 记录但不自动更新 |

## 模式提炼流程

### Step 1: 检测新模式
```
在翻译过程中，如果遇到:
- 技能文件中没有覆盖的翻译情况
- 需要多次尝试才能正确翻译的模式
- 从错误中恢复时发现的新知识
→ 触发模式提炼
```

### Step 2: 验证可复用性
```
新模式必须满足:
- 出现 ≥ 2 次（不是一次性特殊情况）
- 可泛化（不依赖特定项目上下文）
- 有明确的输入→输出模式
- 有反例（知道什么时候不适用）
```

### Step 3: 格式化记录
```markdown
## [编号]: [简短描述]

**源模式 (C/Go):**
```[language]
// 典型代码
```

**Rust 翻译:**
```rust
// 翻译后代码
```

**适用条件:** [什么时候用]
**不适用:** [什么时候不用]
**发现来源:** [哪个模块/场景中发现的]
```

### Step 4: 集成到技能文件
```
1. 确定目标文件（根据模式分类）
2. 追加新模式（保持编号连续）
3. 更新相关决策树（如果影响决策逻辑）
4. 在 memory/semantic-patterns.json 中记录元数据
```

## Hooks

### pre-translate.sh
```bash
#!/bin/bash
# 翻译前：加载相关模式
# 参数: $1 = 源文件路径, $2 = 源语言

echo "Loading patterns for $2..."
# 检查 memory 中是否有与当前模块相关的历史经验
grep -l "$1" memory/episodes.jsonl 2>/dev/null && \
  echo "⚠️  该模块有历史翻译经验，请先查看"
```

### post-translate.sh
```bash
#!/bin/bash
# 翻译后：检查是否有新模式
# 参数: $1 = Rust 文件路径, $2 = 源文件路径

# 检查是否使用了未记录的模式
NEW_PATTERNS=$(analyze_new_patterns "$1" "$2")
if [ -n "$NEW_PATTERNS" ]; then
  echo "🆕 发现潜在新模式:"
  echo "$NEW_PATTERNS"
  echo "请确认是否需要记录到技能文件"
fi
```

### post-fix.sh
```bash
#!/bin/bash
# 修复 bug 后：记录经验
# 参数: $1 = 修复的文件, $2 = 错误类型

echo "Recording fix experience..."
TIMESTAMP=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
echo "{\"time\":\"$TIMESTAMP\",\"file\":\"$1\",\"type\":\"$2\",\"action\":\"fix\"}" \
  >> memory/episodes.jsonl
```

### session-end.sh
```bash
#!/bin/bash
# 会话结束：总结经验
echo "Session summary..."
echo "─────────────────────────"

# 统计本次会话
TRANSLATED=$(git diff --stat HEAD~1 | grep -c "\.rs")
FIXES=$(grep -c "$(date +%Y-%m-%d)" memory/episodes.jsonl 2>/dev/null || echo 0)

echo "翻译文件数: $TRANSLATED"
echo "修复次数: $FIXES"
echo "─────────────────────────"

# 提示检查是否有新模式需要记录
if [ "$FIXES" -gt 2 ]; then
  echo "⚠️  本次修复较多，建议回顾是否有可提炼的新模式"
fi
```

## 记忆衰减策略

不是所有经验都永久有效：

| 记忆类型 | 衰减规则 |
|---------|---------|
| 类型映射 | 永不衰减（累积性知识）|
| 并发模式 | 低频使用 6 个月后标记为"待验证" |
| 特定 bug 修复 | 1 年未重现可归档 |
| 性能优化经验 | Rust 版本更新后需重新验证 |
| 反模式 | 永不衰减（负面经验价值持久）|

## 初始模式库

`memory/semantic-patterns.json` 初始化为空：
```json
{
  "version": "1.0",
  "patterns": [],
  "last_updated": null,
  "total_patterns_discovered": 0
}
```

随着翻译项目进行，自动积累。

## 与其他技能的交互

```
翻译过程 → [检测新模式] → self-improving
     ↓
[提炼模式] → 更新对应技能文件
     ↓
[记录情节] → memory/episodes.jsonl
     ↓
下次翻译 ← [加载相关经验]
```
