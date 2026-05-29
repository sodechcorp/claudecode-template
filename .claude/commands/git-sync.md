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

```bash
git fetch origin {Step 0 で取得したブランチ名}
git checkout origin/{Step 0 で取得したブランチ名} -- docs/overview/ docs/requirements/ docs/flow/ docs/catalog/ docs/architecture/ docs/design/ docs/data/ docs/knowledge/sf-standard.md docs/_README.md CLAUDE.md 2>/dev/null || true
```

### Step 2: 積み上げ同期型ファイルのマージ取得

以下の Python スクリプトを一時ファイルに書き出して実行する。
**BRANCH** プレースホルダーを Step 0 で取得したブランチ名に置換してから実行すること。

```python
import subprocess, re, os

BRANCH = "BRANCH"

def git_show(path):
    r = subprocess.run(["git", "show", f"origin/{BRANCH}:{path}"],
                       capture_output=True, text=True, encoding="utf-8")
    return r.stdout if r.returncode == 0 else None

def read_local(path):
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return f.read()

def write(path, content):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)

# ---- decisions.md ----
def merge_decisions(local, remote):
    def split(text):
        parts = re.split(r'(?=^## \d{4}-\d{2}-\d{2})', text or "", flags=re.MULTILINE)
        pre = parts[0] if parts and not re.match(r'^## \d{4}', parts[0]) else ""
        entries = {}
        for p in parts:
            m = re.match(r'^## (\d{4}-\d{2}-\d{2})', p)
            if m:
                entries[m.group(1)] = p
        return pre, entries

    local_pre, local_e = split(local)
    remote_pre, remote_e = split(remote)
    merged = {**remote_e, **local_e}  # local 優先
    pre = local_pre or remote_pre
    body = "\n".join(merged[k] for k in sorted(merged.keys(), reverse=True))
    print(f"  decisions.md: remote {len(remote_e)} 件 + local {len(local_e)} 件 → {len(merged)} 件")
    return pre + body

path = "docs/decisions.md"
remote = git_show(path)
local  = read_local(path)
if remote is None:
    print(f"  {path}: remote 未存在、スキップ")
elif local is None:
    write(path, remote); print(f"  {path}: 新規作成（remote 版）")
else:
    write(path, merge_decisions(local, remote))

# ---- case-index.md ----
def merge_table(local, remote):
    def parse(text):
        lines = (text or "").splitlines(keepends=True)
        pre, rows = [], {}
        in_table = False
        for line in lines:
            if line.startswith("|"):
                cols = [c.strip() for c in line.split("|")[1:-1]]
                key = cols[1] if len(cols) > 1 else ""
                if key and not re.match(r'^[-:]+$', key) and key not in ("課題ID", "issueKey"):
                    rows[key] = line
                    in_table = True
                else:
                    pre.append(line)
            else:
                if in_table:
                    in_table = False
                pre.append(line)
        return pre, rows

    local_pre, local_rows = parse(local)
    remote_pre, remote_rows = parse(remote)
    merged = {**remote_rows, **local_rows}  # local 優先
    pre = local_pre or remote_pre
    print(f"  case-index.md: remote {len(remote_rows)} 行 + local {len(local_rows)} 行 → {len(merged)} 行")
    return "".join(pre) + "".join(merged.values())

path = "docs/knowledge/case-index.md"
remote = git_show(path)
local  = read_local(path)
if remote is None:
    print(f"  {path}: remote 未存在、スキップ")
elif local is None:
    write(path, remote); print(f"  {path}: 新規作成（remote 版）")
else:
    write(path, merge_table(local, remote))

# ---- pitfalls.md ----
def merge_sections(local, remote):
    def split(text):
        parts = re.split(r'(?=^#{2,3} )', text or "", flags=re.MULTILINE)
        pre = parts[0] if parts and not re.match(r'^#{2,3} ', parts[0]) else ""
        secs = {}
        for p in parts:
            m = re.match(r'^#{2,3} (.+)', p)
            if m:
                secs[m.group(1).strip()] = p
        return pre, secs

    local_pre, local_s = split(local)
    remote_pre, remote_s = split(remote)
    merged = {**remote_s, **local_s}  # local 優先
    pre = local_pre or remote_pre
    print(f"  pitfalls.md: remote {len(remote_s)} 件 + local {len(local_s)} 件 → {len(merged)} 件")
    return pre + "\n".join(merged.values())

path = "docs/knowledge/pitfalls.md"
remote = git_show(path)
local  = read_local(path)
if remote is None:
    print(f"  {path}: remote 未存在、スキップ")
elif local is None:
    write(path, remote); print(f"  {path}: 新規作成（remote 版）")
else:
    write(path, merge_sections(local, remote))

# ---- cases/*.md ----
cases_dir = "docs/knowledge/cases"
r = subprocess.run(["git", "ls-tree", "--name-only", f"origin/{BRANCH}", f"{cases_dir}/"],
                   capture_output=True, text=True, encoding="utf-8")
if r.returncode == 0:
    added = 0
    for rpath in r.stdout.splitlines():
        rpath = rpath.strip()
        if rpath and not os.path.exists(rpath):
            content = git_show(rpath)
            if content:
                write(rpath, content)
                added += 1
                print(f"  新規取得: {rpath}")
    print(f"  cases/: {added} 件追加（既存は上書きしない）")
else:
    print(f"  cases/: remote 未存在、スキップ")

# ---- effort-calibration.md ----
def merge_calibration(local, remote):
    if not local:
        return remote
    if not remote:
        return local

    # アンカー行を課題IDで抽出（例: "- GF-123「...」= 2h"）
    anchor_re = re.compile(r'^- ([A-Za-z]+-\d+)「')

    def extract_anchors(text):
        anchors = {}
        for line in (text or "").splitlines(keepends=True):
            m = anchor_re.match(line)
            if m:
                anchors[m.group(1)] = line
        return anchors

    local_anchors = extract_anchors(local)
    remote_anchors = extract_anchors(remote)

    # 和集合（同キーは local 優先）
    merged_anchors = {**remote_anchors, **local_anchors}
    new_count = len(set(remote_anchors) - set(local_anchors))

    # local のテキストをベースに処理
    # 「全体傾向」統計セクション（先頭ブロック）は local をそのまま保持
    result_lines = []
    seen_keys = set()
    for line in local.splitlines(keepends=True):
        m = anchor_re.match(line)
        if m:
            key = m.group(1)
            seen_keys.add(key)
            result_lines.append(merged_anchors.get(key, line))
        else:
            result_lines.append(line)

    # remote にのみ存在するアンカーを末尾に追加
    for key, line in merged_anchors.items():
        if key not in seen_keys:
            result_lines.append(line)

    print(f"  effort-calibration.md: remote {len(remote_anchors)} 件 + local {len(local_anchors)} 件 → {len(extract_anchors(''.join(result_lines)))} 件（新規 {new_count} 件追加）")
    return "".join(result_lines)

path = "docs/knowledge/effort-calibration.md"
remote = git_show(path)
local  = read_local(path)
if remote is None:
    print(f"  {path}: remote 未存在、スキップ")
elif local is None:
    write(path, remote); print(f"  {path}: 新規作成（remote 版）")
else:
    write(path, merge_calibration(local, remote))

print("\n✅ 積み上げ型マージ完了")
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

### Step 1: 積み上げ同期型ファイルのマージ（push 前に必ず実行）

push する前に「取得する」の Step 2 と同じマージ処理を実行する。  
これにより、ローカルの積み上げ ＋ remote の積み上げを合体させた状態で push できる。

### Step 2: 対象ファイルの選択

AskUserQuestion で選択:

**質問**: 「保存するファイルを選択してください」

**選択肢**（multiSelect: false、排他選択）:
- 全て（引継ぎ対象 docs/ + CLAUDE.md）
- 引継ぎ対象 docs/ のみ（CLAUDE.md 除く）
- CLAUDE.md のみ

> docs/logs/ は選択肢に含まれません（課題作業ログ・対象外）。

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

```bash
git add {対象パス...}
git commit -m "{自動生成したコミットメッセージ}"
git push origin HEAD
```

完了報告:
```
✅ 保存完了 — {コミットメッセージ}
```

エラーが発生した場合（リモート未設定等・push reject 等）はエラー内容を報告して終了。  
push が reject された場合は「先に取得（pull）を実行してから再度保存してください」と案内する。
