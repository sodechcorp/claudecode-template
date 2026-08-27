# Phase 4 オプションインデックス（実装）

backlog-implementer が Phase 4 の Step 0b で参照する判定情報。5 オプション。

判定の使い方は [_README.md](./_README.md) §Step 0 を参照。

---

```yaml
options:

  - name: option-progressive-commits
    description: 細かい単位での段階コミット（ロールバック容易性・レビュー性向上）
    category: D
    auto-execute-when:
      - 複数ファイル・複数メタデータタイプにわたる変更
      - 実装計画がフェーズ分けされている（Phase 別コミット計画あり）
      - 影響範囲が広い修正（全社機能・共通コンポーネント）
    auto-skip-when:
      - 単一ファイルの最小修正（1〜2行変更）
      - typo 修正・ラベル変更のみ
    estimated-cost: 軽

  - name: option-error-handling-comprehensive
    description: 網羅的エラーハンドリング（try-catch・Database.SaveResult・ユーザー通知の整合性）
    category: B
    auto-execute-when:
      - 変更対象に DML 処理（insert/update/delete/upsert）を含む
      - 外部連携（Callout / Platform Event / 非同期処理）を含む
      - 課題に「エラー」「例外」「失敗時の挙動」等のワード
    auto-skip-when:
      - 読み取り専用処理（クエリ・表示のみ）
      - LWC/Aura の表示制御のみ
    estimated-cost: 中

  - name: option-code-comments-detail
    description: コードコメント詳細化（複雑なロジックの意図・前提条件の明文化）
    category: D
    auto-execute-when:
      - 複雑なロジック・条件分岐が多い実装（分岐数 5 以上）
      - 課題に「設計」「パフォーマンス考慮」等の背景ある実装
      - 後続担当者が読んで理解困難な可能性のある処理
    auto-skip-when:
      - 単純な値変更・設定変更
      - 既存コメントで十分な場合
      - typo 修正・ラベル変更のみ
    estimated-cost: 軽

  - name: option-soql-governor-limit-check
    description: SOQL ガバナ制限・効率評価（SOQL in loop / 件数上限 / インデックス有無）
    category: B
    auto-execute-when:
      - 変更対象が Apex クラス・トリガーで SOQL を含む
      - ループ処理の中に SOQL が疑われる
      - バルク・バッチ処理を含む
    auto-skip-when:
      - Apex コードを含まない変更
      - 既存 SOQL の変更なし・新規 SOQL なし
    estimated-cost: 軽

  - name: option-bulk-processing-check
    description: バルク処理対応の確認（トリガー・バッチで 200 件超の処理耐性）
    category: B
    auto-execute-when:
      - 変更対象が Apex トリガー
      - バッチ Apex を含む実装
      - 大量データ操作が想定される処理
    auto-skip-when:
      - Apex コードを含まない変更
      - 単一レコードのみを対象とした処理確定（設定・管理画面操作のみ）
    estimated-cost: 軽
```
