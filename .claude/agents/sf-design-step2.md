---
name: sf-design-step2
description: "sf-design コマンドから委譲されるプログラム設計ステップ。SF_ALIAS 取得・対象機能確定後、sf-screen-writer（画面系）→ sf-design-writer（Apex系 + 機能一覧）の順に委譲する。"
model: opus
tools:
  - Read
  - Glob
  - Grep
  - Bash
  - Agent
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

> **件数チェック＆バッチ分割**:
>
> ```bash
> python -c "
> import json, math
> with open(r'{tmp_dir}/feature_list.json', encoding='utf-8') as f:
>     fl = json.load(f)
> raw_ids = r'{target_ids}'
> try:
>     tids = set(json.loads(raw_ids)) if raw_ids.strip() and raw_ids.strip() != '[]' else set()
> except Exception:
>     tids = set(x.strip() for x in raw_ids.split(',') if x.strip())
> apex_types   = {'Apex', 'Batch', 'Integration', 'Trigger'}
> screen_types = {'LWC', '画面フロー', 'Visualforce', 'Aura'}
> targets     = [f for f in fl if not tids or f['id'] in tids]
> apex_list   = [f for f in targets if f.get('type') in apex_types]
> screen_list = [f for f in targets if f.get('type') in screen_types]
> total = len(apex_list) + len(screen_list)
> BATCH_SIZE = 50
> n_batches = max(1, math.ceil(total / BATCH_SIZE))
> all_ids = [f['id'] for f in targets]
> batches = [all_ids[i:i+BATCH_SIZE] for i in range(0, len(all_ids), BATCH_SIZE)]
> print(f'total:{total}')
> print(f'apex:{len(apex_list)}')
> print(f'screen:{len(screen_list)}')
> print(f'n_batches:{n_batches}')
> for i, b in enumerate(batches):
>     print(f'batch_{i}:' + ','.join(b))
> "
> ```
>
> 出力から `total` / `n_batches` / `batch_N` を読み取り保持する。
> - `total ≤ 50`: `n_batches=1`、`batch_0` = 全件 → Phase 5 を1回だけ実行（既存と同じ）
> - `total > 50`: `n_batches` 回のループを Phase 5 で実行。各バッチ開始時に「バッチ {i+1}/{n_batches} 処理中（{len(batch_i)} 件）」と出力する

---

## Phase 5: 処理の委譲（バッチループ）

> **実行順序は必ず守ること**: sf-design-writer の機能一覧生成は sf-screen-writer が出力した design JSON も収集するため、sf-screen-writer を先に完了させてから sf-design-writer を起動する。

**上位設計 JSON の参照**: `detail_design_tmp` が渡されている場合（step1 連鎖時）、その旨をエージェント起動時に明示する。

`n_batches` 回ループする（`batch_i = 0` から `n_batches - 1`）。各バッチ開始時に「バッチ {i+1}/{n_batches} 処理中」と出力する。前のバッチの完了を確認してから次へ進む。

**各バッチで `current_batch_ids = batch_{i}` のIDリストを確定し、以下の順で委譲する:**

**① 画面系 → sf-screen-writer（current_batch_ids に画面系が1件以上ある場合のみ実行）:**
```
project_dir:       {project_dir}
output_dir:        {output_dir}/03_プログラム設計
tmp_dir:           {tmp_dir}
author:            {author}
project_name:      {project_name}
sf_alias:          {sf_alias}
feature_list:      {feature_list}（全件。sf-screen-writer が自前で画面系のみ type フィルタする）
target_ids:        {current_batch_ids}（このバッチのIDのみ）
version_increment: {version_increment}
上位設計参照:      {detail_design_tmp}（渡されている場合。なければ省略）
```

sf-screen-writer の完了を確認してから次へ進む。

**② Apex系 → sf-design-writer（current_batch_ids に Apex系が1件以上ある場合のみ実行）:**
```
project_dir:           {project_dir}
output_dir:            {output_dir}/03_プログラム設計
tmp_dir:               {tmp_dir}
feature_list_dir:      {output_dir}/01_基本設計
author:                {author}
project_name:          {project_name}
feature_list:          {feature_list}（全件。エージェント側が Apex 系のみフィルタする）
target_ids:            {current_batch_ids}（このバッチのIDのみ）
version_increment:     {version_increment}
generate_feature_list: {最終バッチ（i == n_batches - 1）なら true、それ以外は false}
skip_cleanup:          {最終バッチ（i == n_batches - 1）なら false、それ以外は true}
上位設計参照:          {detail_design_tmp}（渡されている場合。なければ省略）
```

sf-design-writer の完了を確認してから次のバッチへ進む。

> **current_batch_ids に画面系のみ含まれる場合**: sf-screen-writer のみ実行。sf-design-writer はスキップ。
> **current_batch_ids に Apex系のみ含まれる場合**: sf-screen-writer をスキップ。sf-design-writer のみ実行。
> **どちらも0件のバッチ**: スキップして次のバッチへ。

> **ループ完了後**: 最終バッチの sf-design-writer が `generate_feature_list=true` で機能一覧 Excel を生成し `tmp_dir` を削除する。このエージェントでは追加クリーンアップ不要。

テンプレートパス（sf-design-writer / sf-screen-writer に参考として伝える）:
- Apex/Flow/Batch/Integration: `{project_dir}/scripts/python/sf-doc-mcp/プログラム設計書テンプレート.xlsx`
- LWC/画面フロー/VF/Aura: `{project_dir}/scripts/python/sf-doc-mcp/プログラム設計書（画面）テンプレート.xlsx`

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
