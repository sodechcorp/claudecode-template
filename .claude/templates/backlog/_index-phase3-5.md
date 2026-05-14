# Phase 3.5 オプションインデックス（実装前検証）

backlog-validator が Phase 3.5 の Step 0b で参照する判定情報。5 オプション。

判定の使い方は [_README.md](./_README.md) §Step 0 を参照。

---

```yaml
options:

  - name: option-soql-dryrun
    description: 想定 SOQL を Sandbox で実行して件数・パフォーマンスを事前確認
    category: C
    auto-execute-when:
      - 実装計画に SOQL を含む（新規・変更・追加条件）
      - バルク処理・定期バッチを含む実装
      - データ件数が多い可能性のある処理（大量データ・全件取得系）
    auto-skip-when:
      - 典型的自明ケース（`_README.md §典型的自明ケース定義` を参照）
      - SOQL を含まない実装（UI 制御・ラベル変更・設定変更のみ）
      - 既存 SOQL の一切変更なし
    ask-user-prompt: |
      この実装計画は SOQL を含まないようです。Sandbox での想定 SOQL ドライラン確認は省略してもよさそうですか？
    estimated-cost: 中

  - name: option-existing-test-baseline
    description: 変更前の既存テスト状態を記録（カバレッジ・PASS/FAIL ベースライン）
    category: B
    auto-execute-when:
      - 変更対象が Apex クラス・トリガーを含む
      - 既存テストクラスがある
    auto-skip-when:
      - 典型的自明ケース（`_README.md §典型的自明ケース定義` を参照）
      - Apex コードを含まない変更（設定・メタデータ・LWC のみ）
      - 新規プロジェクトでテストクラスが存在しない
    ask-user-prompt: |
      この変更は Apex コードを含まないようです。変更前テストベースライン記録は省略してもよさそうですか？
    estimated-cost: 軽

  - name: option-impact-rescan
    description: 影響範囲の逆参照 grep 再走査（Phase 1 の reverse-grep 結果を実装計画で再確認）
    category: B
    auto-execute-when:
      - 変更対象の API 名・メソッド名・フィールド名を変更または追加
      - Phase 1 で逆参照 grep を実施した場合（確認精度向上）
    auto-skip-when:
      - 典型的自明ケース（`_README.md §典型的自明ケース定義` を参照）
      - 変更が単一ファイル内に完全に閉じている（外部参照なし）
      - コメント・ラベル・表示文字列のみの変更
    ask-user-prompt: |
      この変更は外部への影響が無さそうです。影響範囲の逆参照 grep 再走査は省略してもよさそうですか？
    estimated-cost: 中

  - name: option-cross-review
    description: 多角レビュー（権限/FLS・副作用・類似実装整合の 3 点一括確認）
    category: A
    auto-execute-when:
      - 種別がバグまたは追加要望（常時実行）
    auto-skip-when:
      - 典型的自明ケース（`_README.md §典型的自明ケース定義` を参照）
    ask-user-prompt: |
      この修正は typo 修正・ラベル変更のみのようです。権限/FLS・副作用・類似実装整合の多角レビューは省略してもよさそうですか？
    estimated-cost: 中

  - name: option-evidence-check
    description: 実装前 Before エビデンス取得状況の確認（画面キャプチャ・データ状態）
    category: A
    auto-execute-when:
      - 種別がバグまたは追加要望（常時実行）
    auto-skip-when:
      - typo 修正・ラベル変更のみ（エビデンス概念が無関係）
    ask-user-prompt: |
      この修正は typo 修正・ラベル変更のみのようです。実装前エビデンス取得確認は省略してもよさそうですか？
    estimated-cost: 軽
```
