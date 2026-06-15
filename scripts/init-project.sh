#!/bin/bash
# Transpilot — 项目初始化脚本
# 用法: ./scripts/init-project.sh <project_name> <source_lang> <source_path> <target_path>

set -euo pipefail

PROJECT_NAME="${1:?用法: $0 <project_name> <source_lang> <source_path> <target_path>}"
SOURCE_LANG="${2:?需要源语言: go 或 c}"
SOURCE_PATH="${3:?需要源项目路径}"
TARGET_PATH="${4:?需要目标项目路径}"

if [[ "$SOURCE_LANG" != "go" && "$SOURCE_LANG" != "c" ]]; then
    echo "错误: 源语言必须是 go 或 c"
    exit 1
fi

if [ ! -d "$SOURCE_PATH" ]; then
    echo "错误: 源路径不存在: $SOURCE_PATH"
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
TRANSPILOT_ROOT="$(dirname "$SCRIPT_DIR")"
TEMPLATE_DIR="$TRANSPILOT_ROOT/templates"
TODAY=$(date +%Y-%m-%d)

echo "Transpilot — 初始化翻译项目"
echo "项目: $PROJECT_NAME | 语言: $SOURCE_LANG"
echo "源: $SOURCE_PATH"
echo "目标: $TARGET_PATH"

# 创建目标目录
mkdir -p "$TARGET_PATH"
cd "$TARGET_PATH"

# 初始化 git
if [ ! -d .git ]; then
    git init
fi

# 创建治理文件
mkdir -p .opencode
sed -e "s/__PROJECT_NAME__/$PROJECT_NAME/g"     -e "s/__SOURCE_LANG__/$SOURCE_LANG/g"     -e "s|__SOURCE_PATH__|$SOURCE_PATH|g"     -e "s|__TARGET_PATH__|$TARGET_PATH|g"     -e "s/__START_DATE__/$TODAY/g"     "$TEMPLATE_DIR/translation-state.template.jsonc" > .opencode/translation-state.jsonc

sed -e "s/\[PROJECT_NAME\]/$PROJECT_NAME/g"     "$TEMPLATE_DIR/decisions.template.md" > .opencode/decisions.md

# 链接技能文件
mkdir -p .agents/skills
ln -sfn "$TRANSPILOT_ROOT/.agents/skills/shared" .agents/skills/shared

if [ "$SOURCE_LANG" = "go" ]; then
    ln -sfn "$TRANSPILOT_ROOT/.agents/skills/go2rust" .agents/skills/go2rust
elif [ "$SOURCE_LANG" = "c" ]; then
    ln -sfn "$TRANSPILOT_ROOT/.agents/skills/c2rust" .agents/skills/c2rust
fi

ln -sfn "$TRANSPILOT_ROOT/.agents/skills/translator" .agents/skills/translator
ln -sfn "$TRANSPILOT_ROOT/.agents/skills/parity-checker" .agents/skills/parity-checker
ln -sfn "$TRANSPILOT_ROOT/.agents/skills/e2e-debugger" .agents/skills/e2e-debugger
ln -sfn "$TRANSPILOT_ROOT/.agents/skills/status-dashboard" .agents/skills/status-dashboard
ln -sfn "$TRANSPILOT_ROOT/.agents/skills/self-improving" .agents/skills/self-improving

# 创建 AGENTS.md
cat > AGENTS.md << AGENTSEOF
# $PROJECT_NAME — Translation Project

## Source: $SOURCE_LANG ($SOURCE_PATH)

## Rules
1. Read .opencode/translation-state.jsonc at session start
2. Wave mode (3-5 modules per wave)
3. Leaf-first translation order
4. E2E after each wave
5. Record decisions to .opencode/decisions.md
AGENTSEOF

# 初始化 Cargo workspace
if [ ! -f Cargo.toml ]; then
    cat > Cargo.toml << CARGOEOF
[workspace]
resolver = "2"
members = []

[workspace.package]
version = "0.1.0"
edition = "2021"

[workspace.dependencies]
thiserror = "2"
anyhow = "1"
serde = { version = "1", features = ["derive"] }
serde_json = "1"
tokio = { version = "1", features = ["full"] }
tracing = "0.1"
CARGOEOF
fi

# .gitignore
if [ ! -f .gitignore ]; then
    printf "/target
**/*.rs.bk
Cargo.lock
.DS_Store
" > .gitignore
fi

echo ""
echo "Done! Project initialized at $TARGET_PATH"
echo "Next: open in IDE and run /translate"
