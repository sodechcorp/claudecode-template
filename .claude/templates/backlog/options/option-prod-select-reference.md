# option-prod-select-reference

## 何をするか

本番データを読み取る。Sandbox にないデータパターン・本番特有の状態・実際の件数や入力状況の確認に使う。

## 方針

**本番の読み取り（SELECT・COUNT・メタデータの取得・describe）は許可不要で自由に行ってよい。書き込み・削除（INSERT / UPDATE / DELETE / UPSERT・Apex 実行・メタデータ変更・デプロイ）は禁止**（hook `pre-operation.js` と settings.json でも物理的にブロックされる）。

## 実行手順

1. 目的に必要な項目・条件で SELECT を組み立てる（`SELECT Id, {必要な項目} FROM {Object} WHERE {条件}`）。件数の確認なら `SELECT COUNT()` を使う
2. 本番エイリアスを指定して実行する（接続先の確認は [prod-readonly-check.md](../../common/prod-readonly-check.md)）:
   ```bash
   sf data query --query "{SELECT文}" --target-org {prod-alias} --json
   ```
3. 結果を成果物（investigation.md・test-report.md 等の `docs/logs/{issueID}/` 配下）に要約して記録する。`docs/logs/` は git 管理対象外のため値をそのまま書いてよい。**git 管理のドキュメント（`docs/knowledge/`・`docs/decisions.md`・`docs/logs/changelog.md` 等）へ転記するときは、顧客の個人情報（氏名・メールアドレス・電話番号等）の値は書かず、件数・パターンに置き換える**

## 出力

呼び出し元の成果物に追記:

## 本番データ参照結果

- 実行クエリ: `{SELECT文}`
- 結果要約: {件数・パターン・確認できた値}
- 調査・テストへの活用: {どう使ったか}
