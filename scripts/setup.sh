#!/bin/bash
# =============================================================================
# setup.sh — Salesforceプロジェクトのセットアップ（新規作成 or 参加）
#
# 2モード:
#   - 新規作成モード（$3なし）: sf-claude-template から SFDX プロジェクトを生成。
#                              Git連携は手動（完了メッセージに案内あり）。
#   - 参加モード（$3あり）   : プロジェクトリポジトリからテンプレートを取得し SFDX プロジェクトを生成。
#                              テンプレート取得先以外は新規作成モードと同じ手順。
#
# 使い方:
#
#   # 新規プロジェクト（テンプレートから作成）
#   curl -sSL https://raw.githubusercontent.com/sodechcorp/claudecode-template/main/scripts/setup.sh | bash -s my-project
#   curl -sSL https://raw.githubusercontent.com/sodechcorp/claudecode-template/main/scripts/setup.sh | bash -s my-project /c/workspace
#
#   # 既存プロジェクトに参加（プロジェクトリポジトリからテンプレートを取得）
#   curl -sSL https://raw.githubusercontent.com/sodechcorp/claudecode-template/main/scripts/setup.sh | bash -s my-project /c/workspace https://github.com/your-org/project-a.git
#
# または clone 後:
#   bash scripts/setup.sh my-project /c/workspace
#   bash scripts/setup.sh my-project /c/workspace https://github.com/your-org/project-a.git
#
# 引数:
#   $1  プロジェクト名（必須・作成先のフォルダ名になる）
#   $2  作成先パス（省略時: カレントディレクトリ）
#   $3  プロジェクトリポジトリURL（省略時: 新規作成モード）
# =============================================================================
set -euo pipefail

# --- 設定 ---
DEFAULT_TEMPLATE_URL="https://github.com/sodechcorp/claudecode-template.git"
TEMPLATE_BRANCH="main"

# --- 色付き出力 ---
info()  { echo -e "\033[1;34m[INFO]\033[0m  $*"; }
ok()    { echo -e "\033[1;32m[OK]\033[0m    $*"; }
warn()  { echo -e "\033[1;33m[WARN]\033[0m  $*"; }
error() { echo -e "\033[1;31m[ERROR]\033[0m $*"; exit 1; }

# --- 引数 ---
PROJECT_NAME="${1:-}"
TARGET_DIR="${2:-.}"
PROJECT_REPO_URL="${3:-}"  # 指定時: 参加モード（プロジェクトリポジトリからテンプレート取得）。省略時: 新規作成モード（大本テンプレートから生成）

if [ -z "$PROJECT_NAME" ]; then
    read -p "プロジェクト名を入力してください（英語）: " PROJECT_NAME
fi
[ -z "$PROJECT_NAME" ] && error "プロジェクト名が指定されていません"

PROJECT_PATH="$TARGET_DIR/$PROJECT_NAME"

# --- 前提チェック ---
command -v git >/dev/null 2>&1 || error "Git がインストールされていません"
command -v sf >/dev/null 2>&1 || error "Salesforce CLI がインストールされていません。https://developer.salesforce.com/tools/salesforcecli からインストールしてください"

if [ -d "$PROJECT_PATH" ]; then
    error "$PROJECT_PATH は既に存在します"
fi

# =============================================================================
# SFDXプロジェクトを生成（新規作成・参加モード共通）
# =============================================================================
info "SFDXプロジェクトを作成中..."
sf project generate -n "$PROJECT_NAME" -d "$TARGET_DIR" --manifest
ok "SFDXプロジェクト作成完了: $PROJECT_PATH"

# =============================================================================
# テンプレートを取得（取得先のみモードで分岐）
# =============================================================================
TMP_DIR="$PROJECT_PATH/.claude-template-tmp"

if [ -n "$PROJECT_REPO_URL" ]; then
    # 参加モード: プロジェクトリポジトリからテンプレートを取得
    info "プロジェクトリポジトリを取得中... ($PROJECT_REPO_URL)"
    if ! git clone "$PROJECT_REPO_URL" "$TMP_DIR" 2>/dev/null; then
        error "プロジェクトリポジトリの取得に失敗しました。URL とアクセス権を確認してください"
    fi
else
    # 新規作成モード: 大本テンプレートからテンプレートを取得
    info "テンプレートを取得中..."
    if ! git clone --depth 1 --branch "$TEMPLATE_BRANCH" "$DEFAULT_TEMPLATE_URL" "$TMP_DIR" 2>/dev/null; then
        error "テンプレートの取得に失敗しました。ネットワーク接続を確認してください"
    fi
fi

# =============================================================================
# テンプレートを配置（新規作成・参加モード共通）
# =============================================================================
info "テンプレートを配置中..."
[ -d "$TMP_DIR/.claude" ] && cp -r "$TMP_DIR/.claude" "$PROJECT_PATH/.claude"
[ -f "$TMP_DIR/CLAUDE.md" ] && cp "$TMP_DIR/CLAUDE.md" "$PROJECT_PATH/CLAUDE.md"
# .gitignore: 新規モードのみ大本テンプレートで上書き
# （参加モードは下方の git checkout -- .gitignore でプロジェクトリポジトリの版に戻すので不要）
if [ -z "$PROJECT_REPO_URL" ]; then
    [ -f "$TMP_DIR/.gitignore" ] && cp "$TMP_DIR/.gitignore" "$PROJECT_PATH/.gitignore"
