---
description: "プロジェクトGitリポジトリとの同期コマンド。引継ぎ対象ドキュメント（docs/ のうち logs/ 除く）とCLAUDE.mdのpull/pushを実行する。積み上げ型ファイルは差分マージ（両者の追記を保持）。テンプレート更新は /upgrade を使用。"
---

## ファイル種別定義

### 全文同期型（remote / local を完全に上書き）

| パス | 内容 |
|---|---|
| `docs/overview/` | 組織概要・用語集・ステークホルダー |
| `docs/requirements/` | 要件定義書・ビジネスルール |
| `docs/flow/` | 業務フロー・ユースケース |
| `docs/catalog/` | オブジェクト・項目定義書 |
| `docs/architecture/` | システム構成図用データ |
| `docs/design/` | 機能別設計書 |
| `docs/data/` | マスタデータ・メールテンプレート |
| `docs/knowledge/sf-standard.md` | Salesforce 標準機能仕様（sf-memory cat8 出力） |
| `docs/_README.md` | 情報所在マップ |
| `CLAUDE.md` | プロジェクト固有ルール |

### 積み上げ同期型（差分マージ・どちらの追記も保持）

| パス | マージキー |
|---|---|
| `docs/decisions.md` | `## YYYY-MM-DD` で始まる各エントリ（同キーは local 優先） |
| `docs/knowledge/case-index.md` | テーブル行の第2列（課題ID）（同キーは local 優先） |
| `docs/knowledge/pitfalls.md` | `##` / `###` 見出し（同キーは local 優先） |
| `docs/knowledge/cases/` | ファイル名（issueKey）単位で新規のみ追加（既存は上書きしない） |
| `docs/knowledge/effort-calibration.md` | アンカー行（`^- [ID]「` 形式）の課題ID単位で和集合。「全体傾向」統計セクションは local 優先で保持 |
| `docs/knowledge/global-calibration.md` | `^### ` 見出し（コンポーネント種別帯）単位でマージ。「全体傾向」セクションは local 優先で保持 |
| `docs/knowledge/global-pitfalls.md` | テーブル行の issueID+カテゴリ単位で和集合（第2列・第3列の複合キー）。同キーは local 優先 |
| `docs/knowledge/test-prerequisites.md` | §見出し内の各表 第1列キーで和集合（同キーは local 優先）。§ 3（散文）は local 優先で保持 |

### 同期対象外（担当者ごとに独立蓄積）

| パス | 理由 |
|---|---|
| `docs/logs/` | 課題対応ログ・changelogは各担当者が個別に積み上げる |

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
- プロジェクト部分を取得する — リモートの最新を取得（全文同期型: 上書き / 積み上げ型: マージ）
- プロジェクト部分を保存する — ローカルの変更をリモートに保存（積み上げ型はマージしてから push）

> テンプレート（`.claude/` / `scripts/`）の更新は `/upgrade` を使用してください。
> `docs/logs/` は同期対象外です（課題作業ログは各担当者が独立蓄積）。

---

## プロジェクト部分を取得する

### Step 1: 全文同期型ファイルの取得

取得前に `git status --short` で未コミットの変更を確認する:

```bash
git status --short docs/overview/ docs/requirements/ docs/flow/ docs/catalog/ docs/architecture/ docs/design/ docs/data/ docs/knowledge/sf-standard.md docs/_README.md CLAUDE.md
```

出力がある場合、AskUserQuestion で確認する:

**質問**: 「全文同期型ファイルに未コミットの変更があります。取得を続行しますか？（リモートの内容で上書きされます）」

**選択肢**:
- `続行する` — 変更を破棄してリモートの内容で上書きする
- `中断する` — キャンセルする

`中断する` を選択した場合は処理を終了する。出力がなければそのまま以下を実行する:

```bash
git fetch origin {Step 0 で取得したブランチ名}
git checkout origin/{Step 0 で取得したブランチ名} -- docs/overview/ docs/requirements/ docs/flow/ docs/catalog/ docs/architecture/ docs/design/ docs/data/ docs/knowledge/sf-standard.md docs/_README.md CLAUDE.md 2>/dev/null || true
```

