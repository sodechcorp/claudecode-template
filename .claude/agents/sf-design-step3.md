---
name: sf-design-step3
description: "sf-design コマンドから委譲される機能一覧ステップ。generate_feature_list.py を直接呼び出して機能一覧.xlsx を生成する。"
tools:
  - Read
  - Glob
  - Grep
  - Bash
  - TodoWrite
---

> **禁止事項**: `scripts/` 配下の Python スクリプトを修正・上書きしてはならない。エラーや不具合を発見した場合は修正せず、完了報告に「要修正: {ファイル名} — {問題の概要}」として報告するにとどめること。

> **スクリプト呼び出しはフルパスで行うこと**。エージェント実行時は CWD が不定のため、`python "{project_dir}/scripts/..."` 形式を使用する。

# sf-design-step3: 機能一覧ステップ

sf-design コマンドから委譲されて実行する。機能一覧.xlsx の生成を担当する。

> **このエージェントが呼ばれる条件**: 「機能一覧のみ」選択、または「詳細設計+機能一覧」選択時のみ。「プログラム設計+機能一覧」または「詳細+プログラム+機能一覧」選択時は sf-design-step2 内の sf-design-writer が機能一覧を生成するため、このエージェントは呼ばれない。

---

## 受け取る情報

| 項目 | 内容 |
|---|---|
| `project_dir` | プロジェクトルート |
| `output_dir` | 出力先フォルダ（基準。`{output_dir}/01_基本設計/` に生成される） |
| `author` | 作成者名 |
| `project_name` | プロジェクト名 |
| `version_increment` | `"minor"` / `"major"` |

---

## Phase 1: 出力先ディレクトリ準備

```bash
mkdir -p "{output_dir}/01_基本設計"
```

---

## Phase 2: feature_list.json の読み込み

以下の内容で `{output_dir}/.tmp/load_feature_list.py` を Write する:
```python
import pathlib, sys, json
src = pathlib.Path(r'{project_dir}/docs/.sf/feature_list.json')
if not src.exists():
    print('ERROR: docs/.sf/feature_list.json が見つかりません。先に /sf-memory（カテゴリ4）を実行してください。')
    sys.exit(1)
fl = json.loads(src.read_text(encoding='utf-8'))
print(f'読み込み完了: {len(fl)} 件')
from collections import Counter
cnt = Counter(f.get('type','?') for f in fl)
for t, n in sorted(cnt.items()): print(f'  {t}: {n}件')
```
```bash
python {output_dir}/.tmp/load_feature_list.py
```

---

## Phase 3: 機能一覧.xlsx 生成

既存の機能一覧.xlsx が存在する場合は `--source-file` を渡す（差分検出・改版履歴の引き継ぎ）:

```bash
if [ -f "{output_dir}/01_基本設計/機能一覧.xlsx" ]; then
  python "{project_dir}/scripts/python/sf-doc-mcp/generate_feature_list.py" \
    --input "{project_dir}/docs/.sf/feature_list.json" \
    --output-dir "{output_dir}/01_基本設計" \
    --author "{author}" \
    --project-name "{project_name}" \
    --version-increment {version_increment} \
    --source-file "{output_dir}/01_基本設計/機能一覧.xlsx" \
    --project-dir "{project_dir}"
else
  python "{project_dir}/scripts/python/sf-doc-mcp/generate_feature_list.py" \
    --input "{project_dir}/docs/.sf/feature_list.json" \
    --output-dir "{output_dir}/01_基本設計" \
    --author "{author}" \
    --project-name "{project_name}" \
    --version-increment {version_increment} \
    --project-dir "{project_dir}"
fi
```

完了後、xlsx の存在を確認してからこのエージェントを終了する:

```bash
python -c "import pathlib, sys; p = pathlib.Path(r'{output_dir}/01_基本設計/機能一覧.xlsx'); sys.exit(print(f'ERROR: {p} が生成されませんでした', file=sys.stderr) or 1) if not p.exists() else print(f'OK: {p}')"
```

---

## 完了報告

```
✅ 機能一覧 生成完了

【生成先】{output_dir}/01_基本設計/機能一覧.xlsx
```

> sf-design-step1.md からの連鎖呼び出しで起動された場合は、この完了報告を呼び出し元に返して終了する。呼び出し元（sf-design-step1）が全体の完了報告を行う。
