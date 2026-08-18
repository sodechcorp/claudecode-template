---
description: "MCP（外部ツール連携）のセットアップ。Backlog・GitHub・Slack等の連携を設定する。"
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
- `github` — GitHub PR・Issue連携
- `slack` — Slackメッセージ送受信
- `notion` — Notionページ読み書き

playwright を設定する場合は「その他」を選択して `playwright` と入力する。

## Step 2: 実行

### 「playwright」の場合

トークン不要。以下の設定を `.mcp.json` に追加する:

```json
"playwright": {
  "command": "npx",
  "args": ["-y", "@playwright/mcp@latest"]
}
```

### 「github」の場合

チャットで直接トークンを質問する（自由入力のため AskUserQuestion は使わない）:

```
GitHub Personal Access Token を入力してください。

取得方法:
1. GitHub > 右上のアイコン > Settings
2. 左下 Developer settings
3. Personal access tokens > Tokens (classic) > Generate new token
4. スコープ: repo, read:org にチェック
5. Generate token > コピー
```

入力値を `.mcp.json` に書き込む:

```json
"github": {
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-github@latest"],
  "env": {
    "GITHUB_PERSONAL_ACCESS_TOKEN": "<入力値>"
  }
}
```

### 「slack」の場合

チャットで直接 Slack Bot Token（`xoxb-` で始まる）を質問する（自由入力のため AskUserQuestion は使わない）。入力値を `.mcp.json` に書き込む:

```json
"slack": {
  "command": "npx",
  "args": ["-y", "@modelcontextprotocol/server-slack"],
  "env": {
    "SLACK_BOT_TOKEN": "<入力値>"
  }
}
```

### 「notion」の場合

チャットで直接 Notion Integration Token（`ntn_` または `secret_` で始まる）を質問する（自由入力のため AskUserQuestion は使わない）。取得方法を先に案内してから質問する:

```
取得方法:
1. https://www.notion.so/profile/integrations を開く
2. 「New integration」で Integration を作成
3. Internal integration token をコピー
4. 連携したいページで「接続を追加」→ Integration を選択
```

入力値を `.mcp.json` に書き込む（`OPENAPI_MCP_HEADERS` の値は JSON 文字列のためエスケープに注意）:

```json
"notion": {
  "command": "npx",
  "args": ["-y", "@notionhq/notion-mcp-server@latest"],
  "env": {
    "OPENAPI_MCP_HEADERS": "{\"Authorization\": \"Bearer <入力値>\", \"Notion-Version\": \"2022-06-28\"}"
  }
}
```

### 「backlog」の場合

チャットで直接、以下を2問に分けて質問する（自由入力のため AskUserQuestion は使わない）:

1. **ドメイン** — 例: `yourcompany.backlog.com`
2. **APIキー** — 取得方法を案内してから質問する:

```
取得方法:
1. Backlog にログイン
2. 右上のアイコン > 個人設定
3. API タブ > メモを入力して「登録」→ APIキーをコピー
```

入力値を `.mcp.json` に書き込む:

```json
"backlog": {
  "command": "npx",
  "args": ["-y", "backlog-mcp-server@latest"],
  "env": {
    "BACKLOG_DOMAIN": "<ドメイン>",
    "BACKLOG_API_KEY": "<APIキー>"
  }
}
```

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

「Claude Code を再起動すると設定が反映されます」と案内する。

## 注意

- 入力されたトークン・APIキーをチャット上に表示しない
- `.mcp.json` の内容を docs/ に記録しない
