# CodeGraph 集成指南 — 翻译场景下的准确性 × 效率优化

## 概述

[CodeGraph](https://github.com/colbymchenry/codegraph) 是一个预索引的代码知识图谱工具，通过 MCP (Model Context Protocol) 为 AI Agent 提供符号关系查询能力。在源码翻译场景中，它解决两个核心问题：

1. **准确性** — 翻译前获得完整的调用图和依赖关系，避免遗漏或错误翻译
2. **Token 效率** — 用单次图查询替代多次 grep/Read 暴力搜索，减少 ~50% token 消耗

---

## 安装与配置

### 第一步：安装 CodeGraph CLI

```bash
# macOS / Linux（推荐，无需 Node.js）
curl -fsSL https://raw.githubusercontent.com/colbymchenry/codegraph/main/install.sh | sh

# 或通过 npm
npm i -g @colbymchenry/codegraph
```

### 第二步：配置 Agent 连接

```bash
codegraph install
```

此命令会自动检测已安装的 Agent（Claude Code、Cursor、Codex、OpenCode 等），
并配置 MCP Server 连接。

### 第三步：初始化项目索引

```bash
# 对源项目建索引（Go/C 项目）
cd /path/to/source-project
codegraph init

# 对目标项目建索引（Rust 项目）
cd /path/to/target-rust-project
codegraph init
```

### 验证安装

```bash
codegraph status
```

应输出类似：
```
Index Statistics:
  Files:     853
  Nodes:     28,482
  Edges:     42,991
```

---

## 工作原理

```
┌─────────────────────────────────┐
│         AI Agent (翻译器)        │
│   "翻译 processRequest 函数"     │
│                │                 │
│   以前:                          │
│   grep → Read → grep → Read...  │ ← 5-20 次 tool calls
│                │                 │
│   现在:                          │
│   codegraph_explore             │ ← 1 次 tool call
└────────────────┬────────────────┘
                 │
                 ▼
┌─────────────────────────────────┐
│      CodeGraph MCP Server        │
│                                  │
│   SQLite 知识图谱（自动同步）     │
│   symbols + edges + FTS5         │
│                                  │
│   返回：完整源码 + 调用链         │
│   + 类型定义 + 影响范围           │
└─────────────────────────────────┘
```

### 核心能力

| 能力 | 说明 | 翻译场景用途 |
|------|------|------------|
| **符号搜索** | 全文检索所有符号 | 定位待翻译的函数/类型 |
| **代码探索** | 一次返回完整上下文 | 理解函数行为后再翻译 |
| **调用者查询** | 谁调用了这个函数 | 确保翻译不破坏调用方 |
| **被调用查询** | 这个函数调用了什么 | 确认依赖已翻译 |
| **影响分析** | 改变 X 会影响什么 | 评估翻译顺序和风险 |
| **自动同步** | 文件变化 2s 内更新索引 | 翻译过程中索引保持新鲜 |

---

## 翻译中的使用策略

### 策略 A：翻译前理解（最重要）

> **原则：不理解就不翻译**

```bash
# 1. 用一次查询获取函数的完整上下文
codegraph explore "how does processRequest work"
# 返回：函数源码 + 调用链 + 类型定义 + 依赖关系

# 2. 理解后再翻译
# Agent 现在有完整信息，可以做出正确的翻译决策
```

**为什么这提升准确性：**
- 看到所有 callers → 知道返回类型不能随意改变
- 看到所有 callees → 知道依赖是否已翻译
- 看到相关类型 → 知道泛型/trait 的正确设计

### 策略 B：依赖图驱动的翻译顺序

```bash
# 找出叶子模块（没有项目内依赖的）
codegraph impact <module_entry>
# impact 小 → 叶子 → 先翻译

# 找出核心模块（被大量依赖的）
codegraph callers <public_api>
# callers 多 → 核心 → 后翻译
```

### 策略 C：翻译后验证完整性

```bash
# 源项目中查看接口的所有实现者
codegraph explore "implementations of StorageBackend interface"

# 翻译后在 Rust 项目中验证
codegraph callers StorageBackend  # 确认所有 impl 都有
```

### 策略 D：两侧对照（源 vs 目标）

翻译完一个模块后，在两侧运行相同查询，对比：
- 函数数量是否一致
- 调用关系是否保留
- 公开 API 是否完整

---

## 在 Transpilot 中的位置

```
Transpilot 工具链
├── codegraph-navigator  ← 基础层：代码理解（新增）
├── translator           ← 驱动层：协调流程
├── go2rust / c2rust     ← 翻译层：语言特定模式
├── parity-checker       ← 验证层：等价性检查
├── e2e-debugger         ← 诊断层：失败定位
└── self-improving       ← 进化层：经验积累
```

**CodeGraph 作为基础层**，被所有其他技能调用：
- `translator` 用它做项目分析和依赖排序
- `go2rust`/`c2rust` 用它理解源代码
- `parity-checker` 用它对比两侧结构
- `e2e-debugger` 用它追踪调用路径定位问题

---

## 效果量化

### Benchmark 数据（来自 CodeGraph 官方，7 个真实项目）

| 指标 | 平均改善 |
|------|---------|
| Token 消耗 | **-47%** |
| Tool 调用次数 | **-58%** |
| 耗时 | **-22%** |
| 成本 | **-16%** |

### 对翻译项目的预估影响

| 场景 | 无 CodeGraph | 有 CodeGraph | 节省 |
|------|-------------|-------------|------|
| 模块分析（理解架构） | 10-20 次 grep+Read | 1 次 explore | ~90% calls |
| 函数翻译（获取上下文） | 3-5 次 Read | 1 次 node | ~70% calls |
| 接口验证（检查调用方） | 5-10 次 grep | 1 次 callers | ~85% calls |
| 依赖排序（确定顺序） | 手动遍历 | 1 次 impact | ~95% calls |

### 准确性提升

| 问题类型 | 无 CodeGraph 时的风险 | 有 CodeGraph 后 |
|---------|---------------------|----------------|
| 遗漏调用者 | grep 可能漏掉间接调用 | callers 返回完整列表 |
| 类型理解不全 | 只读到部分定义 | explore 返回关联类型 |
| 接口实现遗漏 | 不知道有多少实现 | 完整 implementations |
| 影响范围低估 | 不知道改动波及范围 | impact 精确分析 |

---

## 限制与补充

CodeGraph 基于静态分析（tree-sitter），以下场景需要补充手段：

| 限制 | 表现 | 补充手段 |
|------|------|---------|
| 动态分发 | 反射/运行时接口查找不在图中 | grep + 运行时日志 |
| 宏展开 | C 宏展开后的符号可能缺失 | 预处理后索引 |
| 代码生成 | codegen 的代码可能未索引 | 先生成再索引 |
| 泛型实例化 | 具体类型实例不在图中 | 类型推断 + 测试验证 |

**建议:** CodeGraph 覆盖 ~85-95% 的静态代码关系，
剩余 5-15% 通过传统手段补充。
对于翻译场景，这个覆盖率已经能大幅提升效率。

---

## OpenSpec 变更治理集成

CodeGraph 与 OpenSpec 在翻译流程中协同工作：

```
┌─────────────────────────────────────────────────────────┐
│                  翻译完整工作流                            │
│                                                          │
│  /opsx-propose ──→ CodeGraph 分析 ──→ design.md          │
│       │                                                  │
│       ▼                                                  │
│  /opsx-apply ───→ codegraph_explore ──→ 翻译 ──→ 验证    │
│       │                (每个任务)                         │
│       ▼                                                  │
│  /opsx-archive ─→ 更新 state + decisions                 │
│       │                                                  │
│       ▼                                                  │
│  /opsx-sync ────→ 更新组件 spec                          │
└─────────────────────────────────────────────────────────┘
```

### OpenSpec 四个阶段

| 阶段 | 命令 | CodeGraph 协助 |
|------|------|---------------|
| 提案 | `/opsx-propose` | `codegraph impact` 分析范围，生成 design.md |
| 执行 | `/opsx-apply` | `codegraph_explore` 理解每个任务的完整上下文 |
| 归档 | `/opsx-archive` | `codegraph_callers` 验证完整性后归档 |
| 同步 | `/opsx-sync` | 更新 specs/ 中的组件状态 |

### Wave 模式 + CodeGraph = 最优翻译顺序

```bash
# 1. 用 CodeGraph 分析依赖图
codegraph impact <component_entry>

# 2. 基于依赖图规划 Wave
#    impact 小 = 叶子 = Wave 1
#    impact 大 = 核心 = 后续 Wave

# 3. 为每个 Wave 创建 OpenSpec 提案
/opsx-propose <component>-wave-1

# 4. 执行时每个任务前都用 CodeGraph
/opsx-apply  # → codegraph_explore → translate → verify
```

### 为什么两者结合

- **CodeGraph** 解决"理解代码"问题（准确性 + 效率）
- **OpenSpec** 解决"管理进度"问题（可追踪性 + 可恢复性）
- 两者结合 = 大规模翻译项目不失控

详细 OpenSpec 工作流见：`.agents/skills/shared/openspec-workflow.md`

---

## 最佳实践总结

1. **每次翻译会话开始时** — 用 `codegraph status` 确认索引新鲜
2. **翻译任何函数前** — 先 `codegraph_explore` 理解完整上下文
3. **修改接口后** — 用 `codegraph_callers` 检查所有调用方
4. **Wave 规划时** — 用 `codegraph impact` 确定翻译顺序
5. **验证阶段** — 两侧 `codegraph_explore` 对比结构一致性
6. **信任结果** — 不要对 CodeGraph 返回的代码再 Read 一次

---

## 配置参考

### Qoder MCP 配置（已通过 `codegraph install` 自动完成）

```jsonc
// 通常位于 ~/.config/qoder/mcp.json 或项目级配置
{
  "mcpServers": {
    "codegraph": {
      "type": "stdio",
      "command": "codegraph",
      "args": ["serve", "--mcp"]
    }
  }
}
```

### 环境变量（可选调优）

| 变量 | 说明 | 默认值 |
|------|------|-------|
| `CODEGRAPH_WATCH_DEBOUNCE_MS` | 文件变更后等待多久再同步 | 2000 |
| `CODEGRAPH_NO_DAEMON` | 禁用后台守护进程 | 0 |
| `CODEGRAPH_MCP_TOOLS` | 启用的 MCP 工具列表 | explore,node,search,callers |
| `CODEGRAPH_TELEMETRY` | 匿名遥测 | 1 (开启) |

---

## 总结

CodeGraph 为 Transpilot 翻译工具链提供了**代码理解的基础设施层**：

- **准确性:** 完整的调用图确保翻译不遗漏、不破坏
- **效率:** ~50% token 节省，~58% 更少的 tool calls
- **实时性:** 自动同步确保索引永远新鲜
- **零配置:** 安装后开箱即用，支持 Go/Rust/C 等 20+ 语言

将它作为 `codegraph-navigator` 技能集成到 Transpilot，使整个翻译流程既准确又经济。
