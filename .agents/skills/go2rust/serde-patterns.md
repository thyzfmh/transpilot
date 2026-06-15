# Go → Rust Serialization Patterns

## Critical Difference: Missing Field Handling

**Go**: `encoding/json` silently zero-initializes missing struct fields
**Rust**: `serde` REJECTS missing non-Option fields by default

This is the #1 source of deserialization bugs in Go→Rust translation (Taibai D-AUTHN-MIDDLEWARE-RESOLVED).

### Solution Matrix

| Scenario | Go Behavior | Rust Solution |
|----------|-------------|---------------|
| Field always present | Normal | Normal (no annotation) |
| Field sometimes absent, zero is valid | Zero-init | `#[serde(default)]` on field |
| Field sometimes absent, None is distinct | Zero-init | `Option<T>` + `#[serde(default)]` |
| All fields may be absent | Zero-init | `#[serde(default)]` on struct |

## Pattern S-001: omitempty → skip_serializing_if

**Go**:
```go
type Config struct {
    Name    string `json:"name"`
    Timeout int    `json:"timeout,omitempty"`
    Labels  map[string]string `json:"labels,omitempty"`
}
```

**Rust**:
```rust
#[derive(Serialize, Deserialize)]
struct Config {
    name: String,
    #[serde(default, skip_serializing_if = "is_zero")]
    timeout: i32,
    #[serde(default, skip_serializing_if = "HashMap::is_empty")]
    labels: HashMap<String, String>,
}

fn is_zero(v: &i32) -> bool { *v == 0 }
```

**Go omitempty rules** (must replicate exactly):
- `int/float`: omit if 0
- `string`: omit if ""
- `bool`: omit if false
- `slice/map`: omit if nil (NOT empty!)
- `pointer`: omit if nil

## Pattern S-002: Field Renaming

**Go**:
```go
type Pod struct {
    APIVersion string `json:"apiVersion"`
    Kind       string `json:"kind"`
    ObjectMeta `json:"metadata"`
}
```

**Rust**:
```rust
#[derive(Serialize, Deserialize)]
#[serde(rename_all = "camelCase")]  // Covers most cases
struct Pod {
    api_version: String,  // → "apiVersion"
    kind: String,         // → "kind"
    metadata: ObjectMeta, // → "metadata"
}
```

Or explicit per-field:
```rust
#[serde(rename = "apiVersion")]
api_version: String,
```

## Pattern S-003: Embedded Struct → Flatten

**Go** (embedded struct promotes fields):
```go
type Pod struct {
    metav1.TypeMeta   `json:",inline"`
    metav1.ObjectMeta `json:"metadata"`
    Spec PodSpec      `json:"spec"`
}
```

**Rust**:
```rust
#[derive(Serialize, Deserialize)]
struct Pod {
    #[serde(flatten)]
    type_meta: TypeMeta,    // Fields promoted to top level
    metadata: ObjectMeta,   // Normal nested field
    spec: PodSpec,
}
```

## Pattern S-004: Duration Serialization

**Go**: `time.Duration` serializes as nanoseconds (int64), `metav1.Duration` as "1.5s"

**Rust**: Custom wrapper
```rust
#[derive(Clone, Debug)]
pub struct Duration(pub std::time::Duration);

impl Serialize for Duration {
    fn serialize<S: Serializer>(&self, s: S) -> Result<S::Ok, S::Error> {
        let secs = self.0.as_secs_f64();
        s.serialize_str(&format!("{}s", secs))
    }
}

impl<'de> Deserialize<'de> for Duration {
    fn deserialize<D: Deserializer<'de>>(d: D) -> Result<Self, D::Error> {
        let s = String::deserialize(d)?;
        let secs: f64 = s.trim_end_matches('s').parse()
            .map_err(serde::de::Error::custom)?;
        Ok(Duration(std::time::Duration::from_secs_f64(secs)))
    }
}
```

## Pattern S-005: Enum Serialization

**Go**: String constants
```go
type Phase string
const (
    PhasePending Phase = "Pending"
    PhaseRunning Phase = "Running"
    PhaseDone    Phase = "Done"
)
```

**Rust**:
```rust
#[derive(Serialize, Deserialize, Debug, Clone, PartialEq)]
pub enum Phase {
    Pending,
    Running,
    Done,
}
// Serializes as: "Pending", "Running", "Done"
```

For non-matching case:
```rust
#[derive(Serialize, Deserialize)]
#[serde(rename_all = "lowercase")]
pub enum Phase { Pending, Running, Done }
// Serializes as: "pending", "running", "done"
```

## Pattern S-006: Nullable vs Absent

**Go**: `*int` can be nil (absent) or 0 (present with zero value)
```go
type Config struct {
    Replicas *int32 `json:"replicas,omitempty"`
}
```

**Rust**: `Option<i32>` distinguishes None (absent) from Some(0)
```rust
#[derive(Serialize, Deserialize)]
struct Config {
    #[serde(default, skip_serializing_if = "Option::is_none")]
    replicas: Option<i32>,
}
```

## Wire Compatibility Checklist

- [ ] JSON field names match exactly (case-sensitive)
- [ ] omitempty behavior replicated (zero vs nil distinction)
- [ ] Missing fields don't cause deserialization errors (#[serde(default)])
- [ ] Enum string values match exactly
- [ ] Duration format matches ("1.5s" vs nanoseconds)
- [ ] Null vs absent distinction preserved (Option vs default)
- [ ] Embedded/inline fields flattened correctly
