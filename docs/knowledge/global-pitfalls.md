# 全プロジェクト横断 汎用ハマりポイント

> このファイルは `/sf-memory` cat6-global（sf-analyst-cat6-global）が自動生成します。
> Salesforce 技術として汎用性の高いハマりポイントを全プロジェクトから蒸留した内容のみを収録します。
> プロジェクト固有の内容は docs/knowledge/pitfalls.md を参照してください。

| 日付 | 由来 issueID | カテゴリ | 何をするとどうなるか（全角60字以内） | 対処・回避策（全角40字以内） | 検出方法 |
|---|---|---|---|---|---|
| 2026-06-22 | 手動登録（LINK 系バグ調査）| レコード複製（clone / recordClone）| `excludedFieldNames` の一部項目のみ確認して打ち止めると、真因の除外項目を見落とし INSERT 時に入力規則・連動項目エラーが残る | Flow 定義の `excludedFieldNames` を**全件列挙**し、各項目について①`ISNEW()` 条件の入力規則に関与しないか②controlling/dependent 関係に関与しないかを全件チェック。チェックボックス型など型固有の除外不備に注意 | Flow の `excludedFieldNames` リストを grep して件数確認。エラーメッセージに含まれる入力規則名と全除外項目を突合 |
