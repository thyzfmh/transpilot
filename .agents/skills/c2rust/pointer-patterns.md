# C→Rust 指针模式翻译

## P-001: 数组遍历 → 迭代器

**C 模式:**
```c
void process(int *arr, size_t len) {
    for (int *p = arr; p < arr + len; p++) {
        handle(*p);
    }
}
```

**Rust 翻译:**
```rust
fn process(arr: &[i32]) {
    for item in arr.iter() {
        handle(*item);
    }
}
```

**决策规则:** 指针+长度参数对 → 切片引用 `&[T]` 或 `&mut [T]`

---

## P-002: 指针算术 → 切片索引

**C 模式:**
```c
char *find_char(char *s, char c) {
    while (*s) {
        if (*s == c) return s;
        s++;
    }
    return NULL;
}
```

**Rust 翻译:**
```rust
fn find_char(s: &[u8], c: u8) -> Option<usize> {
    s.iter().position(|&b| b == c)
}
```

**决策规则:**
- 返回指向内部的指针 → 返回索引或子切片
- 返回 NULL 表示未找到 → `Option<usize>` 或 `Option<&T>`
- 绝不返回裸指针

---

## P-003: 双指针（输出参数） → &mut Option<Box<T>>

**C 模式:**
```c
int create_resource(resource_t **out) {
    *out = malloc(sizeof(resource_t));
    if (!*out) return -ENOMEM;
    init_resource(*out);
    return 0;
}
```

**Rust 翻译:**
```rust
fn create_resource() -> Result<Box<Resource>, Error> {
    let res = Box::new(Resource::new());
    Ok(res)
}
```

**决策规则:**
- 双指针用于输出 → 返回 `Result<Box<T>, E>`
- 双指针用于重分配 → `&mut Vec<T>` 或 `&mut Box<T>`
- 双指针链表 → `&mut Option<Box<Node>>`

---

## P-004: void* → 泛型/dyn Trait

**C 模式:**
```c
typedef struct {
    void *data;
    size_t size;
    int (*compare)(const void*, const void*);
} container_t;
```

**Rust 翻译（泛型，首选）:**
```rust
struct Container<T: Ord> {
    data: Vec<T>,
}
```

**Rust 翻译（trait object，异构时用）:**
```rust
trait Comparable: std::fmt::Debug {
    fn compare(&self, other: &dyn Comparable) -> std::cmp::Ordering;
}

struct Container {
    data: Vec<Box<dyn Comparable>>,
}
```

**决策树:**
```
void* 用途
├── 泛型容器 → 使用 Rust 泛型 <T: Trait>
├── 异构集合 → Box<dyn Trait>
├── 类型擦除回调 → 闭包 Fn/FnMut/FnOnce
└── FFI 兼容层 → *mut c_void（仅限 unsafe 边界）
```

---

## P-005: 侵入式链表 → Arena / Vec 索引

**C 模式:**
```c
struct node {
    struct node *next;
    struct node *prev;
    int data;
};
// 通过 container_of 宏访问外围结构
```

**Rust 翻译（Arena 方案）:**
```rust
use typed_arena::Arena;

struct Node<'a> {
    next: Option<&'a Node<'a>>,
    prev: Option<&'a Node<'a>>,
    data: i32,
}

// Arena 统一管理生命周期
let arena = Arena::new();
let node = arena.alloc(Node { next: None, prev: None, data: 42 });
```

**Rust 翻译（索引方案，推荐）:**
```rust
struct NodePool {
    nodes: Vec<NodeData>,
}

#[derive(Clone, Copy)]
struct NodeId(usize);

struct NodeData {
    next: Option<NodeId>,
    prev: Option<NodeId>,
    data: i32,
}
```

**决策规则:**
- 内核风格侵入式链表 → 索引方案（最安全、最简单）
- 需要频繁分配/释放 → Arena（typed_arena 或 bumpalo）
- 简单单向链表 → `Vec<T>` 或 `VecDeque<T>` 直接替代
- `container_of` 宏 → 不翻译，重构为组合/索引

