---
name: sf-analyst-cat4-apex
description: sf-memory カテゴリ4（Apex/Trigger/Batch/Integration）担当。docs/design/apex/ / batch/ / integration/ 配下の設計書を生成・更新する。/sf-memoryコマンドから委譲されて実行する。cat1/cat2/cat3 の出力を参照してから設計書を生成する。
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

**テンプレート置換ルール（厳守）:** [共通ルール参照](.claude/CLAUDE.md#テンプレート置換ルール厳守) — `{project_dir}` `{api_name}` `{source_file_paths}` `{new_hash}` `{kebab_name}` を実値で置換する。`{source_file_paths}` は Python list リテラル形式（`["path1", "path2"]`）で渡す。

## 受け取る情報

- **プロジェクトフォルダのパス**
- **対象コンポーネントAPI名**（全て or 特定 API 名リスト）
- **対象機能グループID**（全て or 特定 FG-XXX）
- **コンポーネントインデックス JSON**（任意: 大量処理時の効率化用）

## 担当種別・出力フォルダ

| 種別 | 出力フォルダ | 判定基準 |
|---|---|---|
| Apex クラス（非 Batch / 非 Schedule） | `apex/` | `Database.Batchable` / `Schedulable` 未実装 |
| Apex トリガー | `apex/` | ApexTrigger クエリで検出 |
| バッチ・スケジュールジョブ | `batch/` | `Database.Batchable` or `Schedulable` 実装 |
| 外部 API・Named Credential 連携 | `integration/` | NamedCredential 使用 or callout 含む Apex |

> **ハンドラクラスの扱い**: 単一 Trigger/Batch から排他的に呼ばれる Handler は呼び出し元に統合。複数から共通に呼ばれる場合は独立ファイル。統合時のファイル名は `【CMP-002〜CMP-003】name.md` のように全 CMP を列挙する。

---

## Phase 0 追加: Apex スケルトン生成（全件）

Phase 0 の `scan_features.py` 実行後に続けて、全 Apex クラスのスケルトンを生成して `_apex_skeletons.json` にキャッシュする。既存キャッシュが **5分以内** の場合はスキップ。

```bash
python -c "
import datetime, json, pathlib, subprocess, sys
proj = pathlib.Path(r'{project_dir}')
cache_path = proj / 'docs' / '.sf' / '_apex_skeletons.json'
if cache_path.exists():
    try:
        cached_at = json.loads(cache_path.read_text(encoding='utf-8')).get('cached_at', '')
        delta = datetime.datetime.utcnow() - datetime.datetime.fromisoformat(cached_at.rstrip('Z'))
        if delta.total_seconds() < 300:
            print('SKIP: cache fresh')
            sys.exit(0)
    except Exception:
        pass
skeletons = {}
for cls_file in sorted((proj / 'force-app' / 'main' / 'default' / 'classes').glob('*.cls')):
    result = subprocess.run(
        ['python', str(proj / 'scripts' / 'python' / 'sf-doc-mcp' / 'extract_apex_skeleton.py'),
         '--input', str(cls_file)],
        capture_output=True, text=True, encoding='utf-8'
    )
    if result.returncode == 0 and result.stdout.strip():
        try:
            skeletons[cls_file.stem] = json.loads(result.stdout)
        except Exception:
            pass
skeletons['cached_at'] = datetime.datetime.utcnow().isoformat() + 'Z'
cache_path.parent.mkdir(parents=True, exist_ok=True)
cache_path.write_text(json.dumps(skeletons, ensure_ascii=False, indent=2), encoding='utf-8')
print(f'[apex_skeletons] {len(skeletons) - 1} classes → {cache_path}')
"
```

Phase 2 の設計書生成では `_apex_skeletons.json` の当該クラスエントリを LLM への入力として使う（ソース全文読みの補完・SOQL/DML 件数確定に使用）。

---

## Phase 1: 対象コンポーネントの収集（Apex 種別固有）

_metadata_cache.json が 5 分以内に存在する場合は `apex_classes` / `apex_triggers` / `named_credentials` / `cron_triggers` キーを読んで再クエリをスキップ。存在しない or 期限切れの場合のみ以下を実行し `build_metadata_cache.py` でキャッシュする。

```bash
# Apex クラス（テストクラス除外）
sf data query -q "SELECT Name, IsTest FROM ApexClass WHERE NamespacePrefix = null AND IsTest = false ORDER BY Name" --json

# Apex トリガー
sf data query -q "SELECT Name, TableEnumOrId FROM ApexTrigger WHERE NamespacePrefix = null" --json

# Named Credential（外部連携の存在確認）
sf data query -q "SELECT DeveloperName, Endpoint FROM NamedCredential" --json 2>/dev/null

# バッチ・スケジュール（実行中ジョブ確認）
sf data query -q "SELECT Name, JobType, CronExpression FROM CronTrigger WHERE State = 'WAITING' OR State = 'ACQUIRED'" --json 2>/dev/null
```

各コンポーネントのソースを **全文読み込む**（500 行超は 200 行ずつ分割）:
- Apex: `force-app/main/default/classes/{Name}.cls` + `{Name}.cls-meta.xml`
- Integration: `force-app/main/default/namedCredentials/` / `externalCredentials/`

既存設計書がある場合はそのファイルも Read してアップデートモードで更新する。

> **deprecated 設計書の扱い**: 対象 API 名が `feature_ids.yml` で `deprecated=true` の場合、本フェーズでは設計書を更新せずスキップする。deprecated 注記の付与は `cat4-common.md` Phase 2.0 の `mark_design_deprecated.py` が一括処理する。
