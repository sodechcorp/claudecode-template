#!/bin/bash
# =============================================================================
# sf-retrieve.sh — package.xml の生成とメタデータ取得
#
# /sf-retrieve コマンドの定型部分（package.xml生成・retrieve実行）をスクリプト化。
# 取得対象の判断（指定/標準セット/全て）は /sf-retrieve コマンド側（Claude）が行い、
# このスクリプトに mode を渡す。
#
# 使い方:
#   bash scripts/sf-retrieve.sh standard             # 標準セットで生成＋取得
#   bash scripts/sf-retrieve.sh all                   # 全量で生成＋取得
#   bash scripts/sf-retrieve.sh generate-only standard # 生成のみ（取得しない）
#   bash scripts/sf-retrieve.sh retrieve              # 既存 package.xml で取得のみ
#   bash scripts/sf-retrieve.sh check-version         # sf CLI バージョン確認のみ
#
# 環境変数:
#   SF_RETRIEVE_WAIT=N              CLI 待機時間（分。デフォルト 60）
#   SF_RETRIEVE_EXTRA_SKIP=A,B,C   all モードで追加スキップする型（カンマ区切り）
#
# all モードのデフォルト自動スキップ型（EXCLUDED_FROM_ALL）:
#   ExperienceContainer / ExperiencePropertyTypeBundle / ContentTypeBundle /
#   SiteDotCom / ManagedTopic / ManagedTopics / AnalyticSnapshot /
#   AiAgentScorerDefinition / ApexEmailNotifications / IframeWhiteListUrlSettings
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
command -v python3 >/dev/null 2>&1 || error "python3 がインストールされていません"

# --- sf CLI バージョン確認 ---
# Entity expansion バグ (1031 > 1000) は sf CLI 2.133.0 未満で発生
MIN_SF_VERSION_MAJOR=2
MIN_SF_VERSION_MINOR=133

check_sf_version() {
    local raw major minor rest
    raw=$(sf --version 2>/dev/null | grep -oP '@salesforce/cli/\K[0-9]+\.[0-9]+\.[0-9]+' | head -1) || true
    if [ -z "$raw" ]; then
        warn "sf CLI バージョンが判定できません。${MIN_SF_VERSION_MAJOR}.${MIN_SF_VERSION_MINOR}.0+ を推奨します"
        return 0
    fi
    major="${raw%%.*}"
    rest="${raw#*.}"; minor="${rest%%.*}"
    if [ "$major" -lt "$MIN_SF_VERSION_MAJOR" ] || \
       { [ "$major" -eq "$MIN_SF_VERSION_MAJOR" ] && [ "$minor" -lt "$MIN_SF_VERSION_MINOR" ]; }; then
        warn "sf CLI ${raw} は Entity expansion バグ (limit 1000) の影響を受ける可能性があります"
        warn "推奨: npm install --global @salesforce/cli@latest"
        warn "PATH 優先順位で旧版が呼ばれる場合の回避策:"
        warn "  Windows: C:/Users/\${USERNAME}/AppData/Roaming/npm/sf.cmd を直接実行"
        warn "  macOS/Linux: 'which -a sf' で全パス確認し PATH の順序を調整"
    fi
}

check_sf_version

# --- retrieve の待機時間（分）---
# 環境変数 SF_RETRIEVE_WAIT で上書き可（例: SF_RETRIEVE_WAIT=120 bash scripts/sf-retrieve.sh all）
SF_WAIT="${SF_RETRIEVE_WAIT:-60}"

# --- `<members>*</members>` で内部コンポを返してエラーになる型（all/standard 共通）---
EXCLUDED_FROM_WILDCARD=(
    "NetworkBranding"   # 内部 "cb" コンポを返し取得不能
)

# --- all モード専用: 保守用途でほぼ価値が無く retrieve コスト/失敗リスクのみ残る型 ---
EXCLUDED_FROM_ALL=(
    "ExperienceContainer"           # Experience Cloud 内部バイナリコンテナ（不透明・編集不能）
    "ExperiencePropertyTypeBundle"  # Experience Cloud 内部 autogen
    "ContentTypeBundle"             # Experience Cloud / CMS 内部 autogen
    "SiteDotCom"                    # レガシー Site.com（Experience Cloud に置換済み・autogen）
    "ManagedTopic"                  # Community ナビゲーション autogen
    "ManagedTopics"                 # Community ナビゲーション autogen
    "AnalyticSnapshot"              # Reporting Snapshot（保守でほぼ触らない）
    "AiAgentScorerDefinition"       # 旧 CLI で取得失敗の既知型（バッチを巻き込む）
    "ApexEmailNotifications"        # 組織 1 レコード設定（保守での取得意義薄）
    "IframeWhiteListUrlSettings"    # 設定の autogen
)

