# Skill Cookbook：编写高质量的翻译 Skill

> 目标读者：想为 Transpilot 添加新 skill 或定制现有 skill 的开发者
> 核心理念：**SKILL.md 是索引，不是手册**

---

## 1. Skill 是什么

Skill = **触发条件 + 决策树 + 关键规则** 的最小可执行单元。
它不是文档，不是教程，**它是 AI 在某种场景下被自动调用的入口**。

一个好 skill 应该：
- 在合适的时机自动被 AI 选中（靠 frontmatter `description`）
- 让 AI 在 30 秒内读完并知道下一步（靠 ≤40 行的 SKILL.md）
- 详细规则按需展开（靠 reference.md）

---

## 2. 目录结构（黄金模板）

```
.agents/skills/<skill-name>/
├── SKILL.md            # ≤40 行，必读索引
├── reference.md        # 详细规则、示例（按需加载）
├── patterns/           # 可复用代码片段（可选）
│   └── <pattern>.md
└── examples/           # 完整案例（可选）
    └── <case>.md
```

**铁律**：
- SKILL.md ≤40 行
- 单个 reference.md ≤300 行
- 超过 300 行就拆 patterns/ 或 examples/

---

## 3. SKILL.md 的 5 个必备区块

### 3.1 Frontmatter（触发器）
```yaml
---
name: parity-checker
description: 翻译完成后验证行为对齐 — 当 cargo test 通过但需要确认与源项目语义一致时触发
prerequisites:
  - codegraph 已索引源/目标项目
  - 源项目可编译运行（用于行为对照）
---
```

**关键**：`description` 决定 AI 何时**自动**调用此 skill。
- ❌ 模糊：`description: 验证翻译质量`
- ✅ 精准：`description: 翻译完成后验证行为对齐 — 当 cargo test 通过但需要确认与源项目语义一致时触发`

### 3.2 何时使用（场景边界）
```markdown
## 何时使用
- 模块翻译完成、cargo test 全绿后
- 需要量化 parity 数值供 status-dashboard 展示
- 不用于：编译错误诊断（用 e2e-debugger）
```

明确"用"和"不用"两面，避免 AI 错调。

### 3.3 决策树（最核心）
```markdown
## 工具选择
- "X 怎么工作？" → codegraph_explore（首选）
- "谁调用了 X？" → codegraph_callers
- 以上不适用 → 退回 grep/Read
```

决策树一定是 **input → output** 的映射，不是 step-by-step 教程。

### 3.4 关键规则（3-5 条不可违反）
```markdown
## 关键规则
1. CodeGraph First — 任何探索优先用图查询
2. 信任结果 — 不要对返回的源码再 Read 一次
3. 翻译前必查 — 非叶子函数先 codegraph_callers
```

**控制在 3-5 条**。每多一条，AI 遵守的概率下降。

### 3.5 详细参考（按需加载入口）
```markdown
## 详细参考
- 查询策略与示例 → reference.md
- 安装配置 → ../../docs/codegraph-integration.md
```

---

## 4. 写好 description 的 3 个套路

`description` 决定 AI 何时自动激活 skill，是 frontmatter 中**最重要**的字段。

### 套路 1：场景 + 触发词
> "当 cargo test 通过但需要确认与源项目语义一致时触发"

包含：领域（cargo test）+ 状态（通过）+ 目的（语义一致）。

### 套路 2：负向排除
> "用于翻译完成后的对齐校验，不用于诊断编译错误（见 e2e-debugger）"

显式说明"不是什么"，避免 AI 在错场景调它。

### 套路 3：量化指标
> "节省 ~50% token，替代 5-20 次 grep/Read"

带数字的描述会让 AI 在 token 紧张时优先选你。

---

## 5. reference.md 的写法

reference.md 是 **AI 决定深入时才读**的二级文档。它应该：

- 包含完整的代码示例
- 包含边界场景的处理方式
- 包含与其他 skill 的协作模式
- **不重复** SKILL.md 的内容

