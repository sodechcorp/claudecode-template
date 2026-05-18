# カテゴリ1 出力ファイル スキーマ定義

---

## org-profile.md

### プロジェクト基本情報テーブル（ファイル冒頭の最初の H2 として配置・必須）

下流の `generate_basic_doc.py` は表の左列キー名を一字一句で探索するため、**左列のキー名は以下の通り厳密に書くこと**:

**重要**: プロジェクト名・システム名は `sf-analyst-cat1.md` Phase 2.5 でユーザーから取得した正式名を使う。LLM が推測・自由生成することを禁止（`〜組織` `〜システム` 等の suffix を勝手に付けない）。

```markdown
## プロジェクト基本情報

| 項目 | 値 |
|---|---|
| プロジェクト名 | （Phase 2.5 で取得した正式プロジェクト名。例: MMPC顧客管理刷新プロジェクト / リンク Salesforce 保守開発） |
| システム名 | （Phase 2.5 で取得した正式システム名。例: MMPC顧客管理システム / リンク受注管理） |
| 開始日 | YYYY-MM-DD |
| 本番公開日 | YYYY-MM-DD |
| Salesforce Edition | Enterprise / Unlimited / Professional 等 |
| 対象業務 | （1行サマリ） |
```

### 含める内容

- **会社・事業概要**: 業種・主要ビジネス・顧客層（推定根拠を明記）
- **利用規模**: ユーザー数・プロファイル分布（人数付き）・組織階層
- **データ構成**: カスタムオブジェクト一覧（用途・関連標準オブジェクト付き）・Mermaid ER 図（主要関係のみ）
- **カスタマイズ構成**: Apex（クラス数・テスト有無）・Flow（タイプ別件数）・外部連携（相手先・方式）
- **セキュリティ構成**: プロファイル種別・権限セット（用途付き）
- **技術的所見**: API バージョン・技術的負債・注目点
- **ステークホルダーマップ（必須・4列固定）**: `generate_basic_doc.py` は 1列目=役割 / 2列目=氏名・組織 / 3列目=担当領域 / 4列目以降=備考 として読み取る:
  ```markdown
  ## ステークホルダーマップ
  
  | 役割 | 氏名・組織 | 担当領域 | 備考 |
  |---|---|---|---|
  | 発注者 | 〇〇株式会社 / 〇〇部 | 要件定義・意思決定 | — |
  | 開発ベンダー | 〇〇社 | 保守開発全般 | — |
  ```
- **用語集（Glossary）**: プロジェクト固有の略語・業務用語

---

## requirements.md

### 必須見出し骨格

下流パーサーが見出し名から本文を拾うため、以下のいずれかの見出しを必ず含める:

| 用途 | 必須の見出し（いずれかを含む／部分一致でヒット） | 目安の配置 |
|---|---|---|
| 導入背景 | `## 導入背景` / `## 背景・目的` / `## 背景` | 先頭近く |
| AS-IS | `## AS-IS` / `## 現状` | 背景の直後 |
| TO-BE | `## TO-BE` / `## 目指す姿` | AS-IS の直後 |
| 対象スコープ | `## 対応スコープ` / `## 対象スコープ` / `## 対象範囲` / `## 対象業務` | スコープ定義の下 |
| 対象外スコープ | `## 対象外スコープ` / `## スコープ外` / `## 非対象` | 対象スコープの直後 |

> 例: `## 6. スコープ定義` の H2 の下に `### 6-1. 対応スコープ` `### 6-2. スコープ外` と置く形式でも可（見出しに「対応スコープ」「スコープ外」が含まれていれば認識される）。

要件番号体系: `FR-001`〜（機能要件）、`NFR-001`〜（非機能要件）

---

## system.json

### フィールド定義

| フィールド | 型 | 説明 |
|---|---|---|
| `system_name` | string | システム名 |
| `core` | object | `name`（例: "Salesforce (Sales Cloud)"）, `role`（主な役割） |
| `actors` | array | `name`, `count`（人数）, `channels[]`（利用画面・経路） |
| `external_systems` | array | `name`, `direction`(in/out/both), `protocol`(REST/SOAP/Bulk/Platform Event/File), `frequency`(リアルタイム/日次/月次等), `purpose` |
| `data_stores` | array | `name`, `purpose` |
| `touchpoints` | array | `name`, `platform`(Experience Cloud/LWC/API等), `users` |
| `notes` | array | 要確認事項 |

**重要**: `system_name` は Phase 2.5 で取得した正式名と org-profile.md の「システム名」を必ず一致させる。LLM 自由生成禁止。

### サンプル

```json
{
  "system_name": "（Phase 2.5 で確定した正式システム名 例: MMPC顧客管理システム）",
  "core": { "name": "Salesforce (Sales Cloud)", "role": "受注・契約・請求の中枢" },
  "actors": [{ "name": "営業担当", "count": 30, "channels": ["Salesforce 標準UI", "LWC受注画面"] }],
  "external_systems": [{ "name": "基幹システム", "direction": "out", "protocol": "REST", "frequency": "日次", "purpose": "受注データ連携" }],
  "data_stores": [{ "name": "Salesforce (本番)", "purpose": "全トランザクションデータ" }],
  "touchpoints": [{ "name": "受注申請画面", "platform": "LWC", "users": "営業担当" }],
  "notes": ["外部連携の認証方式が未確認"]
}
```

