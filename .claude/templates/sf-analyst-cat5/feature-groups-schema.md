# カテゴリ5 feature_groups.yml スキーマ定義

---

## docs/.sf/feature_groups.yml のスキーマ

```yaml
# docs/.sf/feature_groups.yml
# sf-memoryカテゴリ5が生成。sf-design[詳細設計]の生成単位。
# 手動追記・修正可（次回実行時に保持される）
generated_at: "YYYY-MM-DD"    # 実行日のみ（YYYY-MM-DD）。メモ・経緯・改行は絶対に書かない
groups:
  - group_id: "FG-001"            # FG-001〜 で採番
    name_ja: "商談受注後処理"       # 業務担当者が呼ぶ名前（Apex命名でなく業務名）
    name_en: "OpportunityPostProcess"
    description: "受注確定後に請求レコードと納品スケジュールを自動生成する処理群"
    trigger: "Opportunity.StageName が '受注確定' に更新されたとき（トリガー起動）"
    uc_id: "UC-03"                  # 紐付くUCのID（usecases.md の uc_id）
    feature_ids:                   # docs/.sf/feature_ids.yml の F-xxx（例: F-001）。存在する場合は必ず参照
      - "F-001"
      - "F-002"
    components:                    # このFGに属するコンポーネントのAPI名
      - "OpportunityTrigger"
      - "OpportunityHandler"
      - "BillingCreator"
    related_objects:
      - "Opportunity"
      - "Billing__c"
    related_fgs:                   # 処理が一部またがるFGのID（存在する場合）
      - "FG-002"
  - group_id: "FG-CMN"            # 共通FG固定ID。UCに対応付けられないコンポーネントを格納
    name_ja: "共通基盤"
    name_en: "Common"
    description: "特定のUCに紐付かない汎用ユーティリティ・バッチ基盤・認証・通知等の処理群"
    trigger: "各UCから呼び出し or スケジュール起動"
    uc_id: null
    feature_ids: []
    components: []
    related_objects: []
```

---

## フィールド一覧

| フィールド | 型 | 説明 |
|---|---|---|
| `generated_at` | string | 実行日（`^\d{4}-\d{2}-\d{2}$` のみ）。修正経緯・メモ・改行は**絶対に書かない** |
| `groups` | array | FGのリスト |
| `group_id` | string | `FG-001`〜 で採番。共通基盤は `FG-CMN` 固定 |
| `name_ja` | string | 業務担当者が呼ぶ名前。Apex命名ではなく業務名 |
| `name_en` | string | 英語名（PascalCase推奨） |
| `description` | string | 「何をどのタイミングでなぜ行うか」を1〜2文で |
| `trigger` | string | UC起動条件（いつ・誰が・何をきっかけに） |
| `uc_id` | string or null | 対応UCのID（`usecases.md` の `uc_id`）。共通基盤は null |
| `feature_ids` | array | `feature_ids.yml` の F-xxx IDリスト |
| `components` | array | このFGに属するコンポーネントのAPI名リスト |
| `related_objects` | array | 関連するSalesforceオブジェクトのAPI名リスト |
| `related_fgs` | array | 処理が一部またがる他FGのIDリスト |

---

## generated_at の書式（厳守）

- **書く内容**: 本セッションの実行日のみ。例: `"2026-05-28"`
- **書式**: ISO 8601 日付。`^\d{4}-\d{2}-\d{2}$` に完全一致する 10 文字の文字列
- **禁止**: 修正経緯・運用メモ・補足・改行を一切含めない
- **修正経緯の置き場所**: `docs/logs/changelog.md`（sf-org-analyst Phase 7.5 が 1 セッション 1 行に集約する）
- **差分更新時の例外**: 既存の `generated_at` が上記書式に一致しない場合（汚染済み）は、「手動追記を消さない」原則の例外として実行日で上書きしてよい

---

## 採番規則

- 通常グループ: `FG-001` 〜 `FG-999`（3桁ゼロ埋め）
- 共通基盤: `FG-CMN`（固定値）
- 共通基盤10件超の場合: `FG-CMN-通知`・`FG-CMN-バッチ基盤` 等に分割（`FG-CMN-*` 形式）
- 目安: 1プロジェクトあたり UC数 ± 3 FG（共通系含む）
