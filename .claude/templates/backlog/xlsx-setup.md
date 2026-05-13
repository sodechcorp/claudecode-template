# Phase 1.5: xlsx フォルダパスの確定 — 実行手順

---

## 「作成しない」が選ばれた場合

`{xlsx_folder}` = null、`{evidence_dir}` = `docs/logs/{issueID}/evidence` として Phase 2 へ進む。

> **エビデンス取得依頼は Phase 3 末尾（実装方針確定後・実装直前）で行う**。Phase 1.5 ではフォルダ確定のみを行い、ユーザに作業負荷をかけない。

---

## 「作成する」が選ばれた場合

### フォルダパスの確定

`docs/.backlog_config.yml` を確認する（出力が空の場合は初回として扱う）:

```bash
python -c "import yaml,pathlib; p=pathlib.Path('docs/.backlog_config.yml'); d=yaml.safe_load(p.read_text(encoding='utf-8')) if p.exists() else {}; print(d.get('report_dir',''))"
```

- **初回（出力が空）**: 保存先フォルダパスをテキストで入力してもらう（絶対パスで指定。例: `C:/work/backlog_records`）
- **2回目以降（出力に前回パスあり）**: AskUserQuestion でフォルダを選択する:
  - label: `{前回のパス} を使う`、description: "前回と同じフォルダに保存する"
  - label: `別のパスを指定する`、description: "新しいフォルダパスを絶対パスで入力する"
  - 「別のパスを指定する」が選ばれた場合はチャットで絶対パスを入力してもらう

確定したパスを `docs/.backlog_config.yml` の `report_dir` に保存する:

```bash
python -c "import yaml,pathlib; pathlib.Path('docs/.backlog_config.yml').write_text(yaml.dump({'report_dir': '{確定したパス}'}), encoding='utf-8')"
```

`{件名}` から Windows 禁則文字を除去した `{件名_sanitized}` を生成する（出力値を変数として保持すること）:

```bash
python -c "import re,sys; print(re.sub(r'[/\\\\:*?\"<>|]', '_', sys.argv[1]))" "{件名}"
```

`{xlsx_folder}` = `{report_dir}/{issueID}_{件名_sanitized}`、`{evidence_dir}` = `{xlsx_folder}/evidence` として会話の最後まで保持する。

### 1.5.2 値の確認（Claude が必ず実行・スキップ不可）

`{xlsx_folder}` を以下の形式でチャットに表示する（実値で置換して表示すること）:

> **xlsx_folder** = `{xlsx_folder}`

次の 3 点を確認し、1 つでも NG なら STOP してユーザに「Phase 1.5 を最初からやり直す」と伝える:

- `{` や `}` が含まれない（含む場合はプレースホルダー置換漏れ）
- 絶対パス形式（`C:/...` または `/...`）
- 親ディレクトリ（`{report_dir}`）が存在する:
  ```bash
  python -c "import pathlib; p=pathlib.Path('{report_dir}'); print('OK' if p.is_dir() else 'NG: '+str(p))"
  ```

すべて OK の場合のみ次へ進む。

**xlsx ファイルの生成は Phase 3 末尾（実装方針確定後）で実施する。この時点では生成しない。**

> **エビデンス取得依頼は Phase 3 末尾（xlsx 生成後）で行う**。Phase 1.5 では xlsx ファイルがまだ存在しないため、貼付先を案内できない。

---

## 次に進む条件

フォルダパス確定後 — デプロイ適否判定セクション（backlog.md 末尾）を参照し、「Phase 2 に進んでよろしいですか？」とテキストで確認する。
