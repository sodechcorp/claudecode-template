---
description: "プロジェクトGitリポジトリとの同期コマンド。初期設定系ドキュメント（docs/overview/ docs/requirements/ 等）とCLAUDE.mdのpull/pushを実行する。積み上げ系（docs/logs/ docs/decisions.md docs/knowledge/）は各担当者が独自に蓄積するため対象外。テンプレート更新は /upgrade を使用。"
---

## 同期スコープ定義

### 同期対象（チーム共有・初期設定系）

| パス | 内容 |
|---|---|
| `docs/overview/` | 組織概要・用語集・ステークホルダー |
| `docs/requirements/` | 要件定義書・ビジネスルール |
| `docs/flow/` | 業務フロー・ユースケース |
| `docs/catalog/` | オブジェクト・項目定義書 |
| `docs/architecture/` | システム構成図用データ |
| `docs/design/` | 機能別設計書 |
| `docs/data/` | マスタデータ・メールテンプレート |
| `docs/_README.md` | 情報所在マップ |
| `CLAUDE.md` | プロジェクト固有ルール |

### 同期対象外（担当者ごとに独立蓄積・上書き禁止）

| パス | 理由 |
|---|---|
| `docs/logs/` | 課題対応ログ・changelogは各担当者が積み上げる |
| `docs/decisions.md` | 判断記録は各担当者が随時追記する |
| `docs/knowledge/` | case-index.md / pitfalls.md は各担当者が独自蓄積する |

---

## Step 0: 操作の選択

まず現在のブランチを取得する:
```bash
git rev-parse --abbrev-ref HEAD
```

取得値が `HEAD` の場合は detached HEAD 状態。以下を報告して終了:
```
⚠️ detached HEAD 状態です。ブランチに切り替えてから再実行してください（例: `git checkout main`）
```

AskUserQuestion で操作を選択:

**質問**: 「何をしますか？」

**選択肢**:
- プロジェクト部分を取得する — プロジェクトリポジトリの最新を取得（git pull）
- プロジェクト部分を保存する — 変更したファイルをプロジェクトリポジトリに保存（git push）

> テンプレート（`.claude/` / `scripts/`）の更新は `/upgrade` を使用してください。
> docs/logs/ / docs/decisions.md / docs/knowledge/ は同期対象外です（各担当者が独立蓄積）。

---

## プロジェクト部分を取得する

同期対象パスに絞って pull する:

```bash
git fetch origin {Step 0 で取得したブランチ名}
git checkout origin/{Step 0 で取得したブランチ名} -- docs/overview/ docs/requirements/ docs/flow/ docs/catalog/ docs/architecture/ docs/design/ docs/data/ docs/_README.md CLAUDE.md 2>/dev/null || true
```

> `git pull` ではなく `git checkout origin/{branch} -- {paths}` で対象パスのみ取得する。積み上げ系（docs/logs/ / docs/decisions.md / docs/knowledge/）はリモートの状態に上書きされない。

完了後、更新されたファイル一覧を `git status --short` で確認し報告:
```
✅ 取得完了 — {更新ファイル数}件のファイルが更新されました
（積み上げ系 docs/logs/ / docs/decisions.md / docs/knowledge/ は取得対象外）
```

変更がなかった場合:
```
✅ 既に最新です。
```

---

## プロジェクト部分を保存する

### 1. 対象ファイルの選択

AskUserQuestion で選択:

**質問**: 「保存するファイルを選択してください」

**選択肢**（multiSelect: false、排他選択）:
- 初期設定系のみ（docs/overview/ docs/requirements/ docs/flow/ docs/catalog/ docs/architecture/ docs/design/ docs/data/ docs/_README.md + CLAUDE.md）
- 初期設定系 docs/ のみ（CLAUDE.md 除く）
- CLAUDE.md のみ

> docs/logs/ / docs/decisions.md / docs/knowledge/ は選択肢に含まれません（積み上げ系・対象外）。

### 2. 変更確認

同期対象パスに変更があるか確認:

```bash
git status --short docs/overview/ docs/requirements/ docs/flow/ docs/catalog/ docs/architecture/ docs/design/ docs/data/ docs/_README.md CLAUDE.md
```

変更が1件もない場合は「保存対象の変更がありません」と報告して終了。

### 3. コミット・push

変更内容からコミットメッセージを自動生成する。形式は以下に固定:

- **prefix**: 変更が `docs/` のみなら `docs:`、`CLAUDE.md` を含む場合は `chore:`
- **suffix**: `git diff --stat` から取得した変更ファイル名を `,` 区切りで列挙（先頭ディレクトリは省略、拡張子は残す）
- 例: `docs: update catalog.md,requirements.md` / `chore: update CLAUDE.md,usecases.md`
- 60 文字を超える場合は `...` で末尾を短縮

```bash
git add {対象パス...}
git commit -m "{自動生成したコミットメッセージ}"
git push origin HEAD
```

完了報告:
```
✅ 保存完了 — {コミットメッセージ}
```

エラーが発生した場合（リモート未設定等）はエラー内容を報告して終了。
