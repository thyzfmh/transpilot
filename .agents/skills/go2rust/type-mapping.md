# Go → Rust Complete Type Mapping Reference

## Concurrency Primitives

| Go | Rust | Rationale |
|---|---|---|
| `context.Context` | `CancellationToken` + `tokio::time::timeout` | Go Context combines cancel+deadline+values. Rust splits them. |
| `go func()` | `tokio::spawn(async {})` | Goroutine ≈ tokio task (both lightweight, non-blocking) |
| `sync.WaitGroup` | `tokio::sync::Semaphore` or `futures::join!` | WaitGroup → Semaphore (dynamic N) or join! (fixed N) |
| `sync.Once` | `std::sync::OnceLock<T>` | Type-safe one-time initialization |
| `sync.RWMutex` | `parking_lot::RwLock<T>` | Prefer parking_lot: smaller, faster, no poisoning |
| `sync.Mutex` | `parking_lot::Mutex<T>` | Same rationale as RwLock |
| `sync.Map` | `Arc<DashMap<K, V>>` | Sharded concurrent map (dashmap crate) |
| `sync.AtomicInt64` | `std::sync::atomic::AtomicI64` | Direct equivalent. Use `Ordering::SeqCst` for Go default |
| `select { case <-ch1: }` | `tokio::select! { r = fut1 => }` | Go select on channels → tokio select on futures |
| `time.After(d)` | `tokio::time::sleep(d)` | Timer for select/select! usage |
| `chan T` | `tokio::sync::mpsc::Sender/Receiver<T>` | Async channel. Use `watch` for single-value broadcast |
| `chan struct{}` (signal) | `CancellationToken` or `tokio::sync::Notify` | Signal-only channels |

## Error Handling

| Go | Rust | Rationale |
|---|---|---|
| `error` interface | `thiserror` derive enum | Typed enum errors with `#[derive(Error)]` |
| `errors.Is(err, Target)` | `match err { MyErr::Target => }` | Enum variant matching replaces Is() |
| `errors.As(err, &target)` | `match err { MyErr::X(ref inner) => }` | Variant destructuring replaces As() |
| `fmt.Errorf("msg: %v", err)` | `err.context("msg")` via anyhow | Error wrapping with context |
| `panic("msg")` | `unreachable!()` or `expect()` | ONLY for truly impossible states |
| `log.Fatalf("msg")` | `return Err(...)` | Never crash — always propagate |
| `recover()` | Catch panics with `std::panic::catch_unwind` | Rarely needed in idiomatic Rust |

## Type System

| Go | Rust | Rationale |
|---|---|---|
| `interface{}` / `any` | `enum` (closed set) or `dyn Any` (open) | enum for known types, Any for truly dynamic |
| Go interface (implicit) | `trait` (explicit `impl`) | Rust requires explicit implementation |
| `type X struct { ... }` | `struct X { ... }` | Add `#[derive(Debug, Clone, Serialize, Deserialize)]` |
| `type X interface { ... }` | `trait X: Send + Sync { ... }` | Add Send+Sync if shared across threads |
| Embedded struct | `struct Outer { inner: Inner }` | Explicit field + manual delegation |
| `func (r *T) M()` | `impl T { fn m(&mut self) }` | Pointer receiver → &mut self |
| `func (r T) M()` | `impl T { fn m(&self) }` | Value receiver → &self |
| `map[K]V` | `HashMap<K, V>` | BTreeMap for sorted iteration |
| `[]T` (slice) | `Vec<T>` | Direct mapping |
| `[N]T` (array) | `[T; N]` | Direct mapping |
| `*T` (pointer) | `&T` or `&mut T` or `Box<T>` | Choose by ownership semantics |
| `nil` | `None` (for Option) | Nullable → Option<T> |

## Serialization & Wire Compatibility

| Go | Rust | Rationale |
|---|---|---|
| `json.Marshal(obj)` | `serde_json::to_string(&obj)` | Ensure field names match |
| `json.Unmarshal(data, &obj)` | `serde_json::from_str(data)` | Direct equivalent |
| `` `json:"name,omitempty"` `` | `#[serde(rename="name", skip_serializing_if="Option::is_none")]` | omitempty = skip if None |
| `` `json:"-"` `` | `#[serde(skip)]` | Skip entirely |
| Missing field → zero value | `#[serde(default)]` on struct/field | Go silently zeros; Rust rejects by default |
| protobuf | `prost` + `tonic` | Proto files must match exactly |
| HTTP handler | `axum` handler | Same wire behavior, different framework |
| gRPC | `tonic` | Same proto definitions |

## Common Patterns

| Go Pattern | Rust Pattern | Notes |
|---|---|---|
| `defer f.Close()` | RAII / `Drop` trait | Automatic cleanup on scope exit |
| `for range slice` | `for item in slice.iter()` | Iterator pattern |
| `switch v := x.(type)` | `match x { Variant(v) => }` | Type switch → enum match |
| `make(chan T, N)` | `mpsc::channel(N)` | Bounded channel |
| `close(ch)` | Drop the Sender | Receiver gets None/error |
| `_, ok := map[key]` | `map.contains_key(&key)` | Key existence check |
| `iota` enum | `#[repr(u8)] enum` with explicit values | Or use `num_enum` crate |
| `init()` function | `OnceLock` + explicit init call | No auto-init in Rust |
| Table-driven tests | `#[test_case]` or loop in `#[test]` | Use `test-case` crate or manual loop |
