---
name: sf-design-step2
description: "sf-design コマンドから委譲されるプログラム設計ステップ。SF_ALIAS 取得・対象機能確定後、sf-screen-writer（画面系）→ sf-design-writer（Apex系 + 機能一覧）の順に委譲する。"
model: opus
tools:
  - Read
  - Glob
  - Grep
  - Bash
  - Task
  - TodoWrite
---

> **禁止事項**: `scripts/` 配下の Python スクリプトを修正・上書きしてはならない。エラーや不具合を発見した場合は修正せず、完了報告に「要修正: {ファイル名} — {問題の概要}」として報告するにとどめること。

> **スクリプト呼び出しはフルパスで行うこと**。エージェント実行時は CWD が不定のため、`python "{project_dir}/scripts/..."` 形式を使用する。

# sf-design-step2: プログラム設計ステップ

sf-design コマンドから委譲されて実行する。プログラム設計書の生成処理を担当する。

---

## 受け取る情報

| 項目 | 内容 |
|---|---|
| `project_dir` | プロジェクトルート |
| `output_dir` | 出力先フォルダ（基準。`{output_dir}/03_プログラム設計/` に生成される） |
| `author` | 作成者名 |
| `project_name` | プロジェクト名 |
| `sf_alias` | Salesforce 組織エイリアス（orchestrator で確定済み）|
| `target_group_ids` | 対象グループIDリスト（step1 連鎖時は確定済み）。`[]` の場合は全件対象 |
| `step0_3_done` | `true` の場合 step1 連鎖（グループ→機能ID変換を自動実行）。`false` の場合は単独実行（orchestrator 確定済みの target_ids をそのまま使う）|
| `target_ids` | 対象機能IDリスト（step0_3_done=false 時、orchestrator の Step 0-5 で確定済み。空リスト = 全件対象）|
| `detail_design_tmp` | 詳細設計の tmp フォルダパス（step1 連鎖時のみ渡される。省略された場合は上位設計参照なし） |
| `version_increment` | `"minor"` / `"major"` |

---

## Phase 1: ディレクトリ準備

```bash
mkdir -p "{output_dir}/01_基本設計" && mkdir -p "{output_dir}/03_プログラム設計"
```

一時フォルダはローカルドライブに生成する（共有ドライブへの書き込み・自動削除を避けるため）:
```bash
python -c "
import tempfile, pathlib
tmp = pathlib.Path(tempfile.mkdtemp(prefix='sf-design-step2-'))
print('tmp_dir:' + str(tmp).replace(chr(92), '/'))
"
```

出力の `tmp_dir:` 以降の値を **`tmp_dir`** として保持する。

---

## Phase 2: 機能リスト読み込み

`docs/.sf/feature_list.json` を tmp にコピーして使う（再スキャンは行わない — 二重実行・差分防止）:
```bash
python -c "
import shutil, pathlib, sys
src = pathlib.Path(r'{project_dir}/docs/.sf/feature_list.json')
dst = pathlib.Path(r'{tmp_dir}/feature_list.json')
if not src.exists():
    print('ERROR: docs/.sf/feature_list.json が見つかりません。先に /sf-memory（カテゴリ4）を実行してください。')
    sys.exit(1)
shutil.copy2(src, dst)
import json
fl = json.loads(src.read_text(encoding='utf-8'))
print(f'読み込み完了: {len(fl)} 件')
from collections import Counter
cnt = Counter(f.get('type','?') for f in fl)
for t, n in sorted(cnt.items()): print(f'  {t}: {n}件')
"
```

---

## Phase 3: 対象機能の確定

### step0_3_done = true の場合（step1 連鎖）

`target_group_ids` に属する機能IDを自動抽出する（AskUserQuestion 不要）:
```bash
python -c "
import yaml, json, pathlib
with open(r'{project_dir}/docs/.sf/feature_groups.yml', encoding='utf-8') as f:
    _grp_data = yaml.safe_load(f)
groups = _grp_data.get('groups', []) if isinstance(_grp_data, dict) else (_grp_data or [])
raw = '{target_group_ids}'
try:
    gid_list = json.loads(raw) if raw.strip() else []
except (json.JSONDecodeError, ValueError):
    gid_list = [x.strip() for x in raw.split(',') if x.strip()]
if not gid_list:
    print('total:全件（グループ指定なし）')
else:
    target_groups = set(gid_list)
    fids = []
    for g in groups:
        if g['group_id'] in target_groups:
            fids.extend(g.get('feature_ids', []))
    for fid in fids:
        print(f'feature_id:{fid}')
    print(f'total:{len(fids)}件')
"
```
出力の `feature_id:` 以降を `target_ids` として使用する。`target_group_ids` が空（全グループ）の場合は `target_ids = []`。

