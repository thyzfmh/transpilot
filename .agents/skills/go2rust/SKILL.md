---
name: go2rust
description: Go → Rust 翻译技能 — 类型映射、并发模式、错误处理、序列化兼容
---

# Go → Rust 翻译技能

## 何时使用
- 源语言为 Go 的翻译项目
- 遇到 Go 特有模式需要 Rust 等价实现

## 核心映射（速查）
| Go | Rust | 注意 |
|----|------|------|
| `goroutine` | `tokio::spawn` / `std::thread` | IO→tokio, CPU→thread |
| `chan` | `tokio::mpsc` / `crossbeam` | 按缓冲区大小选型 |
| `interface{}` | `dyn Trait` / 泛型 | 优先泛型 |
| `error` | `Result<T, E>` | 用 `thiserror` 定义 |
| `defer` | `Drop` / `scopeguard` | 按场景选 |
| `struct embedding` | 组合 + `Deref` | 不是继承 |

## 关键规则
1. 并发：判断 IO/CPU 再选 spawn 方式
2. 零值：Go 有默认零值，Rust 需 `Default` trait
3. 序列化：`serde` + `skip_serializing_if` 保兼容
4. 接口：优先泛型，fallback `dyn Trait`

## 详细参考
- 类型映射完整表 → `type-mapping.md`
- 并发模式详解 → `concurrency-patterns.md`
- 错误处理 → `error-handling.md`
- 序列化兼容 → `serde-patterns.md`
