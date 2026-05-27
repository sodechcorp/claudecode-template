#!/bin/bash
# =============================================================================
# upgrade.sh — テンプレートリポジトリから .claude/ 配下を更新する
#
# 使い方:
#   bash scripts/upgrade.sh            # main ブランチの最新版
#   bash scripts/upgrade.sh develop    # ブランチ指定
#   bash scripts/upgrade.sh main <URL> # 別リポジトリ
# =============================================================================
set -euo pipefail

# --- 設定 ---
DEFAULT_URL="https://github.com/sodechcorp/claudecode-template.git"
DEFAULT_BRANCH="main"
TMP_DIR=".claude-upgrade-tmp"

# エラー・中断時も必ず一時フォルダを削除する
trap 'rm -rf "$TMP_DIR"' EXIT

AUTO_YES=false
BRANCH=""
URL=""
for arg in "$@"; do
    case "$arg" in
        -y|--yes) AUTO_YES=true ;;
        http*) URL="$arg" ;;
        *) BRANCH="$arg" ;;
    esac
done
BRANCH="${BRANCH:-$DEFAULT_BRANCH}"
URL="${URL:-$DEFAULT_URL}"

# --- 色付き出力 ---
info()  { echo -e "\033[1;34m[INFO]\033[0m  $*"; }
ok()    { echo -e "\033[1;32m[OK]\033[0m    $*"; }
warn()  { echo -e "\033[1;33m[WARN]\033[0m  $*"; }
error() { echo -e "\033[1;31m[ERROR]\033[0m $*"; exit 1; }

# --- 前提チェック ---
command -v git >/dev/null 2>&1 || error "Git がインストールされていません"
[ -d ".claude" ] || error ".claude/ が見つかりません。プロジェクトのルートで実行してください"

# --- テンプレート取得 ---
rm -rf "$TMP_DIR"  # 前回の中断で残留していた場合に備えてクリア
info "テンプレートを取得中... (${URL} @ ${BRANCH})"
if ! git clone --depth 1 --branch "$BRANCH" "$URL" "$TMP_DIR" 2>/dev/null; then
    error "テンプレートの取得に失敗しました。URL とブランチ/タグを確認してください"
fi

# テンプレートのコミットハッシュ（表示用）
TEMPLATE_COMMIT=$(cd "$TMP_DIR" && git rev-parse --short HEAD 2>/dev/null || echo "不明")

# --- upgrade.sh 自己更新チェック（旧バージョン検出時は更新して終了 → 再実行を促す） ---
_SELF="${BASH_SOURCE[0]:-$0}"
if [ -f "$TMP_DIR/scripts/upgrade.sh" ] && ! diff -q "$_SELF" "$TMP_DIR/scripts/upgrade.sh" >/dev/null 2>&1; then
    cp "$TMP_DIR/scripts/upgrade.sh" "$_SELF"
    echo ""
    ok "upgrade.sh を新バージョンに更新しました。もう一度実行してください: bash ${_SELF}${AUTO_YES:+ -y}"
    exit 0
fi

# --- 差分チェック ---
CHANGES=()
ADDITIONS=()
DELETIONS=()

# .gitignore
if [ -f "$TMP_DIR/.gitignore" ]; then
    if ! diff -q ".gitignore" "$TMP_DIR/.gitignore" >/dev/null 2>&1; then
        CHANGES+=(".gitignore（除外設定）")
    fi
fi

# .claude/CLAUDE.md
if [ -f "$TMP_DIR/.claude/CLAUDE.md" ]; then
    if ! diff -q ".claude/CLAUDE.md" "$TMP_DIR/.claude/CLAUDE.md" >/dev/null 2>&1; then
        CHANGES+=(".claude/CLAUDE.md（共通ルール）")
    fi
fi

