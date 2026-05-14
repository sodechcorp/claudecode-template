# option-impact-rescan

## 何をするか

実装計画確定後に影響範囲を再走査する。Phase 1 の逆参照 grep から実装計画が変わった場合や、実装計画で新たに追加・変更されたファイルへの影響を確認する。

## 実行手順

### Phase 1 reverse-grep がスキップされていた場合のフォールバック

investigator が `option-reverse-grep` を skip していた場合、比較対象が存在しないため以下の分岐で対応する:

- **課題種別がバグ・追加要望**: 変更対象シンボル（Apex メソッド名・LWC コンポーネント名・項目 API 名）を `force-app/` 全体で Grep し、全件を新規参照として扱う（初回全件探索）
- **課題種別が typo / ラベル変更 / 典型的自明ケース**: 本 option 自体を skip し、validation-report.md の Step 3 セクションに「Phase 1 reverse-grep スキップ済み・自明ケースのため本 option も skip」と記録する

---

1. implementation-plan.md から変更対象ファイル・API 名・メソッド名を全て抽出する
2. Phase 1 の option-reverse-grep で調査済みの内容と比較して「新たに追加された変更対象」を特定する（Phase 1 skip の場合は上記フォールバックを適用）
3. 新たな変更対象について逆参照 grep を実行する:
   ```bash
   Grep pattern: {新規変更対象の API 名 / メソッド名}
   ファイル: force-app/
   ```
4. ヒット箇所を確認して影響を評価する
5. 発見した影響を validation-report.md に追記する（implementation-plan.md の修正が必要な場合は合わせて修正する）

## 出力

validation-report.md に追記:

## 影響範囲再走査（Phase 1 からの追加分）

| 変更対象（新規追加） | ヒットファイル | 影響評価 | 対応 |
|---|---|---|---|
| {API 名 / メソッド名} | {ファイルパス} | あり / なし | 実装計画に反映 / 無視 |

Phase 1 からの変更: なし / あり（{内容}）
