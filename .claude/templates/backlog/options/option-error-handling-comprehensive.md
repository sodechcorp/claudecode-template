# option-error-handling-comprehensive

## 何をするか

網羅的エラーハンドリングを実装する。try-catch・Database.SaveResult・ユーザー通知を漏れなく実装する。

## 実行手順

> **Phase 3 で `option-error-handling-design` がスキップされていた場合**は、まず最小限の設計判断（例外型・ロールバック方針・通知方式）を行ってから実装漏れチェックに進む（Phase 3 で実行済みなら設計判断はスキップ）。

1. 実装したコードのエラーハンドリングを確認する
2. 以下の観点で網羅的に実装されているか確認・修正する:

   **DML エラーハンドリング**:
   ```apex
   // allOrNone=false の場合
   Database.SaveResult[] results = Database.insert(records, false);
   for (Database.SaveResult result : results) {
       if (!result.isSuccess()) {
           for (Database.Error error : result.getErrors()) {
               // エラー処理: ログ / 通知 / addError
           }
       }
   }
   ```

   **AuraHandledException / LwcResponse**:
   - Apex から LWC にエラーを返す場合は AuraHandledException をスロー
   - メッセージは業務ユーザーが理解できる日本語で記述

   **try-catch の網羅性**:
   - DmlException・NullPointerException・CalloutException を個別にキャッチ
   - finally 句でのリソース解放（必要な場合）

   **ログ記録**:
   - 重大なエラーはシステム管理者が後から確認できる形で記録する
   - Platform Event / ApexLog を活用する

3. エラーハンドリングを実装したコードを確認して漏れがないことを確認する

## 出力

特になし（コードに直接実装するため）。実装完了後に test-report.md のエラーハンドリング確認欄を更新する。
