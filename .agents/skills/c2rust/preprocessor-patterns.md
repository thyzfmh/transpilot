# C→Rust 预处理器模式翻译

## PP-001: 常量宏 → const / const fn

**C 模式:**
```c
#define MAX_BUFFER_SIZE 4096
#define PAGE_SIZE (1 << 12)
#define ALIGN(x, a) (((x) + (a) - 1) & ~((a) - 1))
```

**Rust 翻译:**
```rust
const MAX_BUFFER_SIZE: usize = 4096;
const PAGE_SIZE: usize = 1 << 12;

const fn align(x: usize, a: usize) -> usize {
    (x + a - 1) & !(a - 1)
}
```

**规则:** 所有纯值宏 → `const`；带计算的宏 → `const fn`（编译时求值）

---

## PP-002: 类型别名宏 → type / newtype

**C 模式:**
```c
#define HANDLE int
#define BOOL int
typedef unsigned long size_t;
```

**Rust 翻译:**
```rust
// 简单别名（不需要类型安全时）
type Handle = i32;

// newtype（需要类型安全时，推荐）
#[derive(Debug, Clone, Copy, PartialEq, Eq, Hash)]
struct Handle(i32);

// 已有标准类型
// size_t → usize（自动）
// BOOL → bool
```

**决策规则:**
- 语义性类型 → newtype 模式（防止混用）
- 纯缩写 → type alias
- C 标准类型 → 使用 Rust 对应类型

---

## PP-003: 条件编译 → cfg 属性

**C 模式:**
```c
#ifdef __linux__
    #include <linux/io_uring.h>
#elif defined(_WIN32)
    #include <windows.h>
#else
    #error "Unsupported platform"
#endif

#ifdef DEBUG
    #define LOG(fmt, ...) fprintf(stderr, fmt, ##__VA_ARGS__)
#else
    #define LOG(fmt, ...)
#endif
```

**Rust 翻译:**
```rust
// 平台条件编译
#[cfg(target_os = "linux")]
mod io_uring_impl;

#[cfg(target_os = "windows")]
mod windows_impl;

#[cfg(not(any(target_os = "linux", target_os = "windows")))]
compile_error!("Unsupported platform");

// 调试日志
#[cfg(debug_assertions)]
macro_rules! log {
    ($($arg:tt)*) => { eprintln!($($arg)*) }
}

#[cfg(not(debug_assertions))]
macro_rules! log {
    ($($arg:tt)*) => {}
}
```

**常用 cfg 映射:**
```
C 宏                    Rust cfg
──────────────────────────────────────
__linux__               target_os = "linux"
_WIN32                  target_os = "windows"
__APPLE__               target_os = "macos"
__x86_64__              target_arch = "x86_64"
__aarch64__             target_arch = "aarch64"
DEBUG / NDEBUG          debug_assertions
__SIZEOF_POINTER__ == 8 target_pointer_width = "64"
```

---

## PP-004: 功能开关 → Cargo features

**C 模式:**
```c
// config.h
#define ENABLE_SSL 1
#define ENABLE_COMPRESSION 0
#define USE_CUSTOM_ALLOCATOR 0

// code.c
#ifdef ENABLE_SSL
    ssl_init();
#endif
```

**Rust 翻译 (Cargo.toml):**
```toml
[features]
default = ["ssl"]
ssl = ["dep:rustls"]
compression = ["dep:flate2"]
custom-allocator = ["dep:mimalloc"]
```

**Rust 翻译 (代码):**
```rust
#[cfg(feature = "ssl")]
fn init_ssl() {
    // ...
}

#[cfg(feature = "ssl")]
pub use ssl_module::*;
```

**规则:** 编译开关 → Cargo features；运行时开关 → 配置结构体

---

## PP-005: 函数式宏 → macro_rules! / 泛型函数

**C 模式:**
```c
#define MIN(a, b) ((a) < (b) ? (a) : (b))
#define SWAP(a, b) do { typeof(a) _t = (a); (a) = (b); (b) = _t; } while(0)
#define ARRAY_SIZE(arr) (sizeof(arr) / sizeof((arr)[0]))
#define container_of(ptr, type, member) \
    ((type *)((char *)(ptr) - offsetof(type, member)))
```

**Rust 翻译:**
```rust
// MIN → 泛型函数（首选，有类型检查）
fn min<T: Ord>(a: T, b: T) -> T {
    if a < b { a } else { b }
}
// 或直接用 std::cmp::min

// SWAP → std::mem::swap
std::mem::swap(&mut a, &mut b);

// ARRAY_SIZE → 不需要（切片自带 .len()）

// container_of → 不翻译（重构为组合模式）
```

**决策树:**
```
函数式宏
├── 类型无关的简单计算 → 泛型函数（首选）
├── 需要调用者变量的操作 → macro_rules!
├── 标准库已有等价物 → 直接用标准库
├── 代码生成/重复 → proc_macro（复杂时）
└── 不安全/底层技巧 → 不翻译，重构
```

---

## PP-006: X-Macro → proc_macro / 枚举 + 派生

