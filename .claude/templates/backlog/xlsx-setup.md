# Phase 1.5: xlsx フォルダパスの確定 — 実行手順

---

## 「作成しない」が選ばれた場合

`{xlsx_folder}` = null、`{evidence_dir}` = `docs/logs/{issueID}/evidence` として Phase 2 へ進む。

investigation.md フロントマターに `evidence_dir` を書き戻す（`/test` 起動時の保存先解決 ① に必要。省くと `/test` がフォールバックして `docs/logs/{issueID}/` に証跡が出る）:

```bash
python - <<'PYEOF'
import pathlib, re
invest = pathlib.Path('docs/logs/{issueID}/investigation.md')
if invest.exists():
    text = invest.read_text(encoding='utf-8')
    ev = 'docs/logs/{issueID}/evidence'
    if text.startswith('---'):
        end = text.index('---', 3)
        front = text[3:end]
        body = text[end+3:]
        if re.search(r'^evidence_dir:', front, re.MULTILINE):
            front = re.sub(r'^evidence_dir:.*$', f'evidence_dir: {ev}', front, flags=re.MULTILINE)
        else:
            front = front.rstrip('\n') + f'\nevidence_dir: {ev}\n'
        invest.write_text(f'---\n{front}---{body}', encoding='utf-8')
    else:
        invest.write_text(f'---\nevidence_dir: {ev}\n---\n\n{text}', encoding='utf-8')
    print('[OK] investigation.md evidence_dir 書き戻し完了')
else:
    print('[SKIP] investigation.md が存在しません（Phase 1 未完了）')
PYEOF
```

> **エビデンス取得依頼は Phase 3 末尾（実装方針確定後・実装直前）で行う**。Phase 1.5 ではフォルダ確定のみを行い、ユーザに作業負荷をかけない。

---

## 「作成する」が選ばれた場合

### フォルダパスの確定

`docs/.backlog_config.yml` を確認する（出力が空の場合は初回として扱う）:

```bash
python -c "import yaml,pathlib; p=pathlib.Path('docs/.backlog_config.yml'); d=yaml.safe_load(p.read_text(encoding='utf-8')) if p.exists() else {}; print(d.get('report_dir',''))"
```

- **初回（出力が空）**: 保存先フォルダパスをテキストで入力してもらう（絶対パスで指定。例: `C:/work/backlog_records`）
- **2回目以降（出力に前回パスあり）かつ `--reconfigure` 未指定**: AskUserQuestion を出さず前回パスを silent に再利用する（`{確定したパス}` = 出力値）。チャットに1行通知する:
  > report_dir: `{前回のパス}`（プロジェクト設定により自動継続。再指定は `--reconfigure`）
- **2回目以降かつ `--reconfigure` 指定時**: AskUserQuestion でフォルダを選択する:
  - label: `{前回のパス} を使う`、description: "前回と同じフォルダに保存する"
  - label: `別のパスを指定する`、description: "新しいフォルダパスを絶対パスで入力する"
  - 「別のパスを指定する」が選ばれた場合はチャットで絶対パスを入力してもらう

確定したパスを `docs/.backlog_config.yml` の `report_dir` に保存する（既存エントリを保持してマージ）:

```bash
python -c "
import yaml, pathlib
p = pathlib.Path('docs/.backlog_config.yml')
d = yaml.safe_load(p.read_text(encoding='utf-8')) if p.exists() else {}
d['report_dir'] = '{確定したパス}'
p.write_text(yaml.dump(d, allow_unicode=True), encoding='utf-8')
"
```

`{件名}` から Windows 禁則文字を除去した `{件名_sanitized}` を生成する（出力値を変数として保持すること）:

```bash
python -c "import re,sys; print(re.sub(r'[/\\\\:*?\"<>|]', '_', sys.argv[1]))" "{件名}"
```

`{xlsx_folder}` = `{report_dir}/{issueID}_{件名_sanitized}`、`{evidence_dir}` = `{xlsx_folder}/evidence` として会話の最後まで保持する。

### 1.5.2 値の確認（Claude が必ず実行・スキップ不可）

