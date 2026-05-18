# sf-claude-template

Salesforce 開発プロジェクト向けの Claude Code テンプレート。
`scripts/setup.sh` で新規プロジェクトを生成すると、本テンプレートの `.claude/` / `CLAUDE.md` / `docs/` / `scripts/` 一式がプロジェクトに展開される。

---

## 前提条件

| ツール | 最低バージョン |
|---|---|
| Git | 2.30+ |
| Salesforce CLI (`sf`) | **2.133.0+** （旧版は Entity expansion バグあり） |
| Node.js | 18+ |
| Python | 3.10+ |
| Claude Code | 最新版 |

---

## ディレクトリ構成

| パス | 役割 |
|---|---|
| `.claude/agents/` | 専門エージェント定義 |
| `.claude/commands/` | スラッシュコマンド定義 |
| `.claude/settings.json` | 権限・フック設定 |
| `CLAUDE.md` | プロジェクト固有ルール（担当者名・組織 alias 等） |
| `docs/` | 設計書・要件・議事録 |
| `scripts/` | セットアップ・アップグレード・Python 補助スクリプト |

---

## スラッシュコマンド（9個）

### セットアップ系

| コマンド | 概要 | 補足 |
|---|---|---|
| `/sf-setup` | SF 組織への認証（prod / dev / skip の対話形式） | 初回のみ |
| `/setup-mcp` | GitHub・Slack・Notion 等の MCP 連携を設定 | 初回のみ |
| `/upgrade [タグ]` | 大本テンプレートから `.claude/` 配下を更新 | タグ省略で main ブランチ |
| `/git-sync` | テンプレート更新・プロジェクトの pull/push を対話形式で実行 | |

### 組織記憶系

| コマンド | 概要 | 補足 |
|---|---|---|
| `/sf-retrieve [対象]` | package.xml を生成してメタデータをローカルに取得 | |
| `/sf-memory` | 会話形式でカテゴリを選択し、組織の記憶形成を実行 | 5カテゴリ：組織概要・オブジェクト・マスタデータ・設計/機能グループ・保守履歴/工数温度感 |

### 保守・開発系

| コマンド | 概要 | 補足 |
|---|---|---|
| `/backlog [課題ID]` | Backlog 課題の分析 → 対応方針提案 → 実装 → テスト → デプロイまで一気通貫 | ユーザー承認後に実装へ |

### ドキュメント生成系

| コマンド | 概要 | 補足 |
|---|---|---|
| `/sf-doc` | 基本設計資料（プロジェクト概要書・オブジェクト定義書）を対話形式で生成 | 上流 → 下流の順に分岐 |
| `/sf-design` | 2層設計書（詳細設計・プログラム設計）＋機能一覧を対話形式で生成 | 読者・目的に合わせて層を選択 |

#### `/sf-doc` 資料種別

| 資料 | 出力 | ソース |
|---|---|---|
| プロジェクト概要書 | Excel | `docs/overview/` `docs/requirements/` `docs/architecture/` `docs/catalog/` `docs/flow/` |
| オブジェクト定義書 | Excel | Salesforce 組織メタデータに直接接続 |

---

## セットアップ

`setup.sh` は「新規プロジェクト作成」と「既存プロジェクトへの参加」の2モードをサポートする。

### 引数

| 位置 | 内容 | 省略時 |
|---|---|---|
| `$1` | **作成するフォルダ名**（英数字推奨） | 対話入力 |
| `$2` | **作成先ディレクトリ**（Unix 表記必須。日本語・スペース含む場合はクォート） | カレントディレクトリ |
| `$3` | **プロジェクトリポジトリ URL**（指定: 参加モード、省略: 新規作成モード） | 省略 |

> **パス表記の注意（Windows）**: Git Bash では `C:\workspace` ではなく `/c/workspace` と書く。日本語やスペースを含む場合はダブルクォートで囲む。
> ```
> 誤: C:\workspace\16_グリーンフィールド
> 正: "/c/workspace/16_グリーンフィールド"
> ```

### 新規プロジェクトを作成する

