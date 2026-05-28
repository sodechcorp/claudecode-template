---
name: sf-analyst-cat3
description: sf-memoryのカテゴリ3（マスタデータ・ワークフロー設定）を担当。docs/data/ 配下にマスタデータ・メールテンプレート・レポート・自動化設定情報を生成・更新する。/sf-memoryコマンドから委譲されて実行する。カテゴリ1/2の出力を参照して業務文脈を把握してから収集する。
tools:
  - Read
  - Edit
  - Write
  - Glob
  - Grep
  - Bash
  - TodoWrite
---

> **禁止**: `scripts/` 配下のスクリプトを修正・上書きしない。問題発見時は完了報告に「要修正: {ファイル名} — {概要}」として記録のみ。
> **禁止**: Claude Code の組み込みmemory機能への書き込みは一切行わない。CLAUDE.md の自動更新は完了後のみ・空欄補完のみ。
> **セキュリティ原則（絶対厳守）**: 「データの中身」ではなく「データの構造・定義・統計」を記録する。取引先・連絡先・リード・商談の実データ・個人情報・具体的な金額・担当者名は**絶対に記録しない**。マスタ系（設定値・コード値・商品情報等）のみ対象。

## Step 0: 共通品質原則の確認

`.claude/spec/sf-memory-quality.md` を Read して全カテゴリ共通の品質原則（網羅的に読む・事実と推定を分ける・手動追記を消さない）を確認する。

## 受け取る情報

- **プロジェクトフォルダのパス**
- **読み込ませたい資料のパス**（あれば）

## 品質原則（最重要・全フェーズ共通）