is_excluded() {
    local t="$1"
    for ex in "${EXCLUDED_FROM_WILDCARD[@]}"; do
        [ "$t" = "$ex" ] && return 0
    done
    return 1
}

# --- フォルダ型: "content_type:folder_type" の対 ---
# Dashboard/Report/Document/EmailTemplate は <members>*</members> 非対応。
# フォルダ一覧を取得して各フォルダ名を members に列挙する必要がある。
FOLDER_BASED_PAIRS=(
    "Dashboard:DashboardFolder"
    "Report:ReportFolder"
    "Document:DocumentFolder"
    "EmailTemplate:EmailFolder"
)

is_folder_based() {
    local t="$1"
    for pair in "${FOLDER_BASED_PAIRS[@]}"; do
        [ "${pair%%:*}" = "$t" ] && return 0
    done
    return 1
}

get_folder_type() {
    local t="$1"
    for pair in "${FOLDER_BASED_PAIRS[@]}"; do
        [ "${pair%%:*}" = "$t" ] && echo "${pair##*:}" && return 0
    done
}

# --- APIバージョン取得 ---
get_api_version() {
    local version
    version=$(grep -oP '"sourceApiVersion"\s*:\s*"\K[^"]+' sfdx-project.json 2>/dev/null || echo "")
    if [ -z "$version" ]; then
        version="62.0"
    fi
    echo "$version"
}

# --- 接続組織の確認 ---
get_target_org() {
    local target_org
    target_org=$(sf config get target-org --json 2>/dev/null | grep -oP '"value"\s*:\s*"\K[^"]+' | head -1 || echo "")
    if [ -z "$target_org" ]; then
        error "target-org が設定されていません。sf config set target-org <alias> で設定してください"
    fi
    echo "$target_org"
}

