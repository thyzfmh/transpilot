# Go → Rust Concurrency Patterns

## Pattern 1: Worker Pool

**Go**: N goroutines reading from a shared channel
```go
jobs := make(chan Job, 100)
for i := 0; i < N; i++ {
    go func() {
        for job := range jobs { process(job) }
    }()
}
```

**Rust**: tokio tasks with mpsc receiver
```rust
let (tx, rx) = tokio::sync::mpsc::channel(100);
let rx = Arc::new(Mutex::new(rx));
for _ in 0..N {
    let rx = rx.clone();
    tokio::spawn(async move {
        while let Some(job) = rx.lock().await.recv().await {
            process(job).await;
        }
    });
}
```

## Pattern 2: Fan-out / Fan-in

**Go**: Multiple goroutines writing to one result channel
```go
results := make(chan Result, N)
for _, item := range items {
    go func(i Item) { results <- process(i) }(item)
}
for i := 0; i < len(items); i++ { collect(<-results) }
```

**Rust**: Clone sender, spawn tasks, collect from receiver
```rust
let (tx, mut rx) = mpsc::channel(items.len());
for item in items {
    let tx = tx.clone();
    tokio::spawn(async move { tx.send(process(item).await).await.ok(); });
}
drop(tx); // Close sender so receiver knows when done
while let Some(result) = rx.recv().await { collect(result); }
```

## Pattern 3: Long-Running Controller Loop (CRITICAL)

**Go**: Goroutine with infinite loop
```go
go func() {
    for {
        select {
        case <-stopCh: return
        case item := <-queue: syncHandler(item)
        }
    }
}()
```

**Rust**: OS thread (NOT tokio::spawn) — blocking loops starve tokio scheduler
```rust
let stop = cancel_token.clone();
std::thread::spawn(move || {
    let rt = tokio::runtime::Builder::new_current_thread().enable_all().build().unwrap();
    loop {
        if stop.is_cancelled() { break; }
        match queue.recv_timeout(Duration::from_secs(5)) {
            Ok(item) => sync_handler(&item),
            Err(RecvTimeoutError::Timeout) => continue,
            Err(RecvTimeoutError::Disconnected) => break,
        }
    }
});
```

**Why**: Go goroutines are preemptive. tokio tasks are cooperative — infinite sync loops never yield.

## Pattern 4: Context Cancellation Propagation

**Go**: Parent context cancels all children
```go
ctx, cancel := context.WithCancel(parentCtx)
defer cancel()
go worker(ctx)
```

**Rust**: CancellationToken tree
```rust
let token = CancellationToken::new();
let child = token.child_token();
tokio::spawn(async move { worker(child).await; });
// Later:
token.cancel(); // All children cancelled
```

## Pattern 5: sync→async Bridge

**Go**: Implicit (goroutine model is unified)

**Rust**: Explicit bridge required
```rust
// Pattern A: async code calling sync (spawn_blocking)
let result = tokio::task::spawn_blocking(move || {
    expensive_sync_computation()
}).await?;

// Pattern B: sync code calling async (dedicated runtime)
let rt = tokio::runtime::Runtime::new()?;
let result = rt.block_on(async { async_operation().await });

// Pattern C: sync code within existing runtime (Handle)
let handle = tokio::runtime::Handle::current();
let result = handle.block_on(async { async_operation().await });
// WARNING: Pattern C panics if called from within a tokio context!
```

**Critical from Taibai D-ETCD3-02**: Use dedicated Runtime (Pattern B) for storage layers to avoid nested `block_on` panics.

## Pattern 6: Condition Variable / Notification

**Go**: sync.Cond
```go
cond := sync.NewCond(&sync.Mutex{})
go func() { cond.L.Lock(); cond.Wait(); cond.L.Unlock(); doWork() }()
cond.Signal()
```

**Rust**: tokio::sync::Notify (subscribe-then-recheck pattern)
```rust
let notify = Arc::new(Notify::new());
let n = notify.clone();
tokio::spawn(async move {
    loop {
        n.notified().await; // Subscribe FIRST
        if ready.load(Ordering::SeqCst) { break; } // Then recheck
    }
    do_work();
});
notify.notify_one();
```

**Critical**: The subscribe-then-recheck pattern prevents lost wakeups. Verified in Taibai D-PHASE1-CACHE-CORE.
