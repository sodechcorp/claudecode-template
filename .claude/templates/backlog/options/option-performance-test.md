# option-performance-test

## 何をするか

応答時間・大量データ時の動作・ガバナ制限余裕を確認するパフォーマンステストを実施する。

## 実行手順

1. パフォーマンスが問題になりうるシナリオを確認する:
   - 一覧表示・レポート（大量件数の描画）
   - バッチ処理・バルク処理（大量 DML）
   - 複雑な SOQL（多数の結合・条件）

2. Sandbox でパフォーマンス計測を実施する（Apex のログの取り方は [option-apex-debug-log.md](option-apex-debug-log.md) の Step 1 の 1.（isSandbox の確認）と Step 2〜5 のとおり。Step 1 の 2. の既存ログは変更前の処理のログなので計測値に使わない。TraceFlag・DebugLevel を Tooling API で置き、計測する処理は Tooling API の executeAnonymous で実行し、終わったら TraceFlag を片付ける。`sf apex run` で実行したログはレベルが `APEX_CODE,DEBUG;APEX_PROFILING,INFO` に固定され `SOQL_EXECUTE_BEGIN`・`SOQL_EXECUTE_END` が出ないので、SOQL 1件ごとの行数・時間には使わない〔1 トランザクションの SOQL の総件数・CPU 時間は `LIMIT_USAGE_FOR_NS` に出るので読める〕）:

   **Apex 実行時間**:
   - Apex デバッグログで `EXECUTION_FINISHED` の時間を確認する
   - 目安: 通常処理 < 1 秒、バッチ処理 < CPU 10 秒（上限）

   **SOQL 件数・ガバナ使用量**:
   - ログの `SOQL_EXECUTE_END` / `SOQL_EXECUTE_BEGIN` で件数・時間確認
   - 1 トランザクション内の SOQL 総件数（上限 100）の余裕を確認

   **LWC ロード時間**:
   - ブラウザの開発ツールで Network タブでの応答時間を確認
   - 目安: 画面ロード < 3 秒

3. 問題を発見した場合は実装を修正する:
   - SOQL 最適化（インデックス・WHERE 条件改善）
   - キャッシュ活用（カスタム設定・Custom Metadata の事前ロード）
   - 非同期処理化（バッチ / Queueable への変更）

## 出力

test-report.md に追記:

## パフォーマンステスト結果

| シナリオ | 計測値 | 目安値 | 判定 | 対応 |
|---|---|---|---|---|
| Apex 実行時間 | {N} ms | {処理の種別に合う手順 2. の目安: 通常処理 < 1000 ms／バッチ処理 CPU < 10000 ms} | OK / NG | {修正内容} |
| SOQL 件数 | {N} / 100 | < 80 | OK / NG | ... |
| LWC ロード | {N} ms | < 3000 ms | OK / NG | ... |
