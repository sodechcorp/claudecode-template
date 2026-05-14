# Phase 6 オプションインデックス（リリース）

backlog-releaser が Phase 6 の Step 0b で参照する判定情報。3 オプション。

判定の使い方は [_README.md](./_README.md) §Step 0 を参照。

---

```yaml
options:

  - name: option-release-note-generation
    description: リリースノート生成（変更内容・影響範囲・注意事項の文書化）
    category: D
    auto-execute-when:
      - 全社影響を伴う機能追加・変更
      - 課題優先度が「高」以上かつ影響ユーザーが広い
      - 定期リリースでまとめて記録が必要なケース
      - お客様向け通知が必要な変更
    auto-skip-when:
      - 内部設定変更のみ（エンドユーザーへの影響なし）
      - typo 修正・ラベル変更レベル
      - 単一ユーザー・単一プロファイル向け修正
    ask-user-prompt: |
      この修正はエンドユーザーへの影響が無さそうです。リリースノート生成は省略してもよさそうですか？
    estimated-cost: 中

  - name: option-stakeholder-notification
    description: 関係者への完了通知（Slack・メール等の文面案起案。Backlog コメント投稿はユーザーが手動）
    category: D
    auto-execute-when:
      - 全社影響を伴う修正
      - 課題に「関係者に連絡」「周知が必要」等の言及
      - お客様・他チームへの影響がある修正
      - 課題優先度が「緊急」
    auto-skip-when:
      - 開発者内のみで完結する修正
      - 単純なバグ修正で影響範囲が小さい
      - typo 修正・ラベル変更レベル
    ask-user-prompt: |
      この修正は影響範囲が小さく関係者周知は不要そうです。ステークホルダーへの完了通知は省略してもよさそうですか？
    estimated-cost: 軽

  - name: option-rollback-readiness
    description: ロールバック手順最終確認（git reset / 再デプロイ手順の検証・確認）
    category: C
    auto-execute-when:
      - 本番デプロイを含む（管理画面操作・Metadata API 問わず）
      - データ変更・構造変更を含む（ロールバックが複雑になる可能性）
      - 課題に「本番」「リリース」「デプロイ」等のワード
    auto-skip-when:
      - Sandbox のみの変更（本番デプロイなし）
      - 設定変更のみで即時ロールバック可能
    ask-user-prompt: |
      この修正は Sandbox のみの変更のようです。本番ロールバック手順最終確認は省略してもよさそうですか？
    estimated-cost: 軽
```
