# option-regression-test

## 何をするか

変更によって既存機能が壊れていないかを確認するリグレッションテスト。共通コンポーネント変更・影響範囲が広い修正後に実施する。

## 実行手順

1. 変更が影響する可能性のある既存機能を特定する:
   - option-reverse-grep の結果（変更対象を参照している全コンポーネント）
   - 共通ユーティリティを変更した場合: そのユーティリティを使う全機能
2. 既存テストを一括実行する（dry-run のため変更後のコードで実行され、Sandbox には永続化されない。`CI=true` は進捗表示の再描画で出力が数MBに膨らむのを防ぐ。Bash の timeout は 600000 を指定し、時間切れの場合は `sf project deploy report --use-most-recent --target-org {sandbox-alias}` で結果を取得する）:
   ```bash
   CI=true sf project deploy start --dry-run --source-dir force-app --target-org {sandbox-alias} \
     --test-level RunLocalTests --concise \
     --coverage-formatters json-summary --results-dir docs/logs/{issueID}/coverage-regression
   ```
3. テスト結果を確認する（変更前ベースラインとの差分比較は行わない設計。Phase 3.5 の regression-guard 統合により変更前の実測記録が撤廃されたため）:
   - 全テストが PASS しているか確認する
   - 変更対象クラス・トリガーのカバレッジが基準値（75% 以上）を満たしているか確認する
4. FAIL が出た場合:
   - 変更対象・option-reverse-grep で見つかった参照元と関連する FAIL か確認する
   - 関連する FAIL（実装バグ、または変更でテストの期待値が古くなった）→ backlog-tester の総合判定を FAIL にして Phase 4 に差し戻す
   - 無関係な FAIL（変更前から存在する可能性）→ `[要確認] 既存FAILの可能性` として記録し、本対応スコープでは修正しない
5. 手動での UI リグレッション確認（必要な場合）:
   - 変更の影響を受ける可能性のある機能を Sandbox で実際に操作する

## 出力

test-report.md に追記:

## リグレッションテスト結果

- 全テスト実行: {N} クラス / {N} メソッド
- テスト結果: PASS {N}/{N} / FAIL {N}（関連 {N} / 無関係・要確認 {N}）
- カバレッジ: {変更対象クラス・トリガー: N%}（基準 75% 以上）
- 問題: なし / あり（{内容}）