**C 模式:**
```c
// 用 X-Macro 生成枚举和字符串表
#define ERROR_CODES(X) \
    X(OK, 0, "success") \
    X(NOMEM, 1, "out of memory") \
    X(IO, 2, "I/O error")

// 生成枚举
enum error_code {
    #define X(name, val, _) ERR_##name = val,
    ERROR_CODES(X)
    #undef X
};

// 生成字符串表
const char *error_strings[] = {
    #define X(_, __, str) str,
    ERROR_CODES(X)
    #undef X
};
```

**Rust 翻译（简单情况用 macro_rules!）:**
```rust
macro_rules! define_errors {
    ($($name:ident = $val:expr => $desc:expr),* $(,)?) => {
        #[derive(Debug, Clone, Copy, PartialEq, Eq)]
        #[repr(i32)]
        pub enum ErrorCode {
            $($name = $val),*
        }

        impl ErrorCode {
            pub fn description(&self) -> &'static str {
                match self {
                    $(Self::$name => $desc),*
                }
            }
        }
    }
}

define_errors! {
    Ok = 0 => "success",
    NoMem = 1 => "out of memory",
    Io = 2 => "I/O error",
}
```

**Rust 翻译（复杂情况用 derive macro）:**
```rust
// 使用 strum 或自定义 proc_macro
#[derive(Debug, strum::Display, strum::EnumString)]
pub enum ErrorCode {
    #[strum(serialize = "success")]
    Ok = 0,
    #[strum(serialize = "out of memory")]
    NoMem = 1,
    #[strum(serialize = "I/O error")]
    Io = 2,
}
```

---

## PP-007: 头文件保护 → Rust 模块系统

**C 模式:**
```c
// utils.h
#ifndef UTILS_H
#define UTILS_H

struct util_config { /* ... */ };
int util_init(struct util_config *cfg);

#endif
```

**Rust 翻译:**
```rust
// src/utils.rs（无需保护，模块系统天然保证）
pub struct UtilConfig { /* ... */ }

pub fn util_init(cfg: &UtilConfig) -> Result<()> {
    // ...
}
```

**规则:** 头文件 → 模块 (`mod`)，头文件保护 → 自动（Rust 模块不会重复包含）

---

## PP-008: #include → use / mod

**C 模式:**
```c
#include <stdio.h>
#include <stdlib.h>
#include "my_module.h"
#include "../common/utils.h"
```

**Rust 翻译:**
```rust
// 标准库
use std::io;
use std::collections::HashMap;

// 项目内部模块
mod my_module;
use my_module::MyStruct;

// 公共工具
use crate::common::utils;
```

**映射规则:**
```
C include               Rust 等价
───────────────────────────────────────
<std_header.h>          use std::...
"local.h"              mod local; / use crate::local
"../relative.h"        use crate::parent_mod::...
"third_party/lib.h"    use external_crate::...
```

---

## PP-009: 编译时断言 → const assert

**C 模式:**
```c
#define STATIC_ASSERT(cond, msg) typedef char static_assert_##msg[(cond)?1:-1]
STATIC_ASSERT(sizeof(int) == 4, int_must_be_4_bytes);
_Static_assert(sizeof(struct header) == 64, "header must be 64 bytes");
```

**Rust 翻译:**
```rust
// Rust 原生 const assert（1.57+）
const _: () = assert!(std::mem::size_of::<i32>() == 4, "int must be 4 bytes");
const _: () = assert!(std::mem::size_of::<Header>() == 64, "header must be 64 bytes");

// 对齐断言
const _: () = assert!(std::mem::align_of::<Header>() == 8);

// 更复杂的编译时检查
const fn verify_layout() {
    assert!(std::mem::size_of::<Packet>() <= 1500, "packet exceeds MTU");
}
const _: () = verify_layout();
```

---

## 预处理器翻译决策总表

| C 预处理器构造 | Rust 首选方案 | 备选方案 |
|--------------|-------------|---------|
| `#define VAL 42` | `const VAL: i32 = 42` | — |
| `#define MACRO(x) (x*2)` | `fn / const fn` | `macro_rules!` |
| `#ifdef FEATURE` | `#[cfg(feature = "...")]` | — |
| `#ifdef PLATFORM` | `#[cfg(target_os = "...")]` | — |
| `#include "x.h"` | `mod x; use x::...` | — |
| `typedef` | `type` / newtype | — |
| X-Macro | `macro_rules!` | proc_macro |
| `_Static_assert` | `const _: () = assert!(...)` | — |
| `#pragma once` | 不需要（模块系统） | — |
| `__attribute__` | `#[repr(...)]` / `#[inline]` | — |

## 常见错误

| 错误做法 | 正确做法 |
|---------|---------|
| 用 `lazy_static!` 替代所有宏常量 | 优先 `const` / `const fn` |
| 把 `#ifdef` 翻译为运行时 `if` | 用 `#[cfg(...)]` 保持零开销 |
| 每个 `.h` 翻译为独立 crate | 按功能聚合为模块 |
| 保留 C 命名风格 `MY_CONSTANT` | 用 Rust 风格 `MY_CONSTANT`（常量）/ `my_function`（函数）|
| 把 `#define LOG(...)` 翻译为函数 | 用 `macro_rules!` 保留调用位置信息 |
