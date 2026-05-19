# カテゴリ5 feature_groups.yml スキーマ定義

---

## docs/.sf/feature_groups.yml のスキーマ

```yaml
# docs/.sf/feature_groups.yml
# sf-memoryカテゴリ5が生成。sf-design[詳細設計]の生成単位。
# 手動追記・修正可（次回実行時に保持される）
generated_at: "YYYY-MM-DD"
groups:
  - group_id: "FG-001"            # FG-001〜 で採番
    name_ja: "商談受注後処理"       # 業務担当者が呼ぶ名前（Apex命名でなく業務名）
    name_en: "OpportunityPostProcess"
    description: "受注確定後に請求レコードと納品スケジュールを自動生成する処理群"
    trigger: "Opportunity.StageName が '受注確定' に更新されたとき（トリガー起動）"
    uc_id: "UC-03"                  # 紐付くUCのID（usecases.md の uc_id）
    feature_ids:                   # docs/.sf/feature_ids.yml の CMP-xxx。存在する場合は必ず参照
      - "CMP-001"
      - "CMP-002"
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
| `generated_at` | string | 生成日（YYYY-MM-DD） |
| `groups` | array | FGのリスト |
| `group_id` | string | `FG-001`〜 で採番。共通基盤は `FG-CMN` 固定 |
| `name_ja` | string | 業務担当者が呼ぶ名前。Apex命名ではなく業務名 |
| `name_en` | string | 英語名（PascalCase推奨） |
| `description` | string | 「何をどのタイミングでなぜ行うか」を1〜2文で |
| `trigger` | string | UC起動条件（いつ・誰が・何をきっかけに） |
| `uc_id` | string or null | 対応UCのID（`usecases.md` の `uc_id`）。共通基盤は null |
| `feature_ids` | array | `feature_ids.yml` の CMP-xxx IDリスト |
| `components` | array | このFGに属するコンポーネントのAPI名リスト |
| `related_objects` | array | 関連するSalesforceオブジェクトのAPI名リスト |
| `related_fgs` | array | 処理が一部またがる他FGのIDリスト |

---

## 採番規則

- 通常グループ: `FG-001` 〜 `FG-999`（3桁ゼロ埋め）
- 共通基盤: `FG-CMN`（固定値）
- 共通基盤10件超の場合: `FG-CMN-通知`・`FG-CMN-バッチ基盤` 等に分割（`FG-CMN-*` 形式）
- 目安: 1プロジェクトあたり UC数 ± 3 FG（共通系含む）
