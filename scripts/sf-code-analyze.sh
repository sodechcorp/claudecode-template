#!/bin/bash
# =============================================================================
# sf-code-analyze.sh — sf code-analyzer（PMD/CPD/regex）実行 → reviewer.md形式に整形
#
# /sf-code-analyze コマンドの定型部分（CLI実行・出力整形）をスクリプト化。
# 解析対象ディレクトリの判断は /sf-code-analyze コマンド側（Claude）が行い、このスクリプトに渡す。
#
# 使い方:
#   bash scripts/sf-code-analyze.sh [target]     # target省略時は force-app 全体
#
# 前提:
#   - sf CLI がインストール済み（code-analyzer プラグインは初回実行時に自動インストールされる。
#     初回のみ数十秒程度かかる場合がある）
#   - sfdx-project.json のある SFDX プロジェクトルートで実行すること
#   - org 接続は不要（ローカルファイルのみを解析。デプロイ・データ操作は一切行わない）
# =============================================================================
set -euo pipefail

# --- 色付き出力 ---
info()  { echo -e "\033[1;34m[INFO]\033[0m  $*"; }
ok()    { echo -e "\033[1;32m[OK]\033[0m    $*"; }
warn()  { echo -e "\033[1;33m[WARN]\033[0m  $*"; }
error() { echo -e "\033[1;31m[ERROR]\033[0m $*"; exit 1; }

# --- 前提チェック ---
command -v sf >/dev/null 2>&1 || error "Salesforce CLI がインストールされていません"
[ -f "sfdx-project.json" ] || error "sfdx-project.json が見つかりません。SFDXプロジェクトのルートで実行してください"
command -v python >/dev/null 2>&1 || error "python がインストールされていません"

TARGET="${1:-force-app}"
[ -e "$TARGET" ] || error "解析対象が見つかりません: $TARGET"

# プロジェクトルート（カレントディレクトリ）からの相対パスで参照する
# （BASH_SOURCE から動的解決すると Git Bash の POSIX/Windows パス変換で壊れるため使わない。
#   git-sync.md 等の既存コマンドと同じ「カレント=プロジェクトルート」前提に合わせる）
FORMATTER="scripts/python/sf-code-analyzer/format_results.py"
[ -f "$FORMATTER" ] || error "整形スクリプトが見つかりません: $FORMATTER（プロジェクトルートで実行してください）"

TMPDIR="docs/.tmp/code-analyzer"
mkdir -p "$TMPDIR"
RESULTS_JSON="$TMPDIR/results.json"

info "sf code-analyzer 実行中（対象: $TARGET）"
info "初回実行時は code-analyzer プラグインの自動インストールが走るため数十秒かかる場合があります"

sf code-analyzer run --workspace . --target "$TARGET" --rule-selector Recommended -f "$RESULTS_JSON" -v table

[ -f "$RESULTS_JSON" ] || error "結果ファイルが生成されませんでした: $RESULTS_JSON"

ok "解析完了。reviewer.md 形式に整形します"
echo ""
PYTHONIOENCODING=utf-8 python "$FORMATTER" "$RESULTS_JSON"

# 一時ファイルは整形後に破棄する（docs/.tmp/ 配下に永続ゴミを残さない）
rm -f "$RESULTS_JSON"
rmdir "$TMPDIR" 2>/dev/null || true
rmdir "docs/.tmp" 2>/dev/null || true
