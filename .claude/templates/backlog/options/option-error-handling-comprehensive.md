# option-error-handling-comprehensive

## 何をするか

今回の変更箇所のエラーハンドリング（try-catch・Database.SaveResult・ユーザーへの通知）に漏れが無いかを確かめて補う。

## 実行手順

> 照らす基準は、実装計画で決めたエラー時の扱い（Phase 3 の「エラーハンドリング設計レビュー」を含む）。計画に無い点は、変更したもの（新規なら同じ種類の既存のもの）の既存のやり方に合わせる。どちらにも無い扱い（ロールバック方針・エラーの通知先・ログの記録先）は足さない。それが無いと計画の処理が成り立たないなら backlog-implementer の経路2（実装方針の問題）、そうでなければ派生事項に記録する。

1. 実装したコードのエラーハンドリングを確認する
2. 以下の観点で、上の基準どおりに今回の変更箇所に実装されているか確認・修正する:

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
   - 重大なエラーは、計画または既存のやり方で決まっている記録先（Platform Event・ログ用のオブジェクト等）に記録する

3. エラーハンドリングを実装したコードを確認して漏れがないことを確認する

## 出力

特になし（コードに直接実装するため）。
