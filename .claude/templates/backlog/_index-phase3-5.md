# Phase 3.5 オプションインデックス（実装前検証）

backlog-validator が Phase 3.5 の Step 0b で参照する判定情報。4 オプション。

判定の使い方は [_README.md](./_README.md) §Step 0 を参照。

---

```yaml
options:

  - name: option-existing-test-baseline
    description: 変更前の既存テスト状態を記録（カバレッジ・PASS/FAIL ベースライン）
    category: A
    auto-execute-when:
      - 常に採用（regression-guard の静的確認で代替。実測は Phase 5。backlog-validator.md Step 2-3「option との関係」）
    auto-skip-when:
      - （なし）
    estimated-cost: 軽

  - name: option-impact-rescan
    description: 影響範囲の逆参照 grep 再走査（Phase 1 の reverse-grep 結果を実装計画で再確認）
    category: A
    auto-execute-when:
      - 常に採用（regression-guard が代替実行。backlog-validator.md Step 2-3「option との関係」）
    auto-skip-when:
      - （なし）
    estimated-cost: 中

  - name: option-cross-review
    description: 多角レビュー（権限/FLS・副作用・類似実装整合の 3 点一括確認）
    category: A
    auto-execute-when:
      - 種別がバグまたは追加要望（常時実行）
    auto-skip-when:
      - （なし。常時実行）
    estimated-cost: 中

  - name: option-evidence-check
    description: 実装前 Before エビデンス取得状況の確認（画面キャプチャ・データ状態）
    category: A
    auto-execute-when:
      - 常に採用（backlog.md Phase 3.5 Step B で本体が実行。backlog-validator.md Step 5）
    auto-skip-when:
      - （なし）
    estimated-cost: 軽
```
