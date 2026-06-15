# C→Rust FFI 互操作模式

## 迁移策略选择

### 策略一：自底向上（叶子函数先行）

```
阶段 1: 翻译无外部依赖的叶子函数
阶段 2: 通过 FFI 暴露 Rust 实现给 C 调用者
阶段 3: 逐步替换调用者
阶段 4: 移除 FFI 层
```

**适用场景:** 工具库、算法模块、数据结构
**优势:** 每步可独立验证，风险低
**劣势:** FFI 维护成本

### 策略二：自顶向下（入口先行）

```
阶段 1: Rust main / 入口点
阶段 2: Rust 调用 C 库（通过 FFI）
阶段 3: 逐步用 Rust 替换 C 实现
阶段 4: 移除 FFI 层
```

**适用场景:** 应用程序、服务、CLI 工具
**优势:** 快速获得 Rust 工具链优势（cargo、测试）
**劣势:** 初期大量 FFI 绑定

### 策略三：完全替换（无 FFI 阶段）

```
阶段 1: 完整分析 C 代码
阶段 2: 设计 Rust 接口（可能与 C 不同）
阶段 3: 全部用 Rust 重写
阶段 4: 验证行为等价性
```

**适用场景:** 小型模块、代码质量差的遗留代码、需要重构的模块
**优势:** 无 FFI 开销，可重新设计
**劣势:** 风险高，需要完整理解

### 策略决策矩阵

| 条件 | 推荐策略 |
|------|---------|
| 模块 < 500 行 | 完全替换 |
| 模块 500-5000 行 | 自底向上 |
| 模块 > 5000 行 | 自底向上 + 分批 |
| 是应用入口 | 自顶向下 |
| 是动态库 | 自底向上（保持 ABI） |
| 有完善测试 | 任意（测试验证） |
| 无测试 | 先写测试，再完全替换 |

---

## FFI 安全规则

### 规则 1: 边界明确化

```rust
// ✗ 错误：unsafe 散布在业务逻辑中
pub fn process_data(ptr: *const u8, len: usize) -> i32 {
    unsafe {
        let slice = std::slice::from_raw_parts(ptr, len);
        // ... 100 行业务逻辑 ...
    }
}

// ✓ 正确：unsafe 仅在边界，内部全 safe
pub fn process_data(ptr: *const u8, len: usize) -> i32 {
    // FFI 边界：验证 + 转换
    let slice = unsafe {
        assert!(!ptr.is_null());
        assert!(len <= isize::MAX as usize);
        std::slice::from_raw_parts(ptr, len)
    };
    
    // 内部全 safe
    process_slice(slice)
}

fn process_slice(data: &[u8]) -> i32 {
    // 纯 safe 业务逻辑
    data.iter().map(|&b| b as i32).sum()
}
```

### 规则 2: 所有权边界契约

```rust
/// FFI 函数的所有权契约必须在文档中明确声明
///
/// # Safety
/// - `ptr` must be a valid pointer allocated by `create_resource`
/// - Caller transfers ownership: after calling this, `ptr` is invalid
/// - This function will free the memory pointed to by `ptr`
#[no_mangle]
pub unsafe extern "C" fn destroy_resource(ptr: *mut Resource) {
    if !ptr.is_null() {
        let _ = Box::from_raw(ptr);  // 接管所有权并 drop
    }
}

/// # Safety
/// - Returns a pointer that the caller owns
/// - Caller must call `destroy_resource` to free
#[no_mangle]
pub extern "C" fn create_resource() -> *mut Resource {
    Box::into_raw(Box::new(Resource::new()))
}
```

### 规则 3: 错误处理桥接

```rust
// C 风格错误码
#[repr(C)]
pub enum CError {
    Ok = 0,
    InvalidArg = -1,
    OutOfMemory = -2,
    IoError = -3,
}

// Rust Result → C 错误码
fn result_to_c_error<T>(result: Result<T, Error>) -> (CError, Option<T>) {
    match result {
        Ok(val) => (CError::Ok, Some(val)),
        Err(e) => (error_to_code(&e), None),
    }
}

// 对外暴露的 FFI 函数
#[no_mangle]
pub extern "C" fn do_operation(input: *const c_char, out: *mut *mut Result) -> CError {
    let result = std::panic::catch_unwind(|| {
        let input_str = unsafe { CStr::from_ptr(input) }.to_str().map_err(|_| Error::InvalidArg)?;
        internal_operation(input_str)
    });
    
    match result {
        Ok(Ok(val)) => {
            unsafe { *out = Box::into_raw(Box::new(val)) };
            CError::Ok
        }
        Ok(Err(e)) => error_to_code(&e),
        Err(_) => CError::InternalPanic,  // panic 不能跨 FFI！
    }
}
```

### 规则 4: 字符串处理

