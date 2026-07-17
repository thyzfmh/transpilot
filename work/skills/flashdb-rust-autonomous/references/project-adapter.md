# 当前项目适配器

本文件只描述当前仓库的项目事实。通用执行方法位于 `autonomous-source-translation-method.md`，C 到 Rust 约束位于 `c-to-rust-translation-spec.md`。

机器执行所需的路径、测试文件和公开头文件同时保存在 harness 的
`project-adapter.json`。通用发现、状态和覆盖脚本从该文件读取项目事实。

## 路径和产物

- 源项目：`code/FlashDB`
- 目标项目：`code/flashDB_rust`
- 目标语言：Rust
- 目标产物：`code/flashDB_rust/target/release/libflashdb_rust.a`
- 结果文件：`result/output.md`
- 交互和验证记录：`logs/trace/`
- 可信完成命令：`work/skills/flashdb-rust-autonomous/scripts/final_verify_target.sh`

## 固定配置

- POSIX 文件模式
- KVDB 和 TSDB 启用
- `FDB_WRITE_GRAN=1`
- 32 位有符号时间戳

配置事实必须由 `tests/fdb_cfg.h`、编译结果和 `config_profile_check.py` 验证，不得只相信本文件。

## Harness 安装

从仓库根目录执行：

```bash
SKILL_DIR="work/skills/flashdb-rust-autonomous"
TARGET="code/flashDB_rust"
"$SKILL_DIR/scripts/install_target_harness.sh" "$TARGET"
```

该命令可在目标目录完全不存在时执行。它只创建缺失的目标骨架、安装固定
Cargo 配置和 harness，不覆盖已有 `Cargo.toml`、Rust 源码或测试。

## 原项目基线

从目标目录执行：

```bash
python3 harness/source_oracle_runner.py
```

运行器必须清理旧二进制，重新编译原 C 实现，运行全部原测试并生成
`reports/source-oracle.json` 和 `reports/source-oracle-logs/`。该结果是
最终证据门 `final-source-oracle` 的输入。原测试数量和顺序必须由测试源码机械发现，
提取语法由适配器提供，不在 Skill 核心流程中硬编码。

## 源原生目标验收

从目标目录执行：

```bash
./harness/c_link_test.sh
```

该命令使用原头文件和原 C 测试调用 Rust 静态库，并生成 `reports/source-acceptance.json`。这是主要行为进度，不得用 Rust 自测替代。

每轮先执行 `./harness/build_check.sh` 登记唯一待测静态库，再执行
`./harness/c_link_test.sh`。后续源测试、互操作和 ABI/布局探针必须复用
该产物；后续源测试、差分和 ABI/布局探针必须复用它，测试过程中产物变化
会使证据失败。

## 当前项目附加契约

- release 静态库导出公开 `fdb_*` C 符号；
- C 与 Rust 编译后的控制命令数值一致；
- C ABI 公共结构的大小、对齐和字段偏移由双端探针逐项一致；
- 公开函数 LLVM 签名、枚举和回调兼容；
- C 与 Rust 双向读取持久化数据；
- 确定性输入的介质布局与源实现兼容；
- 原测试重复运行原实现以校准动态字节，再运行 Rust 产物，自动比较用例结果、文件集合、长度与稳定内容字节；
- panic 不跨越 C ABI；
- 源码与固定 harness 保持不变。

`project-adapter.json` 只保存可机械验证的项目事实和命令，不保存按业务
名称编写的测试逻辑。源模块与原测试套件由发现结果自动形成覆盖表；运行
副作用由通用快照器自动捕获，源实现重复运行后由通用比较器排除自身变化
的动态字节。`layout_contracts` 只描述从公开头文件和目标
FFI 类型发现的双端类型/字段对应关系，不包含业务行为或固定用例数量。

这些契约来自当前项目边界。换项目时应替换本适配器，而不是修改通用方法。
