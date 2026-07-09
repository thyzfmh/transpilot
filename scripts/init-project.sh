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
cat > .opencode/translation-state.jsonc <<EOF
// Translation State — $PROJECT_NAME
{
  "project": "$PROJECT_NAME",
  "src_lang": "$SOURCE_LANG",
  "dst_lang": "rust",
  "source_path": "$SOURCE_PATH",
  "target_path": "$TARGET_PATH",
  "started_at": "$TODAY",
  "overall_parity": 0.0,
  "current_wave": null,
  "waves": {},
  "modules": {},
  "blockers": [],
  "exclusions": [],
  "session_history": []
}
EOF

# decisions.md
cat > .opencode/decisions.md <<EOF
# Translation Decisions — $PROJECT_NAME

Record non-trivial translation decisions here.

## Format

## D-XXX: Title
- Date: YYYY-MM-DD
- Context: why the decision is needed
- Options: alternatives considered
- Decision: selected option
- Reason: why this option was selected
- Consequences: impact on translation and verification

## Project Decisions

_Append decisions during translation._
EOF

# acceptance-plan.yaml (Rule 14: T0 必填)
cat > acceptance-plan.yaml <<EOF
scope:
  source_project: "$SOURCE_PATH"
  target_project: "./"
  in:
    - "src"
  out:
    - "vendor/**"
    - "**/*_generated.*"

verification:
  oracle_primary: run-source
  oracle_fallback: static-codegraph
  forbidden:
    - ai-derived-expected-values
    - hardcoded-string-literals-in-assert
  source_runnable: true
  source_test_coverage_pct: 30

dimensions:
  api_compat:    { weight: 0.30, target: 1.00 }
  behavior:      { weight: 0.40, target: 0.95 }
  perf:          { weight: 0.10, target: 0.80 }
  test_coverage: { weight: 0.10, target: 0.60 }
  e2e_smoke:     { weight: 0.10, target: 1.00 }

forbidden:
  unwrap_in_production: true
  todo_macros_left: 0
  hallucination_score_max: 0.10
  ai_derived_oracles_max: 0

e2e_command: "cargo test --test e2e --release"

cases:
  - id: AC-001
    type: smoke
    must_pass: true
    desc: "minimum runnable translated behavior"
    adapter: cli-tool
    setup: { }
    actions: [ ]
    assert: [ ]

escalate_to_human:
  - any_must_pass_failed
  - overall_score_below: 0.85
  - hallucination_score_above: 0.20
  - ai_derived_oracles_above: 0
  - consecutive_waves_regress: 2
EOF

echo ""
echo "⚠️  请编辑 acceptance-plan.yaml 确认验收策略后再启动翻译"
echo "    特别关注: oracle_primary / dimensions / cases"

# === 链接脚本 ===
mkdir -p scripts
for SCRIPT in "$TRANSPILOT_ROOT/scripts/"*; do
    [ -f "$SCRIPT" ] || continue
    BASENAME="$(basename "$SCRIPT")"
    if [ "$BASENAME" != "init-project.sh" ] && [[ "$BASENAME" == *.sh || "$BASENAME" == "transpilot" ]]; then
        ln -sfn "$SCRIPT" "scripts/$BASENAME"
    fi
done

# === 链接 harness ===
mkdir -p harness
if [ -f "$TRANSPILOT_ROOT/harness/run-autonomous.sh" ]; then
    ln -sfn "$TRANSPILOT_ROOT/harness/run-autonomous.sh" "harness/run-autonomous.sh"
fi

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
15. Analyze sync before Wave 1 — after project analysis, summarize findings to the user and ask scope/Oracle/E2E questions before planning the first Wave
16. Wave writing plan first — every Wave needs .opencode/plans/wave-NNN.md with goal, requirements, atomic tasks, full test matrix, acceptance criteria, and review-agent feedback loop before implementation

## Local Commands
| I want to... | Run |
|---|---|
| Review acceptance gate | \`./scripts/transpilot acceptance review\` |
| Confirm acceptance gate | \`./scripts/transpilot acceptance confirm\` |
| Create Wave plan | \`./scripts/transpilot plan new wave-1 --goal "..." --scope "..."\` |
| Review Wave plan | \`./scripts/transpilot plan review wave-1\` |
| Start/continue translating | \`./scripts/transpilot run --dry-run\` then follow the OpenCode handoff |
| Check progress | \`./scripts/transpilot status\` |
| Expert progress | \`./scripts/transpilot status --expert\` |
| Diagnose setup | \`./scripts/transpilot doctor\` |
| Check index freshness | \`./scripts/check-codegraph-freshness.sh\` |
| Check placeholders | \`./scripts/forbid-placeholders.sh src\` |
| Check Oracle independence | \`./scripts/check-oracle-independence.sh tests\` |

## State Contract
Progress and decisions are stored under \`.opencode/\`.
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
