# Phase 1.6 オプションインデックス（Sandbox 仮説検証）

backlog-investigator が Phase 1.6 モードで参照する判定情報。1 オプション。

判定の使い方は [_README.md](./_README.md) §Step 0 を参照。

---

```yaml
options:

  - name: option-sandbox-hypothesis-verification
    description: Phase 1 で立てた全仮説を Sandbox で実際に操作して検証し、再現する仮説と再現しない仮説を分類する
    category: A
    auto-execute-when:
      - 種別がバグ（常時実行）
    auto-skip-when:
      - 種別が追加要望（原因仮説概念が無関係）
      - 種別がその他かつ再現確認が不要と明確
    ask-user-prompt: |
      この課題は新機能追加のため Sandbox での仮説検証は不要です。省略してよさそうですか？
    estimated-cost: 重
```

---

## メンテナンス

新しいオプションを追加する場合は [_README.md](./_README.md) §メンテルール を参照。
