# テンプレート置換ルール 詳細仕様

Python インラインコード内、および AskUserQuestion の label / description 内の `{project_dir}` `{output_dir}` `{author}` 等の `{...}` は f-string ではなく **Claude が実行前に実値でテキスト置換する** プレースホルダー。

## 値の種別別エスケープ規則

### パス値（`{project_dir}` / `{output_dir}` 等）

- Windows パスの `\` はすべて `/` に置換する（例: `C:\work\` → `C:/work`）
- 末尾の `/` は除去する
- 理由: raw string 末尾 `\` による SyntaxError を回避するため。`pathlib.Path` は Windows でも forward slash を正しく解釈する

### 任意文字列値（`{author}` 等）

- シングルクォートで囲まれた箇所 (`'{author}'`) への埋め込み時は、値内の `'` を `\'` にエスケープし、改行 (`\n` `\r`) は空白に置換する（例: `O'Brien` → `O\'Brien`）
- シェル引数 (`"{author}"`) への埋め込み時は値内の `"` を `\"` にエスケープする

## 連鎖エージェントへの適用

同じ規則は `.claude/agents/*.md` 等の連鎖エージェントでも適用される。委譲時に渡す値も上記規則で正規化済みの状態にすること。

## backlog 専用プレースホルダー一覧

> `/backlog` 系コマンドでのみ使用するプレースホルダー。詳細は `.claude/templates/backlog/_README.md` を参照。

| プレースホルダー | 種別 | 確定タイミング |
|---|---|---|
| `{report_dir}` | パス | `.backlog_config.yml` 読み込み時 |
| `{xlsx_folder}` | パス | `/backlog` Phase 1.5 |
| `{evidence_dir}` | パス | Phase 1.5 連動 |
| `{issueID}` | 文字列 | `/backlog` Phase 0 |
| `{件名}` / `{件名_sanitized}` | 文字列 | Phase 1.5 |
