# 新手教程：从 0 到 1 翻译一个项目

> 目标读者：第一次使用 Transpilot 的开发者
> 完成时间：~30 分钟（不含实际翻译耗时）

本教程以将一个 Go 项目翻译为 Rust 为例，演示完整流程。

---

## Step 0: 前置环境准备

### 0.1 安装 Rust 工具链
```bash
curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh
rustup default stable
cargo --version  # 应输出 cargo 1.7x.x 或更新
```

### 0.2 安装 CodeGraph（必须）
```bash
# macOS / Linux
curl -fsSL https://raw.githubusercontent.com/colbymchenry/codegraph/main/install.sh | sh

# 配置到 AI Agent（自动检测 Claude Code/Cursor/Codex/OpenCode）
codegraph install

# 验证
codegraph version
```

### 0.3 克隆 Transpilot
```bash
git clone https://github.com/thyzfmh/transpilot.git ~/transpilot
cd ~/transpilot
./scripts/transpilot install
```

---

## Step 1: 初始化翻译项目

假设你要翻译 `/path/to/myapp-go`（Go 源项目）到 `/path/to/myapp-rs`（Rust 目标）。

```bash
cd ~/transpilot
./scripts/transpilot init /path/to/myapp-go /path/to/myapp-rs --name myapp
```

**这一步会自动:**
- 创建 Rust workspace 骨架（`Cargo.toml`、`src/`）
- 在目标项目中通过 symlink 挂载 `.agents/skills/`
- 创建 `.opencode/translation-state.jsonc`（状态文件）和 `decisions.md`（决策日志）
- 创建 `acceptance-plan.yaml`（T0 验收方案）
- 写入 `AGENTS.md`（Agent 指令）和 `.gitignore`
- 初始化 git 仓库

**验证初始化成功:**
```bash
cd /path/to/myapp-rs
ls -la .agents/skills    # 应该看到 symlink
cat .opencode/translation-state.jsonc | head -20
```

---

## Step 2: 确认验收边界

```bash
./scripts/transpilot acceptance review
```

检查 `scope.in/out`、`oracle_primary`、`e2e_command` 和 must-pass 用例。确认风险后运行：

```bash
./scripts/transpilot acceptance confirm
```

未确认前，`transpilot run` 和自驱 harness 都会拒绝启动。

---

## Step 3: 为源项目和目标项目建立 CodeGraph 索引

```bash
# 源项目（Go）
cd /path/to/myapp-go
codegraph init && codegraph index

# 目标项目（Rust，初始很小）
cd /path/to/myapp-rs
codegraph init && codegraph index

# 验证
codegraph status  # 应显示 nodes/edges 数量
```

> CodeGraph 之后会自动同步——文件变化 2s 内更新索引，无需手动操作。

---

## Step 4: 用 AI 进行架构分析（首次）

在 IDE（Claude Code/Cursor/Qoder/OpenCode 等）中打开 `/path/to/myapp-rs`，先运行分析：

```bash
./scripts/transpilot analyze /path/to/myapp-go
```

如果只想翻译部分功能，带上目标和范围：

```bash
./scripts/transpilot analyze /path/to/myapp-go \
  --goal "只迁移配置解析模块" \
  --scope "pkg/config,internal/parser"
```

**Agent 会自动:**
1. 读 `translation-state.jsonc` 恢复上下文
2. 把分析结果同步给你，并询问 scope / Oracle / E2E
3. 用 `codegraph_explore` 分析源项目（**1 次 MCP 调用** 替代几十次 grep）
4. 用 `codegraph impact` 计算依赖图
5. 输出 Wave 计划：哪些模块先翻译、哪些后翻译

**预期输出（示例）:**
```
分析完成：
- 源项目共 23 模块，~12000 行 Go 代码
- 叶子模块（无内部依赖）: util, errors, config (Wave 1)
- 中间层: storage, transport (Wave 2)
- 核心层: server, controller (Wave 3, 4)
- 入口: main, cmd (Wave 5)

预估 5 个 Wave 完成，每 Wave 约 4-5 模块。
```

---

## Step 5: 创建第一个 Wave 提案

```
请为 Wave 1 创建 OpenSpec 提案。
```

