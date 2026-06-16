# CodeGraph Navigator 详细参考

> 本文件按需加载，SKILL.md 为入口索引。


# CodeGraph 翻译导航器

## 前置条件

> **必须:** 本技能依赖 CodeGraph 预索引知识图谱。使用前确保：

```bash
# 1. 安装 CodeGraph
curl -fsSL https://raw.githubusercontent.com/colbymchenry/codegraph/main/install.sh | sh
# 或
npm i -g @colbymchenry/codegraph

# 2. 配置 Agent 连接
codegraph install

# 3. 对源项目索引
cd /path/to/source-project
codegraph init

# 4. 对目标项目索引
cd /path/to/target-rust-project
codegraph init
```

**验证就绪:**
```bash
codegraph status  # 应显示 nodes/edges 数量 > 0
```

---

## 为什么翻译需要 CodeGraph

### 问题：暴力搜索浪费 token

传统翻译流程中，Agent 需要频繁使用 `grep`/`Read`/`Glob` 来：
1. 理解源函数的调用者和被调用者
2. 追踪类型定义和依赖关系
3. 确认接口实现的完整列表
4. 验证翻译后的 Rust 代码是否覆盖了所有调用路径

每次探索消耗大量 token（平均 47% 浪费在发现阶段）。

### 解决：预索引图谱 = 一次查询到位

CodeGraph 将代码结构预索引为知识图谱（symbols + edges + FTS5），
Agent 可以用**一次 MCP 工具调用**获得完整的：
- 符号定义 + 完整源码
- 调用图（callers/callees）
- 影响范围（impact radius）
- 跨文件依赖关系

**效果:** ~58% fewer tool calls, ~47% fewer tokens, ~22% faster

---

## 翻译场景专用查询策略

### 策略 1: 翻译前理解（Understand Before Translate）

**目的:** 翻译一个函数/模块前，先完整理解其上下游关系

```
# 用一次 codegraph_explore 获取完整上下文
codegraph explore "how does <function_name> work and what calls it"

# 结果包含：
# - 函数完整源码
# - 调用链（谁调用它，它调用谁）
# - 相关类型定义
# - 接口实现
```

**替代的低效做法（不要做）:**
```
grep -r "function_name" .  # 第 1 次 tool call
Read file_a.go             # 第 2 次
Read file_b.go             # 第 3 次
grep -r "TypeX" .          # 第 4 次
Read file_c.go             # 第 5 次
```

**节省:** 5+ tool calls → 1 tool call

### 策略 2: 依赖图构建（Dependency Graph）

**目的:** 确定模块翻译顺序（叶子优先）

```
# 查看模块的所有依赖
codegraph impact <module_entry_point>

# 查看谁依赖这个模块
codegraph callers <exported_function>
```

**用于 Wave 规划:**
- impact 小的模块 = 叶子模块 → 先翻译
- callers 多的模块 = 核心模块 → 后翻译

### 策略 3: 翻译验证（Verify Completeness）

**目的:** 确认翻译覆盖了所有调用路径

```
# 在源项目中查看某个接口的所有实现
codegraph explore "all implementations of <trait/interface>"

# 在目标项目中验证对应的 Rust trait 实现
codegraph callers <rust_trait_name>
```

**检查清单:**
- [ ] 源项目中 N 个 callers → Rust 项目中也有 N 个 callers
- [ ] 源项目中的 impact 范围 ⊆ Rust 项目的 impact 范围

### 策略 4: 跨模块翻译一致性

**目的:** 翻译模块 B 时，确认与已翻译的模块 A 接口兼容

```
# 查看模块 A 暴露的接口被哪些地方使用
codegraph callers <module_a_public_fn>

# 查看调用点的完整上下文（确认参数/返回类型）
codegraph node <caller_function>
```

---

## 工具选择决策树

```
翻译中需要了解代码
├── "X 怎么工作？" / "从 A 到 B 的流程" → codegraph_explore（首选）
├── "谁调用了 X？" → codegraph_callers
├── "X 的完整源码 + 上下文" → codegraph_node
├── "查找名为 X 的符号" → codegraph_search
├── "改 X 会影响什么？" → codegraph impact (CLI)
└── 以上都不适用 → 退回传统 grep/Read
```

## 关键规则

### R1: CodeGraph First
任何代码探索，优先尝试 CodeGraph。
只有在 CodeGraph 无法回答时（动态分发、反射、未索引的代码）才使用 grep/Read。

### R2: 信任结果，不重复验证
CodeGraph 返回的源码就是文件内容（自动同步）。
不要用 Read 重新读取同一个文件——这是浪费 token。

### R3: 翻译前必查调用图
翻译任何非叶子函数前，先用 `codegraph_callers` 确认所有调用者。
这确保翻译后的签名不会破坏已有代码。

### R4: 两侧对照查询
翻译完一个模块后，在目标项目也运行相同的 CodeGraph 查询。
对比源/目标的结构差异，快速发现遗漏。

---

## 与翻译工作流的集成

| 翻译阶段 | CodeGraph 用法 | 替代多少 tool calls |
|---------|---------------|-------------------|
| Phase 0: 项目分析 | `codegraph_explore` 理解架构 | 替代 10-20 次 grep+Read |
| Phase 1: 依赖排序 | `codegraph impact` 确定叶子 | 替代手动追踪依赖 |
| Phase 2: 逐函数翻译 | `codegraph_node` 获取完整上下文 | 替代 3-5 次 Read |
| Phase 2: 接口验证 | `codegraph_callers` 检查调用方 | 替代 grep + 逐文件检查 |
| Phase 3: 集成验证 | 两侧 `codegraph_explore` 对比 | 替代大量手动对比 |

---

## Token 节省估算

基于 CodeGraph 官方 benchmark（7 个真实项目）：

| 项目规模 | 无 CodeGraph | 有 CodeGraph | 节省 |
|---------|-------------|-------------|------|
| 小型 (~100 文件) | ~850k tokens/问题 | ~650k tokens | ~23% |
| 中型 (~650 文件) | ~1.1M tokens/问题 | ~500k tokens | ~54% |
| 大型 (~3000 文件) | ~1.4M tokens/问题 | ~560k tokens | ~60% |
| 超大型 (~10000 文件) | ~1.8M tokens/问题 | ~640k tokens | ~64% |

**对翻译项目的预估:**
- 每个模块翻译涉及 ~10 次代码探索
- 无 CodeGraph: ~10M tokens/模块（探索密集）
- 有 CodeGraph: ~5M tokens/模块（节省 ~50%）
- 42 模块项目: 节省约 **210M tokens** ≈ 数百美元