### reference.md 模板
```markdown
# <skill-name> 详细参考

## 1. 完整查询示例
<具体的 input → output 案例>

## 2. 边界场景
- 当 X 时：...
- 当 Y 时：...

## 3. 与其他 skill 协作
- 与 translator：...
- 与 e2e-debugger：...

## 4. 常见错误与修复
- 错误 A → 修复 B
```

---

## 6. patterns/ 与 examples/ 的区分

| 目录 | 内容 | 大小 | 何时读 |
|------|------|------|--------|
| `patterns/` | 可复用代码片段 | 各 ~50 行 | 翻译时套用 |
| `examples/` | 完整案例 | 各 100-300 行 | 学习时参考 |

**示例**：
- `patterns/go-channel-to-tokio-mpsc.md` — 一种语言特性的标准翻译
- `examples/translate-deployment-controller.md` — 一个完整模块从 0 到 100% parity

---

## 7. 7 条踩坑总结

### 坑 1：SKILL.md 写成长文档
**症状**：SKILL.md 100+ 行，AI 每次激活都吞大量 token。
**修复**：搬到 reference.md，SKILL.md 只留索引。

### 坑 2：description 写成"功能介绍"
**症状**：`description: 这是一个翻译工具`
**修复**：写"何时被触发"，不写"它能做什么"。

### 坑 3：决策树写成步骤列表
**症状**：`Step 1: 读文件; Step 2: 分析; Step 3: 输出`
**修复**：改成 `场景 X → 工具 A`，让 AI 跳过不相关步骤。

### 坑 4：规则超过 5 条
**症状**：列了 12 条 best practices。
**修复**：合并/删除，最多 5 条。次要规则进 reference.md。

### 坑 5：没声明 prerequisites
**症状**：AI 在缺工具的环境调用，失败后无法理解。
**修复**：frontmatter 加 prerequisites，AI 会先校验。

### 坑 6：skill 之间互相不知道
**症状**：translator 不知道 parity-checker 存在。
**修复**：在 SKILL.md 末尾加 "Related Skills" 链接。

### 坑 7：忘记更新 reference 时的索引
**症状**：reference.md 改了但 SKILL.md 还指向旧章节。
**修复**：每次改 reference.md 都同步检查 SKILL.md。

---

## 8. 编写新 skill 的 5 步流程

```
Step 1: 在 .agents/skills/ 下建目录
        mkdir -p .agents/skills/<name>/{patterns,examples}

Step 2: 写 SKILL.md（先写 frontmatter description）
        — 反复打磨 description 直到能精准触发

Step 3: 写决策树和 3-5 条关键规则
        — SKILL.md 控制在 40 行内

Step 4: 把详细内容搬进 reference.md
        — 不与 SKILL.md 重复

Step 5: 在 skills-lock.json 注册
        — 让 AI 知道有这个 skill
```

---

## 9. Skill 质量自检清单

发布新 skill 前过一遍：

- [ ] SKILL.md ≤40 行
- [ ] frontmatter `description` 包含触发场景而非功能描述
- [ ] 列了明确的"何时使用"和"何时不使用"
- [ ] 决策树是 input → output 形式，不是 step list
- [ ] 关键规则 ≤5 条
- [ ] 声明了 `prerequisites`
- [ ] 链接到 reference.md 和相关 skill
- [ ] reference.md 没有重复 SKILL.md 内容
- [ ] 在 skills-lock.json 注册

---

## 10. 高质量 skill 范例

参考 transpilot 自带：
- 索引模板：[`.agents/skills/codegraph-navigator/SKILL.md`](../.agents/skills/codegraph-navigator/SKILL.md)
- 决策树模板：[`.agents/skills/translator/SKILL.md`](../.agents/skills/translator/SKILL.md)
- reference 模板：[`.agents/skills/parity-checker/reference.md`](../.agents/skills/parity-checker/reference.md)

---

## 11. 下一步

- 入门见 [GETTING_STARTED.md](./GETTING_STARTED.md)
- 自驱见 [harness-autonomous.md](./harness-autonomous.md)
- 项目治理见 [codegraph-integration.md](./codegraph-integration.md)
