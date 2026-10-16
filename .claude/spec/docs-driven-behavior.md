# 開発タスク — 指示パターン別の詳細手順

> 概要ルール（作業前参照・実装後更新・判断記録）は `.claude/CLAUDE.md` の「開発タスク着手時の docs/ 参照」セクションに記載。本ファイルは指示パターン別の詳細手順のみ。

---

## 指示パターン別の動き方

### 「項目を作って」「項目追加して」
1. `docs/catalog/` で対象オブジェクトの既存構成を確認
2. `docs/overview/org-profile.md` の用語集で命名を統一
3. プロジェクトルート `CLAUDE.md` の命名規則に従う
4. メタデータファイルを作成（force-app 配下）
5. **権限・基本設定を設定する**: `.claude/templates/common/new-metadata-permissions-checklist.md` の「カスタム項目」セクションに従い、FLS・ページレイアウト配置を必ず実施（付与方針の詳細はchecklist参照）。チェック漏れを黙殺しない
6. `docs/catalog/` の該当定義書があれば下記「実装後のドキュメント更新マッピング」に従って更新。無ければ作らず、デプロイ後の `/sf-memory` カテゴリ2（対象オブジェクト: {API名}）を案内する

### 「オブジェクトを作って」「カスタムオブジェクト追加して」
1. `docs/catalog/` で既存オブジェクト構成・命名規則を確認
2. `docs/overview/org-profile.md` の用語集で命名を統一
3. プロジェクトルート `CLAUDE.md` の命名規則に従う
4. メタデータファイルを作成（`force-app/main/default/objects/` 配下）
5. **権限・基本設定を設定する**: `.claude/templates/common/new-metadata-permissions-checklist.md` の「カスタムオブジェクト」セクションに従い、CRUD権限・タブ・ページレイアウト・アプリ追加を必ず実施（付与方針の詳細はchecklist参照）
6. 定義書は作らず、デプロイ後の `/sf-memory` カテゴリ2（対象オブジェクト: {API名}）を案内する

### 「レコードタイプを作って」
1. 対象オブジェクトの既存レコードタイプ構成（`force-app/` の `recordType-meta.xml`）を確認
2. 要件（ピックリスト制限・レイアウト分岐・対象ユーザー）を確認
3. メタデータファイルを作成
4. **権限・基本設定を設定する**: `.claude/templates/common/new-metadata-permissions-checklist.md` の「レコードタイプ」セクションに従い、プロファイル割当・レイアウト割当・ピックリスト値割当を必ず実施（付与方針の詳細はchecklist参照）

### 「タブを作って」
1. 対象オブジェクト・Webタブ・VFページ等の種別を確認
2. メタデータファイルを作成（`force-app/main/default/tabs/` 配下）
3. **権限・基本設定を設定する**: `.claude/templates/common/new-metadata-permissions-checklist.md` の「タブ」セクションに従い、タブ表示設定・アプリへの追加を必ず実施（付与方針の詳細はchecklist参照）

### 「Apex 作って」「トリガー書いて」

**Apex / トリガーのコーディングは `/backlog` 経由が必須**（Backlog課題を伴わないアドホック実装の対象外）。理由: `/backlog` の実装は backlog-validator（Phase 3.5）＋regression-guard の多層ゲートを通るが、メインスレッドの直接実装ではこの水準のゲートを提供できないため（[quality-gate.md](../spec/quality-gate.md) 参照）。

1. Backlog課題が未作成の場合: 「Apex / トリガーの実装は `/backlog` 経由が必要です。Backlog課題を作成のうえ `/backlog {issueID}` で対応してください」と案内する（ここでは実装しない）
2. Backlog課題が既にある場合: `/backlog {issueID}` の実行を案内する

### 「フロー作って」

**ロジックを持つフローのコーディングは `/backlog` 経由が必須**（理由は「Apex 作って」と同様）。

1. Backlog課題が未作成の場合: 「フローの実装は `/backlog` 経由が必要です。Backlog課題を作成のうえ `/backlog {issueID}` で対応してください」と案内する（ここでは実装しない）
2. Backlog課題が既にある場合: `/backlog {issueID}` の実行を案内する

