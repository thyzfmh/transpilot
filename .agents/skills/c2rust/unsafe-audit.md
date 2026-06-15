# C→Rust unsafe 审计指南

## unsafe 预算规则

### 目标: 总代码中 unsafe 块占比 < 5%

**计算方式:**
```
unsafe_ratio = unsafe_lines / total_rust_lines × 100%
```

**阈值:**
| 比例 | 状态 | 行动 |
|------|------|------|
| < 2% | 优秀 | 维持 |
| 2-5% | 可接受 | 监控，逐步优化 |
| 5-10% | 警告 | 必须制定消除计划 |
| > 10% | 不可接受 | 停止新功能，优先消除 |

**豁免情况（不计入预算）:**
- FFI 边界层（bindgen 生成的代码）
- 性能关键路径（需要 benchmark 证明）
- 硬件交互代码

---

## unsafe 分类

### 类别 A: 可消除的 unsafe（必须消除）

| 模式 | 替代方案 |
|------|---------|
| `unsafe { &*ptr }` | 用 Option/Result 包装 |
| `unsafe { slice::from_raw_parts }` | 传入 `&[T]` |
| `unsafe { transmute }` | 用 `from_bytes` / `From` trait |
| `unsafe { Vec::set_len }` | 用 `resize` / `extend` |
| `unsafe impl Send` | 重构为 Arc/Mutex |
| 裸指针遍历 | 用迭代器 |

### 类别 B: 可封装的 unsafe（隔离到边界）

| 模式 | 封装策略 |
|------|---------|
| FFI 调用 | 安全 wrapper 类型 |
| 内存映射 | `memmap2` crate |
| 原子操作 | `std::sync::atomic` |
| SIMD 内联 | 安全 wrapper 函数 |
| 全局可变状态 | `OnceLock` / `Mutex` |

### 类别 C: 不可避免的 unsafe（最小化 + 文档化）

| 模式 | 要求 |
|------|------|
| 底层内存分配器 | 完整 Safety 文档 + Miri 测试 |
| 内核接口 | syscall wrapper + 错误处理 |
| 自引用结构 | Pin 保证 + 不暴露内部 |
| 性能热路径 | benchmark 证明必要性 |

---

## 审计检查清单

对每个 `unsafe` 块执行以下检查：

### 1. 必要性验证
- [ ] 确认无法用 safe Rust 实现同等功能
- [ ] 确认无第三方 crate 提供 safe 抽象
- [ ] 如果是性能原因，有 benchmark 数据支撑

### 2. 正确性证明
- [ ] 所有前置条件（preconditions）在 unsafe 块之前验证
- [ ] 指针非空（`assert!(!ptr.is_null())`）
- [ ] 指针正确对齐（alignment）
- [ ] 指向有效内存（lifetime 有保证）
- [ ] 无数据竞争（Send/Sync 约束正确）
- [ ] 无别名违规（&mut 唯一性）

### 3. 文档要求
```rust
/// # Safety
///
/// Caller must ensure:
/// - `ptr` is non-null and points to a valid `T`
/// - `ptr` remains valid for the duration of the returned reference
/// - No mutable references to the same `T` exist
unsafe fn deref_ptr<T>(ptr: *const T) -> &T {
    debug_assert!(!ptr.is_null());
    &*ptr
}
```

### 4. 测试覆盖
- [ ] 单元测试覆盖所有正常路径
- [ ] 单元测试覆盖边界条件（null、零长度、最大值）
- [ ] Miri 测试通过（检测 UB）
- [ ] 地址消毒器（ASan）测试通过
- [ ] 模糊测试覆盖（cargo-fuzz）

---

## unsafe 消除策略

### 策略 1: 类型状态模式（Type State Pattern）

**Before (unsafe):**
```rust
struct Connection {
    socket: *mut Socket,
    connected: bool,
}

impl Connection {
    fn send(&self, data: &[u8]) -> Result<()> {
        if !self.connected {
            return Err(Error::NotConnected);
        }
        unsafe { (*self.socket).write(data) }
    }
}
```

**After (safe):**
```rust
struct Disconnected;
struct Connected { socket: OwnedSocket }

struct Connection<S> {
    state: S,
}

impl Connection<Disconnected> {
    fn connect(addr: &str) -> Result<Connection<Connected>> {
        let socket = OwnedSocket::connect(addr)?;
        Ok(Connection { state: Connected { socket } })
    }
}

impl Connection<Connected> {
    fn send(&mut self, data: &[u8]) -> Result<()> {
        self.state.socket.write(data)
    }
}
```

