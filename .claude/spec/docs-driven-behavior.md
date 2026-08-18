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
6. `docs/catalog/` の該当定義書を更新（項目追加を反映）

### 「オブジェクトを作って」「カスタムオブジェクト追加して」
1. `docs/catalog/` で既存オブジェクト構成・命名規則を確認
2. `docs/overview/org-profile.md` の用語集で命名を統一
3. プロジェクトルート `CLAUDE.md` の命名規則に従う
4. メタデータファイルを作成（`force-app/main/default/objects/` 配下）
5. **権限・基本設定を設定する**: `.claude/templates/common/new-metadata-permissions-checklist.md` の「カスタムオブジェクト」セクションに従い、CRUD権限・タブ・ページレイアウト・アプリ追加を必ず実施（付与方針の詳細はchecklist参照）
6. `docs/catalog/` に新オブジェクトの定義書を作成

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

**Apex / トリガーのコーディングは `/backlog` 経由が必須**（Backlog課題を伴わないアドホック実装の対象外）。理由: `/backlog` の実装は backlog-validator（Phase 3.5）＋ blind系3種＋regression-guard の多層ゲートを通るが、メインスレッドの直接実装ではこの水準のゲートを提供できないため（[quality-gate.md](../spec/quality-gate.md) 参照）。

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
3. デプロイコマンドを提示（**本番へのデプロイは必ずユーザー確認**）
   - 本番判定の根拠（target-org の alias が `*prod*` / `*production*` に一致）は `.claude/spec/security-and-permissions.md` に記載

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
| カスタム項目の追加・変更・削除 | `docs/catalog/{standard\|custom}/{オブジェクト名}.md` | 項目一覧テーブルに反映 |
| Apex / トリガーの追加・変更 | `docs/design/apex/{クラス名}.md` | 設計書があれば更新、なければ作成を提案 |
| フローの追加・変更 | `docs/design/flow/{フロー名}.md` | 設計書があれば更新、なければ作成を提案 |
| LWCの追加・変更 | `docs/design/lwc/{コンポーネント名}.md` | 設計書があれば更新、なければ作成を提案 |
| Visualforce ページの追加・変更 | `docs/design/vf/{ページ名}.md` | 設計書があれば更新、なければ作成を提案 |
| Aura コンポーネントの追加・変更 | `docs/design/aura/{コンポーネント名}.md` | 設計書があれば更新、なければ作成を提案 |
| バッチクラスの追加・変更 | `docs/design/batch/{クラス名}.md` | 設計書があれば更新、なければ作成を提案 |
| 外部API連携クラスの追加・変更 | `docs/design/integration/{クラス名}.md` | 設計書があれば更新、なければ作成を提案 |
| 権限セット・プロファイル変更 | `docs/catalog/{standard\|custom}/{オブジェクト名}.md` | 権限マトリクスに反映 |
| 入力規則の追加・変更 | `docs/catalog/{standard\|custom}/{オブジェクト名}.md` | 自動化・ビジネスルールセクションに反映 |
| レイアウト変更 | — | ドキュメント更新不要 |
