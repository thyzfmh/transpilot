# Go → Rust Error Handling Patterns

## Pattern E-001: Simple Error Return

**Go**:
```go
func doWork() error {
    if err := step1(); err != nil { return fmt.Errorf("step1 failed: %w", err) }
    if err := step2(); err != nil { return fmt.Errorf("step2 failed: %w", err) }
    return nil
}
```

**Rust**:
```rust
fn do_work() -> Result<(), WorkError> {
    step1().map_err(|e| WorkError::Step1Failed(e))?;
    step2().map_err(|e| WorkError::Step2Failed(e))?;
    Ok(())
}
```

## Pattern E-002: Error Type Hierarchy (thiserror)

**Go**: Single `error` interface, wrapped with `fmt.Errorf("%w")`

**Rust**: Typed enum with `thiserror`
```rust
#[derive(Debug, thiserror::Error)]
pub enum ServiceError {
    #[error("database error: {0}")]
    Database(#[from] DbError),
    #[error("network error: {0}")]
    Network(#[from] NetworkError),
    #[error("validation failed: {message}")]
    Validation { message: String },
    #[error("not found: {resource}")]
    NotFound { resource: String },
}
```

## Pattern E-003: Error Context (anyhow)

**Go**: `fmt.Errorf("doing X: %w", err)` chains context

**Rust**: `anyhow::Context` trait
```rust
use anyhow::{Context, Result};

fn load_config(path: &str) -> Result<Config> {
    let data = std::fs::read_to_string(path)
        .with_context(|| format!("failed to read config from {}", path))?;
    let config: Config = serde_json::from_str(&data)
        .context("failed to parse config JSON")?;
    Ok(config)
}
```

**When to use anyhow vs thiserror**:
- Library code: `thiserror` (callers need to match on variants)
- Application code: `anyhow` (just propagate with context)
- Translation rule: Use thiserror for public APIs, anyhow for internal logic

## Pattern E-004: errors.Is / errors.As → match

**Go**:
```go
if errors.Is(err, ErrNotFound) { handleNotFound() }
var validErr *ValidationError
if errors.As(err, &validErr) { handleValidation(validErr) }
```

**Rust**:
```rust
match err {
    ServiceError::NotFound { .. } => handle_not_found(),
    ServiceError::Validation { message } => handle_validation(&message),
    _ => return Err(err),
}
```

## Pattern E-005: Panic Recovery → Result

**Go**: Sometimes uses panic for "impossible" states with recover()
```go
func safeDiv(a, b int) (result int, err error) {
    defer func() {
        if r := recover(); r != nil { err = fmt.Errorf("panic: %v", r) }
    }()
    return a / b, nil
}
```

**Rust**: Use Result directly — no need for panic/recover pattern
```rust
fn safe_div(a: i32, b: i32) -> Result<i32, DivError> {
    if b == 0 { return Err(DivError::DivideByZero); }
    Ok(a / b)
}
```

## Pattern E-006: Multi-Error Accumulation

**Go**: `k8s.io/apimachinery/pkg/util/errors` aggregates errors
```go
var errs []error
for _, item := range items {
    if err := validate(item); err != nil { errs = append(errs, err) }
}
return utilerrors.NewAggregate(errs)
```

**Rust**:
```rust
let errors: Vec<ValidationError> = items.iter()
    .filter_map(|item| validate(item).err())
    .collect();
if errors.is_empty() { Ok(()) } else { Err(AggregateError(errors)) }
```

## Rules

1. **Never use `unwrap()` in production** — use `?` or explicit error handling
2. **Never use `todo!()`** — return `Ok(default)` with `// TODO:` comment
3. **Go's `log.Fatal` → `return Err()`** — propagate upward, let main() decide
4. **Go's sentinel errors → enum variants** — `var ErrNotFound = errors.New(...)` → `enum::NotFound`
5. **Go's typed error checking → match** — no need for Is()/As() in Rust
