# 翻译工作流定义

## 工作流状态机

```
[未开始] → [分析中] → [初始化] → [翻译中] → [验证中] → [完成]
                                      ↑          |
                                      └── [诊断中] ←┘
```

## 状态转移条件

| 当前状态 | 触发条件 | 下一状态 |
|---------|---------|---------|
| 未开始 | 用户提供源项目路径 | 分析中 |
| 分析中 | 分析报告生成完成 | 初始化 |
| 初始化 | Rust 骨架 + 状态文件就绪 | 翻译中 |
| 翻译中 | 当前 Wave 所有模块翻译完成 | 验证中 |
| 验证中 | parity + E2E 全部通过 | 翻译中（下一 Wave）或 完成 |
| 验证中 | 存在失败 | 诊断中 |
| 诊断中 | 问题定位并修复 | 验证中 |
| 翻译中 | 所有模块完成 + 最终验证通过 | 完成 |

## Wave 执行详细流程

### Step 1: Wave 规划
```
输入: translation-state.jsonc（当前进度）
输出: wave-plan（本 Wave 要翻译的模块列表）

算法:
1. 从依赖图中找出所有"就绪"模块（依赖已全部翻译完成）
2. 按难度排序（Easy 优先）
3. 取前 3-5 个作为本 Wave
4. 确保模块间无循环依赖
```

### Step 2: 模块翻译（每个模块）
```
2.1 接口翻译
    - 提取 public API（类型 + 函数签名）
    - 翻译为 Rust traits + types
    - 确保与已翻译模块的接口兼容
    
2.2 实现翻译
    - 逐函数翻译
    - 应用语言特定技能（go2rust/c2rust）
    - 标记不确定的翻译为 PLACEHOLDER
    
2.3 测试翻译
    - 翻译对应的单元测试
    - 确保测试覆盖率 ≥ 源代码
    - 新增 Rust 特有测试（如边界检查）
    
2.4 编译验证
    - cargo check（类型正确）
    - cargo clippy（惯用性）
    - cargo test（功能正确）
```

### Step 3: Wave 验证
```
3.1 Parity Check
    - 对每个翻译模块运行四层等价性检查
    - 结构等价: API 签名匹配
    - 功能等价: 单元测试全部通过
    - 接口等价: 与其他模块交互正确
    - 行为等价: 端到端行为一致

3.2 E2E 验证
    - 运行端到端场景
    - 对比源项目和 Rust 项目的输出
    - 记录差异
    
3.3 回归检查
    - 确保之前 Wave 的模块仍然通过
    - 检查新翻译是否引入回归

3.4 覆盖率差距分析（AP-011 强制）
    - 列出源项目所有测试函数
    - 检查每个是否有对应的 Rust 测试
    - 缺失的 = 必须在下一 Wave 前补齐
    - 特别关注：GC 测试、多扇区边界测试、reboot 持久化测试

3.5 C Oracle 差分测试（Wave 1 后首次建立）
    - 编译 C 源项目，确认 Oracle 可用
    - 建 C Oracle 程序（basic CRUD + GC + multi-sector + reboot）
    - 写 Rust diff tests，解析 C 输出，比对结果
    - 标记 #[ignore]，用 cargo test -- --ignored 运行
    - 差分测试失败 = 行为不等价，必须修复
```

### Step 4: 状态更新
```
4.1 更新 translation-state.jsonc
    - 模块状态: pending → translated → verified
    - 等价性分数
    - 发现的问题
    
4.2 更新 decisions.md
    - 记录翻译决策
    - 记录遇到的问题和解决方案
    
4.3 触发自我改进
    - 分析本 Wave 的翻译模式
    - 更新技能文件（如果发现新模式）
```

## 恢复协议

每次新会话开始时：

```
1. 读取 translation-state.jsonc
2. 确定最后完成的 Wave
3. 检查是否有未完成的 Wave
   - 如有: 继续该 Wave
   - 如无: 规划新 Wave
4. 检查是否有未解决的诊断问题
   - 如有: 优先解决
5. 显示当前进度摘要
```

## 错误恢复

