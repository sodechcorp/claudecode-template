# cat4 共通テンプレート（sf-analyst-cat4-apex / cat4-flow / cat4-lwc 共通）

> 各種別エージェントは本ファイルを冒頭で参照し、固有の Phase 1 差分のみを自身のファイルで定義する。

---

## 禁止・共通参照

> **禁止**: `scripts/` 配下のスクリプトを修正・上書きしない。問題発見時は完了報告に「要修正: {ファイル名} — {概要}」として記録のみ。
> **禁止**: Claude Code の組み込みmemory機能への書き込みは一切行わない。

**テンプレート置換ルール（厳守）:** [共通ルール参照](.claude/CLAUDE.md#テンプレート置換ルール厳守)

**マーカー規約:** [共通ルール参照](.claude/CLAUDE.md#マーカー規約sf-memory-全カテゴリ共通)

---

## Step 0: 共通品質原則の確認

`.claude/spec/sf-memory-quality.md` を Read して全カテゴリ共通の品質原則（網羅的に読む・事実と推定を分ける・手動追記を消さない）を確認する。

---

## 品質原則（cat4 固有・全フェーズ共通）

以下はカテゴリ4固有の追加原則（全カテゴリ共通原則は上記 sf-memory-quality.md 参照）。

1. **具体的に書く**: 「処理を行う」ではなく「Account.Billing_Status__c を"請求済"に更新し、関連するOpportunityLineItemを削除する（DELETE）」。メソッド名・引数・戻り値・SOQL件数・DML件数を必ず記述する。
2. **関連付けを明記する（1周目で確定）**: 要件番号（FR-XXX）・ユースケースID（UC-XX）・担当オブジェクト・呼び出し元コンポーネントを Phase 0.5 で読み込んだ usecases.md / requirements.md と突き合わせて確定し `**[要確認]**` を残さない。
3. **未実装を明示する**: ソースが存在しない場合は骨格を生成し全セクションに `**[未実装]**` を付ける。

---

## Phase 0: scan_features.py 実行

```bash
python {project_dir}/scripts/python/sf-doc-mcp/scan_features.py \
  --project-dir "{project_dir}" \
  --output "{project_dir}/docs/.sf/feature_list.json"
```

---

## Phase 0.5: 前段カテゴリの出力を読む（必須）

**cat1/cat2 の生成物:**

まず `docs/.sf/_context_cache.json` が存在する場合はそれを Read して Glossary / UC index / FR-XXX index を取得する。存在しない場合は従来通り各ファイルを直接 Read する。

- `docs/overview/org-profile.md`（または _context_cache.json の glossary フィールド） — 用語集
- `docs/flow/usecases.md`（または _context_cache.json の uc_ids / related_objects フィールド） — UC / 担当オブジェクト
- `docs/requirements/requirements.md`（または _context_cache.json の fr_ids フィールド） — FR-XXX
- `docs/catalog/_index.md` — オブジェクト一覧
- 当該コンポーネントが触るオブジェクトに絞って `docs/catalog/custom/*.md` を Read

**cat3 の生成物（E-1: 承認プロセス・キュー連携）:**

- `docs/data/automation-config.md` — 承認プロセス・キュー割り当て・自動化設定を Read する。当該コンポーネントに関係する承認プロセス・キューが特定できた場合は設計書の「処理タイミング」「呼び出し元」欄に転記する。

**cat6 の生成物（E-3: 過去の不具合・運用ハマりポイント）:**

- `docs/.sf/_cmp_case_index.json` が存在する場合は Read し、当該 CMP API 名に紐付く過去課題 ID リストを取得する。Phase 2 の設計書生成時に「## 過去の不具合・運用ハマりポイント」セクションとして転記する。

**cat8 の生成物（E-4: ガバナ制限リスク）:**

- `docs/knowledge/sf-standard.md` が存在する場合は Read し、ガバナ制限リスク表を取得する。Batch/Trigger/大規模 Apex に該当するコンポーネントの設計書に「## ガバナ制限リスク」セクションとして転記する。

**モード判定（差分更新）:**

`docs/design/` 配下にmdファイルが存在するか確認する。存在しない → 初回生成モード、存在する → アップデートモード（手動追記・設計判断の根拠を絶対に消さない）。

---

## Phase 1.5: ハッシュチェック（変更なしスキップ）

```bash
python -c "
import hashlib, json, pathlib
proj = pathlib.Path(r'{project_dir}')
cache_path = proj / 'docs' / '.sf' / 'cat4_hash_cache.json'
cache = json.loads(cache_path.read_text(encoding='utf-8')) if cache_path.exists() else {}
api_name = '{api_name}'
src_paths = {source_file_paths}
h = hashlib.md5()
for p in sorted(src_paths):
    path = pathlib.Path(p)
    if path.exists():
        h.update(path.read_bytes())
current_hash = h.hexdigest()
if cache.get(api_name) == current_hash:
    print('SKIP')
else:
    print(f'UPDATE:{current_hash}')
"
```

`SKIP` → Phase 2 をスキップ。`UPDATE:{hash}` → Phase 2 で設計書を生成/更新後にキャッシュを更新:

```bash
python -c "
import json, pathlib
proj = pathlib.Path(r'{project_dir}')
cache_path = proj / 'docs' / '.sf' / 'cat4_hash_cache.json'
cache = json.loads(cache_path.read_text(encoding='utf-8')) if cache_path.exists() else {}
cache['{api_name}'] = '{new_hash}'
cache_path.write_text(json.dumps(cache, ensure_ascii=False, indent=2), encoding='utf-8')
"
```

---

## Phase 2: 設計書の生成

**ファイル命名規則**: `docs/design/{種別}/【{機能ID}】{コンポーネント名-kebab-case}.md`

機能IDは `docs/.sf/feature_ids.yml` を参照（読み取り専用）。独自採番・TBD使用禁止。

**既存 【TBD】ファイルの処理**:

```bash
python -c "
import pathlib
design_dir = pathlib.Path(r'{project_dir}/docs/design')
for tbd in design_dir.rglob('【TBD】{kebab_name}.md'):
    tbd.unlink()
    print(f'削除: {tbd}')
"
```

テンプレートは `{project_dir}/docs/templates/component-design-template.md` を Read して使用する。

---

## Phase 2.5: feature_list.json の再生成（リネーム後の整合）

Phase 2 でファイル名が1件でも変わった場合のみ:

```bash
python {project_dir}/scripts/python/sf-doc-mcp/scan_features.py \
  --project-dir "{project_dir}" \
  --output "{project_dir}/docs/.sf/feature_list.json"
```

---

## Phase 3: 差分更新 / 変更履歴

差分更新時は手動追記を保持し、更新した設計書のみ記録する。`docs/logs/changelog.md` への追記は **sf-org-analyst Phase 7.5 で 1 セッション 1 行に集約** するためここでは行わない（F-4）。

---

## Phase 最終: クリーンアップ

[共通ルール参照](.claude/CLAUDE.md#一時ファイルの後片付け全エージェント共通)

---

## 最終報告フォーマット

```
## カテゴリ4-{種別} 完了

### 生成/更新ファイル
- docs/design/{種別}/: XX件（新規 X件 / 更新 X件）

### 主な発見・所見
（重要な設計パターン・ガバナ制限リスク・依存関係の注意点）

### セキュリティ確認
（`without sharing` 使用箇所・外部API認証情報の管理状況）

### 要確認事項（優先度順）
```
