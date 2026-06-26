# Security & Permissions — 詳細規則

## settings.json による技術的ブロック

`settings.json` は Git管理対象。`.claude/` 編集・`rm -rf .claude` は行動指示のみ。本番デプロイは deny（⚠️ `*prod*`/`*production*` エイリアスパターン依存）。`git push origin main` 等の破壊操作は未実装（チーム導入時に追加）。

テンプレート更新は `/upgrade` コマンド経由のみ。

## 本番組織接続時の絶対ルール

`sf org display` で `isSandbox: false` の場合は以下を **絶対に実行しない**（ユーザー指示があっても解除不可）。DML / デプロイ / force-app 書き込みの直前に `sf org display` でライブ確認する（毎メッセージではなく操作直前の1回）:

- DML 操作（`sf data create/update/delete/upsert/import/bulk/resume`・Apex 匿名 DML）
- Apex 匿名実行（`sf apex run`）
- デプロイ（`sf project deploy start`・`sf metadata deploy`（旧コマンドも同様にブロック））
- パッケージ操作（`sf package install/uninstall`）
- org 設定変更（`sf org assign/enable/disable/delete`）
- メタデータ変更・force-app への書き込み

**許可**: SOQL SELECT・`sf project retrieve`・ファイル読み取り・docs/ への書き込み

## 共有フォルダ保護

- `G:\共有ドライブ` 削除: hook ハードブロック（bypass 不可）
- `G:\共有ドライブ` 書き込み: 実行前に日本語警告を地の文で出し、ユーザー明示承認後のみ実行（AskUserQuestion 禁止・回避経由禁止）
- Backlog 書き込み（コメント投稿・課題更新・PR操作等）: hook ハードブロック（bypass 不可）。文面案はチャットで提示のみ。投稿・更新は人間が Backlog UI から手動で実施。`mcp__backlog__add_*` / `update_*` / `delete_*` / `mark_*` / `reset_*` が対象。読み取り（`get_*` / `count_*` / `list_*`）は許可。
- 警告文体・例外パターン詳細: `.claude/templates/common/shared-folder-protection.md` 参照

## ファイル変更ルール

`.claude/` 配下は読み取りのみ。`CLAUDE.md`（ルート）/ `docs/` / `force-app/` は編集可。`.mcp.json` は .gitignore 対象（個人設定）。`.gitignore` 変更時はユーザー確認。

## 確認必須操作

以下は必ずユーザー確認を取る:
- Slack / メール / 外部サービスへのメッセージ送信
- 機密情報（トークン・パスワード・個人情報・組織ID）の出力・ログへの記録
- 既存ファイルの削除・上書き（読み取り確認なしに）