Agent 会执行 `/opsx-propose`，生成：
- `openspec/changes/myapp-wave-1/proposal.md` — 范围说明
- `openspec/changes/myapp-wave-1/design.md` — 技术决策（基于 CodeGraph 分析）
- `openspec/changes/myapp-wave-1/tasks.md` — 可执行任务清单

**审阅 design.md** — 这是你介入的重要节点。检查：
- 类型映射是否合理（如 `goroutine` → `tokio` 还是 `thread`？）
- 重大权衡是否符合预期
- 不合理的地方直接编辑 design.md 修改

---

## Step 6: 执行翻译

```
按 tasks.md 执行 Wave 1。
```

Agent 会逐任务执行：
```
任务 1/5: util 模块翻译
  - codegraph_explore "util module structure"
  - 翻译为 Rust（应用 go2rust skill）
  - cargo check ✓
  - cargo test ✓
  - 标记任务完成
任务 2/5: errors 模块翻译
  ...
```

**这阶段不需要你介入**，除非：
- AI 主动报告"需要决策"（设计歧义）
- AI 报告"卡住了"（外部依赖缺失）
- 你看到 AI 走偏了想干预

---

## Step 7: 验证 Wave

```
运行 Wave 1 验证。
```

Agent 加载 `parity-checker` skill 执行四层验证：
- **结构层**: API 签名匹配
- **功能层**: `cargo test` 全部通过
- **接口层**: 调用方兼容
- **行为层**: 关键测试输出一致

**通过后**: 自动归档（`/opsx-archive`）+ 同步规格（`/opsx-sync`）+ 更新 state。

**Wave 1 特殊要求**: 第一个 Wave 必须建立 E2E 框架。Agent 会创建一个最小可运行路径并验证。

---

## Step 8: 重复 Step 5-7 直到完成

```
继续下一个 Wave。
```

Agent 会从 `translation-state.jsonc` 读取进度，自动开始 Wave 2。

**会话中断了不怕** — 下次会话发"继续翻译"，Agent 会读 state 文件恢复。

---

## Step 9: 最终验收

所有 Wave 完成后：

```bash
# 查看进度仪表盘（在翻译项目根目录执行）
./scripts/parity-report.sh summary     # 总览
./scripts/parity-report.sh full        # 总览 + 风险评估
./scripts/parity-report.sh module foo  # 单模块详情
./scripts/parity-report.sh wave 3      # 单 wave 详情
```

**输出示例:**
```
=== Transpilot Progress Report ===
Project: myapp
Language: go → rust
Current Wave: wave-5
Overall Parity: 96.8%
Modules: 23 total
  Verified:    23 (100.0%)
  Translated:  0
  In Progress: 0
  Pending:     0
  Blocked:     0
- 占位符 (todo!): 0 ✓
- unsafe 比例: 1.2% (预算 5%)

✅ 准备验收
```

此时你接手做最终验收：
- 跑你自己的端到端业务测试
- review `decisions.md` 看 AI 做的关键决策
- review `openspec/changes/archive/` 看每个 Wave 的过程

---

## 常见问题

### Q1: AI 卡住不动了怎么办？
检查 `translation-state.jsonc` 的 `blockers` 字段。如果有内容，按提示解决（通常是依赖缺失或决策歧义）。

### Q2: 翻译结果不对怎么改？
- 编辑 Rust 代码（CodeGraph 会自动重索引）
- 在 `decisions.md` 记录新决策
- 让 Agent 更新 `self-improving` 模式库（避免下次犯同样错误）

### Q3: 想看 AI 做了什么决策？
全部记录在 `decisions.md`，每条决策都有：日期、组件、问题、决策、理由、影响。

### Q4: Token 消耗太大？
检查是否启用了 CodeGraph（`codegraph status`）。没有的话，AI 会用 grep 暴力搜索，耗 token。

---

## 下一步

- [Harness 自驱指南](harness-autonomous.md) — 让 AI 端到端跑完，最少干预
- [Skill Cookbook](skill-cookbook.md) — 各技能的实战调用示例
- [CodeGraph 集成详解](codegraph-integration.md) — 深入理解 CodeGraph 用法
