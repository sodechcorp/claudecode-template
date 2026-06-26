# プロジェクト資材（フォルダ構成・生成コマンド）

| フォルダ | 内容 | 生成コマンド |
|---|---|---|
| `docs/overview/` | 組織概要・用語集・ステークホルダー | `/sf-memory` |
| `docs/requirements/` | 要件定義書・ビジネスルール | `/sf-memory` |
| `docs/flow/` | 業務フロー・ユースケース一覧・スイムレーン定義 | `/sf-memory` |
| `docs/architecture/` | システム構成図用データ（system.json） | `/sf-memory` |
| `docs/design/{種別}/` | 機能別設計書（apex/flow/batch/lwc/vf/aura/integration） | `/sf-memory` |
| `docs/catalog/` | オブジェクト・項目定義書（Markdown・Claude記憶形成用） | `/sf-memory` |
| `docs/data/` | マスタデータ・テンプレート・統計・品質 | `/sf-memory` |
| `docs/logs/changelog.md` | 変更履歴 | 実装後に手動追記（/backlog は読み取りのみ）・/sf-memory Phase5 で自動追記 |
| `docs/knowledge/effort-calibration.md` | 工数温度感（Backlog実績から生成） | `/sf-memory`（Q2でcat6選択） |
| `docs/decisions.md` | 対応履歴・判断記録 | `/backlog`（Phase5未到達時）または開発タスク経由で追記 |
| `docs/knowledge/sf-standard.md` | Salesforce 標準仕様（ガバナ制限・API制限・トリガ順序等） | `/sf-memory`（Q3でcat8選択） |
| `docs/knowledge/case-index.md` | 過去不具合・対応実績のインデックス | `/sf-memory`（Q2でcat6選択） |
| `docs/knowledge/pitfalls.md` | ハマりポイント（Backlog実績から生成） | `/sf-memory`（Q2でcat6選択） |
| `force-app/main/default/` | Salesforceメタデータ（初回は `sf project retrieve` 実行後に生成） | SFDX |
| `manifest/` | package.xml（`/sf-retrieve` 実行後に生成） | `/sf-retrieve` |
