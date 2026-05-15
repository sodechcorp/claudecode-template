---
description: "Salesforce 設計書（詳細設計・プログラム設計・機能一覧）を生成する。詳細設計/プログラム設計/機能一覧の3種別をマルチセレクトで選択して実行。"
---

Salesforce プロジェクトの設計書を生成します。

**詳細設計 / プログラム設計** の2層構成に対応しています。

**AskUserQuestion のルール（厳守）:** [共通ルール参照](.claude/CLAUDE.md#askuserquestion-ルール厳守)

**テンプレート置換ルール（厳守）:** [共通ルール参照](.claude/CLAUDE.md#テンプレート置換ルール厳守) — 加えて以下の固有規則を適用する:
- **列挙値** (`{version_increment}`): `minor` / `major` 以外が指定された場合は `minor` にフォールバックし、ユーザーに「未知の値のためminorに置換」と警告する。

---

## 2層設計の概要

| 層 | 対象読者 | 内容 | 出力先 |
|---|---|---|---|
| 詳細設計 | エンジニア | 機能グループ単位のコンポーネント仕様・インターフェース・画面項目 | `{output_dir}/02_詳細設計/` |
| プログラム設計 | 実装者 | コンポーネント単位の処理フロー・SOQL・DML | `{output_dir}/03_プログラム設計/` |

---

## Step 0: 設計書種別の選択

AskUserQuestion で生成する設計書を選択する:
- question: "どの設計書を生成しますか？"
- header: "設計書種別"
- multiSelect: true
- options:
  - label: "詳細設計"、description: "機能グループ単位の詳細設計書（コンポーネント仕様・インターフェース・画面項目）"
  - label: "プログラム設計"、description: "コンポーネント単位のプログラム設計書（処理フロー・SOQL・DML）"
  - label: "機能一覧"、description: "機能一覧.xlsx だけを再生成（設計書は更新しない）"

> **最低1件選択必須**: 0件選択（空配列）が返された場合は、再度 AskUserQuestion で同じ質問を提示する。3種別のいずれも生成しない無実行は許容しない。3 回連続で 0 件選択された場合はチャットに「選択がないため処理を中止します」と出して終了する。

選択の組み合わせとディスパッチ先:

| 選択 | 委譲先 | 備考 |
|---|---|---|
| 詳細設計のみ | sf-design-step1 | step1 内でグループ選択 |
| プログラム設計のみ | sf-design-step2 | step2 内でグループ選択・SF_ALIAS 取得 ※機能一覧.xlsx も自動更新 |
| 機能一覧のみ | sf-design-step3 | — |
| 詳細+プログラム設計 | sf-design-step1 | step1 内でグループ一括確定 → step2 を連鎖呼び出し ※機能一覧.xlsx も自動更新 |
| 詳細設計+機能一覧 | sf-design-step1 | step1 が詳細設計完了後 step3 を連鎖呼び出し |
| プログラム設計+機能一覧 | sf-design-step2 | step2 内で機能一覧も生成（step3 は不要） |
| 詳細+プログラム+機能一覧 | sf-design-step1 | step1 → step2（機能一覧も生成）の順に連鎖 |

> **副作用注記**: 上表で「※機能一覧.xlsx も自動更新」と記された選択は `{output_dir}/01_基本設計/機能一覧.xlsx` を上書きする（sf-design-writer の仕様）。意図しない上書きを避けたい場合は事前にバックアップすること。

> **詳細+プログラム選択時**: グループの一括確定と連鎖呼び出しは sf-design-step1 が担う。コマンドはディスパッチ後に step1 の完了を待つ。

---

## Step 0-2: 共通情報の取得

### プロジェクトディレクトリ

> sf-design は **カレントディレクトリ（force-app/ / docs/ / scripts/ が存在するフォルダ）** をプロジェクトルートとして使用する。

```bash
python -c "
import pathlib, sys
p = pathlib.Path('.').resolve()
if not any((p / d).exists() for d in ['force-app', 'docs', 'scripts']):
    print('ERROR: カレントディレクトリは Salesforce プロジェクトルートではありません（force-app/ docs/ scripts/ のいずれも見つかりません）。', file=sys.stderr)
    sys.exit(1)
print('project_dir:' + str(p))
"
```

出力の `project_dir:` 以降を **`project_dir`** として控える。

前回設定の読み込み:

Read tool で `{project_dir}/docs/.sf/sf_config.yml` を読み取る。

- ファイルが存在しない場合: 旧ファイル `{project_dir}/docs/.sf/sf_design_config.yml` を Read tool で試みる（移行用 fallback）
- いずれも存在しない場合: `last_author = ""`、`last_output_dir = ""`、`last_project_name = ""` として扱う
- ファイルが存在する場合: `author:` 行の値を `last_author`、`output_dir:` 行の値を `last_output_dir`、`project_name:` 行の値を `last_project_name` として控える（値が空文字、未定義、またはキー自体が存在しない場合は `""` として扱う）

> **重要**: ここで取得した日本語値は **絶対に `python -c` の stdout 経由で再表示・再取得しない**。Read tool で得た値をそのまま AskUserQuestion の補間に使うこと（Bash stdout のラウンドトリップで日本語値が文字化けする事例あり）。

### 作成者名

**前回値がある場合:** AskUserQuestion で提示（2択+Other自動）:
- question: "作成者名はどうしますか？"
- header: "作成者名"
- multiSelect: false
- options:
  - label: "前回: {last_author}"、description: "前回と同じ作成者名を使用"
  - label: "スキップ"、description: "作成者名なし"

**前回値がない場合:** チャットで直接聞く:
```
作成者名を入力してください（不要な場合は「スキップ」と返答）:
```
「スキップ」と返答された場合は空文字として扱う。

確定後、直ちに以下を実行して値を保持する（後続でコンテキスト汚染が起きても正確な値が残るようにするため）:
```bash
python -c "import pathlib; p = pathlib.Path(r'{project_dir}/docs/.sf'); p.mkdir(parents=True, exist_ok=True); p.joinpath('.author_tmp').write_text('{author}', encoding='utf-8')"
```

### 出力先フォルダ

**前回値がある場合:** AskUserQuestion で提示（2択+Other自動）:
- question: "出力先フォルダはどうしますか？"
- header: "出力先"
- multiSelect: false
- options:
  - label: "前回: {last_output_dir}"、description: "前回と同じフォルダを使用"
  - label: "別のフォルダを指定する"、description: "新しいパスをチャットで入力する"

**前回値がない場合:** チャットで直接聞く:
```
資料の出力先フォルダのパスを入力してください（このフォルダ内に 02_詳細設計/ 03_プログラム設計/ が作成されます）:
```

「別のフォルダを指定する」または Other が選ばれた場合はチャットで入力してもらう。確定した値を `output_dir` として控える。

確定後、直ちに以下を実行して値を保持する:
```bash
python -c "import pathlib; p = pathlib.Path(r'{project_dir}/docs/.sf'); p.mkdir(parents=True, exist_ok=True); p.joinpath('.output_dir_tmp').write_text(r'{output_dir}', encoding='utf-8')"
```

### バージョン種別

既存ファイルの有無で出し分ける。判定スクリプト:
```bash
python -c "
import pathlib
selected = {selected_types}
output = pathlib.Path(r'{output_dir}')
checks = []
if '詳細設計' in selected:
    checks += list((output / '02_詳細設計').glob('*.xlsx')) if (output / '02_詳細設計').exists() else []
if 'プログラム設計' in selected:
    checks += list((output / '03_プログラム設計').glob('*.xlsx')) if (output / '03_プログラム設計').exists() else []
if '機能一覧' in selected:
    p = output / '01_基本設計' / '機能一覧.xlsx'
    if p.exists(): checks.append(p)
print('HAS_EXISTING:', len(checks) > 0)
"
```

**判定方法**: stdout に `HAS_EXISTING: True` が含まれる場合は既存ありとして下の「**既存ファイルが1件以上ある場合**」分岐へ進む。`HAS_EXISTING: False` の場合は「**既存ファイルが1件もない場合（新規作成）**」分岐へ進む。

**既存ファイルが1件以上ある場合:** AskUserQuestion で選択する（2択＋Other自動）:
- question: "バージョン更新の種別を選択してください？"
- header: "バージョン"
- multiSelect: false
- options:
  - label: "minor"、description: "機能追加・仕様変更・軽微な修正（デフォルト）"
  - label: "major"、description: "大規模な変更・後方互換性のない改訂"

選択値を **`version_increment`** として保持する。Other が選ばれた場合はチャットで入力してもらう。

**既存ファイルが1件もない場合（新規作成）:** AskUserQuestion をスキップし、`version_increment = "minor"` を自動セット。ユーザーに「新規作成のため version を minor で自動設定しました」と1行通知する。

### プロジェクト名

正式名称を優先順位順に自動取得する:
```bash
python -c "
import json, re, pathlib
proj = pathlib.Path(r'{project_dir}')
name = ''
prof = proj / 'docs/overview/org-profile.md'
if prof.exists():
    text = prof.read_text(encoding='utf-8')
    for pat in [r'\|\s*システム名\s*\|\s*(.+?)\s*\|',
                r'\|\s*プロジェクト名\s*\|\s*(.+?)\s*\|',
                r'システム名[^\n:：]*[:：]\s*(.+)',
                r'プロジェクト名[^\n:：]*[:：]\s*(.+)']:
        m = re.search(pat, text)
        if m:
            name = m.group(1).strip()
            break
if not name:
    p = proj / 'sfdx-project.json'
    if p.exists():
        d = json.loads(p.read_text(encoding='utf-8'))
        name = d.get('name', '') or d.get('namespace', '')
if not name:
    name = proj.name
print('project_name:' + name)
"
```

`project_name:` の値を **`detected_project_name`** として控える。

**`last_project_name` がある場合（sf_config.yml に前回値あり）:** AskUserQuestion で提示（2択+Other自動）:
- question: "設計書表紙に使うプロジェクト名を確認してください？"
- header: "プロジェクト名"
- multiSelect: false
- options:
  - label: "前回: {last_project_name}"、description: "前回と同じプロジェクト名を使用"
  - label: "{detected_project_name}"、description: "自動取得値（org-profile.md / sfdx-project.json）"

**`last_project_name` がない場合:** AskUserQuestion で提示（2択+Other自動）:
- question: "設計書表紙に使うプロジェクト名を確認してください？"
- header: "プロジェクト名"
- multiSelect: false
- options:
  - label: "{detected_project_name}"、description: "自動取得値（org-profile.md / sfdx-project.json）"
  - label: "別名を入力する"、description: "チャットで設計書表紙用のプロジェクト名を入力する"

「別名を入力する」または Other が選ばれた場合はチャットで聞く:
```
プロジェクト名を入力してください（設計書の表紙に記載）:
```

確定値を **`project_name`** として保持する。確定後、直ちに以下を実行して値を保持する:
```bash
python -c "import pathlib; p = pathlib.Path(r'{project_dir}/docs/.sf'); p.mkdir(parents=True, exist_ok=True); p.joinpath('.project_name_tmp').write_text('{project_name}', encoding='utf-8')"
```

### 設定の保存

確定した値を保存する（次回のデフォルト値として使用）:
```bash
python -c "
import pathlib, sys
author_f = pathlib.Path(r'{project_dir}/docs/.sf/.author_tmp')
outdir_f = pathlib.Path(r'{project_dir}/docs/.sf/.output_dir_tmp')
pname_f = pathlib.Path(r'{project_dir}/docs/.sf/.project_name_tmp')
try:
    import yaml
    author = author_f.read_text(encoding='utf-8').strip() if author_f.exists() else ''
    output_dir = outdir_f.read_text(encoding='utf-8').strip() if outdir_f.exists() else ''
    project_name = pname_f.read_text(encoding='utf-8').strip() if pname_f.exists() else ''
    cfg = pathlib.Path(r'{project_dir}/docs/.sf/sf_config.yml')
    cfg.parent.mkdir(parents=True, exist_ok=True)
    existing = yaml.safe_load(cfg.read_text(encoding='utf-8')) or {} if cfg.exists() else {}
    existing.update({'author': author, 'output_dir': output_dir})
    if project_name:
        existing['project_name'] = project_name
    cfg.write_text(yaml.dump(existing, allow_unicode=True, default_flow_style=False), encoding='utf-8')
except Exception as e:
    print('warning: 設定保存に失敗（次回デフォルト値の復元なし）:', e, file=sys.stderr)
finally:
    # 成功・失敗にかかわらず一時ファイルは必ず削除する
    for f in [author_f, outdir_f, pname_f]:
        f.unlink(missing_ok=True)
"
```

**警告通知**: 上記スクリプトの出力（stdout / stderr）に `warning:` を含む場合は、assistant message に「⚠️ 設定保存に失敗しました（次回起動時の前回値復元なし）」を 1 行通知する。

---

## Step 0-3: 対象グループの選択（詳細設計が含まれる場合のみ）

`selected_types` に「詳細設計」が含まれない場合はこのステップをスキップして Step 0-4 に進む。

`feature_ids.yml` の存在確認:
```bash
python -c "
import pathlib, sys
p = pathlib.Path(r'{project_dir}') / 'docs' / '.sf' / 'feature_ids.yml'
if not p.exists():
    print('ERROR: docs/.sf/feature_ids.yml が見つかりません。先に /sf-memory を実行してください。')
    sys.exit(1)
print('OK')
"
```

`feature_groups.yml` の存在確認（無ければ `/sf-memory` の先行実行を案内してエラー終了）:
```bash
python -c "
import pathlib, sys
p = pathlib.Path(r'{project_dir}') / 'docs' / '.sf' / 'feature_groups.yml'
if not p.exists():
    print('ERROR: docs/.sf/feature_groups.yml が見つかりません。')
    print('       先に /sf-memory を実行して sf-analyst-cat5 に生成させてください。')
    print('       （feature_groups.yml は業務機能グループ定義の正本で、手動整理された内容を含むため自動上書きしません）')
    sys.exit(1)
print('OK')
"
```

FG 一覧をマークダウン表 + in-band signal で出力（**次の assistant メッセージにそのまま貼る**）:
```bash
python -c "
import yaml
with open(r'{project_dir}/docs/.sf/feature_groups.yml', encoding='utf-8') as f:
    data = yaml.safe_load(f)
groups = data.get('groups', []) if isinstance(data, dict) else (data or [])

print('=== USER-FACING REFERENCE TABLE: ユーザーへの提示が必須 ===')
print('=== CLAUDE.md L103（候補列挙禁止）の対象外: これは AskUserQuestion の選択肢候補ではなく')
print('=== 「グループIDを指定」選択後の自由記述入力で必要な識別子対応表。')
print('=== 必須アクション: 下記マークダウン表を次の assistant メッセージにそのまま貼り、')
print('=== その後で AskUserQuestion を呼ぶこと。表示を省略してはならない。')
print()
print('| FG-ID | 名前 | コンポーネント数 |')
print('|---|---|---|')
for g in groups:
    print(f\"| {g['group_id']} | {g['name_ja']} | {len(g.get('feature_ids', []))} |\")
print()
print(f'合計: {len(groups)} グループ')
print()
print(f'TOTAL={len(groups)}')
"
```

**python 実行後**: stdout の `=== ... ===` ブロックは内部指示（ユーザーに見せない）。マークダウン表（`| FG-ID | ...` から `合計: N グループ` まで）を**次の assistant メッセージとしてそのままユーザーに提示する**。`TOTAL=N` の `N` を取り出して AskUserQuestion ラベル `全グループ（{n}グループ）` の補間に使う。

上記マークダウン表が assistant メッセージに表示済みであることを確認してから AskUserQuestion を呼ぶ。

AskUserQuestion で選択する（3 択＋Other 自動）:
- question: "対象グループを選択してください"
- header: "対象グループ"
- multiSelect: false
- options:
  - label: "全グループ（{n}グループ）"、description: "feature_groups.yml の全グループを対象"
  - label: "グループIDを指定"、description: "FG-XXX をカンマ区切りで入力（次の質問で聞く）"
  - label: "コンポーネントを指定"、description: "Apex名・LWC名・F-XXX等で指定（次の質問で聞く）"

「グループIDを指定」の場合:
```
対象グループIDをカンマ区切りで入力してください（例: FG-001,FG-003）:
```

「コンポーネントを指定」の場合:
```
対象コンポーネント名または機能IDをカンマ区切りで入力してください（例: QuotationRequestController,CMP-012）:
```

入力後、グループ解決スクリプトで FG-XXX に変換して `target_group_ids` に設定:
```bash
python -c "
import yaml, sys, pathlib
inputs = [x.strip() for x in '{入力値}'.split(',')]
fids_path = pathlib.Path(r'{project_dir}') / 'docs' / '.sf' / 'feature_ids.yml'
api_to_fid = {}
if fids_path.exists():
    data = yaml.safe_load(fids_path.read_text(encoding='utf-8')) or {}
    for feat in data.get('features', []):
        if not feat.get('deprecated', False):
            api_to_fid[feat['api_name']] = feat['id']
with open(r'{project_dir}/docs/.sf/feature_groups.yml', encoding='utf-8') as f:
    _grp_data = yaml.safe_load(f)
groups = _grp_data.get('groups', []) if isinstance(_grp_data, dict) else (_grp_data or [])
fid_to_group = {}
for g in groups:
    for fid in g.get('feature_ids', []):
        fid_to_group[fid] = g['group_id']
resolved = set()
errors = []
for inp in inputs:
    if inp.startswith('FG-'):
        resolved.add(inp)
        continue
    fid = inp if inp.startswith('F-') else api_to_fid.get(inp)
    if fid:
        grp = fid_to_group.get(fid)
        if grp:
            resolved.add(grp)
        else:
            errors.append(f'{inp}: feature_groups.yml にグループが見つかりません')
    else:
        errors.append(f'{inp}: feature_ids.yml に API 名が見つかりません')
for g in sorted(resolved):
    print(f'group_id:{g}')
for e in errors:
    print(f'error:{e}', file=sys.stderr)
"
```

`error:` がある場合は AskUserQuestion で以下の3択を提示する:
- question: "グループ解決エラーが発生しました。どうしますか？"
- header: "エラー対応"
- multiSelect: false
- options:
  - label: "入力を修正して再試行"、description: "Step 0-3 の入力選択に戻る"
  - label: "エラー分を除外して続行"、description: "resolved に含まれる FG のみを target_group_ids に設定して次へ進む"
  - label: "中止"、description: "エラー内容をユーザーに伝えて終了する"

「全グループ」を選択した場合は `target_group_ids = []`（空リスト）と設定する。

---

## Step 0-4: SF_ALIAS の確定（プログラム設計が含まれる場合のみ）

`selected_types` に「プログラム設計」が含まれない場合はこのステップをスキップして Step 0-5 に進む。

### .sf/config.json から target-org を取得

```bash
python -c "
import json, pathlib
p = pathlib.Path(r'{project_dir}/.sf/config.json')
if p.exists():
    d = json.loads(p.read_text(encoding='utf-8'))
    alias = d.get('target-org') or ''
    print('alias:' + alias)
else:
    print('alias:')
"
```

`alias:` 以降の値を **`detected_alias`** として控える。

**detected_alias がある場合** — AskUserQuestion で提示（2択＋Other自動）:
- question: "接続先組織のエイリアスを確認してください"
- header: "接続先組織"
- multiSelect: false
- options:
  - label: "{detected_alias}"、description: "config.json の target-org を使用"
  - label: "別のエイリアスを使用"、description: "別のエイリアスをチャットで入力する"

**detected_alias がない場合** — チャットで直接聞く:
```
接続する Salesforce 組織のエイリアスを入力してください（sf org list で確認できます）:
```

Other または「別のエイリアスを使用」が選ばれた場合もチャットで入力してもらう。確定した値を **`sf_alias`** として保持する。

### エイリアスが未認証の場合のフォールバック

```bash
sf org display --target-org "{sf_alias}" --json 2>/dev/null | python -c "
import sys, json
try:
    d = json.loads(sys.stdin.read())
    print('ok' if d.get('status', 1) == 0 else 'ng')
except Exception:
    print('ng')
"
```

`ng` の場合は以下のメッセージをユーザーに案内して処理を中断する:
```
エイリアス "{sf_alias}" が未認証です。以下のコマンドを端末で実行してブラウザでログインしてから再実行してください:
  sf org login web --alias <任意のエイリアス名>
```

---

## Step 0-5: 対象機能（target_ids）の選択（プログラム設計のみ選択時）

`selected_types` に「プログラム設計」が含まれ、かつ「詳細設計」が含まれない場合のみ実行する。それ以外はスキップして Step 1 に進む。

AskUserQuestion で対象を選択する:
- question: "対象機能を選択してください"
- header: "対象機能"
- multiSelect: false
- options:
  - label: "全機能"、description: "スキャンで検出した全コンポーネントを処理"
  - label: "対象を絞る（F-XXX で指定）"、description: "機能ID（F-XXX 形式）をカンマ区切りで入力（次の質問で聞く）"

「全機能」の場合は `target_ids = []`（全件）。「対象を絞る」または Other が選ばれた場合は F-XXX 形式の機能IDをカンマ区切りで入力してもらい `target_ids` に設定する（例: `F-001, F-002`）。API 名・グループID（FG-XXX）は F-XXX への変換をサポートしていないため受け付けない。

---

## Step 1: ディスパッチ — 各エージェントへの委譲

Step 0-2 完了後、選択内容に応じて以下のエージェントを self-contained プロンプトで起動する。

### 詳細設計が選択された場合 → sf-design-step1 エージェント

```
プロジェクトフォルダパス: {project_dir}
output_dir: {output_dir}
author: {author}
project_name: {project_name}
version_increment: {version_increment}
selected_steps: {選択した種別のリスト。例: ["詳細設計", "プログラム設計"]}
target_group_ids: {Step 0-3 で確定したリスト。「詳細設計」が含まれない場合は []}
sf_alias: {Step 0-4 で確定。「プログラム設計」が含まれない場合は ""}
```

> sf-design-step1 はグループ確定済みパラメータを受け取り、詳細設計の実行・必要に応じた連鎖呼び出し（step2/step3）を全て担う。コマンドは step1 の完了を待つだけでよい。

### 詳細設計が含まれず、プログラム設計が選択された場合（プログラム設計のみ または プログラム設計+機能一覧） → sf-design-step2 エージェント

```
プロジェクトフォルダパス: {project_dir}
output_dir: {output_dir}
author: {author}
project_name: {project_name}
version_increment: {version_increment}
target_group_ids: []
step0_3_done: false
sf_alias: {Step 0-4 で確定}
target_ids: {Step 0-5 で確定。空リスト = 全件}
```

> **パラメータ補足**:
> - `target_group_ids`: 対象グループIDリスト（list[str]）。空リストは全件対象。
> - `step0_3_done`: `true` なら step1 からの連鎖呼び出し（グループ→機能ID変換済み）、`false` なら単独実行（orchestrator 確定済みの target_ids をそのまま使う）。
> - `sf_alias`: Salesforce 組織エイリアス（orchestrator の Step 0-4 で確定済み）。
> - `target_ids`: 対象機能IDリスト（orchestrator の Step 0-5 で確定済み）。空リストは全件対象。

### 機能一覧のみが選択された場合（詳細設計・プログラム設計が含まれない） → sf-design-step3 エージェント

```
プロジェクトフォルダパス: {project_dir}
output_dir: {output_dir}
author: {author}
project_name: {project_name}
version_increment: {version_increment}
```

---

## Step 3: 完了報告

sf-design-step1（または直接呼ばれた sf-design-step2 / sf-design-step3）から返された完了報告をそのまま assistant message に転記する。フォーマット定義は各エージェント側に集約済み。

---

## 注意事項

- 詳細設計は **グループ単位**（feature_groups.yml が必要）
- プログラム設計は **コンポーネント単位**（scan_features.py の出力が必要）
- 詳細設計を含む選択の場合は常に sf-design-step1 が先頭に立ち、連鎖的に後続エージェントを呼び出す
- コンポーネント名（API名・F-XXX）で対象を指定した場合は Step 0-3 のグループ解決スクリプトにより FG-XXX に変換し、確定済みの `target_group_ids` を step1 に渡す