`{xlsx_folder}` を以下の形式でチャットに表示する（実値で置換して表示すること）:

> **xlsx_folder** = `{xlsx_folder}`

次の **4 点**を確認し、1 つでも NG なら STOP してユーザに「Phase 1.5 を最初からやり直す」と伝える:

- `{` や `}` が含まれない（含む場合はプレースホルダー置換漏れ）
- 絶対パス形式（`C:/...` または `/...`）
- 親ディレクトリ（`{report_dir}`）が存在する:
  ```bash
  python -c "import pathlib; p=pathlib.Path('{report_dir}'); print('OK' if p.is_dir() else 'NG: '+str(p))"
  ```
- **`{xlsx_folder}` が `{report_dir}` と異なる**（`{issueID}_{件名_sanitized}` サブフォルダが付いている）:
  ```bash
  python -c "import pathlib; a=pathlib.Path('{report_dir}'); b=pathlib.Path('{xlsx_folder}'); print('OK' if a != b else 'NG: サブフォルダが付いていません。{issueID}_{件名_sanitized} の組み立て漏れを確認してください')"
  ```

すべて OK の場合のみ次へ進む。

---

### 1.5.3 investigation.md フロントマターへの書き戻し（必須・スキップ不可）

> **目的**: `/test` 起動時の xlsx_folder 解決 ① 一次ソースを確実に機能させる。省くと `/test` が `docs/logs/{issueID}/evidence` フォールバックに落ちてエビデンス・証跡が調査ログ置き場に出る。

`investigation.md` フロントマターに `xlsx_folder` / `evidence_dir` を書き込む:

```bash
python - <<'PYEOF'
import pathlib, re
invest = pathlib.Path('docs/logs/{issueID}/investigation.md')
text = invest.read_text(encoding='utf-8') if invest.exists() else ''
keys = {'xlsx_folder': '{xlsx_folder}', 'evidence_dir': '{evidence_dir}'}
if text.startswith('---'):
    end = text.index('---', 3)
    front = text[3:end]
    body = text[end+3:]
    for k, v in keys.items():
        if re.search(rf'^{k}:', front, re.MULTILINE):
            front = re.sub(rf'^{k}:.*$', f'{k}: {v}', front, flags=re.MULTILINE)
        else:
            front = front.rstrip('\n') + f'\n{k}: {v}\n'
    invest.write_text(f'---\n{front}---{body}', encoding='utf-8')
else:
    fm = '\n'.join(f'{k}: {v}' for k, v in keys.items())
    invest.write_text(f'---\n{fm}\n---\n\n{text}', encoding='utf-8')
print('[OK] investigation.md フロントマター更新完了')
PYEOF
```

書き戻し完了後チャットに表示:

> **xlsx_folder**: `{xlsx_folder}`  
> **evidence_dir**: `{evidence_dir}`  
> investigation.md フロントマターへの書き戻し完了

`.backlog_config.yml` に課題固有エントリを追記する（`/test` ② ルートの後方互換用）:

```bash
python -c "
import yaml, pathlib
p = pathlib.Path('docs/.backlog_config.yml')
d = yaml.safe_load(p.read_text(encoding='utf-8')) if p.exists() else {}
issues = d.setdefault('issues', {})
issues.setdefault('{issueID}', {}).update({'xlsx_folder': '{xlsx_folder}', 'evidence_dir': '{evidence_dir}'})
p.write_text(yaml.dump(d, allow_unicode=True), encoding='utf-8')
print('[OK] .backlog_config.yml 課題固有エントリ更新完了')
"
```

---

**xlsx ファイルの生成は Phase 3 末尾（実装方針確定後）で実施する。この時点では生成しない。**

> **エビデンス取得依頼は Phase 3 末尾（xlsx 生成後）で行う**。Phase 1.5 では xlsx ファイルがまだ存在しないため、貼付先を案内できない。

---

## 次に進む条件

フォルダパス確定後 — デプロイ適否判定セクション（backlog.md 末尾）を参照し、「Phase 2 に進んでよろしいですか？」とテキストで確認する。
