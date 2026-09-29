# option-prod-select-reference

## 何をするか

本番 SELECT 参照を実行する。Sandbox にないデータパターン・本番特有の状態確認が必要な場合に使用する。

## 実行手順（許可必須）

1. 実行する SELECT 文を準備する:
   - 課題の原因確認・テストに必要な情報に限定する
   - 個人情報・機密情報を取得しない WHERE / LIMIT / SELECT 列を設計する（本 option は調査・参照用途の規定。`/release` のデータバックアップ〔release-preparer Phase 4 の7.〕は復元に使うためマスクせず取得し、リリース後確認で問題がなければ削除する別ルールで扱う）
   - `SELECT Id, {必要なフィールドのみ} FROM {Object} WHERE {条件} LIMIT {N}` の形式

2. ユーザーに許可を求める:
   ```
   本番組織 [{alias}] で以下の SELECT を実行する許可をください:
   {SELECT 文}
   目的: {なぜ本番で確認が必要か}
   ```

3. ユーザーの明示的承認（「OK」「実行して」など）を得てから実行する:
   ```bash
   sf data query --query "{SELECT文}" --target-org {prod-alias} --json
   ```

4. 実行結果を要約して test-report.md に記録する:
   - 件数・パターン・構造のみを記録する
   - 顧客個人情報・機密値は伏せる（マスク: ****）
   - 原因特定・テストへの活用方法を記録する

**絶対禁止**: 本番に対する INSERT / UPDATE / DELETE / UPSERT / Apex 実行 / メタデータ変更

## 出力

test-report.md に追記:

## 本番 SELECT 参照結果

- 実行クエリ: `{SELECT文}`（個人情報は SELECT 除外済み）
- 許可取得: {日時} にユーザー承認
- 結果要約: {件数・パターン（機密情報は伏せて要約）}
- 調査・テストへの活用: {どう使ったか}
