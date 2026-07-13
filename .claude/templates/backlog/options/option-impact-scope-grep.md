# option-impact-scope-grep

## 何をするか

変更対象に関係する Validation Rule・承認プロセス・割り当てルール・共通ユーティリティへの影響を Grep で網羅確認する。

## 実行手順

1. 変更するフィールド名・オブジェクト名を確定する
2. 以下を順番に Grep で確認する:

   **入力規則（Validation Rule）**:
   ```
   Grep pattern: {フィールド名 or オブジェクト名}
   ファイル: *.validationRule-meta.xml
   ```
   ヒットした場合は XML を Read してロジックへの影響を確認する

   **承認プロセス**:
   ```
   Grep pattern: {フィールド名 or オブジェクト名}
   ファイル: *.approvalProcess-meta.xml
   ```

   **割り当てルール**:
   ```
   Grep pattern: {フィールド名 or オブジェクト名}
   ファイル: *.assignmentRules-meta.xml
   ```

   **共通ユーティリティ**:
   - CommonUtil / Utils 系クラスを Grep して変更対象を使用しているか確認

3. ヒットした各箇所を Read して影響を判定する
4. **「無効だから影響なし」と判定する場合のみ、組織で現在も無効か確認する**: ローカル XML の `<active>false</active>` 等は最後に retrieve した時点のスナップショットであり、組織側で後から有効化されている可能性がある（Flow と同じ鮮度リスク。[option-flow-trigger-trace.md](./option-flow-trigger-trace.md) 参照）。ローカルで有効/影響ありと判定する分には追加確認不要だが、**無効を根拠に対応不要と結論づける場合**は対象組織の Setup（オブジェクトマネージャ > 入力規則 / 割り当てルール、または Process Automation > フロー）で現在の有効/無効を確認してから investigation.md に記載する。確認できない場合は「無効」と断定せず `**[要確認: 有効/無効未確認]**` を付ける

## 出力

investigation.md「影響範囲」セクションに追記:

| メタデータ種別 | ファイルパス | 有効/無効（組織確認、無効判定時のみ必須） | 影響判定 | 対応要否 |
|---|---|---|---|---|
| ValidationRule | ... | 有効 / 無効（{組織名}で確認済み） / [要確認] | 影響あり / なし | 要 / 不要 |
| ApprovalProcess | ... | ... | ... | ... |
