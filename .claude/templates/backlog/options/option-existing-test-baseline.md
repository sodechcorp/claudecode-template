# option-existing-test-baseline

> **現在は `regression-guard` が代替するため個別実行しない（参考として保持）**: Phase 3.5 では `_index-phase3-5.md` の個別判定を行わず、`regression-guard確認結果`（静的確認のみ）を利用する（詳細: [backlog-validator.md](../../../agents/backlog-validator.md) Step 2-3「option との関係」参照）。regression-guard は本ファイルの実測処理（`sf apex run test` 実行によるベースライン記録）は代替しない。実測 PASS/FAIL・カバレッジは Phase 5（backlog-tester の dry-run）で**変更後**の値として確定し、変更前との差分比較は行わない設計（[option-regression-test.md](./option-regression-test.md) 参照）。本ファイルの手順は実装参考として残している。

## 何をするか（現行では実行されない旧設計・参考情報）

変更前の既存テスト状態を記録し、実装後にカバレッジが下がった・テストが壊れた場合に比較できる基準を作る、という設計だった（regression-guard 統合前）。

## 実行手順

1. 関連する Apex テストクラスを特定する:
   ```bash
   Grep pattern: {変更対象クラス名}
   ファイル: force-app/**/*Test*.cls
   ```
2. テストを実行してベースライン状態を記録する:
   ```bash
   sf apex run test --class-names {TestClassName} --target-org {sandbox-alias} --json
   ```
3. 以下を記録する:
   - 全テストメソッド名と PASS / FAIL 状態
   - カバレッジ（変更対象クラスのカバレッジ %）
   - 実行時間（ベースライン）
4. 記録を validation-report.md に保存する（実装後の比較に使う想定だったが、現行では Phase 5 が変更前比較を行わないため使われない）

## 出力

validation-report.md に追記:

## 変更前テストベースライン

| テストクラス | テストメソッド数 | PASS | FAIL | カバレッジ |
|---|---|---|---|---|
| {TestClassName} | {N} | {N} | 0 | {N}% |

記録日時: {YYYY-MM-DD HH:MM}