### 「バグ直して」「エラー出る」
1. エラー内容を確認
2. `docs/catalog/` で関連オブジェクト・項目を把握
3. `docs/design/` で該当機能の設計意図を確認
4. `docs/requirements/requirements.md` で関連ビジネスルールを確認（仕様なのかバグなのか判断）
5. **修正手段を判定する**:
   - 原因が Apex / LWC / Flow / トリガー / バッチのコード変更を要する場合: 「原因はコード側（{該当箇所}）にあり、修正には `/backlog` 経由が必要です。Backlog課題を作成のうえ `/backlog {issueID}` で対応してください」と案内し、ここでは実装しない
   - 原因が宣言的な設定（入力規則の文言・ピックリスト値・レイアウト・FLS等）の場合: そのまま修正実施

### 「デプロイして」
1. `docs/logs/changelog.md` で最近の変更を確認
2. 対象のメタデータを確認
3. デプロイコマンドを提示（**本番〔`sf org display` で `isSandbox: false`〕へは Claude はデプロイしない。本番リリースは `/release` の手順で担当者が実行する**）
   - alias の `*prod*` / `*production*` 一致（`.claude/spec/security-and-permissions.md`）と `.prod-aliases`（ルート `CLAUDE.md` の組織情報）は hook の補助判定

### スコープ外の依頼
`docs/requirements/requirements.md` のスコープ定義と合致しない場合:
1. 作業を始める前に「この依頼は現在のスコープ定義に含まれていない可能性があります」と伝える
2. 該当するスコープ定義を引用して提示する
3. 以下の選択肢を提示する:
   - a. スコープに追加して進める（要件定義書を更新します）
   - b. スコープ外として対応しない
   - c. スコープを確認してから判断する
4. ユーザーの判断を待ってから動く。勝手に進めない

requirements.md にスコープ定義がない場合はこのチェックをスキップして作業する。

---

## 実装後のドキュメント更新マッピング

| 実装内容 | 更新対象 | 更新方法 |
|---|---|---|
| カスタム項目の追加・変更・削除 | `docs/catalog/{standard\|custom}/{オブジェクト名}.md` | 「全項目一覧」（選択リストの値は「ピックリスト値」）に反映。参照・主従関係の項目は、このオブジェクトと参照先の定義書の「リレーション」と `docs/catalog/_data-model.md` にも反映（記法は `.claude/templates/sf-analyst-cat2/object-definition-template.md`「Mermaid ERD 記法の規約」） |
| 選択リスト値セット（標準・グローバル）の変更 | その値セットを使う項目のオブジェクトの `docs/catalog/{standard\|custom}/{オブジェクト名}.md` | 「ピックリスト値」に反映 |
| Apex / トリガー・フロー・LWC・Visualforce・Aura・バッチ・外部API連携クラスの追加・変更 | 機能別設計書（下記の取り方） | 設計書があれば更新。無ければ作らず、`/sf-memory` カテゴリ4（台帳の機能IDで作る）を案内する（`/backlog` は Phase 6 のドキュメント更新通知） |
| 権限セット・プロファイルのオブジェクト権限・項目権限（CRUD・FLS）の変更 | `docs/catalog/{standard\|custom}/{オブジェクト名}.md` | 「権限マトリクス」に反映 |
| レコードタイプの追加・変更 | `docs/catalog/{standard\|custom}/{オブジェクト名}.md` | 「レコードタイプ」に反映 |
| 入力規則の追加・変更 | `docs/catalog/{standard\|custom}/{オブジェクト名}.md` | 「入力規則」に反映 |
| レイアウト変更、権限セット・プロファイルのそれ以外の変更（タブ表示・レイアウトとレコードタイプの割当・Apex クラス／Visualforce ページのアクセス等） | — | ドキュメント更新不要 |

**機能別設計書の取り方**: `docs/.sf/feature_list.json` を API 名で引いたエントリ（同じ API 名が複数あれば種別 `type` の合うもの）の `design_doc`。`design_doc` が無く `absorb_into` があれば、吸収先（`absorb_into` の API 名で引いたエントリ）の `design_doc`。パスは `design_doc` の `docs/design/` 以降（絶対パスでも同じ）を、この案件のルートからのパスとして使う。エントリ・`design_doc` が無ければ設計書なし。そのパスにファイルが無いか、ファイル名の【】に `design_doc` を取ったエントリ（吸収先から取ったときは吸収先）の `id` が無いとき（旧番号・同名の別コンポーネントの設計書のことがある）は、同じフォルダで先頭の【】（重ねたものは全部）の後ろが同じで、【】にその `id` があるファイルを使い、無ければ設計書なし。
