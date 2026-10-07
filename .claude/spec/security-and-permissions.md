# Security & Permissions — 詳細規則

## settings.json による技術的ブロック

`settings.json` は Git管理対象。`.claude/` 編集・`rm -rf .claude` は行動指示のみ。本番デプロイは deny（⚠️ `*prod*`/`*production*` エイリアスパターン依存）。`git push` は `/git-sync`・`/upgrade` の正規手順として許可（両コマンドが自動実行する）。それ以外の文脈で直接 `git push` を実行しない。

テンプレート更新は `/upgrade` コマンド経由のみ。

## 本番組織接続時の絶対ルール

`sf org display` で `isSandbox: false` の場合は以下を **絶対に実行しない**（ユーザー指示があっても解除不可）。DML / デプロイ / force-app 書き込みの直前に `sf org display` でライブ確認する（毎メッセージではなく操作直前の1回）:

- DML 操作（`sf data create/update/delete/upsert/import/bulk/resume`・Apex 匿名 DML）
- Apex 匿名実行（`sf apex run`）
- デプロイ（`sf project deploy start`・`sf metadata deploy`（旧コマンドも同様にブロック））
- パッケージ操作（`sf package install/uninstall`）
- org 設定変更（`sf org assign/enable/disable/delete`）
- メタデータ変更・force-app への書き込み

**許可**: SOQL SELECT・`sf project retrieve`・ファイル読み取り・docs/ への書き込み・画面確認（Playwright での閲覧・スクリーンショット・Login As。範囲と禁止事項: [prod-readonly-check.md](../templates/common/prod-readonly-check.md)「本番 UI 確認（read-only）」）

## 自動モードの分類器設定（メンバー個人設定）

Claude Code の自動モードは、ツール呼び出しを分類器で判定する。分類器の既定では、名前に `prod` を含む接続先は機密性の高いリモート先とみなされ、Salesforce 本番の SOQL や Login As による画面確認が「本番での機密性の高いリモート操作」としてブロックされうる。ブロックされたら、次を各メンバーの `~/.claude/settings.json` に追記する（公式: https://code.claude.com/docs/en/auto-mode-config.md）。

- **プロジェクトの `.claude/settings.json` や `settings.local.json` には書けない**（分類器は `autoMode` をそこから読まない。リポジトリ経由の許可ルール注入を防ぐための仕様）。テンプレートから配布できないため、メンバー個人が設定する
- 各配列の先頭に必ず `"$defaults"` を入れる（無いと本番デプロイ等の既定ブロックが全て消える）
- 本番の書き込み（DML・デプロイ・Apex 実行）は、この設定で許可しない。上記の絶対ルールどおり `permissions.deny` と hook が止める

```json
{
  "autoMode": {
    "environment": [
      "$defaults",
      "Trusted internal domains: *.my.salesforce.com, *.sandbox.my.salesforce.com, *.lightning.force.com, *.sandbox.lightning.force.com, *.salesforce-setup.com, *.force.com (client Salesforce orgs reached through the sf CLI and Playwright)"
    ],
    "allow": [
      "$defaults",
      "Salesforce production org read-only inspection is allowed: sf data query (SOQL SELECT), sf sobject describe, sf org display, sf org list metadata, sf project retrieve into a temp or docs directory, and Tooling API GET queries. These only read data and metadata and change nothing in the org. A production org alias or name containing 'prod' does not by itself make a read-only Salesforce query a Production Reads or Sensitive Remote Exec case, because no remote shell, credential dump or channel opaque to the classifier is involved.",
      "Salesforce production org UI verification with Playwright is allowed: opening the org through the frontdoor URL from 'sf org open --url-only', navigating Lightning and Setup pages, reading page text, taking screenshots, and using Salesforce 'Login As' (servlet.su, Setup > Users > Login, or Experience Cloud 'Log in to Experience as User') to view screens as another user and then logging out of the proxy session (/secur/logout.jsp). This is the standard, audited Salesforce admin verification feature and is for read-only viewing only. It does not include clicking Save, Submit, Delete, Approve or any action that creates, updates or deletes records or setup, changing passwords, or resetting security tokens; those stay blocked by the Production Deploy and other default rules."
    ]
  }
}
```

追記後に反映を確認する: `claude auto-mode config`（`allow` と `environment` の件数が既定より増え、`soft_deny` の件数が変わらないこと）。ブロックされた理由の名前（`[Production Reads]` 等）は拒否メッセージの角括弧、または `/permissions` の「Recently denied」で確認できる。

## 共有フォルダ保護

- `G:\共有ドライブ` 削除: hook ハードブロック（bypass 不可）
- `G:\共有ドライブ` 書き込み: 確認不要（自由に書き込んでよい）
- Backlog 書き込み（コメント投稿・課題更新・PR操作等）: hook ハードブロック（bypass 不可）。文面案はチャットで提示のみ。投稿・更新は人間が Backlog UI から手動で実施。`mcp__backlog__add_*` / `update_*` / `delete_*` / `mark_*` / `reset_*` が対象。読み取り（`get_*` / `count_*` / `list_*`）は許可。
- 対象と削除の扱いの詳細: `.claude/templates/common/shared-folder-protection.md` 参照

## ファイル変更ルール

`.claude/` 配下は読み取りのみ。`CLAUDE.md`（ルート）/ `docs/` / `force-app/` は編集可。`.mcp.json` は .gitignore 対象（個人設定）。`.gitignore` 変更時はユーザー確認。

## 確認必須操作

以下は必ずユーザー確認を取る:
- Slack / メール / 外部サービスへのメッセージ送信
- 機密情報（トークン・パスワード・個人情報・組織ID）の出力・ログへの記録
- 既存ファイルの削除・上書き（読み取り確認なしに）。上書きは共有フォルダでも同じ扱いで、共有フォルダであることを理由にした確認はしない。共有フォルダの削除は確認しても行わない（[shared-folder-protection.md](../templates/common/shared-folder-protection.md)）