# .claude/settings.json
if [ -f "$TMP_DIR/.claude/settings.json" ]; then
    if ! diff -q ".claude/settings.json" "$TMP_DIR/.claude/settings.json" >/dev/null 2>&1; then
        CHANGES+=(".claude/settings.json（権限設定）")
    fi
fi

# hooks（.claude/hooks/*.js）
if [ -d "$TMP_DIR/.claude/hooks" ]; then
    while IFS= read -r f; do
        [ -z "$f" ] && continue
        rel="${f#$TMP_DIR/}"
        if [ ! -f "$rel" ]; then
            ADDITIONS+=("$rel（新規 hook）")
        elif ! diff -q "$rel" "$f" >/dev/null 2>&1; then
            CHANGES+=("$rel")
        fi
    done < <(find "$TMP_DIR/.claude/hooks" -type f -name "*.js")
fi

# エージェント
for f in "$TMP_DIR"/.claude/agents/*.md; do
    [ -f "$f" ] || continue
    name=$(basename "$f")
    if [ ! -f ".claude/agents/$name" ]; then
        ADDITIONS+=(".claude/agents/$name（新規エージェント）")
    elif ! diff -q ".claude/agents/$name" "$f" >/dev/null 2>&1; then
        CHANGES+=(".claude/agents/$name")
    fi
done
for f in .claude/agents/*.md; do
    [ -f "$f" ] || continue
    name=$(basename "$f")
    if [ ! -f "$TMP_DIR/.claude/agents/$name" ]; then
        DELETIONS+=(".claude/agents/$name（テンプレートから削除済み）")
    fi
done

# コマンド
for f in "$TMP_DIR"/.claude/commands/*.md; do
    [ -f "$f" ] || continue
    name=$(basename "$f")
    if [ ! -f ".claude/commands/$name" ]; then
        ADDITIONS+=(".claude/commands/$name（新規コマンド）")
    elif ! diff -q ".claude/commands/$name" "$f" >/dev/null 2>&1; then
        CHANGES+=(".claude/commands/$name")
    fi
done
for f in .claude/commands/*.md; do
    [ -f "$f" ] || continue
    name=$(basename "$f")
    if [ ! -f "$TMP_DIR/.claude/commands/$name" ]; then
        DELETIONS+=(".claude/commands/$name（テンプレートから削除済み）")
    fi
done

# テンプレート（エージェント参照用の独立 MD ファイル群、サブディレクトリ含む再帰チェック）
if [ -d "$TMP_DIR/.claude/templates" ]; then
    while IFS= read -r f; do
        [ -z "$f" ] && continue
        rel="${f#$TMP_DIR/}"
        if [ ! -f "$rel" ]; then
            ADDITIONS+=("$rel（新規テンプレート）")
        elif ! diff -q "$rel" "$f" >/dev/null 2>&1; then
            CHANGES+=("$rel")
        fi
    done < <(find "$TMP_DIR/.claude/templates" -type f -name "*.md")
fi
if [ -d ".claude/templates" ] && [ -d "$TMP_DIR/.claude/templates" ]; then
    while IFS= read -r f; do
        [ -z "$f" ] && continue
        if [ ! -f "$TMP_DIR/$f" ]; then
            DELETIONS+=("$f（テンプレートから削除済み）")
        fi
    done < <(find ".claude/templates" -type f -name "*.md")
fi

# スクリプト（サブディレクトリ含む再帰チェック）
if [ -d "$TMP_DIR/scripts" ]; then
    while IFS= read -r f; do
        [ -z "$f" ] && continue
        rel="${f#$TMP_DIR/}"
        if [ ! -f "$rel" ]; then
            ADDITIONS+=("$rel（新規）")
        elif ! diff -q "$rel" "$f" >/dev/null 2>&1; then
            CHANGES+=("$rel")
        fi
    done < <(find "$TMP_DIR/scripts" -type f -not -path "*/__pycache__/*" -not -name "*.py[co]")
fi

# scripts/ の削除検出（プロジェクト側にあってテンプレートに無いファイル）
if [ -d "scripts" ] && [ -d "$TMP_DIR/scripts" ]; then
    while IFS= read -r f; do
        [ -z "$f" ] && continue
        if [ ! -f "$TMP_DIR/$f" ]; then
            DELETIONS+=("$f（テンプレートから削除済み）")
        fi
    done < <(find "scripts" -type f -not -path "*/__pycache__/*" -not -name "*.py[co]")
fi

# docs scaffold（.claude/templates/docs-scaffold/）→ docs/ への新規ファイル検出（既存ファイルは対象外）
SCAFFOLD_ADDITIONS=()
if [ -d "$TMP_DIR/.claude/templates/docs-scaffold" ]; then
    while IFS= read -r f; do
        [ -z "$f" ] && continue
        rel="${f#$TMP_DIR/.claude/templates/docs-scaffold/}"
        dst="docs/$rel"
        if [ ! -f "$dst" ]; then
            SCAFFOLD_ADDITIONS+=("$dst（テンプレ雛形・新規作成）")
        fi
    done < <(find "$TMP_DIR/.claude/templates/docs-scaffold" -type f)
fi

# --- 結果判定 ---
TOTAL=$(( ${#CHANGES[@]} + ${#ADDITIONS[@]} + ${#DELETIONS[@]} + ${#SCAFFOLD_ADDITIONS[@]} ))

if [ "$TOTAL" -eq 0 ]; then
    ok "テンプレートは最新です。変更はありません。"
    exit 0
fi

# --- 変更内容の表示 ---
echo ""
echo "=========================================="
echo "  テンプレートに以下の変更があります"
echo "=========================================="
echo ""

for item in "${ADDITIONS[@]+"${ADDITIONS[@]}"}"; do
    echo -e "  \033[1;32m追加:\033[0m $item"
done
for item in "${CHANGES[@]+"${CHANGES[@]}"}"; do
    echo -e "  \033[1;33m更新:\033[0m $item"
done
for item in "${DELETIONS[@]+"${DELETIONS[@]}"}"; do
    echo -e "  \033[1;31m削除対象:\033[0m $item"
done
for item in "${SCAFFOLD_ADDITIONS[@]+"${SCAFFOLD_ADDITIONS[@]}"}"; do
    echo -e "  \033[1;32m追加:\033[0m $item"
done

echo ""
echo "  合計: ${TOTAL}件の変更"
echo ""
echo "  ※ 以下は変更されません:"
echo "    - CLAUDE.md（プロジェクト固有ルール）"
echo "    - docs/（プロジェクト資材・既存ファイルは上書きしない）"
echo "    - .mcp.json（個人設定）"
echo "    - force-app/（Salesforceメタデータ）"
echo ""

# --- 確認 ---
if [ "$AUTO_YES" = true ]; then
    info "自動適用モード (-y) で続行します"
else
    read -p "適用しますか？ (y/N): " confirm
    if [[ ! "$confirm" =~ ^[yY] ]]; then
        info "キャンセルしました"
        exit 0
    fi
fi

# --- 適用 ---
info "適用中..."

# .gitignore
[ -f "$TMP_DIR/.gitignore" ] && cp "$TMP_DIR/.gitignore" .gitignore

# 共通ルール
[ -f "$TMP_DIR/.claude/CLAUDE.md" ] && cp "$TMP_DIR/.claude/CLAUDE.md" .claude/CLAUDE.md

# settings.json
[ -f "$TMP_DIR/.claude/settings.json" ] && cp "$TMP_DIR/.claude/settings.json" .claude/settings.json

# hooks（.claude/hooks/*.js）
if [ -d "$TMP_DIR/.claude/hooks" ]; then
    mkdir -p .claude/hooks
    while IFS= read -r f; do
        [ -z "$f" ] && continue
        rel="${f#$TMP_DIR/}"
        cp "$f" "$rel"
    done < <(find "$TMP_DIR/.claude/hooks" -type f -name "*.js")
fi

# エージェント
for f in "$TMP_DIR"/.claude/agents/*.md; do
    [ -f "$f" ] || continue
    cp "$f" .claude/agents/
done

# コマンド
for f in "$TMP_DIR"/.claude/commands/*.md; do
    [ -f "$f" ] || continue
    cp "$f" .claude/commands/
done

# テンプレート（サブディレクトリ含む再帰コピー）
if [ -d "$TMP_DIR/.claude/templates" ]; then
    while IFS= read -r f; do
        [ -z "$f" ] && continue
        rel="${f#$TMP_DIR/}"
        mkdir -p "$(dirname "$rel")"
        cp "$f" "$rel"
    done < <(find "$TMP_DIR/.claude/templates" -type f -name "*.md")
fi

# スクリプト（サブディレクトリ含む再帰コピー、upgrade.sh 自身は最後に上書き）
if [ -d "$TMP_DIR/scripts" ]; then
    while IFS= read -r f; do
        [ -z "$f" ] && continue
        rel="${f#$TMP_DIR/}"
        name=$(basename "$f")
        [ "$name" = "upgrade.sh" ] && continue  # 自身はスキップ
        mkdir -p "$(dirname "$rel")"
        cp "$f" "$rel"
    done < <(find "$TMP_DIR/scripts" -type f -not -path "*/__pycache__/*" -not -name "*.py[co]")
fi

# docs scaffold の配布（既存ファイル上書き禁止・新規作成のみ）
if [ ${#SCAFFOLD_ADDITIONS[@]} -gt 0 ]; then
    info "docs/ 雛形ファイルを配布中..."
    while IFS= read -r f; do
        [ -z "$f" ] && continue
        rel="${f#$TMP_DIR/.claude/templates/docs-scaffold/}"
        dst="docs/$rel"
        if [ ! -f "$dst" ]; then
            mkdir -p "$(dirname "$dst")"
            cp "$f" "$dst"
            ok "新規作成: $dst"
        fi
    done < <(find "$TMP_DIR/.claude/templates/docs-scaffold" -type f)
fi

# --- 削除対象の処理（テンプレートから削除されたファイルを自動削除） ---
if [ ${#DELETIONS[@]} -gt 0 ]; then
    echo ""
    info "テンプレートから削除されたファイルをプロジェクトからも削除します:"
    INSIDE_GIT=false
    if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        INSIDE_GIT=true
    fi
    for item in "${DELETIONS[@]}"; do
        path="${item%（テンプレートから削除済み）}"
        if [ -f "$path" ]; then
            if [ "$INSIDE_GIT" = true ]; then
                git rm -f "$path" >/dev/null 2>&1 || rm -f "$path"
            else
                rm -f "$path"
            fi
            ok "削除: $path"
        fi
    done
fi

# --- Git コミット（リポジトリがある場合のみ・pushは手動） ---
if git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
    git add .claude/ scripts/ .gitignore 2>/dev/null || true
    for item in "${SCAFFOLD_ADDITIONS[@]+"${SCAFFOLD_ADDITIONS[@]}"}"; do
        rel="${item%（テンプレ雛形・新規作成）}"
        [ -n "$rel" ] && git add "$rel" 2>/dev/null || true
    done
    if ! git diff --cached --quiet; then
        git commit -m "chore: upgrade template (${TEMPLATE_COMMIT})"
        ok "コミット完了。push は手動で実行してください: git push origin HEAD"
    else
        info "Git: コミット対象の変更なし（スキップ）"
    fi
else
    info "Git リポジトリ未設定。Git 操作はスキップしました"
fi

# --- 完了報告 ---
echo ""
echo "=========================================="
echo "  アップグレード完了"
echo "=========================================="
echo ""
echo "  ソース: $URL @ $BRANCH ($TEMPLATE_COMMIT)"
echo "  変更件数: ${TOTAL}件"
echo ""
