---
description: "MCP（外部ツール連携）のセットアップ。Backlog・保守ポータル（support-desk）・GitHub・Slack等の連携を設定する。"
---

## Step 1: 現在の設定を自動チェック

スクリプトは使わない。Claude が `.mcp.json` を直接 Read/Write する。

`.mcp.json` の場所: プロジェクトルート（`sfdx-project.json` と同じ階層）

`.mcp.json` を Read して `mcpServers` の内容を確認する。

### 設定が存在する場合（.mcp.json があり mcpServers にキーがある）

設定済みの MCP をリスト形式で表示する:

```
現在の設定:
- backlog
- github
（設定済みのキーを列挙）
```

続けて AskUserQuestion で操作を選択する:

- `追加する` — 新しい MCP を追加する（→ 追加するMCPの選択へ）
- `完了` — そのまま終了する

### 設定が存在しない場合（.mcp.json がないまたは mcpServers が空）

「MCP がまだ設定されていません。」と伝え、AskUserQuestion で追加するMCPを選択する。

---

**追加するMCPの選択**（上記いずれかの分岐から来た場合）:

AskUserQuestion で設定するMCPを選択する:

- `backlog` — Backlogチケット管理
- `support-desk` — 保守ポータル（課題の窓口を保守ポータルに移した顧客の課題を読む・案を渡す）
- `github` — GitHub PR・Issue連携
- `notion` — Notionページ読み書き

playwright・slack を設定する場合は「その他」を選択して `playwright`・`slack` と入力する。

## Step 2: 実行

**鍵の決まり（トークン・APIキー。どの MCP も同じ）**: 鍵はチャットに貼らせず、`.mcp.json` にも値を書かない。本人に PowerShell の `setx <変数名> "<鍵>"` で環境変数に入れてもらい（鍵はその窓にだけ貼る）、`.mcp.json` には `"${<変数名>:-}"` と書く（Claude Code は `.mcp.json` を読むときに `${...}` を展開する）。`.mcp.json` の値は、そのフォルダで動く Claude（自動の下調べの起動役を含む）が読めてしまうため。設定したら VS Code（Claude Code）を開き直してもらう。

### 「playwright」の場合

トークン不要。以下の設定を `.mcp.json` に追加する（既に playwright があり args に `--isolated` が無いときも、この内容で上書きする）:

```json
"playwright": {
  "command": "npx",
  "args": ["-y", "@playwright/mcp@latest", "--isolated"]
}
```

`--isolated` はブラウザのプロファイルをメモリにだけ置く（既定はディスクに保存する方式で、同じ案件の別のセッションが Playwright を使っていると `Browser is already in use` で起動できない）。Salesforce は毎回 frontdoor でログインするので困らないが、Playwright の窓で手でログインした他のサイトは、ブラウザを閉じると消える。

### 「github」の場合

> ⚠️ `@modelcontextprotocol/server-github` は `modelcontextprotocol/servers-archived` へ移動済み（非推奨・セキュリティ修正なし）。現状は動作するが、後継は `github/github-mcp-server`（Docker/バイナリ配布、npx一発導入不可）。

トークンはチャットに貼らせない（上の「鍵の決まり」）。次をそのまま案内する:

```
1. GitHub > 右上のアイコン > Settings > 左下 Developer settings
2. Personal access tokens > Tokens (classic) > Generate new token（スコープ: repo, read:org）> Generate token > コピー
3. PowerShell で: setx GITHUB_PERSONAL_ACCESS_TOKEN "<コピーしたトークン>"（チャットには貼らないでください）
4. VS Code（Claude Code）を開き直す
```

`.mcp.json` に書き込む（値は書かない）:

```json
"github": {
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-github@latest"],
  "env": {
    "GITHUB_PERSONAL_ACCESS_TOKEN": "${GITHUB_PERSONAL_ACCESS_TOKEN:-}"
  }
}
```

### 「slack」の場合

> ⚠️ `@modelcontextprotocol/server-slack` は `modelcontextprotocol/servers-archived` へ移動済み（非推奨・セキュリティ修正なし・1年以上更新なし）。

Slack Bot Token（`xoxb-` で始まる）はチャットに貼らせない（上の「鍵の決まり」）。本人に `setx SLACK_BOT_TOKEN "<トークン>"` を PowerShell で実行してもらい、`.mcp.json` に書き込む（値は書かない）:

```json
"slack": {
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-slack@latest"],
  "env": {
    "SLACK_BOT_TOKEN": "${SLACK_BOT_TOKEN:-}"
  }
}
```

### 「notion」の場合

Notion Integration Token（`ntn_` または `secret_` で始まる）はチャットに貼らせない（上の「鍵の決まり」）。次をそのまま案内する:

```
1. https://www.notion.so/profile/integrations を開く
2. 「New integration」で Integration を作成し、Internal integration token をコピー
3. 連携したいページで「接続を追加」→ Integration を選択
4. PowerShell で: setx NOTION_TOKEN "<コピーしたトークン>"（チャットには貼らないでください）
5. VS Code（Claude Code）を開き直す
```

