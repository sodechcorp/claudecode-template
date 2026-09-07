# option-soql-dryrun

## 何をするか

実装計画で想定している SOQL を Sandbox で実行して件数・パフォーマンスを事前確認する。本番で想定外の大量データ・タイムアウトが発生しないことを確認する。

## 実行手順

1. implementation-plan.md から実装予定の SOQL を全て抽出する
2. Sandbox alias を導出・接続確認する: [sandbox-alias-check.md](../../common/sandbox-alias-check.md) を参照。本番組織での実行は禁止。
3. 各 SOQL を Sandbox で実行する:
   ```bash
   sf data query --query "{SOQL文}" --target-org {sandbox-alias} --json
   ```
4. 以下を確認する:
   - 取得件数が想定通りか（多すぎる / 少なすぎる）
   - WHERE 条件の精度（絞りすぎ / 絞り不足）
   - SOQL の実行時間（遅い場合はインデックスの有無を確認）
   - LIMIT の設定が必要かどうか
5. 問題がある SOQL については implementation-plan.md で修正案を提示する:
   - WHERE 条件の追加・変更
   - LIMIT の追加
   - インデックス対象フィールドへの変更
   - バルク処理（一括取得 + Map での参照）への変更

## 出力

validation-report.md に追記:

## SOQL ドライラン結果

| SOQL 概要 | 取得件数 | 実行時間 | 問題 | 対応 |
|---|---|---|---|---|
| {SOQL の目的} | {N} 件 | {ms} | なし / あり（{詳細}） | 修正案: {内容} |
