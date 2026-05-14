# option-cross-review

## 何をするか

権限 / FLS・副作用・類似実装整合の 3 点を一括確認する多角レビュー。実装計画を「別の視点」から見直す。

## 実行手順

### 1. 権限 / FLS 確認

実コードを Grep して以下の各観点の対応有無を確認し、表に記録する（Apex を含まない変更は該当項目を「対象外」と記録する）:

| 観点 | 確認内容 | 実コード確認結果 |
|---|---|---|
| プロファイル / 権限セット | 変更・追加フィールドへの CRUD 権限設定 | |
| FLS 項目レベル | `Schema.sObjectType.{Object}.fields.{Field}.isAccessible()` 等の enforcement | |
| Apex `with sharing` | クラス宣言が `with sharing` か `without sharing` か `inherited sharing` か | |
| SOQL `WITH SECURITY_ENFORCED` | クエリ単位の enforcement 有無 | |
| DML `Security.stripInaccessible` | 書き込み時のフィールドアクセス制御 | |

- 新規フィールドを追加する場合: 必要な権限セット・プロファイルで readable / editable が設定されているか
- 既存フィールドを変更する場合: FLS の変更が必要ないか
- 実装側（implementer）で再点検が必要な観点は「要実装確認」として明示する

### 2. 副作用確認

option-side-effect-analysis（Phase 2 で実施済みの場合）の結果と、実装計画の内容を照合する:
- 実装計画で副作用が「考慮済み」となっているか
- 「抑制する」と決めた副作用が実際に抑制できる実装になっているか
- 「許容する」と決めた副作用が今も許容できるか再確認する

### 3. 類似実装整合

implementation-plan.md の実装案と、既存の類似実装を比較する:
- 命名規則・コーディングスタイルが統一されているか
- エラーハンドリングの方式が統一されているか
- 今回の実装を見た次の開発者が混乱しないか

## 出力

validation-report.md に追記:

## 多角レビュー結果

**権限 / FLS**: 問題なし / 要修正（{内容}）/ 要実装確認（{観点}）
**副作用考慮**: 実装に反映済み / 未反映（{内容}）
**類似実装整合**: 整合 / 差異あり（{内容・意図的 / 要修正}）

総合判定: OK → 実装進行 / 要修正（{修正内容}）
