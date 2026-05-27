---
description: "Salesforceプロジェクトの基本設計資料（プロジェクト概要書・オブジェクト定義書）のみを会話形式で作成する。機能一覧・詳細設計・プログラム設計は /sf-design を使用。"
---

Salesforceプロジェクトの**基本設計資料（プロジェクト概要書・オブジェクト定義書）のみ**を会話形式で作成します。機能一覧・詳細設計・プログラム設計は `/sf-design` を使用してください。
スクリプトは `scripts/python/sf-doc-mcp/`（プロジェクトルートからの相対パス）にあります。

**AskUserQuestion のルール（厳守）:** [共通ルール参照](.claude/CLAUDE.md#askuserquestion-ルール厳守)

**テンプレート置換ルール（厳守）:** [共通ルール参照](.claude/CLAUDE.md#テンプレート置換ルール厳守)

---

## 前提: 情報源と依存関係

各資料が使う情報源と、最新化に必要なコマンド・選択肢。各エージェントの冒頭でも確認を促すが、事前に把握しておくこと。

| 資料 | 情報源 | 最新化コマンド |
|---|---|---|
| プロジェクト概要書 | `docs/overview/org-profile.md`<br>`docs/requirements/requirements.md`<br>`docs/architecture/system.json`<br>`docs/catalog/_data-model.md`<br>`docs/flow/swimlanes.json` | `/sf-memory` カテゴリ1・2 |
| オブジェクト定義書 | `docs/catalog/_index.md`（対象オブジェクト候補の選択のみ）<br>**Salesforce組織に直接接続**してフィールドメタデータを取得 | `/sf-memory` カテゴリ2 |

> **ユーザー向け注意（新規オブジェクト追加後）**: `/sf-memory` カテゴリ2 を再実行 → _index.md に反映

**出力先**: 全ての資料は `{output_dir}/01_基本設計/` に統一して出力する（`output_dir` は Step 1 で指定）。

---

## Step 0: 資料種別の選択

AskUserQuestion で作成する資料を選択（**上流 → 下流** の順）:
- question: "どの資料を作成しますか？"
- header: "資料種別"
- multiSelect: true
- options:
  - label: "プロジェクト概要書"、description: "プロジェクト概要書.xlsx"
  - label: "オブジェクト定義書"、description: "オブジェクト項目定義書.xlsx"

選択結果を `selected_steps` として保持する（例: `["プロジェクト概要書"]` / `["オブジェクト定義書"]` / `["プロジェクト概要書", "オブジェクト定義書"]`）。

---

## Step 1: 共通情報の取得（資料種別選択後に一度だけ聞く）

> **前提**: このコマンドは Salesforce プロジェクトルート（`force-app/` があるフォルダ）をカレントディレクトリとして実行することを想定している。カレントディレクトリが不明な場合はチャットで確認すること。

まずカレントディレクトリを `project_dir` として確定する（以降の全スクリプト呼び出し・エージェント委譲で使用）:
```bash
python -c "import os; print(os.getcwd())"
```
出力されたパスを `{project_dir}` として保持する。続いて `force-app/` の存在を確認する（存在しない場合は Salesforce プロジェクトルートで再実行するよう案内して終了）:
```bash
python -c "
import pathlib, sys
if not pathlib.Path(r'{project_dir}/force-app').exists():
    print('ERROR: force-app/ が見つかりません。Salesforce プロジェクトルート（force-app/ があるフォルダ）で実行してください。', file=sys.stderr)
    sys.exit(1)
"
```

> **テキスト入力の必須ルール**: チャットでの入力を求めたら、ユーザーが返答するまで次の処理・質問には進まない。

### 前回設定の読み込み

Read tool で `{project_dir}/docs/.sf/sf_config.yml` を読み取る。

- ファイルが存在しない場合（Read エラー）: 旧ファイル `{project_dir}/docs/.sf/sf_doc_config.yml` を Read tool で試みる（移行用 fallback。全プロジェクトへの移行完了後は削除可）
- いずれも存在しない場合: `last_author = ""`、`last_output_dir = ""` として扱う
- ファイルが存在する場合: `author:` 行の値を `last_author`、`output_dir:` 行の値を `last_output_dir` として控える（値が空文字または未定義の場合は `""`）

> **重要（文字化けリスクと対策）**: Claude LLM 生成段階で rare CJK 文字が近傍の頻出字に自動補正されるバイアスがある（例: 「俣」→「係」）。**作成者名（人名）は description に値を埋め込まず、popup 直前に Bash で個別印字する**（Bash stdout = 100% 正確、LLM 生成を経由しない）。**出力先パスは description に値を埋め込む**（一般字のみ構成でドリフトリスクが極めて低い）。

**前回値がある場合:** まず以下を実行して前回値を表示する（stdout = IDE terminal 直接描画なので LLM 生成を経由せず文字化けしない）:
```bash
python -c "
import yaml, pathlib
p = pathlib.Path(r'{project_dir}/docs/.sf/sf_config.yml')
if p.exists():
    d = yaml.safe_load(p.read_text(encoding='utf-8')) or {}
    if d:
        print('━━ 前回の設定値（sf_config.yml）━━')
        if d.get('author'): print('  作成者名       :', d['author'])
        if d.get('output_dir'): print('  出力先フォルダ  :', d['output_dir'])
        print('↑ 各項目で「前回値を使用」を選ぶと上記の値が引き継がれます')
"
```

### 作成者名

**前回値がある場合:** まず以下を実行して作成者名を Bash 印字する（LLM 生成を経由しないため 100% 正確）:
```bash
python -c "
import yaml, pathlib
p = pathlib.Path(r'{project_dir}/docs/.sf/sf_config.yml')
if p.exists():
    d = yaml.safe_load(p.read_text(encoding='utf-8')) or {}
    v = d.get('author', '')
    if v:
        print('━━ 前回の作成者名 ━━')
        print(' ', v)
        print('━━━━━━━━━━━━━')
"
```

その直後に AskUserQuestion で提示（2択+Other自動）:
- question: "作成者名はどうしますか？"
- header: "作成者名"
- multiSelect: false
- options:
  - label: "前回値を使用"、description: "↑ 直前のBash出力に表示された値を使用"
  - label: "スキップ"、description: "作成者名なし"

「前回値を使用」が選ばれた場合は `author = last_author` を使用。「スキップ」の場合は `author = ""`。Other に値が入力された場合はその値を `author` として使用。

> **注意**: 別の作成者名を入力したい場合は「Other」を選択すると自由入力が可能。

**前回値がない場合:** チャットで直接聞く:
```
作成者名を入力してください（不要な場合は「スキップ」と返答）:
```
「スキップ」と返答された場合は空文字として扱う。結果を `{author}` として保持。

確定後、直ちに以下を実行して値を保持する（後続でコンテキスト汚染が起きても正確な値が残るようにするため）:
```bash
python -c "import pathlib; p=pathlib.Path(r'{project_dir}/docs/.sf'); p.mkdir(parents=True, exist_ok=True); (p / '.author_tmp').write_text('{author}', encoding='utf-8')"
```

### 出力先フォルダ

**前回値がある場合:** AskUserQuestion で提示（2択+Other自動）:
- question: "出力先フォルダはどうしますか？"
- header: "出力先"
- multiSelect: false
- options:
  - label: "前回値を使用"、description: "前回値: {last_output_dir}"
  - label: "別のフォルダを指定する"、description: "新しいパスをチャットで入力する"

「前回値を使用」が選ばれた場合は `output_dir = last_output_dir` を使用。「別のフォルダを指定する」または Other が選ばれた場合はチャットで入力してもらう。

**前回値がない場合:** チャットで直接聞く:
```
資料の出力先フォルダのパスを入力してください（このフォルダ内に 01_基本設計/ が作成されます）:
```

いずれの場合も、結果を `{output_dir}` として保持する（末尾のスラッシュは除去）。

確定後、直ちに以下を実行して値を保持する:
```bash
python -c "import pathlib; p=pathlib.Path(r'{project_dir}/docs/.sf'); p.mkdir(parents=True, exist_ok=True); (p / '.output_dir_tmp').write_text(r'{output_dir}', encoding='utf-8')"
```

### 設定の保存

確定した値を保存する（次回のデフォルト値として使用）:
```bash
python -c "
import pathlib, sys
author_f = pathlib.Path(r'{project_dir}/docs/.sf/.author_tmp')
outdir_f = pathlib.Path(r'{project_dir}/docs/.sf/.output_dir_tmp')
try:
    import yaml
    author = author_f.read_text(encoding='utf-8').strip() if author_f.exists() else ''
    output_dir = outdir_f.read_text(encoding='utf-8').strip() if outdir_f.exists() else ''
    cfg = pathlib.Path(r'{project_dir}/docs/.sf/sf_config.yml')
    cfg.parent.mkdir(parents=True, exist_ok=True)
    existing = yaml.safe_load(cfg.read_text(encoding='utf-8')) or {} if cfg.exists() else {}
    existing.update({'author': author, 'output_dir': output_dir})
    cfg.write_text(yaml.dump(existing, allow_unicode=True, default_flow_style=False), encoding='utf-8')
except Exception as e:
    print('設定の保存に失敗:', e, file=sys.stderr)
    sys.exit(1)
finally:
    # 成功・失敗にかかわらず一時ファイルは必ず削除する
    for f in [author_f, outdir_f]:
        f.unlink(missing_ok=True)
"
```

> **設定保存失敗時**: スクリプトが `sys.exit(1)` で終了した場合はコマンドを中断する。以降の Step 2 には進まない。

---

### /sf-memory 最新化確認

`selected_steps` の内容に応じて確認内容を切り替える。

#### 「プロジェクト概要書」のみ選択時

> 概要書は docs/overview, docs/requirements, docs/architecture, docs/flow, docs/catalog/_data-model.md を読む。これらは /sf-memory カテゴリ1・2 で更新される。

AskUserQuestion で確認:
- question: "/sf-memory の最新化状況を確認してください？"
- header: "最新化確認"
- multiSelect: false
- options:
  - label: "最新化済み・このまま続ける"、description: "Step 2 以降の生成に進む"
  - label: "先に /sf-memory を実行する"、description: "コマンドを終了し、/sf-memory 実行を促す"

#### 「オブジェクト定義書」のみ選択時

> オブジェクト定義書は docs/catalog/_index.md（候補リスト用）を読む。フィールドメタは Salesforce 組織から直接取得するため更新不要。

AskUserQuestion で確認:
- question: "docs/catalog/_index.md は最新化済みですか？"
- header: "最新化確認"
- multiSelect: false
- options:
  - label: "このまま続ける"、description: "Step 2 以降の生成に進む"
  - label: "先に /sf-memory カテゴリ2 を実行する"、description: "コマンドを終了"

#### 両方選択時

> 概要書（カテゴリ1・2 由来）+ オブジェクト定義書（カテゴリ2 由来）の両方が対象。

AskUserQuestion で確認:
- question: "/sf-memory の最新化状況を確認してください？"
- header: "最新化確認"
- multiSelect: false
- options:
  - label: "両カテゴリとも最新化済み・このまま続ける"、description: "Step 2 以降の生成に進む"
  - label: "先に /sf-memory を実行する"、description: "コマンドを終了"

#### 共通：「先に実行する」が選ばれた場合

「`/sf-memory` を実行して docs/ を最新化してから、再度 `/sf-doc` を実行してください」と案内してコマンドを終了する。Step 2 以降に進まない。

#### 「このまま続ける」が選ばれた場合

`pre_confirmed=true` として保持し、Step 2 に進む。

---

## Step 2: 各エージェントへの委譲

Step 1 完了後、`selected_steps` に応じて以下のエージェントを self-contained プロンプトで起動する。

| 選択 | 委譲先 | 備考 |
|---|---|---|
| プロジェクト概要書のみ | sf-doc-overview-writer | `pre_confirmed=true`（Step 1 で確認済み） |
| オブジェクト定義書のみ | sf-doc-objects-writer | `selected_steps=["オブジェクト定義書"]` で単独モード |
| 両方選択 | sf-doc-objects-writer | `selected_steps=["プロジェクト概要書", "オブジェクト定義書"]`。Phase 2〜5 の AskUserQuestion を 1 件ずつ順次完了してから Phase 6 で sf-doc-overview-writer を `pre_confirmed=true` で連鎖呼び出し |

> **両方選択時の呼び出し順序**: sf-doc-objects-writer が主役となる。Phase 2〜5 の AskUserQuestion を**1 件ずつ順次呼んで全て回答済みにしてから**、Phase 6 で sf-doc-overview-writer を `pre_confirmed=true` で呼ぶ。これにより「概要書生成フェーズが Phase 2〜5 の途中に割り込まない」UX を保つ。**Phase 2〜5 の確認を 1 メッセージで地の文にまとめて出すのは禁止**（各 Phase ごとに AskUserQuestion を 1 件ずつ呼ぶ）。

### プロジェクト概要書のみ → sf-doc-overview-writer

既存ファイルの有無を確認してバージョン種別を決定する:
```bash
python -c "
import pathlib
p = pathlib.Path(r'{output_dir}/01_基本設計/プロジェクト概要書.xlsx')
print('EXISTS:', p.exists())
print('PATH:', str(p))
"
```

**既存ファイルがある場合:** ファイル名を表示したあと、AskUserQuestion でバージョン種別を選択:
- question: "バージョン更新の種別を選択してください？"
- header: "バージョン"
- multiSelect: false
- options:
  - label: "マイナー更新（vX.Y → vX.Y+1）"、description: "変更箇所を赤字表示"
  - label: "メジャー更新（vX.Y → vX+1.0）"、description: "赤字をリセットして黒字化"

選択結果を `version_increment`（`"minor"` / `"major"`）として保持。選択肢以外の値（Other 等）が入力された場合は `"minor"` にフォールバックし、「⚠️ 入力値が無効のため minor で続行します」と表示する。`source_file = {output_dir}/01_基本設計/プロジェクト概要書.xlsx`。

**既存ファイルがない場合:** `version_increment = "minor"`、`source_file = ""`（新規モード）として続行。

```
project_dir:       {project_dir}
output_dir:        {output_dir}
author:            {author}
pre_confirmed:     true
version_increment: {version_increment}
source_file:       {source_file}
```

### オブジェクト定義書のみ → sf-doc-objects-writer

```
project_dir:    {project_dir}
output_dir:     {output_dir}
author:         {author}
pre_confirmed:  true
selected_steps: ["オブジェクト定義書"]
```

（`version_increment` は sf-doc-objects-writer が Phase 3 で自ら取得するため、コマンド側からは渡し不要）

### 両方選択 → sf-doc-objects-writer

```
project_dir:    {project_dir}
output_dir:     {output_dir}
author:         {author}
pre_confirmed:  true
selected_steps: ["プロジェクト概要書", "オブジェクト定義書"]
```

（`version_increment` は sf-doc-objects-writer が Phase 3 で自ら取得するため、コマンド側からは渡し不要。overview-writer へも objects-writer 側から同値を渡す）

---

## 完了報告

各エージェントの完了報告をそのまま出力する（コマンド側から追加のまとめ出力は行わない）。

- プロジェクト概要書のみ → sf-doc-overview-writer の完了報告を出力
- オブジェクト定義書のみ → sf-doc-objects-writer の完了報告を出力
- 両方選択 → sf-doc-objects-writer が概要書含む完了報告を行う（内部で sf-doc-overview-writer を連鎖呼び出し済み）
