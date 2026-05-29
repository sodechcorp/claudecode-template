# sf-claude-template

Salesforce 開発プロジェクト向けの Claude Code テンプレート。
`scripts/setup.sh` で新規プロジェクトを生成すると、本テンプレートの `.claude/` / `CLAUDE.md` / `docs/` / `scripts/` 一式がプロジェクトに展開される。

> **セットアップ・トラブルシュート・運用ガイドの詳細は社内テンプレートガイド（wiki）を参照。**

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

## クイックスタート

### 新規プロジェクトを作成する

```bash
curl -sSL https://raw.githubusercontent.com/sodechcorp/claudecode-template/main/scripts/setup.sh | bash -s プロジェクト名 /c/workspace
```

設計書生成機能（`/sf-doc` `/sf-design`）を使う場合は Python ライブラリも追加:

```bash
pip install -r scripts/python/sf-doc-mcp/requirements.txt
```

### 既存プロジェクトに参加する

```bash
curl -sSL https://raw.githubusercontent.com/sodechcorp/claudecode-template/main/scripts/setup.sh | bash -s フォルダ名 親ディレクトリ https://github.com/your-org/project-a.git
```

clone 後の初期化順: `/sf-setup` → `CLAUDE.md` 記入 → `/setup-mcp` → `/sf-memory`

### テンプレートの更新・Git 同期

- テンプレート更新: `/upgrade`（`.claude/` / `scripts/` のみ更新。プロジェクト固有ファイルは保護される）
- プロジェクト同期: `/git-sync`（`docs/` / `CLAUDE.md` の pull / push を対話形式で実行）

> セットアップ詳細・前提ツール一覧・トラブルシュートは社内テンプレートガイド（wiki）を参照。
