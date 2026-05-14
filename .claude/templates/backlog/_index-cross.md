# 横断系オプションインデックス（Phase 5 のみ参照）

backlog-tester が Phase 5 の Step 0b で参照する横断系判定情報。2 オプション。

**評価タイミング**: Phase 5 (tester) の Step 0b でのみ評価する。Phase 1〜4・5.5・6 では評価しない（cross オプション 2 件は出力先が `test-report.md` のため、課題対応の最終段階で評価するのが自然）。

判定の使い方は [_README.md](./_README.md) §Step 0 を参照。

---

```yaml
options:

  - name: option-knowledge-extraction
    description: 知見抽出・docs 更新（調査・対応で得た知見を decisions.md / notes.md に残す）
    category: A
    auto-execute-when:
      - 種別がバグまたは追加要望（常時実行）
      - 調査・対応で新たな設計知見・制約・回避策が判明した場合
    auto-skip-when:
      - typo 修正・ラベル変更のみ（知見として残す内容がない）
    ask-user-prompt: |
      この修正は typo 修正・ラベル変更のみのようです。知見抽出・docs 更新は省略してもよさそうですか？
    estimated-cost: 軽

  - name: option-similar-future-prevention
    description: 類似課題の再発防止策提案（同種の問題が再発しないための仕組み・ルール化）
    category: C
    auto-execute-when:
      - 同じ機能領域で過去に類似課題が複数件あった（option-similar-past-issue で発見）
      - 根本原因が設計・仕組みの問題（個人ミスではなく構造的問題）
      - 課題に「再発防止」「根本対応」「仕組みで防ぐ」等の言及
    auto-skip-when:
      - 一時的な設定ミス・typo レベルで再発リスクなし
      - 追加要望で「防止」の概念が無関係
    ask-user-prompt: |
      この課題は一時的なミスで再発リスクが低そうです。類似課題の再発防止策提案は省略してもよさそうですか？
    estimated-cost: 中
```