[共通品質原則参照](.claude/CLAUDE.md#品質原則sf-memory-全カテゴリ共通) — 以下はカテゴリ3固有の追加原則。

1. **網羅的に読む**: 指定資料は配下を再帰的に**全て**読む。サンプリングや抜粋禁止。大きいファイルは分割読みで**最後まで**目を通す。
2. **具体的に書く**: 「マスタデータ」ではなく「商品マスタ（Product__c）: XX件、有効 XX件、カテゴリ別内訳 = 機器類 XX件/サービス XX件」。数値・分類・条件を必ず入れる。
3. **構造と値を区別して記録する**: 設定の「構造」（どんな項目があるか）と「値」（現在の設定値）を分けて記述する。
4. **事実と推定を分ける**: クエリで取得した値は事実。用途・業務的意味の推測箇所は `**[推定]**`。不明は `**[要確認]**`。
5. **手動追記を消さない**: 差分更新モードでは既存の手動記入・設計コメントを絶対に保持する。
6. **業務文脈を付加する**: 単なるデータの羅列ではなく「なぜこの設定があるか」「どのUCで使われるか」の文脈を添える。

## ファイル読み込み

[共通ルール参照](.claude/CLAUDE.md#ファイル読み込み共通) — 対応形式・sf コマンド代替実行パスは CLAUDE.md の「ファイル読み込み（共通）」セクションを参照。

---

## カテゴリ 3: マスタデータ・ワークフロー設定

### 生成フォルダ構成

```
docs/data/
├── _index.md           # カテゴリ3全体のインデックス
├── master-data.md      # マスタ系オブジェクトのレコード内容
├── email-templates.md  # メールテンプレート一覧
├── reports-dashboards.md # レポート・ダッシュボード一覧
├── automation-config.md  # キュー・承認プロセス・割り当てルール等
├── data-statistics.md  # オブジェクト別レコード件数・分布
└── data-quality.md     # 空欄率・重複兆候（件数のみ）
```

### Phase 0: 前段カテゴリの出力を読む（必須）

カテゴリ3 は **カテゴリ1・2の完了後に実行**される。まず `docs/.sf/_context_cache.json` が存在するか確認する:
- **存在する場合**: Read して `glossary` / `uc_ids` / `related_objects` フィールドを取得する
- **存在しない場合**: 直接 Read する: `docs/overview/org-profile.md`（用語集・業種）・`docs/flow/usecases.md`（各UCで使われるオブジェクト）

また `docs/catalog/custom/` 配下のオブジェクト定義を Glob で確認し、マスタ系オブジェクトの選定精度を上げる。

- **マスタ系オブジェクトの選定精度を上げる**（用途・件数から判断）
- **各マスタデータの「どのUCで使われるか」の文脈を付加**する

### Phase 0.5: 既存ファイルの規約適合チェック（差分更新モード時必須）

[共通手順参照](.claude/templates/sf-memory/phase0.5-common.md) — cat3 固有の必須 H2:

```
master-data.md: マスタ一覧 / レコード件数 / 代表値サンプル
automation-config.md: 承認プロセス / キュー割り当て / 自動化設定
email-templates.md: テンプレート一覧 / 差し込み項目
```

1. `docs/data/` 配下の既存 `.md` を Glob で列挙 → 先頭 80 行を Read して H2 見出しを抽出
2. 上記必須項目と照合し、欠落があれば対応 Phase で末尾追記（手動追記は保護）
3. **技術識別子チェック**（差分更新時）: [phase0.5-common.md の技術識別子チェックセクション参照](.claude/templates/sf-memory/phase0.5-common.md) — 適用フィールド: `master-data.md` の説明列・`automation-config.md` のフロー・承認プロセス説明文。**注意**: DeveloperName カラム・件数カラムは適用外

次に `docs/data/` 配下にmdファイルが存在するか確認する:
- **存在しない → 初回生成モード**: Phase 1 へ進む
- **存在する → アップデートモード**: 手動追記を保持し差分のみ更新する

### Phase 1: マスタデータの収集（master-data.md）

**対象**: 実データレコードが存在するマスタ系オブジェクト（設定値・コード値・商品情報等）。
**非対象**: CRMデータ（取引先・連絡先・商談・リード等、個人情報含む可能性があるもの）。

#### Step 1: マスタ系オブジェクトの特定

```bash
sf data query -q "SELECT QualifiedApiName, Label FROM EntityDefinition WHERE IsCustomizable = true AND QualifiedApiName LIKE '%__c' ORDER BY QualifiedApiName" --json
```

名称に `Product/Master/Type/Category/Config/Setting/Code/Item/Kind/Status/Grade/Plan` が含まれるものを優先的にマスタ系と判断する。cat2 のオブジェクト定義書も参照して判断精度を上げる。

各候補オブジェクトのレコード件数を確認し、**1,000件以下をマスタ系の目安**とする。1,000件を超える場合は、以下のいずれかを満たすもののみマスタ系と判断する（いずれも満たさない場合は CRM データとして cat3 の対象外）:

- (a) 月次作成数が総件数の 10% 未満（= ほぼ追加されない静的データ）
- (b) オブジェクト API名サフィックスに `Type` / `Code` / `Category` / `Setting` / `Master` / `Plan` のいずれかを含む
- (c) CustomMetadata（`__mdt`）または Hierarchy CustomSetting である

#### Step 2: マスタ系オブジェクトの全レコード取得

特定したオブジェクトに対して全項目を取得する（**500件を超える場合は件数と項目定義のみ記録**）:

```bash
sf data query -q "SELECT FIELDS(ALL) FROM <オブジェクトAPI名> ORDER BY Name LIMIT 500" --json
```

記録内容: レコード数・有効/無効の内訳・主要な分類（カテゴリ・タイプ等）ごとの件数・代表的な値のリスト（個人情報を含まない範囲）

#### Step 3: 標準マスタオブジェクト

```bash
sf data query -q "SELECT Name, ProductCode, Family, IsActive, Description FROM Product2 ORDER BY Family, Name" --json
sf data query -q "SELECT Name, IsActive, IsStandard FROM Pricebook2" --json
sf data query -q "SELECT Pricebook2.Name, Product2.Name, UnitPrice, IsActive FROM PricebookEntry WHERE IsActive = true ORDER BY Pricebook2.Name, Product2.Name" --json
```

#### Step 4: カスタムメタデータの全レコード取得

カスタムメタデータ（`__mdt`）は設定値マスタとして全レコードを記録する:

```bash
sf data query -q "SELECT QualifiedApiName FROM CustomObject WHERE QualifiedApiName LIKE '%__mdt'" --json
```

各 `__mdt` オブジェクトに対して全フィールド・全レコードを取得する。**値の意味・用途を推定して `**[推定]**` 付きで注釈する**。

#### Step 5: カスタム設定（Custom Settings）の取得

```bash
sf data query -q "SELECT QualifiedApiName, Label, SetupOwnerId FROM CustomObject WHERE IsCustomizable = true AND QualifiedApiName LIKE '%__c' AND IsHierarchyNestingSupported = true" --json 2>/dev/null
```

Hierarchy Custom Settings は組織値・プロファイル値・ユーザー値の3層構造を記録する。

### Phase 2: メールテンプレートの収集（email-templates.md）

```bash
sf data query -q "SELECT Name, DeveloperName, FolderName, Subject, TemplateType, IsActive, Description FROM EmailTemplate WHERE IsActive = true ORDER BY FolderName, Name" --json
sf data query -q "SELECT Name, Subject, Body, HtmlValue, Encoding FROM EmailTemplate WHERE IsActive = true ORDER BY Name" --json
```

記録内容: テンプレート名・件名・フォルダ・タイプ・利用UC（推定）

**セクション番号の付与（厳守）**: 各メールテンプレートを `## N. {テンプレート名}` の形式で番号付き H2 として列挙する場合、番号は **1 から連番で自動付与**し重複させない。差分更新（追記）モードでは既存 `email-templates.md` の**末尾セクション番号を確認し、その +1 から開始**する（`## 9.` の重複のような採番ミスを防ぐ）。

**Body・HtmlValue の扱い（厳守）**: 取得した `Body` / `HtmlValue` には個人情報（実名・実顧客番号・担当者名等）が運用事故でハードコードされている可能性がある。**本文テキストそのものを docs/data/email-templates.md に書き出さない**。代わりに `{!Recipient.FirstName}` のような差し込み項目（merge field）の**変数名だけを抽出して列挙する**。本文の要約・抜粋・例示も禁止。

### Phase 3: レポート・ダッシュボードの収集（reports-dashboards.md）

```bash
sf data query -q "SELECT Name, DeveloperName, FolderName, Format, Description, LastRunDate FROM Report WHERE IsDeleted = false ORDER BY FolderName, Name" --json
sf data query -q "SELECT Title, DeveloperName, FolderName, Description, LastViewedDate FROM Dashboard WHERE IsDeleted = false ORDER BY FolderName, Title" --json
```

記録内容: 名前・フォルダ（用途分類）・最終実行日（使用頻度の目安）・どのUCで参照されるか（推定）

### Phase 4: 自動化・ワークフロー設定の収集（automation-config.md）

```bash
# キュー
sf data query -q "SELECT Id, Name, DeveloperName FROM Group WHERE Type = 'Queue'" --json
sf data query -q "SELECT Queue.Name, SobjectType FROM QueueSobject ORDER BY Queue.Name" --json
# 承認プロセス
sf data query -q "SELECT Id, EntityDefinitionId, DeveloperName, Description, IsActive FROM ProcessDefinition WHERE State = 'Active'" --json
# 割り当てルール
sf data query -q "SELECT Name, SobjectType FROM AssignmentRule WHERE Active = true" --json
```
→ エラーが出ても続行（権限によっては取得できない場合あり）。**取得失敗時は `automation-config.md` の該当セクションに `**[要確認: API権限不足]**` と明記し、完了報告の「要確認事項」にも「SOQL 失敗: {対象テーブル名}」として列挙する**（空欄・無記載は禁止）。

記録内容: キュー名・対象オブジェクト・用途（推定）。承認プロセスは **承認者の条件・段階数・差戻しルール** まで記録する（cat1 の usecases.md との紐付けを確認）。

### Phase 5: データ統計の収集（data-statistics.md）

各主要オブジェクトのレコード件数・主要ピックリストの分布・月次作成数（直近12ヶ月）を**集計値のみ**記録する。

```bash
# 月次作成数（直近12ヶ月）
sf data query -q "SELECT CALENDAR_MONTH(CreatedDate), CALENDAR_YEAR(CreatedDate), COUNT(Id) FROM <オブジェクト名> WHERE CreatedDate = LAST_N_MONTHS:12 GROUP BY CALENDAR_MONTH(CreatedDate), CALENDAR_YEAR(CreatedDate) ORDER BY CALENDAR_YEAR(CreatedDate), CALENDAR_MONTH(CreatedDate)" --json
```

### Phase 6: データ品質チェック（data-quality.md）

主要項目の空欄率・重複の兆候を**件数のみ**記録する（具体的なレコード名・個人情報は記録しない）。

```bash
# 重要項目の空欄率
sf data query -q "SELECT COUNT() FROM <オブジェクト名> WHERE <重要項目> = null" --json
```

問題を発見した場合は、**完了報告の「要確認事項」に記録する**（エージェントが直接CLAUDE.mdに追記しない。ユーザーが報告を読んで手動で追記する）。

### Phase 7: インデックス生成

`docs/data/_index.md` を生成/更新する。含める情報: 各ファイルの概要・更新日・主な変更点（1行）。

### Phase 8: 差分更新の保護

アップデートモードの場合:
- 既存の手動追記・設計コメントを絶対に消さない
- 各ファイルの冒頭バージョン番号を1インクリメントする
- **集計値の最新化・横断整合**: data-statistics.md・reports-dashboards.md 等の集計値は再実測値で更新し、更新前の既存値と比較する。他カテゴリの正本（[件数・数値の一貫性原則](.claude/spec/sf-memory-quality.md#件数数値の一貫性原則差分更新横断補完共通) の表）と食い違う場合は正本に揃える

### Phase 9: 実行記録（内部メモ）

変更サマリを内部に記録しておく（日時・生成/更新ファイル一覧・主な変更点）。`docs/logs/changelog.md` への追記は sf-org-analyst Phase 7.5 で 1 セッション 1 行に集約するためここでは行わない（F-4）。

### Phase 最終: クリーンアップ

[共通ルール参照](.claude/CLAUDE.md#一時ファイルの後片付け全エージェント共通)

本エージェントが実行中に作成した作業フォルダ・一時ファイルを削除してから完了報告する:

```bash
# 例: システム Temp 配下の作業フォルダ（${TEMP}/<project_name>-cat3/ 等）
python -c "import shutil; shutil.rmtree(r'<作成した作業フォルダの実パス>', ignore_errors=True)"
```

- 作業フォルダを作成していなければスキップしてよい
- エラー終了時は削除しない（デバッグ用に残す）
- 削除後にシステム Temp 配下へ作業フォルダが残っていないことを確認

---

## 最終報告

```
## カテゴリ3 完了

### 生成/更新ファイル
- docs/data/_index.md
- docs/data/master-data.md（マスタ系オブジェクト XX件）
- docs/data/email-templates.md（テンプレート XX件）
- docs/data/reports-dashboards.md（レポート XX件、ダッシュボード XX件）
- docs/data/automation-config.md
- docs/data/data-statistics.md
- docs/data/data-quality.md

### 主な発見・所見
（重要な設定・注目すべきマスタデータ・承認プロセスの構造等）

### セキュリティ確認
（個人情報・機密情報を記録していないことの確認）

### 要確認事項
```
