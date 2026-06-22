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

# --- retrieve の待機時間・並行度 ---
# 環境変数で上書き可:
#   SF_RETRIEVE_WAIT=N           CLI 待機時間（分、デフォルト 60）
#   SF_RETRIEVE_PARALLEL=N       バッチ並行度（デフォルト 4）
#   SF_RETRIEVE_RETRY_PARALLEL=N 個別リトライ並行度（デフォルト 2）
SF_WAIT="${SF_RETRIEVE_WAIT:-60}"
SF_RETRIEVE_PARALLEL="${SF_RETRIEVE_PARALLEL:-4}"
SF_RETRIEVE_RETRY_PARALLEL="${SF_RETRIEVE_RETRY_PARALLEL:-2}"

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
#   manifest/package-{TYPE}.xml        ... 重い type 独立（ApexClass/Layout/Profile/Flow/FlexiPage）
#   manifest/package-CustomObject-N.xml ... CustomObject を 100 件ずつ分割（動的生成）
#   manifest/package-Dashboard.xml     ... フォルダ列挙（DashboardFolder 経由）
#   manifest/package-Report.xml        ... フォルダ列挙（ReportFolder 経由）
#
# 注: EmailTemplate / Document はフォルダ型のため standard から除外。
#     必要な場合は /sf-retrieve select で個別取得してください。
# 注: Flow は他の不安定な型と同バッチになると巻き添えで取得失敗するため専用バッチに隔離。
generate_standard() {
    local api_version="$1"
    local target_org="$2"
    mkdir -p manifest

    # 軽い type まとめ（wildcard）
    # ※ EmailTemplate はフォルダ型のため除外済み
    # ※ Flow は巻き添え防止のため専用バッチ（package-Flow.xml）に分離
    cat > manifest/package.xml << XMLEOF
<?xml version="1.0" encoding="UTF-8"?>
<Package xmlns="http://soap.sforce.com/2006/04/metadata">
    <types><members>*</members><name>ApexTrigger</name></types>
    <types><members>*</members><name>ApexPage</name></types>
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
    # Flow は他の不安定な型による巻き添えを防ぐため独立バッチに含める
    for TYPE in ApexClass Layout Profile Flow; do
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
    ok "  重い type: manifest/package-{ApexClass,Layout,Profile,Flow}.xml"
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
# Flow は他の不安定な型との同バッチによる巻き添えを防ぐため HEAVY_TYPES に追加
HEAVY_TYPES = {
    'ApexClass', 'Layout', 'Profile', 'CustomObject',
    'Bot', 'BotVersion', 'Community', 'ContentAsset',
    'ConnectedApp', 'CustomApplication', 'Flow',
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

# --- 取得後の重要型検証 ---
# Flow は保守業務の中核。取得後に1件も存在しない場合は ERROR で止める。
verify_critical_types() {
    local flow_count
    flow_count=$(find force-app/ -name "*.flow-meta.xml" 2>/dev/null | wc -l)
    if [ "$flow_count" -eq 0 ]; then
        error "Flow が1件も取得されていません（force-app/main/default/flows/ が空）。\n  スキップログを確認: manifest/.retrieve-skipped.log\n  対処: bash scripts/sf-retrieve.sh retrieve-manifest manifest/package-Flow.xml"
    fi
    ok "取得後検証: Flow ${flow_count} 件確認"
}

# --- Flow バージョン監査（Tooling API）---
# Metadata API v44+ は常に Latest バージョンを取得する（Active 版指定不可）。
# Active 版と Latest 版が乖離している Flow を検知して warn する。取得自体は成功しているため error では止めない。
audit_flow_versions() {
    local target_org="$1"
    local flow_query_json
    flow_query_json=$(sf data query --use-tooling-api \
        -q "SELECT DeveloperName, ActiveVersionId, ActiveVersion.VersionNumber, LatestVersion.VersionNumber FROM FlowDefinition" \
        --target-org "$target_org" --json 2>/dev/null) || {
        warn "Flow バージョン監査スキップ（Tooling API クエリ失敗）"
        return
    }

    python3 - << PYEOF
import json, sys

data = json.loads("""${flow_query_json}""")
records = data.get("result", {}).get("records", [])

drifted = []
no_active = []

for r in records:
    name = r.get("DeveloperName", "")
    active_id = r.get("ActiveVersionId")
    active_ver = (r.get("ActiveVersion") or {}).get("VersionNumber")
    latest_ver = (r.get("LatestVersion") or {}).get("VersionNumber")

    if not active_id:
        no_active.append(f"  {name}（Active なし／Draft のみ）")
    elif active_ver is not None and latest_ver is not None and active_ver != latest_ver:
        drifted.append(f"  {name}（Active=v{active_ver}、取得済み=v{latest_ver} Draft）")

total = len(records)
ok_count = total - len(drifted) - len(no_active)

print(f"\033[36m[INFO]\033[0m Flow バージョン監査: {total} 件（正常={ok_count}、乖離={len(drifted)}、未有効化={len(no_active)}）")

if no_active:
    print("\033[33m[WARN]\033[0m 未有効化 Flow（組織で一度も Active になっていない）:")
    for m in no_active:
        print(m)

if drifted:
    print("\033[33m[WARN]\033[0m Active 版と乖離あり（取得済みは Active より新しい Draft）:")
    for m in drifted:
        print(m)
    print("\033[33m[WARN]\033[0m 対処が必要な場合: 組織で Draft を破棄または有効化してから再 retrieve")
    print("       → bash scripts/sf-retrieve.sh retrieve-manifest manifest/package-Flow.xml")
PYEOF
}

# --- 未コミット変更の確認（情報提供のみ・中断しない）---
# コマンド側（sf-retrieve.md）が AskUserQuestion で続行可否を確認済みのため、
# スクリプトは警告のみ出力して自動継続する。
check_uncommitted() {
    if command -v git >/dev/null 2>&1 && git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
        local changes
        changes=$(git status --porcelain force-app/ 2>/dev/null | head -5)
        if [ -n "$changes" ]; then
            warn "force-app/ に未コミットの変更があります（取得で上書きされます）:"
            echo "$changes"
            echo ""
        fi
    fi
}

# --- 並行バッチ取得 ---
# SF_RETRIEVE_PARALLEL 並行でバッチを取得する（bash 5.2 以上、wait -n 使用）。
# 各バッチは retrieve_manifest をバックグラウンドで実行し、
# 成否は manifest/.retrieve-status/<label>.status（OK/FAIL）に記録する。
run_parallel() {
    local target_org="$1"
    shift
    local manifests=("$@")
    local total=${#manifests[@]}
    local batch=0
    local running=0

    for manifest in "${manifests[@]}"; do
        batch=$((batch + 1))
        local label
        label=$(basename "$manifest" .xml | sed 's/package-//')

        # 上限に達したら 1 つ完了するまで待つ
        while [ "$running" -ge "$SF_RETRIEVE_PARALLEL" ]; do
            wait -n 2>/dev/null || true
            running=$((running - 1))
        done

        info "[バッチ${batch}/${total}] ${label} 取得開始..."
        retrieve_manifest "$manifest" "$target_org" "$label" &
        running=$((running + 1))
    done

    # 残り全待機
    wait 2>/dev/null || true
}

# ヘルパ: ログファイルに「この組織で利用不可」エラーが含まれているか判定
# 未ライセンス機能・未使用機能のメタデータ型取得時に SF CLI が返すエラーパターンを検出する。
# 一致 → return 0（組織で利用不可）、不一致 → return 1（他の原因）
_is_org_unavailable_error() {
    local logfile="$1"
    [ -f "$logfile" ] || return 1
    grep -qiE 'INVALID_TYPE|Entity of type .* cannot be found|is not available in this org|No component named.*not found' "$logfile" 2>/dev/null
}

# --- 単一バッチ取得（heartbeat 付き。失敗時に構造ベース並行リトライ）---
#
# 並行実行時の画面混線を避けるため、CLI 出力はログファイルへのみ書き込む。
# バッチ成否は manifest/.retrieve-status/<label>.status（OK/FAIL）に記録する。
# heartbeat もログへ書くので進捗監視は以下で確認:
#   grep "\[heartbeat\]" manifest/.retrieve-*.log
#
# リトライ戦略（manifest の XML 構造から自動判定）:
#   複数型バッチ（package.xml / package-all-N）
#     → 型単位リトライ（SF_RETRIEVE_RETRY_PARALLEL 並行）
#   単一型 + 具体 member（CustomObject-N / FlexiPage-N / Dashboard / Report）
#     → member 単位リトライ（同並行）
#   単一型 + wildcard（ApexClass / Flow / Layout / Profile 等）
#     → 分割不能。失敗として上位に伝播し手動リトライを案内する。
retrieve_manifest() {
    local manifest="$1"
    local target_org="$2"
    local label="$3"
    local status_dir="manifest/.retrieve-status"
    mkdir -p "$status_dir"  # retrieve-manifest サブコマンドから直接呼ばれる場合も対応

    local log_file="manifest/.retrieve-${label}.log"
    local status_file="${status_dir}/${label}.status"
    local skipped_file="${status_dir}/${label}.skipped"

    # heartbeat: 60 秒ごとに経過時間をログファイルへ出力
    local hb_start
    hb_start=$(date +%s)
    (while sleep 60; do
        local hb_now hb_elapsed
        hb_now=$(date +%s)
        hb_elapsed=$((hb_now - hb_start))
        echo "[$(date +%H:%M:%S)] [heartbeat] ${label}: elapsed ${hb_elapsed}s" >> "$log_file"
    done) &
    local hb_pid=$!

    if sf project retrieve start --manifest "$manifest" --target-org "$target_org" \
        --wait "$SF_WAIT" --ignore-conflicts > "$log_file" 2>&1; then
        kill "$hb_pid" 2>/dev/null
        echo "OK" > "$status_file"
        return 0
    fi
    kill "$hb_pid" 2>/dev/null

    warn "[${label}] 取得失敗。エラーログ: ${log_file}"

    # manifest の構造判定: リトライ戦略を決定する
    local name_count wildcard_count
    name_count=$(grep -c '<name>' "$manifest" 2>/dev/null || echo 0)
    wildcard_count=$(grep -c '<members>\*</members>' "$manifest" 2>/dev/null || echo 0)

    local api_ver label_safe
    api_ver=$(get_api_version)
    label_safe=$(echo "$label" | sed 's/[^a-zA-Z0-9_-]/_/g')

    if [ "$name_count" -gt 1 ]; then
        # ── 複数型バッチ: 型を 1 つずつ並行リトライ ─────────────────────────
        warn "[${label}] バッチ取得失敗。型を 1 つずつ取得します（${SF_RETRIEVE_RETRY_PARALLEL} 並行）..."
        local types=()
        while IFS= read -r type_name; do
            types+=("$type_name")
        done < <(grep -oP '(?<=<name>)[^<]+' "$manifest")

        local running_r=0
        for type_name in "${types[@]}"; do
            while [ "$running_r" -ge "$SF_RETRIEVE_RETRY_PARALLEL" ]; do
                wait -n 2>/dev/null || true
                running_r=$((running_r - 1))
            done
            local type_safe retry_xml retry_log retry_status
            type_safe=$(echo "$type_name" | sed 's/[^a-zA-Z0-9_-]/_/g')
            retry_xml="${status_dir}/retry-${label_safe}-type-${type_safe}.xml"
            retry_log="${status_dir}/retry-${label_safe}-type-${type_safe}.log"
            retry_status="${status_dir}/retry-${label_safe}-type-${type_safe}.status"
            cat > "$retry_xml" << XMLEOF
<?xml version="1.0" encoding="UTF-8"?>
<Package xmlns="http://soap.sforce.com/2006/04/metadata">
    <types><members>*</members><name>${type_name}</name></types>
    <version>${api_ver}</version>
</Package>
XMLEOF
            (
                if sf project retrieve start --manifest "$retry_xml" --target-org "$target_org" \
                    --wait "$SF_WAIT" --ignore-conflicts > "$retry_log" 2>&1; then
                    echo "OK" > "$retry_status"
                else
                    echo "FAIL" > "$retry_status"
                fi
            ) &
            running_r=$((running_r + 1))
        done
        wait 2>/dev/null || true

        # 結果集約: 組織未使用エラーと本当の取得失敗を区別する
        local skipped_types=()
        local unavail_types=()
        for type_name in "${types[@]}"; do
            local type_safe retry_status retry_log
            type_safe=$(echo "$type_name" | sed 's/[^a-zA-Z0-9_-]/_/g')
            retry_status="${status_dir}/retry-${label_safe}-type-${type_safe}.status"
            retry_log="${status_dir}/retry-${label_safe}-type-${type_safe}.log"
            if [ "$(cat "$retry_status" 2>/dev/null)" = "FAIL" ]; then
                if _is_org_unavailable_error "$retry_log"; then
                    unavail_types+=("$type_name")
                    echo "${type_name} [組織未使用]" >> "$skipped_file"
                else
                    warn "  スキップ: ${type_name}（取得失敗。ログ: ${retry_log}）"
                    skipped_types+=("$type_name")
                    echo "${type_name}" >> "$skipped_file"
                fi
            fi
        done

        if [ ${#skipped_types[@]} -gt 0 ]; then
            warn "[${label}] 以下の型はスキップしました（CLI 更新で解消する可能性あり）:"
            for t in "${skipped_types[@]}"; do warn "  - ${t}"; done
            warn "  対処: npm install --global @salesforce/cli@latest"
            echo "FAIL" > "$status_file"
            return 1
        elif [ ${#unavail_types[@]} -gt 0 ]; then
            info "[${label}] スキップ（この組織で未使用/未ライセンスの型: ${unavail_types[*]}）"
            echo "SKIP" > "$status_file"
            return 0
        fi
        echo "OK" > "$status_file"
        return 0

    elif [ "$wildcard_count" -eq 0 ]; then
        # ── 単一型 + 具体 member: member を 1 件ずつ並行リトライ ─────────────
        local type_name
        type_name=$(grep -oP '(?<=<name>)[^<]+' "$manifest" | head -1)
        warn "[${label}] バッチ取得失敗。${type_name} を 1 件ずつ取得します（${SF_RETRIEVE_RETRY_PARALLEL} 並行）..."
        local members=()
        while IFS= read -r mem; do
            members+=("$mem")
        done < <(grep -oP '(?<=<members>)[^<]+' "$manifest")

        local running_r=0
        for mem in "${members[@]}"; do
            while [ "$running_r" -ge "$SF_RETRIEVE_RETRY_PARALLEL" ]; do
                wait -n 2>/dev/null || true
                running_r=$((running_r - 1))
            done
            local mem_safe retry_xml retry_log retry_status
            mem_safe=$(echo "$mem" | sed 's/[^a-zA-Z0-9_-]/_/g')
            retry_xml="${status_dir}/retry-${label_safe}-mem-${mem_safe}.xml"
            retry_log="${status_dir}/retry-${label_safe}-mem-${mem_safe}.log"
            retry_status="${status_dir}/retry-${label_safe}-mem-${mem_safe}.status"
            cat > "$retry_xml" << XMLEOF
<?xml version="1.0" encoding="UTF-8"?>
<Package xmlns="http://soap.sforce.com/2006/04/metadata">
    <types><members>${mem}</members><name>${type_name}</name></types>
    <version>${api_ver}</version>
</Package>
XMLEOF
            (
                if sf project retrieve start --manifest "$retry_xml" --target-org "$target_org" \
                    --wait "$SF_WAIT" --ignore-conflicts > "$retry_log" 2>&1; then
                    echo "OK" > "$retry_status"
                else
                    echo "FAIL" > "$retry_status"
                fi
            ) &
            running_r=$((running_r + 1))
        done
        wait 2>/dev/null || true

        # 結果集約
        local skipped=()
        for mem in "${members[@]}"; do
            local mem_safe retry_status retry_log
            mem_safe=$(echo "$mem" | sed 's/[^a-zA-Z0-9_-]/_/g')
            retry_status="${status_dir}/retry-${label_safe}-mem-${mem_safe}.status"
            retry_log="${status_dir}/retry-${label_safe}-mem-${mem_safe}.log"
            if [ "$(cat "$retry_status" 2>/dev/null)" = "FAIL" ]; then
                warn "  スキップ: ${mem}（取得失敗。ログ: ${retry_log}）"
                skipped+=("$mem")
                echo "${mem}" >> "$skipped_file"
            fi
        done

        if [ ${#skipped[@]} -gt 0 ]; then
            warn "[${label}] 以下のコンポーネントはスキップしました（手動取得が必要です）:"
            for s in "${skipped[@]}"; do warn "  - ${s}"; done
            echo "FAIL" > "$status_file"
            return 1
        fi
        echo "OK" > "$status_file"
        return 0

    else
        # ── 単一型 + wildcard: 分割不能 ──────────────────────────────────────
        # （ApexClass, Flow, Layout, Profile 等の wildcard バッチが失敗した場合）
        if _is_org_unavailable_error "$log_file"; then
            info "[${label}] スキップ（この組織で未使用/未ライセンスの型）"
            echo "SKIP" > "$status_file"
            return 0
        fi
        warn "[${label}] 取得失敗（分割不能な型）。スキップします。"
        warn "  手動リトライ: bash scripts/sf-retrieve.sh retrieve-manifest ${manifest}"
        echo "FAIL" > "$status_file"
        return 1
    fi
}

# --- 標準取得（複数バッチ並行）---
retrieve_standard() {
    local target_org="$1"
    info "接続中の組織: ${target_org}"
    check_uncommitted

    local manifests=()

    # 軽い type まとめ
    manifests+=("manifest/package.xml")
    # 重い type 独立（Flow は巻き添え防止のため独立バッチ）
    for TYPE in ApexClass Layout Profile Flow; do
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

    # ステータスディレクトリを初期化してから並行取得
    rm -rf manifest/.retrieve-status
    mkdir -p manifest/.retrieve-status
    run_parallel "$target_org" "${manifests[@]}"

    # 結果集約: SKIP（組織未使用）と FAIL（本当の取得失敗）を区別する
    local skipped_manifests=()
    local unavail_batches=0
    local batch=0
    for manifest in "${manifests[@]}"; do
        batch=$((batch + 1))
        local label
        label=$(basename "$manifest" .xml | sed 's/package-//')
        local status_file="manifest/.retrieve-status/${label}.status"
        local status
        status=$(cat "$status_file" 2>/dev/null)
        if [ "$status" = "SKIP" ]; then
            info "[バッチ${batch}/${total}] ${label} スキップ（この組織で未使用の型）"
            unavail_batches=$((unavail_batches + 1))
        elif [ "$status" != "OK" ]; then
            warn "[バッチ${batch}/${total}] ${label} 失敗"
            skipped_manifests+=("$manifest")
        else
            ok "[バッチ${batch}/${total}] ${label} 完了"
        fi
    done

    # スキップ記録を統合
    rm -f manifest/.retrieve-skipped.log
    for f in manifest/.retrieve-status/*.skipped; do
        [ -f "$f" ] && cat "$f" >> manifest/.retrieve-skipped.log
    done

    if [ ${#skipped_manifests[@]} -gt 0 ]; then
        warn "以下のバッチが失敗しました。手動で再試行してください:"
        for m in "${skipped_manifests[@]}"; do warn "  bash scripts/sf-retrieve.sh retrieve-manifest ${m}"; done
        warn ""
        warn "取得できなかったバッチがあります。force-app/ は不完全な状態です。"
        warn "スキップログ: manifest/.retrieve-skipped.log"
        check_sf_version
        error "メタデータ取得が一部失敗しました（${#skipped_manifests[@]}/${total} バッチ未取得）"
    fi

    local skip_msg=""
    if [ "$unavail_batches" -gt 0 ]; then
        skip_msg="（${unavail_batches} バッチはこの組織で未使用の型のためスキップ）"
    fi

    verify_critical_types
    audit_flow_versions "$target_org"
    ok "メタデータ取得完了 → force-app/ （計 ${total} バッチ${skip_msg}）"
}

# --- 全量取得（複数バッチ並行）---
retrieve_all() {
    local target_org="$1"
    info "接続中の組織: ${target_org}"
    check_uncommitted

    local manifests=()

    # 軽い type 分割バッチ
    for f in manifest/package-all-*.xml; do
        [ -f "$f" ] && manifests+=("$f")
    done
    # 重い type 独立（Flow は巻き添え防止のため独立バッチ）
    for TYPE in ApexClass Layout Profile Flow Bot BotVersion Community ContentAsset ConnectedApp CustomApplication; do
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

    # ステータスディレクトリを初期化してから並行取得
    rm -rf manifest/.retrieve-status
    mkdir -p manifest/.retrieve-status
    run_parallel "$target_org" "${manifests[@]}"

    # 結果集約: SKIP（組織未使用）と FAIL（本当の取得失敗）を区別する
    local skipped_manifests=()
    local unavail_batches=0
    local batch=0
    for manifest in "${manifests[@]}"; do
        batch=$((batch + 1))
        local label
        label=$(basename "$manifest" .xml | sed 's/package-//')
        local status_file="manifest/.retrieve-status/${label}.status"
        local status
        status=$(cat "$status_file" 2>/dev/null)
        if [ "$status" = "SKIP" ]; then
            info "[バッチ${batch}/${total}] ${label} スキップ（この組織で未使用の型）"
            unavail_batches=$((unavail_batches + 1))
        elif [ "$status" != "OK" ]; then
            warn "[バッチ${batch}/${total}] ${label} 失敗"
            skipped_manifests+=("$manifest")
        else
            ok "[バッチ${batch}/${total}] ${label} 完了"
        fi
    done

    # スキップ記録を統合
    rm -f manifest/.retrieve-skipped.log
    for f in manifest/.retrieve-status/*.skipped; do
        [ -f "$f" ] && cat "$f" >> manifest/.retrieve-skipped.log
    done

    if [ ${#skipped_manifests[@]} -gt 0 ]; then
        warn "以下のバッチが失敗しました。手動で再試行してください:"
        for m in "${skipped_manifests[@]}"; do warn "  bash scripts/sf-retrieve.sh retrieve-manifest ${m}"; done
        warn ""
        warn "取得できなかったバッチがあります。force-app/ は不完全な状態です。"
        warn "スキップログ: manifest/.retrieve-skipped.log"
        check_sf_version
        error "メタデータ取得が一部失敗しました（${#skipped_manifests[@]}/${total} バッチ未取得）"
    fi

    local skip_msg=""
    if [ "$unavail_batches" -gt 0 ]; then
        skip_msg="（${unavail_batches} バッチはこの組織で未使用の型のためスキップ）"
    fi

    verify_critical_types
    audit_flow_versions "$target_org"
    ok "メタデータ取得完了 → force-app/ （計 ${total} バッチ${skip_msg}）"
}

# --- 単一 package.xml 取得（後方互換）---
retrieve() {
    [ -f "manifest/package.xml" ] || error "manifest/package.xml が見つかりません。先に生成してください"

    local target_org
    target_org=$(get_target_org)
    info "接続中の組織: ${target_org}"
    check_uncommitted

    info "メタデータを取得中..."
    sf project retrieve start --manifest manifest/package.xml --target-org "$target_org" --wait "$SF_WAIT" --ignore-conflicts
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
