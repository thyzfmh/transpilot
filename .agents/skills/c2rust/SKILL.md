---
name: c2rust
description: C → Rust 翻译技能 — 内存安全、指针翻译、预处理器映射、FFI 互操作、unsafe 审计
---

# C → Rust 翻译技能

## 何时使用
- 源语言为 C 的翻译项目
- 需要安全消除 unsafe 代码
- FFI 边界设计

## 核心映射（速查）
| C | Rust | 策略 |
|---|------|------|
| `malloc/free` | `Box`/`Vec`/`Arc` | 按所有权选型 |
| `*T` (拥有) | `Box<T>` | 独占所有权 |
| `*T` (借用) | `&T`/`&mut T` | 生命周期标注 |
| `*T` (可空) | `Option<&T>` | 编译时检查 |
| `#define CONST` | `const` / `static` | 编译期求值 |
| `#define MACRO(x)` | `macro_rules!` | 类型安全 |
| `#ifdef` | `#[cfg(...)]` | 条件编译 |

## 关键规则
1. **unsafe 预算 < 5%** — 仅限 FFI 边界和硬件交互
2. 指针翻译先分类（拥有/借用/可空/数组）再选型
3. 预处理器 → 静态类型方案（const > macro > cfg）
4. FFI：Safe Rust Wrapper 包裹所有 C 调用

## 详细参考
- 内存管理模式 → `memory-patterns.md`
- 指针翻译决策树 → `pointer-patterns.md`
- 预处理器映射 → `preprocessor-patterns.md`
- FFI 互操作 → `ffi-patterns.md`
- unsafe 审计指南 → `unsafe-audit.md`
