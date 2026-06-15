# C → Rust Memory Management Patterns

## M-001: malloc/free → Box<T> (Single Ownership)

**C**:
```c
struct Node *node = malloc(sizeof(struct Node));
node->value = 42;
// ... use node ...
free(node);
```

**Rust**:
```rust
let node = Box::new(Node { value: 42 });
// ... use node ...
// Automatically freed when Box goes out of scope
```

## M-002: realloc → Vec<T> (Dynamic Array)

**C**:
```c
int *arr = malloc(n * sizeof(int));
arr = realloc(arr, (n * 2) * sizeof(int));
free(arr);
```

**Rust**:
```rust
let mut arr = Vec::with_capacity(n);
arr.reserve(n); // Equivalent to growing capacity
// Vec handles all allocation/deallocation automatically
```

## M-003: Reference Counting (Shared Ownership)

**C**:
```c
struct Obj { int refcount; void *data; };
void retain(struct Obj *o) { o->refcount++; }
void release(struct Obj *o) {
    if (--o->refcount == 0) { free(o->data); free(o); }
}
```

**Rust**:
```rust
use std::sync::Arc; // Thread-safe (or Rc for single-thread)
let obj = Arc::new(Obj { data: vec![1, 2, 3] });
let obj2 = Arc::clone(&obj); // Increment refcount
// Automatically freed when last Arc is dropped
```

## M-004: String Handling

**C**:
```c
char *s = strdup("hello");
char *result = malloc(strlen(s) + strlen(" world") + 1);
strcpy(result, s); strcat(result, " world"); // Buffer overflow risk!
free(s); free(result);
```

**Rust**:
```rust
let mut s = String::from("hello");
s.push_str(" world"); // Safe, auto-reallocates
// No manual free needed
```

## M-005: Output Parameters → Return Values

**C**:
```c
int parse_int(const char *input, int *result, char **error) {
    // Returns 0 on success, -1 on failure
    // *result set on success, *error set on failure
}
```

**Rust**:
```rust
fn parse_int(input: &str) -> Result<i32, ParseError> {
    input.parse::<i32>().map_err(|e| ParseError::new(e))
}
```

## M-006: Nullable Pointers → Option<T>

**C**:
```c
Node *find(List *list, int key) {
    // Returns NULL if not found
    for (Node *n = list->head; n; n = n->next)
        if (n->key == key) return n;
    return NULL;
}
```

**Rust**:
```rust
fn find(list: &List, key: i32) -> Option<&Node> {
    list.iter().find(|n| n.key == key)
}
```

## M-007: Ownership Transfer Semantics

**C** (convention: caller must free):
```c
char *generate_report(void); // Caller must free() return value
void consume_buffer(char *buf); // Function takes ownership, will free
```

**Rust**:
```rust
fn generate_report() -> String { ... } // Ownership transferred to caller
fn consume_buffer(buf: Vec<u8>) { ... } // Takes ownership via move
```

## M-008: Borrowing Decision Tree

```
Does the function need to OWN the data?
├── YES: Does it share with others?
│   ├── YES → Arc<T> (thread-safe) or Rc<T> (single-thread)
│   └── NO  → Box<T> (heap) or T (stack, if sized)
└── NO: Does it need to MODIFY the data?
    ├── YES → &mut T
    └── NO  → &T
```

**C const correctness → Rust borrows**:
- `const T *` → `&T` (immutable borrow)
- `T *` (read-write) → `&mut T` (mutable borrow)
- `T *` (ownership transfer) → `Box<T>` or `T`

## M-009: Memory Pools / Arenas

**C**:
```c
Pool *pool = pool_create(4096);
void *obj1 = pool_alloc(pool, sizeof(Obj));
void *obj2 = pool_alloc(pool, sizeof(Obj));
pool_destroy(pool); // Free ALL objects at once
```

**Rust** (using `bumpalo` crate):
```rust
use bumpalo::Bump;
let arena = Bump::new();
let obj1 = arena.alloc(Obj { ... });
let obj2 = arena.alloc(Obj { ... });
// All objects freed when arena is dropped
```

Alternative: typed-arena for homogeneous allocation:
```rust
use typed_arena::Arena;
let arena = Arena::new();
let obj = arena.alloc(Obj { ... }); // Returns &Obj (borrowed from arena)
```

## Common Pitfalls

| C Pattern | Pitfall | Rust Solution |
|-----------|---------|---------------|
| `free(ptr); use(ptr)` | Use-after-free | Ownership system prevents this |
| `free(ptr); free(ptr)` | Double-free | Drop called exactly once |
| Forget to free | Memory leak | Drop called automatically |
| Return stack pointer | Dangling pointer | Lifetime system prevents this |
| Buffer overflow | UB, security vuln | Vec bounds checking |
| Uninitialized read | UB | All values initialized in Rust |