```rust
use std::ffi::{CStr, CString};
use std::os::raw::c_char;

// C → Rust（借用，不获取所有权）
fn c_str_to_rust(ptr: *const c_char) -> Result<&str, Error> {
    if ptr.is_null() {
        return Err(Error::NullPointer);
    }
    unsafe { CStr::from_ptr(ptr) }
        .to_str()
        .map_err(|_| Error::InvalidUtf8)
}

// Rust → C（转移所有权）
fn rust_str_to_c(s: &str) -> *mut c_char {
    CString::new(s)
        .expect("string contains null byte")
        .into_raw()  // 调用者负责用 CString::from_raw 释放
}

// 释放 Rust 分配的 C 字符串
#[no_mangle]
pub unsafe extern "C" fn free_string(ptr: *mut c_char) {
    if !ptr.is_null() {
        let _ = CString::from_raw(ptr);
    }
}
```

### 规则 5: 回调函数安全

```rust
// C 回调类型
type CCallback = extern "C" fn(data: *mut c_void, event: i32) -> i32;

// 安全包装
struct CallbackWrapper {
    func: CCallback,
    data: *mut c_void,
}

// Safety: 确保回调不会被并发调用（如果不是线程安全的）
unsafe impl Send for CallbackWrapper {}

impl CallbackWrapper {
    /// # Safety
    /// - `func` must be a valid function pointer
    /// - `data` must remain valid for the lifetime of this wrapper
    /// - `func` must be safe to call with `data`
    unsafe fn new(func: CCallback, data: *mut c_void) -> Self {
        Self { func, data }
    }
    
    fn invoke(&self, event: i32) -> i32 {
        (self.func)(self.data, event)
    }
}
```

---

## bindgen 使用指南

### 基本配置 (build.rs)

```rust
fn main() {
    println!("cargo:rerun-if-changed=wrapper.h");
    
    let bindings = bindgen::Builder::default()
        .header("wrapper.h")
        // 只生成需要的类型
        .allowlist_function("target_.*")
        .allowlist_type("target_.*")
        // 使用 Rust 枚举
        .rustified_enum("target_error_t")
        // 派生常用 trait
        .derive_debug(true)
        .derive_default(true)
        .derive_eq(true)
        // 安全设置
        .layout_tests(true)  // 生成布局测试
        .generate()
        .expect("bindgen failed");
    
    let out_path = std::path::PathBuf::from(std::env::var("OUT_DIR").unwrap());
    bindings.write_to_file(out_path.join("bindings.rs")).unwrap();
}
```

### 安全封装层模式

```rust
// src/ffi.rs — 自动生成的绑定（不手动修改）
#![allow(non_upper_case_globals, non_camel_case_types, non_snake_case, dead_code)]
include!(concat!(env!("OUT_DIR"), "/bindings.rs"));

// src/safe_wrapper.rs — 手写的安全封装
use crate::ffi;

pub struct LibHandle {
    inner: *mut ffi::lib_handle_t,
}

impl LibHandle {
    pub fn new(config: &Config) -> Result<Self, Error> {
        let raw = unsafe { ffi::lib_create(config.as_raw()) };
        if raw.is_null() {
            Err(Error::CreateFailed)
        } else {
            Ok(Self { inner: raw })
        }
    }
    
    pub fn process(&mut self, data: &[u8]) -> Result<Vec<u8>, Error> {
        let mut out_ptr: *mut u8 = std::ptr::null_mut();
        let mut out_len: usize = 0;
        
        let ret = unsafe {
            ffi::lib_process(self.inner, data.as_ptr(), data.len(), &mut out_ptr, &mut out_len)
        };
        
        if ret != 0 {
            return Err(Error::from_code(ret));
        }
        
        let result = unsafe { std::slice::from_raw_parts(out_ptr, out_len).to_vec() };
        unsafe { ffi::lib_free(out_ptr as *mut _) };
        Ok(result)
    }
}

impl Drop for LibHandle {
    fn drop(&mut self) {
        unsafe { ffi::lib_destroy(self.inner) };
    }
}

// Send + Sync 只在确认线程安全时实现
unsafe impl Send for LibHandle {}
```

---

## FFI 检查清单

在暴露或调用 FFI 函数时，逐项检查：

- [ ] 所有指针参数都有 null 检查
- [ ] 所有权转移方向明确文档化
- [ ] panic 不会跨越 FFI 边界（使用 `catch_unwind`）
- [ ] 字符串编码处理正确（UTF-8 验证）
- [ ] 内存分配/释放配对（谁分配谁释放）
- [ ] 线程安全性明确（Send/Sync 是否正确）
- [ ] `repr(C)` 用于跨边界的结构体
- [ ] 枚举有明确的整数表示（`repr(i32)` 等）
- [ ] 数组参数同时传递长度
- [ ] 回调函数生命周期管理正确
- [ ] 布局测试通过（bindgen 生成的）
- [ ] Miri 测试通过（检测 UB）

## 常见错误

| 错误做法 | 正确做法 |
|---------|---------|
| `panic!()` 在 extern "C" 函数中 | `catch_unwind` + 返回错误码 |
| 手写 FFI 绑定 | 用 bindgen 自动生成 |
| unsafe 块包含业务逻辑 | unsafe 仅做转换，逻辑在 safe 函数中 |
| 忽略 `*mut T` 的生命周期 | 用 wrapper 类型 + Drop 管理 |
| 跨 FFI 传递 `String`/`Vec` | 用 `CString`/指针+长度 |
| 假设 C 结构体对齐 | 用 `repr(C)` + 布局测试验证 |
