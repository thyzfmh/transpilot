---
name: parity-checker
description: 四层等价性验证器 — 确保翻译后的 Rust 代码与源代码行为一致
---

# 等价性验证器 (Parity Checker)

## 概述

验证翻译后的 Rust 代码与源语言代码在四个层面保持等价。
从 Taibai 项目的实战中提炼：99.5% parity 目标需要严格的多层验证。

## 四层等价性模型

### Layer 1: 结构等价 (Structural Parity)

**验证内容:** API 表面一致
```
检查项:
- [ ] 所有 public 类型都有对应的 Rust 类型
- [ ] 所有 public 函数都有对应的 Rust 函数
- [ ] 函数签名语义等价（参数/返回值类型映射正确）
- [ ] 模块结构对应（包/crate 映射正确）
- [ ] 常量/枚举值一一对应
```

**计算方式:**
```
structural_parity = translated_public_items / total_public_items × 100%
```

**通过标准:** ≥ 95%（允许有意删除/合并的例外）

### Layer 2: 功能等价 (Functional Parity)

**验证内容:** 单个函数行为一致
```
检查项:
- [ ] 所有源测试翻译后通过
- [ ] 边界条件行为一致（空输入、最大值、错误输入）
- [ ] 错误返回语义等价
- [ ] 默认值/零值行为一致
- [ ] 并发行为等价（不要求实现相同，但结果一致）
```

**计算方式:**
```
functional_parity = passing_translated_tests / total_translated_tests × 100%
```

**通过标准:** 100%（测试失败 = 翻译 bug）

### Layer 3: 接口等价 (Interface Parity)

**验证内容:** 模块间交互一致
```
检查项:
- [ ] 模块间调用的参数/返回值正确传递
- [ ] 依赖注入接口兼容
- [ ] 事件/回调触发时机一致
- [ ] 序列化格式一致（如果有跨模块数据交换）
- [ ] 错误传播路径一致
```

**验证方法:**
```
1. 集成测试（两个以上模块组合测试）
2. 接口合约测试（验证 trait 实现满足约束）
3. Mock 验证（确保 Mock 行为与 Real 实现一致）
```

**通过标准:** 100%

### Layer 4: 行为等价 (Behavioral Parity)

**验证内容:** 端到端系统行为一致
```
检查项:
- [ ] 完整工作流程输出一致
- [ ] 错误场景响应一致
- [ ] 性能在可接受范围内（±30%）
- [ ] 资源使用合理（内存、CPU）
- [ ] 边缘情况处理一致
```

**验证方法:**
```
1. E2E 测试场景
2. 录制 + 回放（记录源系统输出，对比 Rust 输出）
3. 混沌测试（注入故障，对比恢复行为）
```

**通过标准:** ≥ 99%（允许有意的行为改进，需决策记录）

## 等价性分数计算

### 公式
```
parity_score = real_implementations / (total_items - excluded_items) × 100%

其中:
- real_implementations: 有实际实现的项（非占位符）
- total_items: 源项目中的所有 public 项
- excluded_items: 明确排除的项（autogen、deprecated、platform-specific）
```

### 排除规则
可以排除的项（不计入分母）：
- 自动生成的代码（codegen）
- 已弃用的 API（deprecated）
- 平台特定代码（当前不支持的平台）
- 测试辅助代码（test helpers）

排除必须在 translation-state.jsonc 中明确记录。

## 验证流程

### 单模块验证
```bash
# 1. 结构检查
./scripts/check-structure.sh <module>

# 2. 功能测试
cargo test -p <crate> --all-features

# 3. 接口测试
cargo test -p <crate> --test integration_*

# 4. 生成报告
./scripts/parity-report.sh <module>
```

### Wave 验证
```bash
# 对 Wave 内所有模块执行验证
for module in $WAVE_MODULES; do
    check_parity $module || FAILED+=($module)
done

# E2E 验证
./scripts/e2e-test.sh

# 生成 Wave 报告
./scripts/wave-report.sh $WAVE_ID
```

## DI 验证规则（从 Taibai L001/L004 提炼）

**规则:** 任何依赖注入接口，必须同时提供 Mock 和 Real 实现

```
验证:
- [ ] trait 存在
- [ ] Mock 实现存在（用于单元测试）
- [ ] Real 实现存在（用于集成测试和生产）
- [ ] Mock 和 Real 行为一致（核心逻辑相同）
- [ ] 测试中同时使用了 Mock 和 Real
```

**反模式:** 只有 Mock 没有 Real → Stub Accumulation（必须避免）

## 报告格式

```markdown
## Parity Report — [模块名] — [日期]

| 层级 | 分数 | 状态 |
|------|------|------|
| 结构等价 | XX% | ✅/❌ |
| 功能等价 | XX% | ✅/❌ |
| 接口等价 | XX% | ✅/❌ |
| 行为等价 | XX% | ✅/❌ |

**综合分数:** XX%

### 未通过项
- [L1] 缺少翻译: `FunctionName`
- [L2] 测试失败: `test_xxx` — 预期 X 实际 Y
- [L3] 接口不兼容: `ModuleA::call(ModuleB)` 参数类型不匹配

### 行动计划
1. [P1] 翻译缺失函数
2. [P2] 修复测试失败
3. [P3] 统一接口类型
```
