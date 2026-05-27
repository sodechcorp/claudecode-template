# [プロジェクト名] - プロジェクト固有ルール

> このファイルをプロジェクトフォルダの直下に「CLAUDE.md」として配置する。
> `.claude/CLAUDE.md`（共通ルール）に追加・上書きされる形で読み込まれる。
> 不要なセクションは削除してよい。共通ルールで十分なセクションは記載不要。

> このプロジェクトは [3 層メモリ設計](.claude/CLAUDE.md#メモリ設計3-層) に従う。
> - 共通ルール: `.claude/CLAUDE.md`
> - 個人プロファイル: ClaudeCode Auto Memory（設定不要・自動）
> - 案件固有メタデータ: `docs/`（`/sf-memory` で生成・全エージェントが消費）

---

## Salesforce組織情報

| 環境 | org alias | 用途 | denyパターン一致 |
|---|---|---|---|
| 開発 | `project-dev` | 開発・動作確認 | — |
| ステージング | `project-stg` | テスト・検証 | — |
| 本番 | `project-prod` | 本番（デプロイ時は必ず確認） | `*prod*` ✓ |

デフォルトorg: `project-dev`

> ⚠️ denyパターン一致が ✓ でない本番 alias を設定した場合は、`settings.json` の deny ルールにそのエイリアス名パターンを追加すること（例: alias が `gf-main` なら `*gf-main*` を追加）。

---

## 命名規則

> ※ `{PREFIX}` はプロジェクト略称のプレースホルダー。実際の略称に置き換えること（例: 営業支援なら `SFA_`、受注管理なら `OM_` 等）。

| 対象 | ルール | 例 |
|---|---|---|
| カスタムオブジェクト | `PREFIX_` プレフィックス | `{PREFIX}_Order__c` |
| カスタム項目 | `PREFIX_` プレフィックス | `{PREFIX}_Status__c` |
| Apexクラス | `PREFIX` プレフィックス | `{PREFIX}OrderService` |
| LWCコンポーネント | camelCase | `{prefix}OrderList` |
| フロー | 種別_機能名 | `Screen_OrderCreate` |
| 権限セット | `PREFIX_` プレフィックス | `{PREFIX}_SalesUser` |

---

## Salesforce 権限ポリシー

- 標準プロファイルは編集禁止。権限セットで対応する
- 標準プロファイルの変更指示を受けた場合は実行前に「標準プロファイルは編集禁止です。権限セットで対応してください」と警告する
- （プロジェクト固有の権限ルールをここに記載）

---

## 主要カスタムオブジェクト

| オブジェクト名 | API名 | 概要 |
|---|---|---|
| | | |

---

## プロジェクト資材

| 資材 | 場所 | 生成コマンド | 生成タイミング | 備考 |
|---|---|---|---|---|
| 組織プロフィール・要件定義 | `docs/overview/` `docs/requirements/` | `/sf-memory` | プロジェクト開始時・変更時 | 組織概要・用語集・AS-IS/TO-BE・要件一覧 |
| 業務フロー・ユースケース一覧 | `docs/flow/` | `/sf-memory` | プロジェクト開始時・変更時 | 業務フロー図・スイムレーン定義 |
| システム構成図データ | `docs/architecture/` | `/sf-memory` | プロジェクト開始時・変更時 | system.json |
| オブジェクト・項目定義書（Markdown） | `docs/catalog/` | `/sf-memory` | プロジェクト開始時・オブジェクト変更時 | オブジェクト・項目構成・権限。Claude記憶形成用 |
| オブジェクト・項目定義書（Excel/PowerPoint） | `docs/` 任意 | `/sf-doc` | 成果物提出・共有時 | 正式な成果物として提出・共有するための定義書 |
| 機能設計書 | `docs/design/{種別}/` | `/sf-memory` | 機能実装前 | apex/flow/batch/lwc/integration/config |
| データ統計・マスタ | `docs/data/` | `/sf-memory` | プロジェクト開始時・変更時 | マスタデータ・テンプレート・統計・品質 |
| 変更履歴 | `docs/logs/changelog.md` | 自動 | 各コマンド実行時に自動追記 | コマンド実行時に自動追記 |
| 工数ログ | `docs/logs/effort-log.md` | `/backlog` | `/backlog` 実行時に自動追記 | 見込み工数。`/backlog` 実行時に自動追記 |
| 対応履歴・判断記録 | `docs/decisions.md` | 自動 | `/backlog` 完了時に自動追記 | 保守・開発の判断根拠。`/backlog` 完了時に自動追記 |
| Salesforceメタデータ | `force-app/main/default/` | SFDX | `/sf-retrieve` 実行後（初回・定期同期） | Apexクラス・LWC・フロー等（`/sf-retrieve` 実行後に生成） |
| package.xml | `manifest/package.xml` | `/sf-retrieve` | `/sf-retrieve` 実行後 | standard / all / 個別指定の3モード |

---

## 過去の判断・決定事項

<!-- 判明した設計判断・確定事項を手動で記載する -->
<!-- 例: 2026-04-01: 受注はOpportunity流用。理由: カスタムオブジェクトはライセンス上限の懸念あり。排除案: OrderManagementカスタムは追加コストで却下 -->

---

## 注意事項・地雷

<!-- 触る前に知っておくべきこと、過去にハマったことを記載 -->
<!-- 例: 2026-04-01: AccountトリガーはOrderTriggerHandlerと競合するため、isExecuting チェックが必要 -->

---

## プロジェクト固有の品質基準

<!-- 共通ルール（.claude/CLAUDE.md）に追加・補足したい場合のみ記載 -->
<!-- このセクションに記載した基準は共通ルールの Quality Standards より優先して適用すること -->
<!-- 例: テストカバレッジ目標を95%以上とする -->