ソース優先順位: ①既存システム構成図（画像/PPT/Visio）→最優先で読み込み再構築 ②Named Credential/Connected App/Apex HTTP呼び出し ③org-profile・要件定義書 ④不明は `notes` に記録

外部連携は**方向・方式・頻度**を必ず抽出。不明な場合は `**[要確認]**`。

---

## usecases.md

各UCに必ず含める項目（採番規則: `UC-01` 〜 `UC-99` の 2桁ゼロ埋め固定）:
- `UC-XX` 番号と UC 名（業務担当者が普段呼んでいる名前）
- **トリガー**: 誰が何をしたら発動するか（「申込フォーム送信時」「課長が承認ボタンを押した時」等）
- **主な登場人物**: 社内/社外を区別して記載（人数の目安があれば）
- **主要オブジェクト**: 作成・更新されるオブジェクト（Lead → Opportunity → Contract の流れ等）
- **承認の有無・経路**: 承認がある場合は条件・担当者・却下時の経路まで記述
- **関連する外部連携**: 連携先システム・タイミング
- **頻度**: 1日/件、月次等（概算でよい）
- **主要な例外・エラーケース**: 資料に記載がある場合は必ず含める

ソース優先順位: ①既存業務フロー図・業務マニュアル ②Flow/Approval Process の命名・説明 ③カスタムオブジェクト名・レコードタイプ・ステータス項目値 ④Apexトリガーの対象オブジェクト

---

## swimlanes.json

### スキーマ

```json
{
  "flows": [
    {
      "id": "overall",
      "flow_type": "overall | usecase | asis | exception | dataflow",
      "title": "フロータイトル",
      "description": "概要（任意）",
      "usecase_id": "UC-XX（usecase タイプの場合）",
      "parent_usecase_id": "UC-XX（exception タイプの場合）",
      "lanes": [
        { "name": "レーン名", "type": "external_actor | internal_actor | system | external_system" }
      ],
      "steps": [
        { "id": 1, "lane": "レーン名", "title": "ステップ名", "trigger": "発動タイミング", "output": "作成/更新されるレコード・状態変化" }
      ],
      "transitions": [
        { "from": 1, "to": 2, "condition": "条件（分岐の場合のみ）" }
      ]
    }
  ]
}
```

### flow_type の使い分け

| flow_type | 用途 | 必須性 |
|---|---|---|
| `overall` | プロジェクト全体の時系列俯瞰（1件） | 必須 |
| `usecase` | 各UCの詳細フロー（UCごと1件、5〜15件） | 必須（最低3件以上） |
| `asis` | SF導入前（または導入前フェーズ）の業務フロー | **必須（最低1件）** |
| `tobe` | SF導入後（現行・目指す姿）の業務フロー | **必須（最低1件）**（`asis` と対で生成） |
| `exception` | 例外・差戻し・承認却下経路 | 任意（資料に記載がある場合は必須） |
| `dataflow` | データの流れ（誰が作って誰が使うか） | 任意 |

**`asis` / `tobe` フローの生成ルール**:
- ソース: ①既存資料の旧業務フロー記述 ②`requirements.md` / `org-profile.md` の「AS-IS課題」「導入背景」「TO-BE」 ③旧システム名への言及
- レーン構成: 旧システム名（「ジーニー」「受注システム」等）、担当者を分けて表現
- 粒度: 不明な場合も推測で空白にせず、`**[推定]**` を付けて記述
- `id` は `"asis-overall"` / `"tobe-overall"` 形式を推奨
- **対の原則**: `asis` を出すなら必ず対の `tobe` も出す

### レーンの type（必須）

| type 値 | 用途 | 下流での表示グループ名 |
|---|---|---|
| `external_actor` | 社外・エンドユーザ（顧客・取引先・代理店・委託元等） | 「社外・お客様」 |
| `internal_actor` | 社内担当者（営業・CS・管理者・経理等） | 「社内担当」 |
| `system` | Salesforce 本体・Experience Cloud・自組織内システム | 「Salesforce」 |
| `external_system` | 外部連携先（Pardot・OPROARTS・基幹システム等） | 「外部システム」 |

> 固有名詞（会社名・プロジェクト名）をレーン名やグループ名に混ぜ込まないこと。下流描画ロジックは `type` のみでグループ分けする。

### 粒度のルール（最重要）

- **レーンは「システム」で省略しない**: 「Salesforce」ではなく「Salesforce (ApexTrigger)」「Salesforce (Flow: 申込確認)」のように分ける
- **操作タイミングを全ステップに明記**: 「ボタン押下時」「レコード保存時」「日次バッチ（毎朝3時）」等
- **承認経路を必ず入れる**: 申請→承認→差戻しの分岐を描く。条件（金額・役職等）も `condition` に記載
- **データ作成タイミングを入れる**: 「Contract__c を作成」「Opportunity のステータスを『受注』に更新」のように具体的に
