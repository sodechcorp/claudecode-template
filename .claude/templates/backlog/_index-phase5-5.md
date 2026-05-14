# Phase 5.5 オプションインデックス（最終確認）

backlog-tester が Phase 5.5 の Step 0b で参照する判定情報。4 オプション。

判定の使い方は [_README.md](./_README.md) §Step 0 を参照。

---

```yaml
options:

  - name: option-final-verifier
    description: 課題本文の期待結果と実挙動だけで blind 解決判定 — subagent 化必須
    category: A
    auto-execute-when:
      - 種別がバグまたは追加要望（常時実行）
    auto-skip-when:
      - typo 修正・ラベル変更のみ（期待結果と実挙動の比較概念が無関係）
    ask-user-prompt: |
      この修正は typo 修正・ラベル変更のみのようです。blind 解決判定（subagent）は省略してもよさそうですか？
    estimated-cost: 重

  - name: option-cross-functional-impact
    description: 横断機能への影響再確認（リリース直前の最終スコープ確認）
    category: A
    auto-execute-when:
      - 種別がバグまたは追加要望（常時実行）
      - 共通コンポーネント・共通ユーティリティへの変更
    auto-skip-when:
      - typo 修正・ラベル変更のみ
      - 影響が単一画面・単一処理に完全に閉じている最小修正
    ask-user-prompt: |
      この修正は影響範囲が単一機能に閉じているようです。横断機能への影響再確認は省略してもよさそうですか？
    estimated-cost: 中

  - name: option-acceptance-criteria-recheck
    description: 受入基準の再確認（課題コメントの追加要件漏れ・ステークホルダー期待整合）
    category: A
    auto-execute-when:
      - 種別がバグまたは追加要望（常時実行）
      - 課題にコメントが複数ある（追記要件が埋まっている可能性）
    auto-skip-when:
      - typo 修正・ラベル変更のみ（受入基準の概念が無関係）
      - 課題コメントが 0 件
    ask-user-prompt: |
      この修正は typo 修正のようです。課題コメントの追加要件・受入基準再確認は省略してもよさそうですか？
    estimated-cost: 軽

  - name: option-diff-review
    description: 実 diff と implementation-plan.md の整合・計画外変更検出・影響範囲再 rescan
    category: A
    auto-execute-when:
      - 種別がバグまたは追加要望 かつ コード変更を伴う
    auto-skip-when:
      - typo 修正・ラベル変更のみ
      - 設定ファイル・メタデータのみの変更（field-meta.xml / layout-meta.xml 等）
    ask-user-prompt: |
      この修正はコード変更が無いか軽微です。diff レビュー（実装計画整合・計画外混入・影響範囲再 rescan）は省略してもよさそうですか？
    estimated-cost: 中
```
