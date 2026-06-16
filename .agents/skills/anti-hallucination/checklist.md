# 翻译核验清单（函数级强制）

> 每个**非平凡函数**翻译前必答 5 问。叶子工具函数（无外部调用、纯计算）可跳过。

## 5 问

### Q1. 源码证据
> 我刚才描述的源码行为，能贴出 `codegraph_node` 返回的原始片段吗？带行号？

- [ ] 是 → 继续
- [ ] 否 → **停**，先 codegraph_node

### Q2. API 证据
> 我用的目标语言 API（trait 方法/crate 函数），见过文档吗？

- [ ] 仓库内已有相同用法（codegraph_search 验证）
- [ ] docs.rs / cargo doc 看过当前版本签名
- [ ] 写了最小 cargo check 片段验证
- [ ] 以上都没有 → **停**，先做一项

### Q3. 常量证据
> 所有数字/字符串常量都引用了源码行号吗？

- [ ] 所有 const/static 都有 `// from <src>:<line>` 注释
- [ ] 关键数值（端口/超时/重试）grep 双方仓库一致
- [ ] 否 → **停**，回去补引用

### Q4. 调用方向证据
> codegraph_callers 跑过吗？

- [ ] 翻译前查源：N 个调用方
- [ ] 翻译后查译：M 个调用方，|N - M| ≤ 2
- [ ] 否 → **停**，跑 callers

### Q5. 反例证据
> 我能想出一个让源/译行为不一致的输入吗？

- [ ] 想到了 → 写成测试用例
- [ ] 想不到 → **警告**，覆盖可能不够，标记 `coverage:thin`

---

## 输出（写到 wave 报告）

```jsonc
{
  "function": "crates::foo::Bar::process",
  "checklist": {
    "q1_source_evidence": "k8s.io/foo/bar.go:42-87",
    "q2_api_evidence": "docs.rs/tokio/1.x/sync/struct.Mutex.html#method.try_lock",
    "q3_constant_evidence": ["TIMEOUT=30s (bar.go:51)", "MAX_RETRY=3 (bar.go:53)"],
    "q4_callers_match": { "src": 7, "dst": 7 },
    "q5_counterexample": "concurrent close+send → both panic"
  }
}
```

---

## 何时跳过本清单

仅以下场景允许跳过（AI 自决，无需问人类）：

- 函数 < 10 行**且**纯计算（无 I/O、无并发）
- 单纯重命名（如 camelCase → snake_case）
- 字符串常量搬运（无逻辑）

跳过时在 commit message 标 `[skip-checklist: trivial]`。
