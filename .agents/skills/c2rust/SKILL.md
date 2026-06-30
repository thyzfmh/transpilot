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

## C 测试移植规则

### 测试计数器必须用 thread_local!

C 测试中常见的 `static int cur_time = 0;` + `get_time()` 模式在 Rust 测试中必须翻译为：

```rust
// ❌ 错误 — cargo test 并行执行时跨线程污染
static mut CUR_TIME: i32 = 0;
// ❌ 错误 — AtomicI32 也是跨线程共享的
static CUR_TIME: AtomicI32 = AtomicI32::new(0);

// ✅ 正确 — 每个线程独立计数器
thread_local! {
    static CUR_TIME: Cell<i32> = Cell::new(0);
}
fn get_time() -> i32 {
    CUR_TIME.with(|c| {
        let v = c.get() + 2;
        c.set(v);
        v
    })
}
```

### GC/扇区布局测试的值大小必须精确计算

GC 触发条件依赖于精确的扇区布局。移植 C 测试中的 `_TKV_*` 宏计算，不要猜值：

```rust
// ❌ 错误 — 随便选的值，GC 可能不触发
const TEST_KV_VALUE_LEN: usize = 256;

// ✅ 正确 — 从 C 测试的宏计算移植
const _TKV_BASE: usize = KV_HDR_SZ + FDB_WG_ALIGN(3); // header + name
const _TKV_USABLE: usize = (SEC_SIZE as usize) - SEC_HDR_SZ;
const TEST_KV_VALUE_LEN: usize = (_TKV_USABLE - 3 * _TKV_BASE + 3) / 4;
```

### C Oracle 差分测试模板

对关键行为（GC、扇区溢出、多扇区迭代），建 C Oracle 程序验证：

1. C 程序执行固定操作序列 → 输出 JSONL 到 stdout
2. Rust 测试解析 C 输出 → 重放同样操作 → 比对结果
3. 标记 `#[ignore]`，用 `cargo test -- --ignored` 运行

需要的 Oracle 变体：
| Oracle | 场景 | 必要性 |
|--------|------|--------|
| Basic CRUD | set/get/del/iter | 必需 |
| GC trigger | 填满扇区+覆盖+GC | 必需（如果源项目有GC） |
| Multi-sector | 跨扇区边界迭代 | 必需（如果源项目有TSDB） |
| Reboot | deinit+reinit 状态保持 | 必需 |

## 详细参考
- 内存管理模式 → `memory-patterns.md`
- 指针翻译决策树 → `pointer-patterns.md`
- 预处理器映射 → `preprocessor-patterns.md`
- FFI 互操作 → `ffi-patterns.md`
- unsafe 审计指南 → `unsafe-audit.md`