### 编译错误
```
1. 定位错误源（通常是类型不匹配）
2. 检查 type-mapping（是否映射遗漏）
3. 检查上下文（是否跨模块接口不一致）
4. 修复并重新验证
```

### 测试失败
```
1. 对比源测试和 Rust 测试的输入/输出
2. 检查行为差异（零值、错误处理、并发）
3. 判断是翻译错误还是行为差异
4. 修复翻译 或 记录为有意差异（需决策记录）
```

### E2E 失败
```
1. 触发 e2e-debugger 技能
2. 缩小故障范围（二分法）
3. 定位到具体模块/函数
4. 修复并重新运行完整 E2E
5. 记录失败模式到反模式库
```

## 并行策略

对于大型项目（> 50 模块），支持并行翻译：
- Wave 内的独立模块可并行翻译
- 不同 Agent 负责不同模块
- 通过 translation-state.jsonc 同步状态
- 合并时检查接口一致性

## 自主模式

当用户给出源项目路径并要求翻译时，系统进入自主模式。全程不问用户，直到最终验证通过。

### 自主模式触发

用户说：
- "帮我把 /path/to/project 翻译成 Rust"
- "把这个 C 项目用 Rust 重写"
- "迁移 /path/to/source 到 Rust"

### 自主模式流程

```
用户给路径
  ↓
Phase 0: 检测与初始化
  ├─ 检测源语言 → 加载 c2rust/go2rust
  ├─ 运行 init 脚本 → 创建 Rust 骨架
  ├─ 运行 analyze → source-inventory.md
  ├─ 尝试编译 C 源 → 确认 Oracle 可用性
  └─ 自动确认 acceptance-plan.yaml
  ↓
Phase 1: 规划
  ├─ 拓扑排序 → 叶子优先
  └─ 写 wave-001.md
  ↓
Phase 2: 翻译循环 [每个 Wave]
  ├─ 逐模块翻译（接口→实现→测试→验证）
  ├─ 每模块完成后: cargo fmt + check + test
  ├─ 每模块最多 3 轮修复
  ├─ Wave 完成后:
  │   ├─ unsafe_audit + forbid-placeholders
  │   ├─ 覆盖率差距分析（AP-011）
  │   ├─ 补齐缺失测试
  │   └─ 更新 translation-state + decisions
  ├─ Wave 1 后: 建 C Oracle + diff tests
  └─ 下一 Wave
  ↓
Phase 3: 最终验证
  ├─ 全部 C Oracle（basic + GC + multi-sector + reboot）
  ├─ 全部 diff tests vs C Oracle
  ├─ final_verify.sh
  ├─ rustdoc 全部公开 API
  ├─ 更新 README + reports
  └─ 输出完成报告
```

### 自主模式默认决策

| 原本需要问用户的问题 | 自动决策 |
|---|---|
| 翻译范围 | src/ + tests/ |
| E2E 何时跑 | 第一个模块后立即 |
| WRITE_GRAN | 检测 C 源定义，默认 1 |
| 文件模式 | 检测 C 源 #define，有则启用 |
| Oracle 模式 | C 可编译→run-source；否则→static-codegraph |
| unsafe 阈值 | 10% |
| 并行翻译 | Wave 内独立模块可并行 |
| 设计歧义 | 选更 Rust-idiomatic 的方案，记录到 decisions.md |

### 自主模式失败恢复

| 失败 | 处理 |
|---|---|
| 编译错误 | 读 error stack → 精准修补 → 最多 3 轮 |
| 3 轮失败 | 缩小翻译范围 → 拆分模块重试 |
| 测试失败 | 对比 C 预期 → 修复 → 最多 3 轮 |
| 3 轮测试失败 | 回退到上一通过状态 → 缩范围 |
| C Oracle 编译失败 | 降级到 static-codegraph Oracle |
| Deep agent 超时 | AP-005: 先 probe 代码状态 |
| 同模块 3 个 Wave 都失败 | **暂停，报告用户** |

### 自主模式唯一升级条件

只有以下情况暂停并报告用户（其余全部自动处理）：
1. 源项目无法编译且无法降级 Oracle
2. 同一模块连续 3 个 Wave 失败
3. 发现源代码本身有 bug
