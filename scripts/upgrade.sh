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
TMP_DIR="${UPGRADE_TMP_DIR:-.claude-upgrade-tmp}"

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
if [ -n "${UPGRADE_TMP_DIR:-}" ] && [ -d "$TMP_DIR/.claude" ]; then
    info "引き継いだテンプレートを再利用します (${URL} @ ${BRANCH})"
else
    rm -rf "$TMP_DIR"  # 前回の中断で残留していた場合に備えてクリア
    info "テンプレートを取得中... (${URL} @ ${BRANCH})"
    if ! git clone --depth 1 --branch "$BRANCH" "$URL" "$TMP_DIR"; then
        error "テンプレートの取得に失敗しました。URL とブランチ/タグを確認してください"
    fi
fi

# テンプレートのコミットハッシュ（表示用）
TEMPLATE_COMMIT=$(cd "$TMP_DIR" && git rev-parse --short HEAD 2>/dev/null || echo "不明")

# --- upgrade.sh 自己更新チェック（新バージョン検出時は更新して exec 再実行） ---
_SELF="${BASH_SOURCE[0]:-$0}"
if [ -f "$TMP_DIR/scripts/upgrade.sh" ] && ! diff -q "$_SELF" "$TMP_DIR/scripts/upgrade.sh" >/dev/null 2>&1; then
    if [ "${UPGRADE_SELF_UPDATED:-}" = "1" ]; then
        warn "自己更新後も差分が残存。現行スクリプトで続行します（再実行は1回まで）"
    else
        cp "$TMP_DIR/scripts/upgrade.sh" "$_SELF"
        ok "upgrade.sh を更新。新バージョンで続行します..."
        trap - EXIT                          # exec 失敗時の保険。成功時は子が掃除を再登録
        export UPGRADE_TMP_DIR="$TMP_DIR" UPGRADE_SELF_UPDATED="1"
        exec bash "$_SELF" "$@"              # -y / ブランチ / URL を継承
    fi
fi

# --- 適用失敗時の復旧案内 ---
on_err() { warn "適用中にエラー。Git 管理下なら復旧: git checkout -- .claude scripts .gitignore && git clean -fd .claude scripts"; }
trap 'on_err' ERR

# --- ヘルパ関数（差分検出・適用） ---
_is_junk() {
    case "$1" in
        */__pycache__/*|*.pyc|*.pyo|*.DS_Store) return 0 ;;
        *) return 1 ;;
    esac
}

# --- .upgrade-keep: プロジェクト固有ファイルの保護 ---
# プロジェクト直下 .upgrade-keep（1行1パターン、# コメント可）が存在する場合に読み込む。
# パターンは glob 風:
#   末尾スラッシュ付き  → ディレクトリ配下を全て保護 (例: scripts/python/planner-sync/)
#   末尾スラッシュなし  → glob マッチ (fnmatch 相当、例: .mcp.json, docs/*.md)
# .upgrade-keep 自体はプロジェクト直下に置くため upgrade による削除・上書きの対象外。
KEEP_PATTERNS=()
_load_keep_patterns() {
    local file=".upgrade-keep"
    [ -f "$file" ] || return 0
    while IFS= read -r line; do
        # コメント行・空行をスキップ
        [[ "$line" =~ ^[[:space:]]*# ]] && continue
        [[ -z "${line// }" ]] && continue
        KEEP_PATTERNS+=("$line")
    done < "$file"
    if [ ${#KEEP_PATTERNS[@]} -gt 0 ]; then
        info ".upgrade-keep: ${#KEEP_PATTERNS[@]} パターンを保護対象に設定"
        for _p in "${KEEP_PATTERNS[@]}"; do
            info "  保護: $_p"
        done
    fi
}
_is_kept() {
    local path="$1" pattern
    for pattern in "${KEEP_PATTERNS[@]+"${KEEP_PATTERNS[@]}"}"; do
        if [[ "$pattern" == */ ]]; then
            # 末尾スラッシュ付き → ディレクトリプレフィックスとして前方一致
            [[ "$path" == "$pattern"* ]] && return 0
        else
            # 末尾スラッシュなし → glob マッチ（fnmatch 相当）
            # shellcheck disable=SC2254
            [[ "$path" == $pattern ]] && return 0
        fi
    done
    return 1
}