---

## P-006: 函数指针表 → Trait Object / Enum Dispatch

**C 模式:**
```c
typedef struct {
    int (*open)(const char *path);
    int (*read)(void *buf, size_t len);
    int (*write)(const void *buf, size_t len);
    void (*close)(void);
} file_ops_t;
```

**Rust 翻译（trait，首选）:**
```rust
trait FileOps {
    fn open(&mut self, path: &Path) -> Result<()>;
    fn read(&mut self, buf: &mut [u8]) -> Result<usize>;
    fn write(&mut self, buf: &[u8]) -> Result<usize>;
    fn close(&mut self) -> Result<()>;
}
```

**Rust 翻译（enum dispatch，高性能时）:**
```rust
enum FileBackend {
    Local(LocalFile),
    Network(NetworkFile),
    Memory(MemoryFile),
}

impl FileBackend {
    fn read(&mut self, buf: &mut [u8]) -> Result<usize> {
        match self {
            Self::Local(f) => f.read(buf),
            Self::Network(f) => f.read(buf),
            Self::Memory(f) => f.read(buf),
        }
    }
}
```

**决策规则:**
- 虚函数表（固定接口） → trait object（`Box<dyn Trait>`）
- 有限变体集合 → enum dispatch（避免动态分发开销）
- 单个回调 → 闭包 `Box<dyn Fn(...)>`
- 可选回调 → `Option<Box<dyn Fn(...)>>`

---

## P-007: 类型转换 → 安全转换

**C 模式:**
```c
uint32_t val = *(uint32_t*)buf;           // 类型双关
float f = *(float*)&int_val;              // 位重解释
struct header *h = (struct header*)raw;    // 结构覆盖
```

**Rust 翻译:**
```rust
// 类型双关 → from_ne_bytes / from_le_bytes
let val = u32::from_ne_bytes(buf[..4].try_into().unwrap());

// 位重解释 → f32::from_bits
let f = f32::from_bits(int_val);

// 结构覆盖 → zerocopy 或手动解析
use zerocopy::{FromBytes, AsBytes};
#[derive(FromBytes, AsBytes)]
#[repr(C)]
struct Header { /* ... */ }
let h = Header::read_from(&raw[..]).unwrap();
```

**安全等级:**
```
转换类型              安全替代                         允许 unsafe
─────────────────────────────────────────────────────────────
整数截断              as / try_from                     否
整数扩展              From trait                        否
数值→字节            to_ne_bytes()                     否
字节→数值            from_ne_bytes()                   否
位重解释             from_bits/to_bits                  否
指针→引用            &* / as_ref()                     是（需证明有效）
切片→结构           zerocopy / bytemuck                否（safe wrapper）
```

---

## 通用指针翻译决策树

```
C 指针类型
├── T* (只读) → &T
├── T* (读写) → &mut T
├── T* (所有权转移) → Box<T>
├── T* (可空) → Option<&T> / Option<Box<T>>
├── T* + len (数组) → &[T] / &mut [T] / Vec<T>
├── void* → 泛型 T / Box<dyn Trait> / *mut c_void (FFI)
├── T** (输出) → 返回 Result<T> / &mut Option<T>
├── 函数指针 → Fn trait / trait method
└── 自引用结构 → Pin<Box<T>> / Arena / 索引
```

## 常见错误

| 错误做法 | 正确做法 |
|---------|---------|
| 直接 `*const T as *mut T` | 确认可变性后用 `&mut T` |
| `transmute` 做类型转换 | 用 `from_bytes` / `zerocopy` |
| 裸指针传递所有权 | 用 `Box::into_raw` / `Box::from_raw` |
| `unsafe { &*ptr }` 不验证 | 先 `assert!(!ptr.is_null())` |
| 索引方案用 `usize` 直接做 ID | 用 newtype `struct Id(usize)` |