fi
# README: 参加モードではプロジェクトリポジトリを介さず大本テンプレートから直接取得
# （project repo に古い SFDX デフォルト README が入っていても正しいテンプレート内容が適用される）
if [ -n "$PROJECT_REPO_URL" ]; then
    TEMPLATE_README_URL="https://raw.githubusercontent.com/sodechcorp/claudecode-template/${TEMPLATE_BRANCH}/README.md"
    curl -sSfL "$TEMPLATE_README_URL" -o "$PROJECT_PATH/README.md" 2>/dev/null || \
        { [ -f "$TMP_DIR/README.md" ] && cp "$TMP_DIR/README.md" "$PROJECT_PATH/README.md"; }
else
    [ -f "$TMP_DIR/README.md" ] && cp "$TMP_DIR/README.md" "$PROJECT_PATH/README.md"
fi
[ -d "$TMP_DIR/docs" ] && cp -r "$TMP_DIR/docs" "$PROJECT_PATH/docs"
if [ -d "$TMP_DIR/scripts" ]; then
    mkdir -p "$PROJECT_PATH/scripts"
    cp -r "$TMP_DIR/scripts/." "$PROJECT_PATH/scripts/"
fi

# 参加モードのみ: プロジェクトリポジトリの git 履歴を保持し、.gitignore を復元
if [ -n "$PROJECT_REPO_URL" ]; then
    rm -rf "$PROJECT_PATH/.git" 2>/dev/null || true
    mv "$TMP_DIR/.git" "$PROJECT_PATH/.git"
    # SFDXが生成した.gitignoreをプロジェクトリポジトリのものに戻す
    git -C "$PROJECT_PATH" checkout -- .gitignore 2>/dev/null || true
fi

# .mcp.json が未登録なら追記
if ! grep -qF ".mcp.json" "$PROJECT_PATH/.gitignore" 2>/dev/null; then
    {
        echo ""
        echo "# Claude Code（トークン入り個人設定）"
        echo ".mcp.json"
    } >> "$PROJECT_PATH/.gitignore"
fi

rm -rf "$TMP_DIR"
ok "テンプレート配置完了"

# --- 完了 ---
echo ""
echo "=========================================="
echo "  セットアップ完了"
echo "=========================================="
echo ""
echo "  プロジェクト: $PROJECT_PATH"
if [ -n "$PROJECT_REPO_URL" ]; then
    echo "  Git: $PROJECT_REPO_URL"
fi
echo ""
echo "  次のステップ:"

if [ -n "$PROJECT_REPO_URL" ]; then
    # --- 参加モード ---
    echo ""
    echo "    1. /sf-setup    — Sandbox組織を認証する"
    echo "    2. /sf-retrieve — メタデータを取得する（force-app/ に展開）"
    echo "    3. CLAUDE.md    — 担当者名・Sandbox alias 等を記入する"
    echo "    4. /setup-mcp   — 外部ツール連携を設定する（Backlog・Notion・GitHub 連携を使う場合は必須）"
    echo "    5. /sf-memory   — 組織情報を収集・記録する（docs/ を生成）"
else
    # --- 新規作成モード ---
    echo "    0. GitHubでリポジトリを作成して連携する:"
    echo "         cd $PROJECT_PATH"
    echo "         git init && git remote add origin <URL>"
    echo "         git add . && git commit -m 'chore: initial setup'"
    echo "         git push -u origin main"
    echo ""
    echo "    1. /sf-setup    — 本番組織を認証する ★記憶形成は本番接続を推奨"
    echo "    2. /sf-retrieve — メタデータを取得する（force-app/ に展開）"
    echo "    3. CLAUDE.md    — プロジェクト固有情報を記入する"
    echo "    4. /setup-mcp   — 外部ツール連携を設定する（Backlog・Notion・GitHub 連携を使う場合は必須）"
    echo "    5. /sf-memory   — 組織情報を収集しドキュメントを生成する（docs/ に出力）"
    echo "    6. /sf-doc      — 設計書・定義書を生成する"
    echo ""
    echo "    ※ 初期セットアップ完了後、プロジェクトリポジトリをチームメンバーに配布してください"
fi
echo ""

# --- VSCode で開く ---
if command -v code >/dev/null 2>&1; then
    code "$PROJECT_PATH"
    # Windows の場合、起動直後に最大化する（画面サイズに合わせる）
    if [[ "${OSTYPE:-}" == "msys"* ]] || [[ "${OSTYPE:-}" == "cygwin"* ]] || [[ -n "${WINDIR:-}" ]]; then
        PROJECT_BASENAME=$(basename "$PROJECT_PATH")
        powershell.exe -NoProfile -Command "
            Start-Sleep -Seconds 3
            Add-Type -TypeDefinition '
                using System;
                using System.Runtime.InteropServices;
                public class WindowHelper {
                    [DllImport(\"user32.dll\")] public static extern bool ShowWindowAsync(IntPtr hWnd, int nCmdShow);
                }
            ' -ErrorAction SilentlyContinue
            \$procs = Get-Process 'Code' -ErrorAction SilentlyContinue | Where-Object { \$_.MainWindowTitle -like '*${PROJECT_BASENAME}*' } | Sort-Object StartTime -Descending
            if (\$procs) { [WindowHelper]::ShowWindowAsync(\$procs[0].MainWindowHandle, 3) | Out-Null }
        " 2>/dev/null &
    fi
else
    info "VSCode CLI が見つかりません。手動で開いてください: $PROJECT_PATH"
fi