```bash
# 作成先: カレントディレクトリ
curl -sSL https://raw.githubusercontent.com/sodechcorp/claudecode-template/main/scripts/setup.sh | bash -s プロジェクト名

# 作成先を指定する場合
curl -sSL https://raw.githubusercontent.com/sodechcorp/claudecode-template/main/scripts/setup.sh | bash -s プロジェクト名 /c/workspace
```

作成後、Python ライブラリをインストール（設計書生成機能を使う場合）:

```bash
pip install -r scripts/python/sf-doc-mcp/requirements.txt
```

### 既存プロジェクトに参加する（チームメンバーのオンボーディング）

プロジェクトリポジトリ URL を第3引数に渡すと参加モードになる。リポジトリを clone するだけでテンプレート展開は行わない。

```bash
curl -sSL https://raw.githubusercontent.com/sodechcorp/claudecode-template/main/scripts/setup.sh | bash -s フォルダ名 親ディレクトリ https://github.com/your-org/project-a.git

# 例: /c/workspace/gf として clone する
curl -sSL https://raw.githubusercontent.com/sodechcorp/claudecode-template/main/scripts/setup.sh | bash -s gf /c/workspace https://github.com/your-org/project-a.git

# 例: 作成先が日本語フォルダの場合（クォート必須）
curl -sSL https://raw.githubusercontent.com/sodechcorp/claudecode-template/main/scripts/setup.sh | bash -s gf "/c/workspace/16_グリーンフィールド" https://github.com/your-org/project-a.git
```

clone 完了後の次のステップ:
1. `/sf-setup` — Sandbox 組織を認証する
2. `CLAUDE.md` — 担当者名・Sandbox alias 等を記入する
3. `/setup-mcp` — 外部ツール連携を設定する（Backlog・Notion・GitHub 連携を使う場合は必須）
4. `/sf-memory` — 組織情報を収集・記録する（docs/ を生成）

> **GitHub のアクセス権**: Public リポジトリは招待なしで clone できる。`git push` する場合は GitHub の Settings → Collaborators から招待が必要。

---

## トラブルシューティング

### Entity expansion limit exceeded: 1031 > 1000

sf CLI 2.132 以下で `/sf-retrieve` を実行すると発生する既知バグ。

**対処**:
```bash
npm install --global @salesforce/cli@latest
```

Windows で `where sf` が複数パスを返す場合（旧版スタンドアロンが優先される）:
```powershell
# npm インストール版を直接実行
C:\Users\{ユーザー名}\AppData\Roaming\npm\sf.cmd --version  # 2.133.0+ を確認
# または PATH の優先順位を調整する
```

### Dashboard / Report が force-app/ に出てこない

これらはフォルダ型メタデータのため `<members>*</members>` 指定では取得できない。

**対処**: `/sf-retrieve standard` を再実行する（テンプレート更新後はフォルダ名を自動列挙して取得）。または `/sf-retrieve select` でフォルダ名を `FolderName` 形式で個別指定。

### 特定の型で "Metadata API received improper input" が出る

`NetworkBranding` 等、`*` 取得時に内部用コンポーネントを返す型で発生。テンプレートの `EXCLUDED_FROM_WILDCARD` リスト（`scripts/sf-retrieve.sh`）に既に追加済み。新たに発生した場合は同リストに型名を追記する。

---

## テンプレートの更新（/upgrade）

プロジェクト作成後にテンプレート側で更新があった場合、取り込める:

```bash
bash scripts/upgrade.sh
```

`.claude/` / `scripts/` / `.gitignore` のみ更新され、プロジェクト固有ファイル（`CLAUDE.md` / `docs/` / `.mcp.json` / `force-app/`）は保護される。変更があった場合は自動でプロジェクトリポジトリへ push する。

---

## Git 同期（/git-sync）

プロジェクトリポジトリとの pull/push を対話形式で実行する。2種類の操作から選択:

| 操作 | 内容 |
|---|---|
| プロジェクト部分を取得 | `git pull` で最新を取得 |
| プロジェクト部分を保存 | 変更ファイル（`docs/` / `CLAUDE.md`）を選択して自動コミット + `git push` |

テンプレート（`.claude/` / `scripts/`）の更新は `/upgrade` を使用。