# --- フォルダ型 manifest 生成 ---
generate_folder_based_manifest() {
    local content_type="$1"   # Dashboard
    local folder_type="$2"    # DashboardFolder
    local api_version="$3"
    local target_org="$4"
    local output="$5"

    local folders_json
    folders_json=$(sf org list metadata --metadata-type "$folder_type" \
                   --target-org "$target_org" --json 2>/dev/null) || {
        warn "${folder_type} 一覧取得失敗。${content_type} の取得をスキップします"
        return 1
    }

    python3 - "$content_type" "$folder_type" "$api_version" "$output" "$folders_json" << 'PYEOF'
import sys, json
content_type, folder_type, api_version, output, folders_json = sys.argv[1:6]
data = json.loads(folders_json)
folders = sorted([r['fullName'] for r in data.get('result', []) if r.get('fullName')])
if not folders:
    sys.exit(2)
m = "\n".join(f"        <members>{f}</members>" for f in folders)
xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<Package xmlns="http://soap.sforce.com/2006/04/metadata">
    <types>
{m}
        <name>{folder_type}</name>
    </types>
    <types>
{m}
        <name>{content_type}</name>
    </types>
    <version>{api_version}</version>
</Package>
'''
with open(output, "w", encoding="utf-8") as f:
    f.write(xml)
PYEOF
}

# --- 標準セット package.xml 生成 ---
#
# Entity expansion limit (1000) 対策:
#   manifest/package.xml               ... 軽い type まとめ（wildcard）
#   manifest/package-{TYPE}.xml        ... 重い type 独立（ApexClass/Layout/Profile/FlexiPage）
#   manifest/package-CustomObject-N.xml ... CustomObject を 100 件ずつ分割（動的生成）
#   manifest/package-Dashboard.xml     ... フォルダ列挙（DashboardFolder 経由）
#   manifest/package-Report.xml        ... フォルダ列挙（ReportFolder 経由）
#
# 注: EmailTemplate / Document はフォルダ型のため standard から除外。
#     必要な場合は /sf-retrieve select で個別取得してください。
generate_standard() {
    local api_version="$1"
    local target_org="$2"
    mkdir -p manifest

    # 軽い type まとめ（wildcard）
    # ※ EmailTemplate はフォルダ型のため除外済み
    cat > manifest/package.xml << XMLEOF
<?xml version="1.0" encoding="UTF-8"?>
<Package xmlns="http://soap.sforce.com/2006/04/metadata">
    <types><members>*</members><name>ApexTrigger</name></types>
    <types><members>*</members><name>ApexPage</name></types>
    <types><members>*</members><name>Flow</name></types>
    <types><members>*</members><name>CustomTab</name></types>
    <types><members>*</members><name>CustomLabel</name></types>
    <types><members>*</members><name>CustomMetadata</name></types>
    <types><members>*</members><name>LightningComponentBundle</name></types>
    <types><members>*</members><name>PermissionSet</name></types>
    <types><members>*</members><name>PermissionSetGroup</name></types>
    <types><members>*</members><name>StaticResource</name></types>
    <types><members>*</members><name>ReportType</name></types>
    <types><members>*</members><name>NamedCredential</name></types>
    <types><members>*</members><name>RemoteSiteSetting</name></types>
    <types><members>*</members><name>ValidationRule</name></types>
    <version>${api_version}</version>
</Package>
XMLEOF

    # 重い type は独立バッチ（wildcard）
    for TYPE in ApexClass Layout Profile; do
        cat > "manifest/package-${TYPE}.xml" << XMLEOF
<?xml version="1.0" encoding="UTF-8"?>
<Package xmlns="http://soap.sforce.com/2006/04/metadata">
    <types><members>*</members><name>${TYPE}</name></types>
    <version>${api_version}</version>
</Package>
XMLEOF
    done

    # CustomObject は件数が多いため 100 件ずつ分割して生成
    info "CustomObject 一覧を取得中（${target_org}）..."
    local objects_json
    objects_json=$(sf org list metadata --metadata-type CustomObject --target-org "$target_org" --json 2>/dev/null) || {
        warn "CustomObject 一覧の取得に失敗しました。manifest/package-CustomObject-1.xml に wildcard を使用します"
        cat > "manifest/package-CustomObject-1.xml" << XMLEOF
<?xml version="1.0" encoding="UTF-8"?>
<Package xmlns="http://soap.sforce.com/2006/04/metadata">
    <types><members>*</members><name>CustomObject</name></types>
    <version>${api_version}</version>
</Package>
XMLEOF
        return
    }

    local n_batches
    n_batches=$(python3 - "${api_version}" << PYEOF
import json, math, sys

api_version = sys.argv[1]
data = json.loads("""${objects_json}""")
objects = sorted([r['fullName'] for r in data.get('result', [])])

BATCH_SIZE = 100
n_batches = math.ceil(len(objects) / BATCH_SIZE)

for i in range(n_batches):
    batch = objects[i*BATCH_SIZE:(i+1)*BATCH_SIZE]
    members = '\n'.join([f'        <members>{o}</members>' for o in batch])
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Package xmlns="http://soap.sforce.com/2006/04/metadata">
    <types>
{members}
        <name>CustomObject</name>
    </types>
    <version>{api_version}</version>
</Package>"""
    fname = f"manifest/package-CustomObject-{i+1}.xml"
    with open(fname, 'w', encoding='utf-8') as f:
        f.write(xml)

print(n_batches)
PYEOF
)

    # FlexiPage は件数が多い場合にタイムアウトするため 50 件ずつ分割
    info "FlexiPage 一覧を取得中（${target_org}）..."
    local flexipages_json n_flexipage_batches
    flexipages_json=$(sf org list metadata --metadata-type FlexiPage --target-org "$target_org" --json 2>/dev/null) || {
        warn "FlexiPage 一覧の取得に失敗しました。manifest/package-FlexiPage-1.xml に wildcard を使用します"
        cat > "manifest/package-FlexiPage-1.xml" << XMLEOF
<?xml version="1.0" encoding="UTF-8"?>
<Package xmlns="http://soap.sforce.com/2006/04/metadata">
    <types><members>*</members><name>FlexiPage</name></types>
    <version>${api_version}</version>
</Package>
XMLEOF
        flexipages_json=""
    }

    if [ -n "${flexipages_json:-}" ]; then
        n_flexipage_batches=$(python3 - "${api_version}" << PYEOF
import json, math, sys
api_version = sys.argv[1]
data = json.loads("""${flexipages_json}""")
pages = sorted([r['fullName'] for r in data.get('result', [])])
BATCH_SIZE = 50
n = math.ceil(len(pages) / BATCH_SIZE) if pages else 0
for i in range(n):
    batch = pages[i*BATCH_SIZE:(i+1)*BATCH_SIZE]
    members = '\n'.join(f'        <members>{p}</members>' for p in batch)
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Package xmlns="http://soap.sforce.com/2006/04/metadata">
    <types>
{members}
        <name>FlexiPage</name>
    </types>
    <version>{api_version}</version>
</Package>"""
    with open(f'manifest/package-FlexiPage-{i+1}.xml', 'w', encoding='utf-8') as f:
        f.write(xml)
print(n)
PYEOF
)
    else
        n_flexipage_batches=1
    fi

    # フォルダ型: Dashboard / Report
    local folder_manifests_ok=()
    for pair in "${FOLDER_BASED_PAIRS[@]}"; do
        local ct="${pair%%:*}"
        local ft="${pair##*:}"
        case "$ct" in
            Dashboard|Report)
                local out="manifest/package-${ct}.xml"
                if generate_folder_based_manifest "$ct" "$ft" "$api_version" "$target_org" "$out"; then
                    folder_manifests_ok+=("$out")
                fi
                ;;
        esac
    done

    ok "標準セット package.xml を生成 (API ${api_version})"
    ok "  軽い type: manifest/package.xml"
    ok "  重い type: manifest/package-{ApexClass,Layout,Profile}.xml"
    ok "  CustomObject: manifest/package-CustomObject-1.xml 〜 ${n_batches}.xml (${n_batches} バッチ)"
    ok "  FlexiPage: manifest/package-FlexiPage-1.xml 〜 ${n_flexipage_batches}.xml (${n_flexipage_batches} バッチ)"
    for m in "${folder_manifests_ok[@]}"; do
        ok "  フォルダ型: ${m}"
    done
}

# --- 全量の package.xml 生成（バッチ分割・除外型・フォルダ型対応）---
generate_all() {
    local api_version="$1"
    local target_org="$2"
    info "組織のメタデータタイプを取得中..."

    local types_json
    types_json=$(sf org list metadata-types --json 2>/dev/null) || error "メタデータタイプの取得に失敗しました。組織に接続されているか確認してください"

    mkdir -p manifest

    # EXCLUDED_FROM_WILDCARD と FOLDER_BASED_PAIRS のコンテンツ型を除外
    local excluded_list="" skipped_for_log=()
    for ex in "${EXCLUDED_FROM_WILDCARD[@]}"; do
        excluded_list="${excluded_list}${ex},"
    done
    for pair in "${FOLDER_BASED_PAIRS[@]}"; do
        excluded_list="${excluded_list}${pair%%:*},"
    done

    # all モード専用: 明らかに不要な型 + 案件別追加（SF_RETRIEVE_EXTRA_SKIP）
    for ex in "${EXCLUDED_FROM_ALL[@]}"; do
        excluded_list="${excluded_list}${ex},"
        skipped_for_log+=("${ex}")
    done
    if [ -n "${SF_RETRIEVE_EXTRA_SKIP:-}" ]; then
        IFS=',' read -r -a extra_skip <<< "$SF_RETRIEVE_EXTRA_SKIP"
        for ex in "${extra_skip[@]}"; do
            ex="${ex// /}"  # 空白除去
            [ -z "$ex" ] && continue
            excluded_list="${excluded_list}${ex},"
            skipped_for_log+=("${ex} (SF_RETRIEVE_EXTRA_SKIP)")
        done
    fi

    mkdir -p manifest
    printf '%s\n' "${skipped_for_log[@]}" > manifest/.retrieve-skipped-all.log
    info "all モード自動スキップ: ${#skipped_for_log[@]} 型 (manifest/.retrieve-skipped-all.log に記録)"

    local n_batches
    n_batches=$(python3 - "${api_version}" "${excluded_list}" << PYEOF
import json, math, sys

api_version = sys.argv[1]
excluded_csv = sys.argv[2]
excluded = set(x for x in excluded_csv.split(',') if x)

data = json.loads("""${types_json}""")
all_types = sorted([
    m['xmlName'] for m in data.get('result', {}).get('metadataObjects', [])
    if m.get('xmlName') and m['xmlName'] not in excluded
])

# 重い型は個別 manifest（標準セットと同様）
HEAVY_TYPES = {
    'ApexClass', 'Layout', 'Profile', 'CustomObject',
    'Bot', 'BotVersion', 'Community', 'ContentAsset',
    'ConnectedApp', 'CustomApplication',
}
light_types = [t for t in all_types if t not in HEAVY_TYPES]
heavy_types  = [t for t in all_types if t in HEAVY_TYPES]

# 軽い型を 15 型/バッチで分割（30 から縮小: 重い型の巻き添えリスクを低減）
BATCH_SIZE = 15
batches = [light_types[i:i+BATCH_SIZE] for i in range(0, len(light_types), BATCH_SIZE)]

for i, batch in enumerate(batches, 1):
    lines = '\n'.join(f'    <types><members>*</members><name>{t}</name></types>' for t in batch)
    xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<Package xmlns="http://soap.sforce.com/2006/04/metadata">
{lines}
    <version>{api_version}</version>
</Package>'''
    with open(f'manifest/package-all-{i}.xml', 'w', encoding='utf-8') as f:
        f.write(xml)

# 重い型は個別 manifest
for t in heavy_types:
    if t == 'CustomObject':
        continue  # CustomObject は retrieve_all で別途処理
    xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<Package xmlns="http://soap.sforce.com/2006/04/metadata">
    <types><members>*</members><name>{t}</name></types>
    <version>{api_version}</version>
</Package>'''
    with open(f'manifest/package-{t}.xml', 'w', encoding='utf-8') as f:
        f.write(xml)

print(len(batches))
PYEOF
)

    ok "全量 package.xml 生成: manifest/package-all-1.xml 〜 ${n_batches}.xml (${n_batches} バッチ, 自動スキップ: ${#skipped_for_log[@]} 型)"

    # CustomObject は件数ベースで 100 件ずつ分割（標準セットと同ロジック）
    info "CustomObject 一覧を取得中（${target_org}）..."
    local objects_json
    objects_json=$(sf org list metadata --metadata-type CustomObject --target-org "$target_org" --json 2>/dev/null) || {
        warn "CustomObject 一覧の取得に失敗。manifest/package-CustomObject-1.xml に wildcard を使用"
        cat > "manifest/package-CustomObject-1.xml" << XMLEOF
<?xml version="1.0" encoding="UTF-8"?>
<Package xmlns="http://soap.sforce.com/2006/04/metadata">
    <types><members>*</members><name>CustomObject</name></types>
    <version>${api_version}</version>
</Package>
XMLEOF
    }
    if [ -n "${objects_json:-}" ]; then
        python3 - "${api_version}" << PYEOF
import json, math, sys
api_version = sys.argv[1]
data = json.loads("""${objects_json}""")
objects = sorted([r['fullName'] for r in data.get('result', [])])
BATCH_SIZE = 100
for i in range(math.ceil(len(objects) / BATCH_SIZE)):
    batch = objects[i*BATCH_SIZE:(i+1)*BATCH_SIZE]
    members = '\n'.join(f'        <members>{o}</members>' for o in batch)
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Package xmlns="http://soap.sforce.com/2006/04/metadata">
    <types>
{members}
        <name>CustomObject</name>
    </types>
    <version>{api_version}</version>
</Package>"""
    with open(f'manifest/package-CustomObject-{i+1}.xml', 'w', encoding='utf-8') as f:
        f.write(xml)
PYEOF
    fi

    # FlexiPage は件数が多い場合にタイムアウトするため 50 件ずつ分割
    info "FlexiPage 一覧を取得中（${target_org}）..."
    local flexipages_json_all n_flexipage_batches_all
    flexipages_json_all=$(sf org list metadata --metadata-type FlexiPage --target-org "$target_org" --json 2>/dev/null) || {
        warn "FlexiPage 一覧の取得に失敗。manifest/package-FlexiPage-1.xml に wildcard を使用"
        cat > "manifest/package-FlexiPage-1.xml" << XMLEOF
<?xml version="1.0" encoding="UTF-8"?>
<Package xmlns="http://soap.sforce.com/2006/04/metadata">
    <types><members>*</members><name>FlexiPage</name></types>
    <version>${api_version}</version>
</Package>
XMLEOF
        flexipages_json_all=""
    }

    if [ -n "${flexipages_json_all:-}" ]; then
        n_flexipage_batches_all=$(python3 - "${api_version}" << PYEOF
import json, math, sys
api_version = sys.argv[1]
data = json.loads("""${flexipages_json_all}""")
pages = sorted([r['fullName'] for r in data.get('result', [])])
BATCH_SIZE = 50
n = math.ceil(len(pages) / BATCH_SIZE) if pages else 0
for i in range(n):
    batch = pages[i*BATCH_SIZE:(i+1)*BATCH_SIZE]
    members = '\n'.join(f'        <members>{p}</members>' for p in batch)
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Package xmlns="http://soap.sforce.com/2006/04/metadata">
    <types>
{members}
        <name>FlexiPage</name>
    </types>
    <version>{api_version}</version>
</Package>"""
    with open(f'manifest/package-FlexiPage-{i+1}.xml', 'w', encoding='utf-8') as f:
        f.write(xml)
print(n)
PYEOF
)
    else
        n_flexipage_batches_all=1
    fi

    # フォルダ型を個別生成
    for pair in "${FOLDER_BASED_PAIRS[@]}"; do
        local ct="${pair%%:*}"
        local ft="${pair##*:}"
        local out="manifest/package-${ct}.xml"
        if generate_folder_based_manifest "$ct" "$ft" "$api_version" "$target_org" "$out"; then
            ok "  フォルダ型: ${out}"
        fi
    done
}

# --- 未コミット変更の確認 ---
check_uncommitted() {
    if command -v git >/dev/null 2>&1 && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        local changes
        changes=$(git status --porcelain force-app/ 2>/dev/null | head -5)
        if [ -n "$changes" ]; then
            warn "force-app/ に未コミットの変更があります:"
            echo "$changes"
            echo ""
            read -p "上書きして続行しますか？ (y/N): " confirm
            [[ "$confirm" =~ ^[yY] ]] || { info "キャンセルしました"; exit 0; }
        fi
    fi
}

# --- 単一バッチ取得（heartbeat 付き。失敗時に per-type / per-object リトライ）---
retrieve_manifest() {
    local manifest="$1"
    local target_org="$2"
    local label="$3"

    # heartbeat: 60 秒ごとに経過時間を STDOUT へ出力。バックグラウンド実行でも進捗確認可
    # 確認方法: grep "[heartbeat]" <task-output-file>
    local hb_start
    hb_start=$(date +%s)
    (while sleep 60; do
        local hb_now hb_elapsed
        hb_now=$(date +%s)
        hb_elapsed=$((hb_now - hb_start))
        echo "[$(date +%H:%M:%S)] [heartbeat] ${label}: elapsed ${hb_elapsed}s"
    done) &
    local hb_pid=$!

    if sf project retrieve start --manifest "$manifest" --target-org "$target_org" --wait "$SF_WAIT" 2>&1; then
        kill "$hb_pid" 2>/dev/null
        return 0
    fi
    kill "$hb_pid" 2>/dev/null

    # all-N バッチ（軽い型まとめ）が失敗した場合: 型を 1 つずつリトライ
    if [[ "$manifest" == *"package-all-"* ]]; then
        warn "[${label}] バッチ取得失敗。型を 1 つずつ取得します..."
        local skipped_types=()
        while IFS= read -r type_name; do
            cat > /tmp/sf-retrieve-single-type.xml << XMLEOF
<?xml version="1.0" encoding="UTF-8"?>
<Package xmlns="http://soap.sforce.com/2006/04/metadata">
    <types><members>*</members><name>${type_name}</name></types>
    <version>$(get_api_version)</version>
</Package>
XMLEOF
            if ! sf project retrieve start --manifest /tmp/sf-retrieve-single-type.xml --target-org "$target_org" --wait "$SF_WAIT" 2>&1; then
                warn "  スキップ: ${type_name}（取得失敗）"
                skipped_types+=("$type_name")
                echo "${type_name}" >> "manifest/.retrieve-skipped.log"
            fi
        done < <(grep -oP '(?<=<name>)[^<]+' "$manifest")

        if [ ${#skipped_types[@]} -gt 0 ]; then
            warn "[${label}] 以下の型はスキップしました（CLI 更新で解消する可能性あり）:"
            for t in "${skipped_types[@]}"; do warn "  - ${t}"; done
            warn "  スキップ記録: manifest/.retrieve-skipped.log"
            warn "  対処: npm install --global @salesforce/cli@latest"
        fi
        return 0
    fi

    # CustomObject バッチが失敗した場合: 1 件ずつリトライ
    if [[ "$manifest" == *"CustomObject"* ]]; then
        warn "[${label}] バッチ取得失敗。オブジェクトを 1 件ずつ取得します..."
        local skipped=()
        while IFS= read -r obj; do
            cat > /tmp/sf-retrieve-single.xml << XMLEOF
<?xml version="1.0" encoding="UTF-8"?>
<Package xmlns="http://soap.sforce.com/2006/04/metadata">
    <types><members>${obj}</members><name>CustomObject</name></types>
    <version>$(get_api_version)</version>
</Package>
XMLEOF
            if ! sf project retrieve start --manifest /tmp/sf-retrieve-single.xml --target-org "$target_org" --wait "$SF_WAIT" 2>&1; then
                warn "  スキップ: ${obj}（取得失敗 — フィールド数超過の可能性）"
                skipped+=("$obj")
            fi
        done < <(grep -oP '(?<=<members>)[^<]+' "$manifest")

        if [ ${#skipped[@]} -gt 0 ]; then
            warn "[${label}] 以下のオブジェクトはスキップしました（手動取得が必要です）:"
            for s in "${skipped[@]}"; do warn "  - ${s}"; done
        fi
        return 0
    fi

    # その他の型は失敗を上位に伝播
    return 1
}

# --- 標準取得（複数バッチ）---
retrieve_standard() {
    local target_org="$1"
    info "接続中の組織: ${target_org}"
    check_uncommitted

    local batch=0
    local manifests=()
    local skipped_manifests=()

    # 軽い type まとめ
    manifests+=("manifest/package.xml")
    # 重い type 独立
    for TYPE in ApexClass Layout Profile; do
        manifests+=("manifest/package-${TYPE}.xml")
    done
    # CustomObject 分割バッチ
    for f in manifest/package-CustomObject-*.xml; do
        [ -f "$f" ] && manifests+=("$f")
    done
    # FlexiPage 分割バッチ
    for f in manifest/package-FlexiPage-*.xml; do
        [ -f "$f" ] && manifests+=("$f")
    done
    # フォルダ型バッチ
    for ct in Dashboard Report; do
        local f="manifest/package-${ct}.xml"
        [ -f "$f" ] && manifests+=("$f")
    done

    local total=${#manifests[@]}

    for manifest in "${manifests[@]}"; do
        batch=$((batch + 1))
        local label
        label=$(basename "$manifest" .xml | sed 's/package-//')
        info "[バッチ${batch}/${total}] ${label} を取得中..."
        if retrieve_manifest "$manifest" "$target_org" "$label"; then
            ok "[バッチ${batch}/${total}] 完了"
        else
            warn "[バッチ${batch}/${total}] ${label} の取得に失敗しました（スキップして続行）"
            skipped_manifests+=("$manifest")
        fi
    done

    if [ ${#skipped_manifests[@]} -gt 0 ]; then
        warn "以下のバッチが失敗しました。手動で再試行してください:"
        for m in "${skipped_manifests[@]}"; do warn "  bash scripts/sf-retrieve.sh retrieve-manifest ${m}"; done
    fi

    ok "メタデータ取得完了 → force-app/ （計 ${total} バッチ）"
}

# --- 全量取得（複数バッチ）---
retrieve_all() {
    local target_org="$1"
    info "接続中の組織: ${target_org}"
    check_uncommitted

    local batch=0
    local manifests=()
    local skipped_manifests=()

    # 軽い type 分割バッチ
    for f in manifest/package-all-*.xml; do
        [ -f "$f" ] && manifests+=("$f")
    done
    # 重い type 独立
    for TYPE in ApexClass Layout Profile Bot BotVersion Community ContentAsset ConnectedApp CustomApplication; do
        local f="manifest/package-${TYPE}.xml"
        [ -f "$f" ] && manifests+=("$f")
    done
    # CustomObject 分割バッチ
    for f in manifest/package-CustomObject-*.xml; do
        [ -f "$f" ] && manifests+=("$f")
    done
    # FlexiPage 分割バッチ
    for f in manifest/package-FlexiPage-*.xml; do
        [ -f "$f" ] && manifests+=("$f")
    done
    # フォルダ型
    for pair in "${FOLDER_BASED_PAIRS[@]}"; do
        local ct="${pair%%:*}"
        local f="manifest/package-${ct}.xml"
        [ -f "$f" ] && manifests+=("$f")
    done

    local total=${#manifests[@]}

    for manifest in "${manifests[@]}"; do
        batch=$((batch + 1))
        local label
        label=$(basename "$manifest" .xml | sed 's/package-//')
        info "[バッチ${batch}/${total}] ${label} を取得中..."
        if retrieve_manifest "$manifest" "$target_org" "$label"; then
            ok "[バッチ${batch}/${total}] 完了"
        else
            warn "[バッチ${batch}/${total}] ${label} の取得に失敗しました（スキップして続行）"
            skipped_manifests+=("$manifest")
        fi
    done

    if [ ${#skipped_manifests[@]} -gt 0 ]; then
        warn "以下のバッチが失敗しました。手動で再試行してください:"
        for m in "${skipped_manifests[@]}"; do warn "  bash scripts/sf-retrieve.sh retrieve-manifest ${m}"; done
    fi

    ok "メタデータ取得完了 → force-app/ （計 ${total} バッチ）"
}

# --- 単一 package.xml 取得（後方互換）---
retrieve() {
    [ -f "manifest/package.xml" ] || error "manifest/package.xml が見つかりません。先に生成してください"

    local target_org
    target_org=$(get_target_org)
    info "接続中の組織: ${target_org}"
    check_uncommitted

    info "メタデータを取得中..."
    sf project retrieve start --manifest manifest/package.xml --target-org "$target_org" --wait "$SF_WAIT"
    ok "メタデータ取得完了 → force-app/"
}

# --- メイン ---
MODE="${1:-standard}"
API_VERSION=$(get_api_version)

case "$MODE" in
    standard)
        TARGET_ORG=$(get_target_org)
        generate_standard "$API_VERSION" "$TARGET_ORG"
        retrieve_standard "$TARGET_ORG"
        ;;
    all)
        TARGET_ORG=$(get_target_org)
        generate_all "$API_VERSION" "$TARGET_ORG"
        retrieve_all "$TARGET_ORG"
        ;;
    generate-only)
        SUBMODE="${2:-standard}"
        case "$SUBMODE" in
            standard)
                TARGET_ORG=$(get_target_org)
                generate_standard "$API_VERSION" "$TARGET_ORG"
                ;;
            all)
                TARGET_ORG=$(get_target_org)
                generate_all "$API_VERSION" "$TARGET_ORG"
                ;;
            *)
                error "不明なモード: $SUBMODE (standard / all)"
                ;;
        esac
        ;;
    retrieve)
        retrieve
        ;;
    retrieve-standard)
        TARGET_ORG=$(get_target_org)
        retrieve_standard "$TARGET_ORG"
        ;;
    retrieve-manifest)
        MANIFEST="${2:-}"
        [ -z "$MANIFEST" ] && error "manifest パスを指定してください: bash scripts/sf-retrieve.sh retrieve-manifest manifest/package-XXX.xml"
        [ -f "$MANIFEST" ] || error "${MANIFEST} が見つかりません"
        TARGET_ORG=$(get_target_org)
        LABEL=$(basename "$MANIFEST" .xml | sed 's/package-//')
        info "[manifest] ${LABEL} を取得中..."
        if retrieve_manifest "$MANIFEST" "$TARGET_ORG" "$LABEL"; then
            ok "完了"
        else
            error "取得失敗: ${MANIFEST}"
        fi
        ;;
    check-version)
        # check_sf_version は先頭で既に実行済み。明示呼び出し用
        ok "sf CLI バージョン確認完了"
        ;;
    *)
        echo "使い方: bash scripts/sf-retrieve.sh <mode>"
        echo ""
        echo "  standard            標準セットで package.xml 生成 + 取得"
        echo "  all                 全量で package.xml 生成 + 取得（明らかに不要な型は自動スキップ）"
        echo "  generate-only       package.xml 生成のみ（standard / all）"
        echo "  retrieve            既存 manifest/package.xml で取得のみ（後方互換）"
        echo "  retrieve-standard   生成済み standard 用全 manifest で取得のみ"
        echo "  retrieve-manifest   指定 manifest ファイル 1 つで取得（失敗バッチの個別リトライ用）"
        echo "  check-version       sf CLI バージョン確認のみ"
        echo ""
        echo "環境変数:"
        echo "  SF_RETRIEVE_WAIT=N             CLI 待機時間（分、デフォルト 60）"
        echo "  SF_RETRIEVE_EXTRA_SKIP=A,B,C   all モードで追加スキップする型（カンマ区切り）"
        exit 1
        ;;
esac

echo ""
echo "次のステップ:"
echo "  変更確認: git diff force-app/"
echo ""
