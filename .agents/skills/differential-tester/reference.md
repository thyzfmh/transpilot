# Differential-Tester 详细参考

> **核心原则**：Oracle 必须独立于被测代码。
> AI 写代码 + AI 写预期 = 自己批改作业 = 测试无效。

---

## Oracle 可信度排序

| 等级 | 来源 | parity 上限 | 风险 |
|------|------|------------|------|
| ★★★★★ | 源项目运行结果 | 95-99% | 几乎为零，AI 无法伪造运行时输出 |
| ★★★★ | 源代码静态特征（codegraph） | 80-90% | AI 改不了源代码 |
| ★★★ | 另一个 AI（context 隔离） | 70-85% | 同类幻觉共谋（低概率） |
| ★★ | property / metamorphic | 70-85% | 性质本身可能被 AI 误读 |
| ★ | 人类抽样审计 | 保底 | 抽样有遗漏，但戳穿"自洽幻觉" |
| ✗ | **AI 自己写的预期值** | **禁止** | 自我验证，无效 |

---

## 模式 1：run-source（首选）

源项目能跑，函数纯净（或 IO 可控）。

### 标准模板（Rust 端）

```rust
// tests/diff/foo_bar.rs
use std::process::Command;

fn src_run(input: &str) -> String {
    // 调用源项目的 CLI 入口或编译好的可执行文件
    let out = Command::new("../source_project/bin/foo")
        .arg("bar").arg(input)
        .output().unwrap();
    String::from_utf8(out.stdout).unwrap()
}

fn dst_run(input: &str) -> String {
    crate::foo::bar(input)
}

#[test]
fn diff_foo_bar_static_cases() {
    // 输入由 AI 写，预期值由 src_run 提供（AI 不接触预期）
    for input in &["", "a", "hello", "中文"] {
        assert_eq!(src_run(input), dst_run(input));
    }
}

proptest! {
    #[test]
    fn diff_foo_bar_random(input in ".{0,256}") {
        prop_assert_eq!(src_run(&input), dst_run(&input));
    }
}
```

**禁止写法**（必须被 lint/grep 拒绝）：
```rust
// ❌ AI 凭印象写的预期值
assert_eq!(foo("hello"), "HELLO");           // 字符串字面量
assert_eq!(bar(3), 6);                       // 数字字面量
assert!(baz(&v).contains("expected token")); // contains 字面量
```

---

## 模式 2：record-replay（涉及 I/O）

源项目能跑但涉及网络/文件 I/O。先**录制**一次源项目的真实交互，存为 fixture，之后**回放**比对。

### 步骤
1. 拦截源项目的 I/O（用 mitmproxy / strace / 自定义 wrapper）
2. 把交互序列化为 `tests/fixtures/<case>.jsonl`
3. 译码项目在测试时**注入相同输入**，断言**输出序列与 fixture 一致**

### 关键
- Fixture 由源项目运行产生，**AI 不接触**
- AI 只能写"如何注入 fixture"的代码

---

## 模式 3：static-codegraph（源跑不起来）

源项目已死、依赖丢失、只有源码可读。

### 可验证的静态特征

| 特征 | CodeGraph 命令 | 断言 |
|------|----------------|------|
| 函数签名 | `codegraph_node <fn>` | 参数数/类型对齐 |
| 调用方数 | `codegraph_callers <fn>` | \|src_count - dst_count\| ≤ 2 |
| 控制流分支数 | tree-sitter 数 if/match | 数量一致 |
| 常量值 | grep + 行号 | 数值一致 |
| 错误传播路径 | AST 数 ? / try | 路径数一致 |

```bash
# 示例：跑静态对照
./scripts/static-diff.sh \
  --src-node "k8s.io/foo.Bar" \
  --dst-node "crates::foo::Bar" \
  --check signature,callers,branches,constants
```

**parity 上限**：60-75%（无运行时验证，封顶不应虚标）。

---

## 模式 4：dual-AI（双 AI 隔离）

源跑不动 + 静态对照不够 → 上双 AI。

### 角色划分

```
┌─────────────────────────────────────────┐
│ AI-Coder  (translator skill)            │
│   inputs:  source code                  │
│   outputs: translated code (Rust)       │
└────────────────┬────────────────────────┘
                 │ 隔离 context window
                 ▼
┌─────────────────────────────────────────┐
│ AI-Tester (differential-tester skill)   │
│   inputs:  source code  (✓)             │
│           translated code (✗ 看不见)     │
│   outputs: test code (only input gen)   │
└─────────────────────────────────────────┘
```

### 实施
- Harness 用两个独立 subagent
- AI-Tester 的 prompt 严禁包含 `dst_files`、`Cargo.toml`、`src/**`
- AI-Tester 只能产出输入生成器 + 性质断言
- 同类幻觉共谋的概率 << 单 AI 自验证

---

## 与 anti-hallucination 的协作

| anti-halluc 类型 | differential-tester 对应模式 |
|------------------|------------------------------|
| api_fabrication | run-source（运行不会撒谎） |
| behavior_assumption | run-source / property |
| constant_drift | static-codegraph（grep 常量） |
| caller_inversion | static-codegraph（callers 计数） |
| coverage_thin | property + fuzz |

---

## 输出格式

```jsonc
// .opencode/diff-${wave}.jsonc
{
  "wave_id": "wave-3",
  "oracle_mode": "run-source|record-replay|static-codegraph|dual-ai",
  "cases_total": 142,
  "cases_passed": 138,
  "ai_derived_oracles": 0,    // 必须为 0
  "verdict": "pass|fail|escalate"
}
```

**`ai_derived_oracles > 0` 一票否决，触发 escalate。**

---

## 升级触发

写入 harness 第 6 种升级：

| 触发器 | 表现 |
|--------|------|
| **AI Oracle 污染** | `ai_derived_oracles > 0` 或测试代码含字符串/数字字面量预期值 |

人类决策：是引入新 Oracle 源（如装回老依赖让源项目跑起来），还是接受降低 parity 上限。
