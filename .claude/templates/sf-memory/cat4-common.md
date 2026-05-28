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
2. **関連付けを明記する（1周目で確定）**: 要件番号（FR-XXX）・ユースケースID（UC-XX）・担当オブジェクト・呼び出し元コンポーネントを Phase 0.5 で読み込んだ usecases.md / requirements.md と突き合わせて確定する。**FR 番号の確定ルール（厳守）**: `docs/requirements/requirements.md` 本文の FR 見出し（`FR-xxx: タイトル`）と設計書の機能を**意味照合**して特定する。UC 番号からの算術推測（例: UC-20 → FR-020）は禁止。確証ある一致がなければ `**[要確認: 要件番号未特定]**`、requirements.md に該当 FR が存在しない場合は `**[要確認: requirements.md に該当FRなし]**` とする（推測値を確定番号として書かない）。
3. **未実装を明示する**: ソースが存在しない場合は骨格を生成し全セクションに `**[未実装]**` を付ける。
4. **API バージョンは確定値で記録する**: 設計書「基本情報」の `| バージョン |` 行は、コンポーネントの `*-meta.xml`（Apex: `{Name}.cls-meta.xml` / Flow: `*.flow-meta.xml` / LWC: `*.js-meta.xml`）の `<apiVersion>` タグを確定値として記載する（例: `API 62.0`）。`<apiVersion>` が取得できた場合は `**[要確認]**` を付けない。`*-meta.xml` が存在しない（未実装スケルトン）場合のみ `**[未実装]**` とする。Phase 1 で各コンポーネントのメタファイルを読み込む際に、`<apiVersion>` の値を必ず抽出して設計書に反映させること。

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
  > **注意**: `_context_cache.json` の `fr_ids` は FR 番号のみ（タイトルなし）。要件番号を確定する際は必ず `docs/requirements/requirements.md` 本文を Read し FR 見出し（`FR-xxx: タイトル`）で意味照合すること。キャッシュの番号リストだけで確定しない。
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

**アップデートモード時の技術識別子チェック**: [phase0.5-common.md 参照](.claude/templates/sf-memory/phase0.5-common.md) — 適用フィールド: 各設計書の **responsibility（責務）/ 概要 / 注意点・備考 の自然文セクション**。Mermaid コードブロック内の `Apex: ClassName` も対象（業務語または `**[要確認: 業務語へ変換要]**` へ）。担当オブジェクト列（API 名を記録する目的）は適用外。

---

## Phase 1.5 前提: 全件反復処理の明示

受け取った対象 API 名リスト（Phase 1 で取得した N 件すべて）に対し、**1 件ずつ順次** Phase 1.5（ハッシュチェック）→ Phase 2（設計書生成）→ ハッシュキャッシュ更新を実行する。

- **コンテキスト枯渇時の挙動**: 途中停止して「完了」と宣言してはならない。1 件処理完了ごとにハッシュキャッシュへ書き込めば、次のイテレーションで未処理分から再開可能
- **進捗報告**: 概ね 10 件処理ごとに `処理済 X/N 件` を 1 行報告する
- **完了条件**: Phase 3.5 の `verify_cat4_completeness.py` が exit 0 を返した場合のみ「完了」を宣言する。exit 非 0 の場合は missing 一覧から未処理 API 名を抽出して Phase 1.5/Phase 2 を再実行する

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
if not src_paths or not any(pathlib.Path(p).exists() for p in src_paths):
    print('UPDATE:NEW')
else:
    h = hashlib.md5()
    for p in sorted(src_paths):
        path = pathlib.Path(p)
        if path.exists():
            h.update(path.read_bytes())
    current_hash = h.hexdigest()
    print('SKIP' if cache.get(api_name) == current_hash else f'UPDATE:{current_hash}')
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

## Phase 2.0: deprecated 設計書のクリーンアップ（アップデートモード時のみ）

Phase 0 の `scan_features.py` 実行で `feature_ids.yml` に `deprecated=true` が立った機能（過去分含む）の設計書 MD に対し、deprecated バナー注記と「実装状態」セルの `**[廃止]**` 化を一括適用する。

> 初回生成モード時は対象設計書が存在しないためスキップ。

```bash
python {project_dir}/scripts/python/sf-doc-mcp/mark_design_deprecated.py \
  --project-dir "{project_dir}"
```

- 設計書ファイルは **削除しない**（手動追記・設計判断の根拠を保持）
- バナーは冪等マーカー付き（再実行しても差分なし）
- stdout の最終 1 行 `[mark_design_deprecated] deprecated=N updated=M ...` を最終報告に転記する

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

## Phase 3.5: 完了性検証（必須）

Phase 2 の反復完了後、`_metadata_cache.json` の対象種別件数と生成済み設計書件数を突合する。

```bash
python {project_dir}/scripts/python/sf-doc-mcp/verify_cat4_completeness.py \
  --project-dir "{project_dir}" \
  --kind {flow|apex|lwc}
```

- stdout 最終 1 行: `[verify_cat4] kind=K expected=N generated=M missing=Z deprecated=D`
- exit 0（missing == 0）: 全件完了。最終報告へ進む
- exit 1（missing > 0）: stderr の missing 一覧から未処理 API 名を確認し、そのコンポーネントのみを対象に Phase 1.5/Phase 2 を再実行してから再度 verify を呼ぶ（「完了」を宣言してはならない）
- 最終報告の「### 生成/更新ファイル」配下に集計行を転記する

---

## Phase 最終: クリーンアップ

[共通ルール参照](.claude/CLAUDE.md#一時ファイルの後片付け全エージェント共通)

---

## 最終報告フォーマット

```
## カテゴリ4-{種別} 完了

### 生成/更新ファイル
- docs/design/{種別}/: XX件（新規 X件 / 更新 X件）
- 廃止注記更新: XX件（mark_design_deprecated.py の `updated=` を転記）
- **件数突合**: expected=N / generated=M / missing=Z（verify_cat4_completeness.py の最終行を転記。missing > 0 の場合は未完了として処理継続）

### 主な発見・所見
（重要な設計パターン・ガバナ制限リスク・依存関係の注意点）

### セキュリティ確認
（`without sharing` 使用箇所・外部API認証情報の管理状況）

### 要確認事項（優先度順）
```
