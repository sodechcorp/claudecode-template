---
name: sf-analyst-cat4-flow
description: sf-memory カテゴリ4（Flow/Config）担当。docs/design/flow/ 配下の設計書を生成・更新する。/sf-memoryコマンドから委譲されて実行する。cat1/cat2/cat3 の出力を参照してから設計書を生成する。
model: opus
tools:
  - Read
  - Edit
  - Write
  - Glob
  - Grep
  - Bash
  - TodoWrite
---

> **共通手順**: まず Read ツールで `.claude/templates/sf-memory/cat4-common.md` を読み込む。Phase 0 / 0.5 / 1.5 / 2 / 2.5 / 3 / 最終 / 最終報告フォーマットは共通テンプレートに従う。以下はこのエージェント固有の差分のみ。

**テンプレート置換ルール（厳守）:** [共通ルール参照](.claude/CLAUDE.md#テンプレート置換ルール厳守) — `{project_dir}` `{api_name}` `{source_file_paths}` `{new_hash}` `{kebab_name}` を実値で置換する。`{source_file_paths}` は Python list リテラル形式で渡す。

## 受け取る情報

- **プロジェクトフォルダのパス**
- **対象コンポーネントAPI名**（全て or 特定 API 名リスト）
- **対象機能グループID**（全て or 特定 FG-XXX）
- **コンポーネントインデックス JSON**（任意）

## 担当種別・出力フォルダ

| 種別 | 出力フォルダ | 判定基準 |
|---|---|---|
| フロー（全 ProcessType） | `flow/` | FlowDefinitionView で検出 |

---

## Phase 0 追加: フローインデックス生成

Phase 0 の `scan_features.py` 実行後に続けて、全フローの操作オブジェクト・参照関係をインデックス化して `_flow_index.json` にキャッシュする。既存キャッシュが **5分以内** の場合はスキップ。

```bash
python -c "
import datetime, json, pathlib, re, sys
proj = pathlib.Path(r'{project_dir}')
cache_path = proj / 'docs' / '.sf' / '_flow_index.json'
if cache_path.exists():
    try:
        cached_at = json.loads(cache_path.read_text(encoding='utf-8')).get('cached_at', '')
        delta = datetime.datetime.utcnow() - datetime.datetime.fromisoformat(cached_at.rstrip('Z'))
        if delta.total_seconds() < 300:
            print('SKIP: cache fresh'); sys.exit(0)
    except Exception:
        pass
flows_dir = proj / 'force-app' / 'main' / 'default' / 'flows'
index = {}
for f in sorted(flows_dir.glob('*.flow-meta.xml')):
    text = f.read_text(encoding='utf-8', errors='replace')
    objects = sorted(set(re.findall(r'<object>([^<]+)</object>', text)))
    refs = sorted(set(re.findall(r'<targetReference>([^<]+)</targetReference>', text)))
    proc_type = (re.findall(r'<processType>([^<]+)</processType>', text) or [''])[0]
    status = (re.findall(r'<status>([^<]+)</status>', text) or [''])[0]
    index[f.stem] = {'processType': proc_type, 'status': status, 'objects': objects, 'targetReferences': refs}
index['cached_at'] = datetime.datetime.utcnow().isoformat() + 'Z'
cache_path.parent.mkdir(parents=True, exist_ok=True)
cache_path.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'[flow_index] {len(index) - 1} flows → {cache_path}')
"
```

Phase 2 の設計書生成では `_flow_index.json` の `objects` を「担当オブジェクト」欄の確定に使う。

---

## Phase 1: 対象コンポーネントの収集（Flow 種別固有）

_metadata_cache.json が 5 分以内に存在する場合は `flow_definitions` キーを読んで再クエリをスキップ。

```bash
# フロー（アクティブバージョンのみ）
sf data query -q "SELECT ApiName, ProcessType, Label, Description FROM FlowDefinitionView WHERE ActiveVersionId != null ORDER BY ApiName" --json
```

> **Inactive Flow（Draft/Obsolete）の扱い**: `ActiveVersionId == null` の Flow（Inactive）は本クエリの対象外＝設計書生成対象外とする（「設計書は稼働中の組織を記述する」という意図的な設計）。ただし silent 除外を避けるため、Phase 0 で生成した `_flow_index.json` の各エントリの `status` が `Active` 以外（Draft/Obsolete/InvalidDraft 等）の Flow を抽出し、その API 名と件数を**最終報告の「主な発見・所見」に1行**記載する（例: `Inactive Flow 2 件を設計書生成対象から除外（Draft）: GH_UpdateTaskLastActivityDate, GH_UpdateToDoLastActivityDate`）。物理ファイルは存在するが稼働していないため、文書化要否は人間が個別判断する。

各フローのソースを以下の **段階的読み戦略** で読み込む（全量を一気に読まない）:

**Pass 1（骨格把握）**: Grep で主要タグの name 属性を抽出してノード一覧と接続関係を把握。

```bash
python -c "
import re, pathlib
text = pathlib.Path(r'{project_dir}/force-app/main/default/flows/{api_name}.flow-meta.xml').read_text(encoding='utf-8', errors='replace')
tags = ['screens','decisions','actionCalls','recordLookups','recordUpdates','recordCreates','subflows','loops','scheduleStart']
for tag in tags:
    names = re.findall(rf'<{tag}[^>]*>.*?<name>([^<]+)</name>', text, re.DOTALL)
    if names:
        print(f'{tag}: {names}')
"
```

**Pass 2（詳細読み）**: 骨格で特定した主要ノード（Decision 条件式・RecordUpdate 対象項目等）を `Read` の offset/limit で部分読み込み（各 50〜150 行）。

**Pass 3（Scheduled Flow）**: `<scheduleStart>` or `<schedule>` タグがある場合はそのブロックを Read して `frequency / startDate / startTime / offsetNumber / offsetUnit` を抽出し、設計書の「処理タイミング」欄に記述する。

> 500 行以下の小規模 Flow は Pass 1 のみで十分な場合が多い。Pass 2/3 は必要に応じて実施。

既存設計書がある場合はそのファイルも Read してアップデートモードで更新する。

> **deprecated 設計書の扱い**: 対象 API 名が `feature_ids.yml` で `deprecated=true` の場合、本フェーズでは設計書を更新せずスキップする。deprecated 注記の付与は `cat4-common.md` Phase 2.0 の `mark_design_deprecated.py` が一括処理する。
