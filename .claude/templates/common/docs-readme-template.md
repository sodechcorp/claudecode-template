# docs/_README.md テンプレート（情報所在マップ）

ClaudeCode が「どの情報がどのファイルにあるか」を判断するためのマップ。
sf-org-analyst の Phase 7.5 で生成する（cat1 完了後・横断補完時に自動生成）。

```markdown
# docs/ 情報所在マップ

このファイルは ClaudeCode が「どの情報がどのファイルにあるか」を判断するためのマップ。
質問・課題対応時はこのマップを参照して、必要なファイルだけを Read する。

| 知りたい情報 | 主ファイル | 補助ファイル |
|---|---|---|
| 組織概要・業務カレンダー・地雷・対応禁止事項 | overview/org-profile.md | — |
| 用語（ビジネス用語 ⇔ API 名） | overview/org-profile.md（## Glossary セクション） | — |
| ステークホルダー・キーパーソン・問い合わせ先 | overview/org-profile.md（## ステークホルダーマップ / ## キーパーソン一覧） | — |
| 要件・ビジネスルール（FR-XXX, BR-XXX） | requirements/requirements.md | — |
| 業務フロー・ユースケース | flow/usecases.md | flow/swimlanes.json |
| オブジェクト・項目定義 | catalog/{standard\|custom}/{オブジェクト名}.md | catalog/_index.md |
| 機能別設計書 | design/{種別}/{名前}.md | — |
| 機能一覧キャッシュ（コンポーネント一覧 JSON） | .sf/feature_list.json | — |
| 機能ID台帳（コンポーネント↔ID 対応） | .sf/feature_ids.yml | — |
| 業務機能グループ定義 | .sf/feature_groups.yml | — |
| マスタデータ・ピックリスト値 | data/master-data.md | — |
| メールテンプレート | data/email-templates.md | — |
| 自動化・承認・キュー・割り当て設定 | data/automation-config.md | — |
| レポート・ダッシュボード一覧 | data/reports-dashboards.md | — |
| データ統計（件数・分布） | data/data-statistics.md | — |
| データ品質（空欄率・重複兆候） | data/data-quality.md | — |
| 過去の判断・採用方針（why） | decisions.md | — |
| 案件履歴・症状×対策の索引 | knowledge/case-index.md | logs/{issueID}/ |
| Salesforce 標準仕様の照合表 | knowledge/sf-standard.md | — |
| プロジェクト固有のハマりポイント | knowledge/pitfalls.md | — |
| 変更履歴 | logs/changelog.md | logs/{issueID}/ |
| 工数ログ（見込み） | logs/effort-log.md | — |

---
*このファイルは sf-org-analyst により自動生成・更新される。手動追記した行は保護される（削除禁止）。*
```

**生成条件**: cat1 完了（`docs/overview/org-profile.md` 存在）後の横断補完（sf-org-analyst Phase 7.5）で生成。
**更新タイミング**: sf-memory 実行・カテゴリ追加完了後の横断補完時に内容を動的更新。未完了カテゴリのファイルは `—（未生成）` と表示。
