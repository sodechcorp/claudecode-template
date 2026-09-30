# option-cross-review

## 何をするか

権限 / FLS・副作用・類似実装整合の 3 点を一括確認する多角レビュー。実装計画を「別の視点」から見直す。

> **対象範囲**: 本オプションは Phase 3.5（実装前）で実行され、既存コード・実装計画を対象とする。Phase 4 で実際に書かれる新規コードそのものの FLS/CRUD 検証は Phase 5（backlog-tester）が担当する。

## 実行手順

### 1. 権限 / FLS 確認

実コードを Grep して以下の各観点の対応有無を確認する（Apex を含まない変更は該当項目を「対象外」とする）:

| 観点 | 確認内容 |
|---|---|
| プロファイル / 権限セット | 変更・追加オブジェクトへの CRUD 権限設定（allowCreate/allowRead/allowEdit/allowDelete） |
| FLS 項目レベル | `Schema.sObjectType.{Object}.fields.{Field}.isAccessible()` 等の enforcement |
| Apex `with sharing` | クラス宣言が `with sharing` か `without sharing` か `inherited sharing` か |
| SOQL `WITH SECURITY_ENFORCED` | クエリ単位の enforcement 有無 |
| DML `Security.stripInaccessible` | 書き込み時のフィールドアクセス制御 |

- 新規フィールドを追加する場合: 必要な権限セット・プロファイルで readable / editable が設定されているか
- 既存フィールドを変更する場合: FLS の変更が必要ないか
- 実装側（implementer）で再点検が必要な観点は「要実装確認」として明示する

### 2. 副作用確認

implementation-plan.md の副作用調査結果（backlog-planner B-2「副作用」）と、実装計画の内容を照合する:
- 実装計画で副作用が「考慮済み」となっているか
- 「抑制する」と決めた副作用が実際に抑制できる実装になっているか
- 「許容する」と決めた副作用が今も許容できるか再確認する

### 3. 類似実装整合

implementation-plan.md の実装案と、既存の類似実装を比較する:
- 命名規則・コーディングスタイルが統一されているか
- エラーハンドリングの方式が統一されているか
- 今回の実装を見た次の開発者が混乱しないか

## 出力

validation-report.md の `## Step 4: クロスレビュー` 表（[backlog-validator.md](../../../agents/backlog-validator.md) §出力形式）の各行に記録する。権限/FLS 行の確認結果には手順 1 の各観点の結果（「対象外」「要実装確認」を含む）を書く。