### step0_3_done = false の場合（単独実行）

`target_ids` は orchestrator (sf-design.md Step 0-5) で確定済みのパラメータとして受け取る。空リストなら全件対象。

---

## Phase 4: feature_list の読み込み

`{tmp_dir}/feature_list.json` を Read ツールで読み込み、内容を `feature_list` として保持する。

```bash
python -c "
import json
with open(r'{tmp_dir}/feature_list.json', encoding='utf-8') as f:
    fl = json.load(f)
apex_types = {'Apex', 'Batch', 'Integration', 'Trigger'}
screen_types = {'LWC', '画面フロー', 'Visualforce', 'Aura'}
apex_list = [f for f in fl if f.get('type') in apex_types]
screen_list = [f for f in fl if f.get('type') in screen_types]
print(f'Apex系（sf-design-writer対象）: {len(apex_list)}件')
print(f'画面系（sf-screen-writer対象）: {len(screen_list)}件')
"
```

> **⚠️ 件数上限チェック（50件超 warn）**: Phase 4 で確認した Apex系 + 画面系の合計件数が **50件を超える場合**、Phase 5 委譲前に以下の warn を必ず出力する（処理は中断せず続行する）:
>
> ```
> ⚠️ 対象 {N} 件（Apex系 {n1} 件 + 画面系 {n2} 件）は推奨上限（50件/回）を超えています。
> コンテキスト圧迫により sf-design-writer / sf-screen-writer が途中で止まるリスクがあります。
> 推奨: /sf-design → プログラム設計のみ を 50件単位に分割して複数回実行してください。
> このまま全件処理を続行します（中止したい場合は Ctrl+C または /sf-design を再実行してください）。
> ```

---

## Phase 5: 処理の委譲（① sf-screen-writer → ② sf-design-writer の順）

> **実行順序は必ず守ること**: sf-design-writer の機能一覧生成は sf-screen-writer が出力した design JSON も収集するため、sf-screen-writer を先に完了させてから sf-design-writer を起動する。

**上位設計 JSON の参照**: `detail_design_tmp` が渡されている場合（step1 連鎖時）、その旨をエージェント起動時に明示する。

**① LWC・画面フロー・Visualforce・Aura → sf-screen-writer に委譲（先に実行）:**
```
project_dir:       {project_dir}
output_dir:        {output_dir}/03_プログラム設計
tmp_dir:           {tmp_dir}
author:            {author}
project_name:      {project_name}
sf_alias:          {sf_alias}
feature_list:      {feature_list}（全件。sf-screen-writer が自前で画面系のみ type フィルタする）
target_ids:        {target_ids}
version_increment: {version_increment}
上位設計参照:      {detail_design_tmp}（渡されている場合。なければ省略）
```

sf-screen-writer の完了を確認してから次へ進む。

**② Apex・Batch・Flow(非画面)・Integration → sf-design-writer に委譲（sf-screen-writer 完了後）:**
```
project_dir:       {project_dir}
output_dir:        {output_dir}/03_プログラム設計
tmp_dir:           {tmp_dir}
feature_list_dir:  {output_dir}/01_基本設計
author:            {author}
project_name:      {project_name}
feature_list:      {feature_list}（全件。エージェント側が Apex 系のみフィルタする）
target_ids:        {target_ids}
version_increment: {version_increment}
上位設計参照:      {detail_design_tmp}（渡されている場合。なければ省略）
```

sf-design-writer は機能一覧（全コンポーネント索引 Excel）を `{output_dir}/01_基本設計/機能一覧.xlsx` に生成する。sf-screen-writer の design JSON が `{tmp_dir}` に揃っている状態で起動すること。

テンプレートパス:
- Apex/Flow/Batch/Integration: `{project_dir}/scripts/python/sf-doc-mcp/プログラム設計書テンプレート.xlsx`
- LWC/画面フロー/VF/Aura: `{project_dir}/scripts/python/sf-doc-mcp/プログラム設計書（画面）テンプレート.xlsx`

sf-design-writer の完了を確認してからこのエージェントを終了する。

---

## Phase 最終: クリーンアップ

`{tmp_dir}` の削除は sf-design-writer Phase 4 が担う。このエージェントでは実施しない。

---

## 完了報告

```
【プログラム設計完了】
  生成先: {output_dir}/03_プログラム設計/
  Apex系: {n} 件生成
  画面系（LWC/VF/Aura/画面フロー）: {n} 件生成
  機能一覧: {output_dir}/01_基本設計/機能一覧.xlsx（生成した場合）

⚠️ 要確認:
- {要確認事項}（なければ省略）
```