`.mcp.json` に書き込む（値は書かない。`NOTION_TOKEN` は Notion の MCP が読む環境変数）:

```json
"notion": {
  "command": "npx",
  "args": ["-y", "@notionhq/notion-mcp-server@latest"],
  "env": {
    "NOTION_TOKEN": "${NOTION_TOKEN:-}"
  }
}
```

### 「backlog」の場合

1. チャットで **ドメイン** を聞く（自由入力のため AskUserQuestion は使わない）— 例: `yourcompany.backlog.com`
2. **APIキーはチャットに貼らせない**（Claude の会話にも `.mcp.json` にも残さない。`.mcp.json` の値は、そのフォルダで動く Claude が読めてしまうため）。次をそのまま案内する:

```
1. Backlog にログイン → 右上のアイコン > 個人設定 → API タブ > メモを入力して「登録」→ APIキーをコピー
2. PowerShell で次の1行を実行する（キーはこの窓にだけ貼り、チャットには貼らないでください）
   setx BACKLOG_API_KEY "<コピーしたAPIキー>"
3. VS Code（Claude Code）を開き直す
```

`.mcp.json` には、キーを環境変数から読む形で書く（値を書き込まない。Claude Code は `.mcp.json` を読むときに `${...}` を展開する）:

```json
"backlog": {
  "command": "npx",
  "args": ["-y", "backlog-mcp-server@latest"],
  "env": {
    "BACKLOG_DOMAIN": "<ドメイン>",
    "BACKLOG_API_KEY": "${BACKLOG_API_KEY:-}"
  }
}
```

- 開き直したあと `mcp__backlog__get_myself` を呼んで、つながるかを確かめる（401 なら環境変数を確かめてもらう）
- 前の版で `.mcp.json` に APIキーの値を直接書いた案件は、上の 1〜3 のあとで、本人に `.mcp.json` を開いてもらい、`BACKLOG_API_KEY` の値を `${BACKLOG_API_KEY:-}` に書き換えてもらう（Claude は `.mcp.json` を読まない。読むとキーが会話に残るため）

### 「support-desk」の場合

保守ポータル（support-desk）の課題を `/backlog`・`/test`・`/release`・`/triage` で読み、案（一次判断の案・対応の案・返信の下書き）を渡すための設定。**鍵はチャットに貼らせない**（Claude の会話にもファイルにも残さない）。

1. チャットで保守ポータルの URL を聞く（自由入力のため AskUserQuestion は使わない。例: `https://support.example.com`。末尾の `/` は付けない）
2. 鍵は本人に用意してもらう。次をそのまま案内する（鍵の値は Claude に送らないよう添える）:
   ```
   1. 保守ポータルにログインし、「設定」→「Claude連携」で鍵を作る（読める顧客を絞れます）
   2. PowerShell で次の2行を実行する（鍵はこの窓にだけ貼り、チャットには貼らないでください）
      setx SUPPORT_DESK_KEY "<作った鍵>"
      setx SUPPORT_DESK_URL "<保守ポータルの URL>"
   3. VS Code（Claude Code）を開き直す
   ```
3. `.mcp.json` に次を書く（鍵は環境変数から読む。値を書き込まない）:

```json
"support_desk": {
  "type": "http",
  "url": "<URL>/api/claude/mcp",
  "headers": {
    "Authorization": "Bearer ${SUPPORT_DESK_KEY:-}"
  }
}
```

- サーバーの名前は必ず `support_desk`（道具の名前が `mcp__support_desk__*` になり、テンプレートはこの名前で読み先を決める: [issue-source.md](../templates/common/issue-source.md)）
- 開き直したあと `mcp__support_desk__get_myself` を呼び、鍵の持ち主と期限（`keyExpiresAt`）を伝える。つながらない（401 など）ときは、鍵の期限・環境変数を確かめてもらう。それでも直らないときは、Claude Code の版によって `headers` の `${...}` が展開されないことがあるので、本人に次を PowerShell で実行してもらう（鍵はこの PC のユーザーの設定にだけ入り、案件のフォルダには入らない）。そのあと `.mcp.json` の `support_desk` は消す:
  ```
  claude mcp add --transport http --scope local support_desk "<URL>/api/claude/mcp" --header "Authorization: Bearer $env:SUPPORT_DESK_KEY"
  ```
- どの顧客の課題をポータルから読むかは、ポータルの顧客の「窓口」で自動で決まる（案件ごとの設定は要らない）

## Step 3: .mcp.json の書き込みルール

1. `.mcp.json` が存在する場合: Read で読み込み → 該当キーを `mcpServers` に追加または上書き → Write で保存
2. `.mcp.json` が存在しない場合: 以下の構造で新規作成:

```json
{
  "mcpServers": {
    "<Step 2 の設定>"
  }
}
```

## 完了後

「Claude Code を再起動すると設定が反映されます。次は `/sf-memory` で組織情報を収集してください」と案内する。

## 注意

- トークン・APIキーをチャットで受け取らない・表示しない（環境変数に入れてもらう。Step 2 の「鍵の決まり」）
- `.mcp.json` の内容を docs/ に記録しない
