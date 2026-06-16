#!/bin/bash
# Transpilot — 项目初始化脚本
# 用法: ./scripts/init-project.sh <project_name> <source_lang> <source_path> <target_path>
# 遵循 AGENTS.md Rule 14: T0 必须产出 acceptance-plan.yaml
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
echo "项目: $PROJECT_NAME | 语言: $SOURCE_LANG → Rust"
echo "源: $SOURCE_PATH"
echo "目标: $TARGET_PATH"

# 创建目标目录
mkdir -p "$TARGET_PATH"
cd "$TARGET_PATH"

# 初始化 git
if [ ! -d .git ]; then
    git init
fi

# === 治理文件 ===
mkdir -p .opencode

# translation-state.jsonc
sed -e "s/__PROJECT_NAME__/$PROJECT_NAME/g" \
    -e "s/__SOURCE_LANG__/$SOURCE_LANG/g" \
    -e "s|__SOURCE_PATH__|$SOURCE_PATH|g" \
    -e "s|__TARGET_PATH__|$TARGET_PATH|g" \
    -e "s/__START_DATE__/$TODAY/g" \
    "$TEMPLATE_DIR/translation-state.template.jsonc" > .opencode/translation-state.jsonc

# decisions.md
sed -e "s/\[PROJECT_NAME\]/$PROJECT_NAME/g" \
    "$TEMPLATE_DIR/decisions.template.md" > .opencode/decisions.md

# acceptance-plan.yaml (Rule 14: T0 必填)
sed -e "s|../path/to/source|$SOURCE_PATH|g" \
    -e "s|<dir1>|src|g" \
    -e "s|<dir2>|# (add more as needed)|g" \
    "$TEMPLATE_DIR/acceptance-plan.yaml.template" > acceptance-plan.yaml

echo ""
echo "⚠️  请编辑 acceptance-plan.yaml 确认验收策略后再启动翻译"
echo "    特别关注: oracle_primary / dimensions / cases"

# === 链接全量技能 ===
mkdir -p .agents/skills

# 核心 skills (全部挂载)
SKILLS_TO_LINK=(
    shared
    translator
    parity-checker
    e2e-debugger
    status-dashboard
    self-improving
    anti-hallucination
    differential-tester
    codegraph-navigator
)

# 语言相关 skill
if [ "$SOURCE_LANG" = "go" ]; then
    SKILLS_TO_LINK+=(go2rust)
elif [ "$SOURCE_LANG" = "c" ]; then
    SKILLS_TO_LINK+=(c2rust)
fi

for SKILL in "${SKILLS_TO_LINK[@]}"; do
    if [ -d "$TRANSPILOT_ROOT/.agents/skills/$SKILL" ]; then
        ln -sfn "$TRANSPILOT_ROOT/.agents/skills/$SKILL" ".agents/skills/$SKILL"
    else
        echo "  [warn] skill '$SKILL' not found in transpilot, skipping"
    fi
done

# === 链接脚本 ===
mkdir -p scripts
for SCRIPT in "$TRANSPILOT_ROOT/scripts/"*.sh; do
    BASENAME=$(basename "$SCRIPT")
    if [ "$BASENAME" != "init-project.sh" ]; then
        ln -sfn "$SCRIPT" "scripts/$BASENAME"
    fi
done

# === 生成完整 AGENTS.md ===
cat > AGENTS.md << AGENTSEOF
# $PROJECT_NAME — Transpilot Translation Project

## Source
- Language: $SOURCE_LANG
- Path: $SOURCE_PATH
- Started: $TODAY

## Core Rules
1. 1:1 replication — match source *behavior*, not *API shape*
2. Rust idioms — adapt to ownership, Result, traits
3. No unwrap() in production code
4. Update .opencode/translation-state.jsonc after each module
5. E2E Gate — run E2E after FIRST module, not after ALL
6. Dual DI — both Mock and Real implementations
7. Probe first — check if code exists before writing
8. Wave pattern — 3-5 modules per batch
9. Leaf first — translate leaf packages before core
10. Zero placeholders at wave end — \`scripts/forbid-placeholders.sh\` must pass
11. Evidence-based translation — no assertion without source citation; every non-trivial function passes anti-hallucination 6-questions
12. Fresh index — \`scripts/check-codegraph-freshness.sh\` runs before each wave
13. Oracle independence — expected values from src_run()/fixtures/codegraph only; never AI-derived. Enforced by \`scripts/check-oracle-independence.sh\`
14. T0 acceptance plan — acceptance-plan.yaml must be user-confirmed before wave-1

## Skill Usage
| I want to... | Run |
|---|---|
| Start/continue translating | \`/translator $SOURCE_LANG $PROJECT_NAME\` |
| Audit hallucinations | \`/anti-hallucination <wave>\` |
| Verify parity | \`/parity-checker $PROJECT_NAME [module]\` |
| Diff-test behavior | \`/differential-tester <wave>\` |
| Run E2E validation | \`/e2e-validator $PROJECT_NAME\` |
| Check progress | \`/status\` |
| Check index freshness | \`./scripts/check-codegraph-freshness.sh\` |
| Check placeholders | \`./scripts/forbid-placeholders.sh src\` |
| Check Oracle independence | \`./scripts/check-oracle-independence.sh tests\` |

## Cross-Skill Contract
All skills exchange data via \`.opencode/*.jsonc\` — schema at \`.agents/skills/shared/interfaces.md\` (v1.0).
AGENTSEOF

# === Cargo workspace ===
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

# === .gitignore ===
if [ ! -f .gitignore ]; then
    printf "/target\n**/*.rs.bk\nCargo.lock\n.DS_Store\n" > .gitignore
fi

echo ""
echo "✅ Project initialized at $TARGET_PATH"
echo ""
echo "Next steps:"
echo "  1. Edit acceptance-plan.yaml (confirm Oracle strategy & acceptance cases)"
echo "  2. Run CodeGraph indexing on source project (recommended for >500 files)"
echo "  3. Start translating: /translator $SOURCE_LANG $PROJECT_NAME"
