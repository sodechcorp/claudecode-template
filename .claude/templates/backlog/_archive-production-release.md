# 本番リリース手順書テンプレート（アーカイブ）

> **ステータス**: /backlog Phase 6 から除去済み（2025-06以降）。**`/release`（`release-preparer`）Phase 5 が本テンプレートを参照して `docs/logs/{issueID}/release-plan.md` を生成する**（正本はこのファイル。release-preparer.md 側でテンプレート構造を再利用）。
> このファイルは資産の保全先。削除禁止。

---

## 元の配置

`backlog-releaser.md` の旧 `### 2a. 本番（PRODUCTION）の場合` ブロック（旧 L67-103）。

---

## 本番リリース手順書テンプレート

**本番環境への直接デプロイは行わない。** リリース手順書を作成してユーザに引き渡す。

```markdown
## 本番リリース手順書

課題ID: {issueID} — {件名}
作成日: {YYYY-MM-DD}

### リリース対象メタデータ
| 種別 | API名 / ファイルパス | 変更種別 |
|---|---|---|

### 事前確認チェックリスト
- [ ] Sandbox でのテスト完了
- [ ] 関連トリガー・フロー・権限セットへの影響確認済み

### 事前記録: ロールバック用コミットハッシュ
**デプロイ直前**に `git log -1 --pretty=format:'%H'` を実行し、出力結果を以下の `{ROLLBACK_COMMIT_HASH}` に記録する（手順書作成時ではなくデプロイ直前に記録すること）。

ROLLBACK_COMMIT_HASH: （未記録—デプロイ直前に記録する）

### デプロイコマンド
# （このコマンドはリリース手順書のテンプレート。エージェントは実行しない）

# Step 1: dry-run で事前確認（必須）
sf project deploy start --dry-run --source-dir force-app --target-org <本番エイリアス> --test-level RunLocalTests

# Step 2: 本番デプロイ（dry-run 確認後に実行）
sf project deploy start --source-dir force-app --target-org <本番エイリアス> --test-level RunLocalTests

### ロールバック手順
1. git reset --hard {ROLLBACK_COMMIT_HASH}
2. Sandbox で動作確認
3. 本番に再デプロイ
```

---

## オプション: option-rollback-readiness

本番デプロイ前にロールバック手順を最終確認するオプション。Phase 6 インデックス（`_index-phase6.md`）から除去済みだが、将来の本番リリースコマンドで再利用できるよう内容を保全する。

元の定義ファイル: `.claude/templates/backlog/options/option-rollback-readiness.md`

（option 定義ファイル自体は削除していないため、そちらを参照すること）
