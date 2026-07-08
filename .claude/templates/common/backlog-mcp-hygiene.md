# Backlog MCP 利用ルール（レスポンス肥大化対策）

## 背景

`get_issue_comments` / `get_issues` は、本文・投稿者名などの実データに対し `createdUser.nulabAccount` / `notifications[].user`（同一ユーザー情報の重複） / `stars` / `iconUrl` 等のメタデータが数倍のノイズとして付与される（SNM-14 実測: 本文 200 バイト程度に対し 1 コメントあたり約 1.5KB）。`count` を指定せず大量課題・大量コメントを取得すると出力が肥大化し、後続処理が不安定になるリスクがある。

## ルール

1. **`count` を必ず指定する**（コメント目安 20・課題一覧目安 20）。全件取得が必要な場合も一括取得ではなく下記ページングで刻む。
2. **ページング**:
   - `get_issue_comments`: `minId` / `maxId` で範囲を刻む。`order: "desc"` で新しい順から取得し、必要な範囲で打ち切る運用を優先する（最古まで遡る必要がある場合のみ `order: "asc"` で先頭から刻む）。
   - `get_issues`: `offset` でページングする（`minId` / `maxId` はコメント専用パラメータで issue 一覧には存在しない）。
3. **消費するフィールドを絞る**: レスポンスから読む・要約に転記するのは `content` / `created` / `createdUser.name` / `changeLog` 等の実データのみ。`createdUser.nulabAccount` / `notifications[].*` / `stars` / `iconUrl` 等は読み飛ばす。

## 適用対象

`mcp__backlog__get_issue_comments` / `mcp__backlog__get_issues` を呼ぶ全エージェント。特に以下は必ず本ルールに従う:

- `backlog-investigator`（Step A: 課題コメントの全件取得・ページング）
- `pattern-curator`（Step 1: キーワード検索での `get_issues` 呼び出し、Step 2: `docs/logs/` 不在時の `get_issue_comments` 補完）
- `backlog-blind-second-opinion`（Step 1: 課題本文・コメントが省略記号で渡された場合の補完取得）