### 策略 2: 新类型封装（Newtype Wrapper）

**Before (unsafe):**
```rust
fn process(fd: i32) {
    unsafe { libc::read(fd, buf.as_mut_ptr() as *mut _, buf.len()) };
}
```

**After (safe):**
```rust
struct OwnedFd(i32);

impl OwnedFd {
    fn read(&self, buf: &mut [u8]) -> Result<usize> {
        let ret = unsafe { libc::read(self.0, buf.as_mut_ptr() as *mut _, buf.len()) };
        if ret < 0 {
            Err(io::Error::last_os_error())
        } else {
            Ok(ret as usize)
        }
    }
}

impl Drop for OwnedFd {
    fn drop(&mut self) {
        unsafe { libc::close(self.0) };
    }
}
```

### 策略 3: 用成熟 crate 替代

| 自己写的 unsafe | 成熟 crate 替代 |
|---------------|----------------|
| 手写内存映射 | `memmap2` |
| 手写原子操作 | `crossbeam` |
| 手写并发容器 | `dashmap` / `parking_lot` |
| 手写 SIMD | `packed_simd2` / `std::simd` |
| 手写链表 | `slotmap` / `typed_arena` |
| 手写 FFI string | `cstr` crate |

### 策略 4: 验证后封装

```rust
/// 经过验证的非空指针（构造时验证，使用时 safe）
#[derive(Debug)]
struct NonNullPtr<T> {
    ptr: std::ptr::NonNull<T>,
}

impl<T> NonNullPtr<T> {
    /// 唯一的 unsafe 入口点
    /// # Safety: ptr must be non-null and valid
    unsafe fn new_unchecked(ptr: *mut T) -> Self {
        Self { ptr: std::ptr::NonNull::new_unchecked(ptr) }
    }
    
    /// Safe 构造（运行时检查）
    fn new(ptr: *mut T) -> Option<Self> {
        std::ptr::NonNull::new(ptr).map(|ptr| Self { ptr })
    }
    
    /// Safe 解引用（构造时已验证）
    fn as_ref(&self) -> &T {
        // Safety: 构造时已验证非空且有效
        unsafe { self.ptr.as_ref() }
    }
}
```

---

## 审计报告模板

每次 unsafe 审计完成后，生成报告：

```markdown
## unsafe 审计报告 — [模块名]

**日期:** YYYY-MM-DD
**审计人:** [Agent/Human]
**unsafe 比例:** X.X% (N unsafe 块 / M 总行数)

### 统计
| 类别 | 数量 | 状态 |
|------|------|------|
| A (可消除) | N | 🔴 待消除 |
| B (可封装) | N | 🟡 已封装/待封装 |
| C (不可避免) | N | 🟢 已文档化 |

### 发现的问题
1. [文件:行] — 描述 — 严重程度 — 修复建议

### 消除计划
- [ ] 第 1 批：[列出可立即消除的 unsafe]
- [ ] 第 2 批：[需要重构才能消除的]
- [ ] 永久保留：[不可避免的，需完善文档]

### Miri 测试结果
- 通过 / 失败 / 跳过
```

---

## 工具链配置

```bash
# 安装 Miri（检测 UB）
rustup +nightly component add miri
cargo +nightly miri test

# 安装 cargo-geiger（统计 unsafe）
cargo install cargo-geiger
cargo geiger

# 安装 cargo-audit（安全审计）
cargo install cargo-audit
cargo audit

# ASan 测试
RUSTFLAGS="-Zsanitizer=address" cargo +nightly test

# 模糊测试
cargo install cargo-fuzz
cargo fuzz run target_name
```

## 常见错误

| 错误做法 | 正确做法 |
|---------|---------|
| `unsafe` 块覆盖整个函数 | 最小化 unsafe 范围到单条语句 |
| Safety 注释说 "trust me" | 列出所有前置条件和不变量 |
| 跳过 Miri 测试 | 所有含 unsafe 的模块必须 Miri 通过 |
| 用 unsafe 绕过借用检查 | 重构数据结构/使用 RefCell |
| 认为"C 就是这么写的" | 在 Rust 中必须证明安全性 |
| unsafe 分散在各处 | 集中到少数 `_unchecked` 函数中 |