### Step 2: 積み上げ同期型ファイルのマージ取得

対象: decisions.md / case-index.md / pitfalls.md / cases/ / effort-calibration.md / global-calibration.md / global-pitfalls.md

```bash
python scripts/python/git-sync/git-sync-merge.py --branch {Step 0 で取得したブランチ名}
```

### Step 3: 完了報告

更新されたファイル一覧を `git status --short` で確認し報告:
```
✅ 取得完了 — {更新ファイル数}件のファイルが更新されました
（docs/logs/ は取得対象外。effort-calibration.md は docs/knowledge/ で積み上げマージ）
```

変更がなかった場合:
```
✅ 既に最新です。
```

---

## プロジェクト部分を保存する

### Step 1: 対象ファイルの選択

AskUserQuestion で選択:

**質問**: 「保存するファイルを選択してください」

**選択肢**（multiSelect: false、排他選択）:
- 全て（引継ぎ対象 docs/ + CLAUDE.md）
- 引継ぎ対象 docs/ のみ（CLAUDE.md 除く）
- CLAUDE.md のみ

> docs/logs/ は選択肢に含まれません（課題作業ログ・対象外）。

### Step 2: 積み上げ同期型ファイルのマージ（選択に応じて実行）

**Step 1 の選択が「全て」または「引継ぎ対象 docs/ のみ」の場合のみ実行する**（積み上げ同期型ファイルは全て `docs/` 配下のため。「CLAUDE.md のみ」を選択した場合はスキップし、docs/ 配下をローカルで書き換えない）。

push する前に実行することで、ローカルの積み上げ ＋ remote の積み上げを合体させた状態で push できる。

```bash
python scripts/python/git-sync/git-sync-merge.py --branch {Step 0 で取得したブランチ名}
```

### Step 3: 変更確認

同期対象パスに変更があるか確認:

```bash
git status --short docs/overview/ docs/requirements/ docs/flow/ docs/catalog/ docs/architecture/ docs/design/ docs/data/ docs/knowledge/ docs/decisions.md docs/_README.md CLAUDE.md
```

変更が1件もない場合は「保存対象の変更がありません」と報告して終了。

### Step 4: コミット・push

変更内容からコミットメッセージを自動生成する。形式は以下に固定:

- **prefix**: 変更が `docs/` のみなら `docs:`、`CLAUDE.md` を含む場合は `chore:`
- **suffix**: `git diff --stat` から取得した変更ファイル名を `,` 区切りで列挙（先頭ディレクトリは省略、拡張子は残す）
- 例: `docs: update catalog.md,requirements.md` / `chore: update CLAUDE.md,usecases.md`
- 60 文字を超える場合は `...` で末尾を短縮

Step 1 の選択に応じて `git add` の対象パスを以下から**そのまま**使う（`git add -A` / `git add .` は意図しないファイル混入の原因になるため使用禁止）:

| Step 1 の選択 | `git add` 対象パス |
|---|---|
| 全て | `docs/overview/ docs/requirements/ docs/flow/ docs/catalog/ docs/architecture/ docs/design/ docs/data/ docs/knowledge/ docs/decisions.md docs/_README.md CLAUDE.md` |
| 引継ぎ対象 docs/ のみ | `docs/overview/ docs/requirements/ docs/flow/ docs/catalog/ docs/architecture/ docs/design/ docs/data/ docs/knowledge/ docs/decisions.md docs/_README.md` |
| CLAUDE.md のみ | `CLAUDE.md` |

```bash
git add {上表の対象パス}
git commit -m "{自動生成したコミットメッセージ}"
git push origin HEAD
```

完了報告:
```
✅ 保存完了 — {コミットメッセージ}
```

エラーが発生した場合（リモート未設定等・push reject 等）はエラー内容を報告して終了。  
push が reject された場合は「先に取得（pull）を実行してから再度保存してください」と案内する。
