#!/bin/bash
# =============================================================================
# setup-sf-project.sh — Salesforce組織の認証とメタデータ取得
#
# setup.sh でプロジェクト作成後、このスクリプトで組織接続を行う。
# /sf-setup コマンドから呼ばれる。
#
# 使い方:
#   bash scripts/setup-sf-project.sh                    # 対話モード
#   bash scripts/setup-sf-project.sh prod               # 本番認証（alias: prod）
#   bash scripts/setup-sf-project.sh dev                # Sandbox認証（alias: dev）
#   bash scripts/setup-sf-project.sh my-alias sandbox   # カスタムalias + Sandbox
# =============================================================================
set -euo pipefail

# --- 色付き出力 ---
info()  { echo -e "\033[1;34m[INFO]\033[0m  $*"; }
ok()    { echo -e "\033[1;32m[OK]\033[0m    $*"; }
warn()  { echo -e "\033[1;33m[WARN]\033[0m  $*"; }
error() { echo -e "\033[1;31m[ERROR]\033[0m $*"; exit 1; }

# --- 前提チェック ---
command -v sf >/dev/null 2>&1 || error "Salesforce CLI がインストールされていません"

if [ ! -f "sfdx-project.json" ]; then
    error "sfdx-project.json が見つかりません。SFDXプロジェクトのルートで実行してください"
fi

# --- 引数解析 ---
ALIAS="${1:-}"
ORG_TYPE="${2:-}"

# 対話モード
if [ -z "$ALIAS" ]; then
    echo ""
    echo "接続するSalesforce組織の種別を入力してください:"
    echo "  prod     — 本番/Developer Edition（login.salesforce.com）"
    echo "  dev      — Sandbox（test.salesforce.com）"
    echo "  skip     — 後で設定する"
    echo "  その他   — カスタムエイリアス（本番として認証）"
    echo ""
    read -p "種別: " ALIAS
fi

[ -z "$ALIAS" ] && error "組織種別が指定されていません"

# skip の場合
if [ "$ALIAS" = "skip" ]; then
    info "組織認証をスキップしました。後で再実行してください"
    exit 0
fi

# 種別に応じた設定
LOGIN_URL=""
case "$ALIAS" in
    prod)
        LOGIN_URL="https://login.salesforce.com"
        ;;
    dev)
        LOGIN_URL="https://test.salesforce.com"
        ;;
    *)
        # カスタムエイリアス
        if [ "$ORG_TYPE" = "sandbox" ]; then
            LOGIN_URL="https://test.salesforce.com"
        else
            LOGIN_URL="https://login.salesforce.com"
        fi
        ;;
esac

# --- 認証 ---
info "Salesforce組織に接続中... (alias: $ALIAS)"
echo "ブラウザが開きます。Salesforceにログインしてください。"
echo ""

if [ "$LOGIN_URL" = "https://test.salesforce.com" ]; then
    sf org login web -a "$ALIAS" -r "$LOGIN_URL"
else
    sf org login web -a "$ALIAS"
fi

# --- 認証確認 ---
if sf org display -o "$ALIAS" >/dev/null 2>&1; then
    ok "認証成功"
    sf config set target-org "$ALIAS" 2>/dev/null
    ok "デフォルト組織に設定: $ALIAS"
else
    error "認証に失敗しました。もう一度実行してください"
fi

# --- メタデータ取得の確認 ---
echo ""
read -p "組織のメタデータを取得しますか？ (y/N): " retrieve || true
if [[ ! "$retrieve" =~ ^[yY] ]]; then
    echo ""
    echo "セットアップ完了。メタデータ取得は後で /sf-retrieve で実行できます。"
    exit 0
fi

# --- docs/logs フォルダの作成 ---
mkdir -p docs/logs
info "docs/logs/ フォルダを作成しました"

# --- sf CLI バージョン確認（Entity expansion バグを事前警告）---
bash scripts/sf-retrieve.sh check-version

# --- 標準セットの package.xml を生成（sf-retrieve.sh に委譲してリスト一元管理） ---
bash scripts/sf-retrieve.sh generate-only standard

# --- メタデータ取得（Dashboard/Report 等のフォルダ型バッチを含む全 manifest）---
info "メタデータを取得中..."
bash scripts/sf-retrieve.sh retrieve-standard
ok "メタデータ取得完了"

echo ""
echo "=========================================="
echo "  組織セットアップ完了"
echo "=========================================="
echo ""
echo "  組織: $ALIAS"
echo "  メタデータ: force-app/ に保存済み"
echo ""
echo "  次のステップ:"
echo "    1. CLAUDE.md を編集してプロジェクト固有情報を記入"
echo "    2. /setup-mcp で Backlog・Notion・GitHub 等の外部連携を設定する（連携を使う場合は必須）"
echo "    3. /sf-memory で組織情報を docs/ に記録する（カテゴリを対話的に選択）"
echo ""
