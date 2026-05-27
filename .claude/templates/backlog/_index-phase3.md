# Phase 3 オプションインデックス（実装計画レビュー）

backlog-planner が Phase B（実装計画）の Step 0b で参照する判定情報。8 オプション。

判定の使い方は [_README.md](./_README.md) §Step 0 を参照。

---

```yaml
options:

  - name: option-validator-blind
    description: implementation-plan を見ずに別案を書いて比較（blind reviewer）— subagent 化必須
    category: A
    auto-execute-when:
      - 常時実行（auto-skip-when に該当しない場合は必ず実行）
    auto-skip-when:
      - 典型的自明ケース（_README.md §典型的自明ケース定義 を参照）
      - 推奨案 A が唯一解で別案が構造的に立てられない（実装選択肢がゼロ）
    ask-user-prompt: |
      この課題は唯一解のため別案が立てられない可能性があります。blind 別案レビュー（subagent）は省略してもよさそうですか？
    estimated-cost: 重

  - name: option-staged-deployment-plan
    description: 段階的デプロイ計画（Phase 別・ユーザ別・機能別の段階展開）
    category: D
    auto-execute-when:
      - 全社影響を伴う本番デプロイ
      - データ移行を含む
      - 機能フラグ・段階展開の必要性が課題で言及
    auto-skip-when:
      - 単一ユーザー・単一プロファイル向け修正
      - 設定変更のみ
    ask-user-prompt: |
      この修正は段階展開の必要性が無さそうです。段階的デプロイ計画は省略してもよさそうですか？
    estimated-cost: 中

  - name: option-feature-flag-design
    description: フィーチャーフラグ設計（カスタム設定や Custom Metadata で機能 ON/OFF を制御）
    category: D
    auto-execute-when:
      - 全社影響を伴う新機能追加
      - 段階的展開を明示的に要求
      - 既存挙動の変更で「一部ユーザーのみ先行展開」が必要
    auto-skip-when:
      - 単純なバグ修正
      - 既存設定変更のみ
    ask-user-prompt: |
      この修正は段階展開不要のようです。フィーチャーフラグ設計は省略してもよさそうですか？
    estimated-cost: 重
    default-when-uncertain: skip

  - name: option-data-migration-plan
    description: データ移行計画（既存レコードの一括更新・新項目バックフィル等）
    category: C
    auto-execute-when:
      - 課題に「データ移行」「一括更新」「バックフィル」「既存レコードに反映」等のワード
      - 新規必須項目の追加（既存レコードの欠損対応必須）
      - オブジェクト構造変更を含む
    auto-skip-when:
      - データ更新を含まない処理修正
      - UI 表示変更のみ
    ask-user-prompt: |
      この修正はデータ移行を含まないようです。データ移行計画は省略してもよさそうですか？
    estimated-cost: 重
    default-when-uncertain: skip

  - name: option-deployment-dependency-check
    description: デプロイ順序・依存関係確認（オブジェクト → フィールド → Apex の順序等）
    category: D
    auto-execute-when:
      - 複数メタデータタイプを含む変更（オブジェクト + Apex + Flow 等）
      - 新規オブジェクト・新規フィールドを追加
      - LWC + Apex + 設定の組合せ修正
    auto-skip-when:
      - 単一ファイル修正
      - 設定変更のみ
    ask-user-prompt: |
      この修正は単一メタデータタイプのみのようです。デプロイ順序・依存関係確認は省略してもよさそうですか？
    estimated-cost: 軽

  - name: option-implementation-pattern-check
    description: 既存実装パターンとの整合性確認（プロジェクトのコーディング規約・設計パターン準拠）
    category: A
    auto-execute-when:
      - 種別がバグまたは追加要望（常時実行）
      - 新規 LWC・Apex クラス・Flow を作成
    auto-skip-when:
      - 既存メソッド内の最小修正のみ（パターン整合の概念が無関係）
    ask-user-prompt: |
      この修正は既存メソッド内の最小修正のみのようです。既存実装パターンとの整合性確認は省略してもよさそうですか？
    estimated-cost: 中

  - name: option-anti-pattern-check
    description: アンチパターン検出（God Class / 巨大トランザクション / SOQL in loop / hardcoded ID 等）
    category: B
    auto-execute-when:
      - 変更対象が Apex クラス・トリガー
      - 新規 Apex クラス追加
      - 既存メソッドへの大規模追記
    auto-skip-when:
      - LWC / Flow メタデータのみの修正（Apex 非該当）
      - コメント・ラベル修正のみ
    ask-user-prompt: |
      この修正は Apex を含まないようです。アンチパターン検出は省略してもよさそうですか？
    estimated-cost: 中

  - name: option-error-handling-design
    description: エラーハンドリング設計レビュー（例外伝播・ロールバック・ユーザ通知の整合性）
    category: B
    auto-execute-when:
      - 変更対象が Apex の DML 処理を含む
      - 外部連携（Callout / Platform Event）を含む
      - 課題に「エラー」「例外」「失敗時の挙動」等のワード
    auto-skip-when:
      - 読み取り専用処理（クエリ・表示のみ）
      - LWC 内の表示制御のみ
    ask-user-prompt: |
      この修正は読み取り専用処理のようです。エラーハンドリング設計レビューは省略してもよさそうですか？
    estimated-cost: 中
```
