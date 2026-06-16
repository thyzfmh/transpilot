# Anti-Hallucination 详细参考

翻译场景下幻觉的危害不是"代码跑不起来"——那种容易发现。
真正危险的是：**编译过、测试过、parity 显示绿，但语义已经偏离源项目**。
本文档列出 5 类典型幻觉与对治手段。

---

## 类型 1：API 编造（最常见）

### 表现
- 凭印象写 `tokio::sync::Mutex::try_acquire`（实际叫 `try_lock`）
- 写 `Vec::reserve_exact_capacity`（实际叫 `reserve_exact`）
- 用了一个根本不存在的 trait 方法

### 检测
- 编译期：cargo check 会报错（成本：一次迭代浪费）
- 但更危险的是：**AI 用了一个**存在但语义不同**的 API**（如把 Go `sync.Map.LoadOrStore` 翻成 Rust `dashmap::DashMap::insert`，行为不等价）

### 对治
1. **未见过的 API 先写最小示例 cargo check**
   ```rust
   // /tmp/check.rs
   fn main() { let m = tokio::sync::Mutex::new(0); let _ = m.try_lock(); }
   ```
2. **优先在仓库内 codegraph_search 找已有用法**——已有用法 = 团队验证过
3. **chrono / tokio / serde 等核心 crate 的 API 改动**：每次都查 docs.rs 当前版本

---

## 类型 2：行为臆测

### 表现
- "Go 的 `sync.Map` 就是线程安全的 HashMap" → 错，它有 LoadOrStore/CompareAndSwap 等独有原子语义
- "Go 的 channel close 后 send 会 panic" → 对，但翻译时容易漏掉这个边界
- "context.WithTimeout 取消子树" → 翻译时容易把传播链漏译

### 检测
- 单元测试覆盖不到的边界场景

### 对治
1. **codegraph_node 取源码原文**——不要凭记忆描述行为
2. **行为对照表**：每个非平凡源 API，列出"语义点 → 译码对应处"
3. **反例自检**：能想出一个让源/译行为不一致的输入吗？想不出 = 覆盖不够

---

## 类型 3：常量伪造

### 表现
- 端口写 `8443`（实际源码是 `6443`）
- 超时写 `30 * time.Second` → `Duration::from_secs(60)`（值变了）
- 重试次数 `3` → `5`

### 检测
- 单元测试常常测不到具体数值，运行期才暴露

### 对治
1. **任何数字/字符串常量必带源码行号引用**
   ```rust
   // src/foo.rs (translated from k8s.io/foo/bar.go:123)
   const TIMEOUT: Duration = Duration::from_secs(30); // bar.go:127
   ```
2. **批量翻译完后跑 grep 校对**：
   ```bash
   grep -rE "Duration::from_(secs|millis)" src/ | wc -l
   # 对比源项目 time.Duration 出现次数
   ```

---

## 类型 4：依赖反转幻觉

### 表现
- 颠倒"A 调 B"为"B 调 A"
- 编造一个不存在的中间层
- 把同步调用翻成异步（或反之）

### 检测
- 静态可检测：codegraph_callers 双向跑

### 对治
```bash
# 翻译前
codegraph_callers --node "k8s.io/foo.Bar" → 列出 N 个调用方
# 翻译后
codegraph_callers --node "crates::foo::Bar" → 必须也是 N 个（允许 -2 ~ +2 浮动，超出需解释）
```

---

## 类型 5：测试通过 ≠ 语义等价（最隐蔽）

### 表现
- parity-checker 报 100%
- 但只覆盖 happy path
- 边界场景（空输入、超大输入、并发竞态）行为悄悄不一致

### 对治
1. **property-based 测试** — 用 proptest/quickcheck 生成随机输入双跑
2. **fuzz 测试** — 至少对核心数据结构跑 cargo fuzz
3. **差分测试** — 同一输入喂给源项目 + 译码项目，对比输出
4. **拒绝单一指标** — parity score 不是唯一通过条件，必须 + 反例自检

---

## 与其他 skill 的协作

| 上下游 skill | 协作方式 |
|--------------|----------|
| codegraph-navigator | 提供"证据"原料（node/callers） |
| translator | 在翻译前调本 skill 做核验 |
| parity-checker | 在 parity 100% 时，本 skill 做深度核验补刀 |
| self-improving | 本 skill 抓出的幻觉 → 写入 semantic-patterns 防再犯 |

---

## 升级触发器（写入 harness）

连续 3 个 wave 内本 skill 抓出 ≥3 处"无源码引用断言" → 升级人类。
原因：AI 产生了**结构性**幻觉倾向，单纯 retry 解决不了。

---

## 输出格式（与 parity-checker 协议对齐）

本 skill 在 wave 结束时输出一份审计报告：

```jsonc
// .opencode/anti-halluc-wave-N.jsonc
{
  "wave": "N",
  "audited_modules": ["mod1", "mod2"],
  "findings": [
    { "severity": "high",   "type": "api_fabrication",   "loc": "src/foo.rs:42", "evidence": "..." },
    { "severity": "medium", "type": "constant_drift",    "loc": "src/bar.rs:17", "evidence": "..." }
  ],
  "hallucination_score": 0.15,  // 0.0 = 完美，>0.3 触发升级
  "verdict": "pass" | "retry" | "escalate"
}
```
