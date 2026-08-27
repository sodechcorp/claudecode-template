# Phase 2 オプションインデックス（対応方針策定）

backlog-planner が Phase A（対応方針）の Step 0b で参照する判定情報。8 オプション。

判定の使い方は [_README.md](./_README.md) §Step 0 を参照。

---

```yaml
options:

  - name: option-alternative-approaches
    description: 推奨案 A 以外の対応方針 B / C を生成して比較検討
    category: D
    auto-execute-when:
      - 課題本文・コメントに「設計判断が必要」「複数の方向性」「方針 A/B」等の明示的な言及がある
      - 推奨案 A に既存実装パターンとの**構造的**不整合がある（命名・責務境界・設計原則違反）
      - 推奨案 A が複数オブジェクトに横断的影響を持ち、影響範囲が異なる代替案が技術的に成立する
    auto-skip-when:
      - 種別がバグ（原則として唯一解。blind 別案は option-validator-blind に委譲）
      - typo・ラベル・コメント・単一値修正
      - 推奨案 A が業務的・技術的に唯一解
    estimated-cost: 重
    default-when-uncertain: skip
    # 注意: 「課題優先度が高/緊急」は auto-execute-when に含めない。保守課題はデフォルト「高」のため
    #       ほぼ全件 hit してノイズになる。blind 別案は option-validator-blind（category=A）が担う

  - name: option-tradeoff-analysis
    description: 各対応案のメリット・デメリットを深掘り（コスト・工期・将来影響を含む）
    category: D
    auto-execute-when:
      - option-alternative-approaches で複数案が出た場合
      - 課題優先度が「高」以上
      - 影響範囲が広い修正（共通コンポーネント・全社機能）
    auto-skip-when:
      - 単一案で確定の場合
      - typo 修正レベル
    estimated-cost: 中

  - name: option-future-extensibility
    description: 将来拡張性の評価（次の類似要望が来た時に再利用しやすいか）
    category: D
    auto-execute-when:
      - 種別が追加要望
      - 共通コンポーネント・共通ユーティリティへの修正
      - 課題に「他機能でも使いたい」「将来的に拡張」等の言及
    auto-skip-when:
      - 種別がバグの最小修正
      - 単一機能内に閉じる修正
    estimated-cost: 軽

  - name: option-rollback-strategy
    description: 対応方針の段階でロールバック戦略を事前設計
    category: D
    auto-execute-when:
      - 本番影響が大きい修正（オブジェクト構造変更・データ更新を伴う）
      - 課題優先度が「高」以上
      - データ移行を含む
    auto-skip-when:
      - 設定変更のみで簡単に戻せる修正
      - 単純な値修正
    estimated-cost: 中

  - name: option-side-effect-analysis
    description: 対応方針の副作用を網羅列挙（変更点が他処理にどう波及するか）
    category: A
    auto-execute-when:
      - 種別がバグまたは追加要望（常時実行）
      - 共通コンポーネント・共通ユーティリティへの修正
    auto-skip-when:
      - 典型的自明ケース（`_README.md §典型的自明ケース定義` を参照）
    estimated-cost: 中

  - name: option-minimum-change-principle
    description: 最小変更原則チェック（過剰修正・スコープ膨張の検出）
    category: A
    auto-execute-when:
      - 種別がバグ（常時実行・最小修正＋既存影響ゼロが原則）
      - 推奨案 A の変更範囲が複数ファイル・複数オブジェクトに及ぶ
      - 種別が追加要望で既存ファイル改修を含む（純粋な新規ファイル追加だけではない）
    auto-skip-when:
      - 典型的自明ケース（`_README.md §典型的自明ケース定義` を参照）
      - 種別が追加要望で新規ファイル作成のみ（既存ファイル無変更）
    estimated-cost: 軽

  - name: option-conservative-vs-progressive
    description: 保守的案 vs 抜本案の比較（場当たり修正と根本対応の選択）
    category: D
    auto-execute-when:
      - 課題に「根本原因」「再発防止」「設計問題」等の言及
      - 同一機能領域で過去複数回の修正履歴あり（option-similar-past-issue で発見）
    auto-skip-when:
      - 種別が追加要望
      - 単純なバグ修正で抜本対応の選択肢が無い
    estimated-cost: 中

  - name: option-customer-questions
    description: Phase A の業務要件の確認事項を業務語彙に変換した対外向「顧客確認事項ドラフト」を生成（常時・未送信・要人間レビュー）
    category: D
    auto-execute-when:
      - 業務要件の確認事項（Q）が 1 件以上ある場合（常時実行）
    auto-skip-when:
      - 業務要件の確認事項（Q）が 0 件
    estimated-cost: 軽
```
