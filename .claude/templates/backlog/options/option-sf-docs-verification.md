# option-sf-docs-verification

## 何をするか

Salesforce 標準仕様を公式ドキュメントで裏取りする。記憶・推測で標準仕様を語らない。

## 実行手順

1. 今回の調査・修正方針で「標準仕様として前提にしている事項」を列挙する:
   - 標準 UI の挙動（どのボタンが標準で存在する、など）
   - 標準オブジェクトの動作
   - 標準項目の仕様
   - 標準コンポーネント（StandardActions / StandardController 等）の機能
   - ガバナ制限の具体的な数値
2. **まず `docs/knowledge/sf-standard.md` を Read して該当事項が記載されているか確認する**:
   - 記載がある → その内容を根拠として使用し、investigation.md に「出典: sf-standard.md §{セクション名}」と記録する（公式ドキュメント確認は省略可）
   - 記載がない → ステップ 3 で公式ドキュメントを確認する
3. `docs/knowledge/sf-standard.md` に記載がなかった事項について WebSearch または WebFetch で公式ドキュメントを確認する:
   - `help.salesforce.com` — UI・標準機能の仕様
   - `developer.salesforce.com` — Apex / API / コンポーネント仕様
4. 裏取り結果を記録する:
   - 確認済み → 根拠 URL を investigation.md に記録
   - 仕様と異なる前提があった → 方針を修正して記録
   - 確認できなかった → 業務要件の不確実点に追記
5. 公式ドキュメントで確認した内容のうち**汎用性が高い仕様**は `docs/knowledge/sf-standard.md` の該当セクションに追記する（最終照合日も更新する）:

## 出力

investigation.md の根拠・前提セクションに追記:

| 確認事項 | 結果 | 根拠 URL |
|---|---|---|
| ... | 確認済み / 仕様と相違 / 確認不可 | ... |