detect_dir() {
    local dir="$1" label="$2" f rel
    [ -d "$TMP_DIR/$dir" ] || return 0
    while IFS= read -r f; do
        [ -z "$f" ] && continue
        if _is_junk "$f"; then continue; fi
        rel="${f#$TMP_DIR/}"
        if _is_kept "$rel"; then continue; fi
        if [ ! -f "$rel" ]; then
            ADDITIONS+=("$rel（新規$label）")
        elif ! diff -q "$rel" "$f" >/dev/null 2>&1; then
            CHANGES+=("$rel")
        fi
    done < <(find "$TMP_DIR/$dir" -type f)
}
detect_deletions() {
    local dir="$1" f
    [ -d "$dir" ] && [ -d "$TMP_DIR/$dir" ] || return 0
    while IFS= read -r f; do
        [ -z "$f" ] && continue
        if _is_junk "$f"; then continue; fi
        if _is_kept "$f"; then continue; fi
        if [ ! -f "$TMP_DIR/$f" ]; then
            DELETIONS+=("$f（テンプレートから削除済み）")
        fi
    done < <(find "$dir" -type f)
}
apply_dir() {
    local dir="$1" skip="${2:-}" f rel
    [ -d "$TMP_DIR/$dir" ] || return 0
    while IFS= read -r f; do
        [ -z "$f" ] && continue
        if _is_junk "$f"; then continue; fi
        if [ -n "$skip" ] && [ "$(basename "$f")" = "$skip" ]; then continue; fi
        rel="${f#$TMP_DIR/}"
        if _is_kept "$rel"; then continue; fi
        mkdir -p "$(dirname "$rel")"
        cp "$f" "$rel"
    done < <(find "$TMP_DIR/$dir" -type f)
}

# --- .upgrade-keep 読み込み（保護パターンの初期化） ---
_load_keep_patterns

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

# hooks・エージェント・コマンド・テンプレート・spec・スクリプトの差分検出
detect_dir ".claude/hooks" "hook"
detect_dir ".claude/agents" "エージェント"
detect_dir ".claude/commands" "コマンド"
detect_dir ".claude/templates" "テンプレート"
detect_dir ".claude/spec" "spec"
detect_dir "scripts" ""
detect_deletions ".claude/hooks"
detect_deletions ".claude/agents"
detect_deletions ".claude/commands"
detect_deletions ".claude/templates"
detect_deletions ".claude/spec"
detect_deletions "scripts"

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

# exec 再実行後: upgrade.sh 自体の変更を CHANGES に追加（コミット対象にするため）
if [ "${UPGRADE_SELF_UPDATED:-}" = "1" ]; then
    if git rev-parse --is-inside-work-tree >/dev/null 2>&1 && \
       ! git diff --quiet HEAD -- scripts/upgrade.sh 2>/dev/null; then
        CHANGES+=("scripts/upgrade.sh（upgrade.sh 自体の更新）")
    fi
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
if [ ${#KEEP_PATTERNS[@]} -gt 0 ]; then
    echo "    - .upgrade-keep に列挙されたパス（プロジェクト固有保護）:"
    for _kp in "${KEEP_PATTERNS[@]}"; do
        echo "        * $_kp"
    done
fi
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

# hooks・エージェント・コマンド・テンプレート・spec・スクリプトの適用
mkdir -p .claude/hooks .claude/agents .claude/commands .claude/templates .claude/spec scripts
apply_dir ".claude/hooks"
apply_dir ".claude/agents"
apply_dir ".claude/commands"
apply_dir ".claude/templates"
apply_dir ".claude/spec"
apply_dir "scripts" "upgrade.sh"

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
