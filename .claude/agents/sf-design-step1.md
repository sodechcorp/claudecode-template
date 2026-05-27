---
name: sf-design-step1
description: "sf-design コマンドから委譲される詳細設計ステップ専用エージェント。グループ確定・詳細設計の実行・必要に応じた後続エージェント（sf-design-step2/step3）への連鎖呼び出しを担う。"
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

# sf-design-step1: 詳細設計ステップ

sf-design コマンドから委譲されて実行する。グループ確定済みパラメータを受け取り、詳細設計書生成 → 後続エージェント連鎖呼び出しを担当する。

---

## 受け取る情報

| 項目 | 内容 |
|---|---|
| `project_dir` | プロジェクトルート |
| `output_dir` | 出力先フォルダ（基準。`{output_dir}/02_詳細設計/` に生成される） |
| `author` | 作成者名 |
| `project_name` | プロジェクト名 |
| `version_increment` | `"minor"` / `"major"` |
| `selected_steps` | 選択された種別リスト（例: `["詳細設計", "プログラム設計"]`） |
| `target_group_ids` | 対象グループIDリスト（orchestrator で確定済み。空リスト `[]` = 全グループ）|
| `sf_alias` | Salesforce 組織エイリアス（orchestrator で確定済み。「プログラム設計」を伴う場合のみ渡される）|

---

## Phase 1: ディレクトリ準備

```bash
mkdir -p "{output_dir}/02_詳細設計"
```

一時フォルダはローカルドライブに生成する（共有ドライブへの書き込み・自動削除を避けるため）:
```bash
python -c "
import tempfile, pathlib
tmp = pathlib.Path(tempfile.mkdtemp(prefix='sf-design-step1-'))
print('tmp_dir:' + str(tmp).replace(chr(92), '/'))
"
```

出力の `tmp_dir:` 以降の値を **`tmp_dir`** として保持する。

---

## Phase 2: sf-detail-design-writer に委譲

以下の情報を渡して **sf-detail-design-writer** エージェントを起動する:

```
project_dir:           {project_dir}
output_dir:            {output_dir}/02_詳細設計
tmp_dir:               {tmp_dir}
author:                {author}
project_name:          {project_name}
target_group_ids:      {target_group_ids}  # 全グループの場合は空リスト []
version_increment:     {version_increment}
```

sf-detail-design-writer の完了を確認してから Phase 3 へ進む。

---

## Phase 3: 連鎖呼び出し

`selected_steps` に応じて後続エージェントを呼び出す。

### "プログラム設計" が含まれる場合 → sf-design-step2 を呼び出す

```
project_dir:       {project_dir}
output_dir:        {output_dir}
author:            {author}
project_name:      {project_name}
version_increment: {version_increment}
target_group_ids:  {target_group_ids}
step0_3_done:      true
detail_design_tmp: {tmp_dir}
sf_alias:          {sf_alias}
```

> `selected_steps` に "機能一覧" が含まれる場合も sf-design-step2 が機能一覧を生成する。sf-design-step3 は呼ばない。

### "機能一覧" が含まれるが "プログラム設計" は選択なし → sf-design-step3 を呼び出す

```
project_dir:       {project_dir}
output_dir:        {output_dir}
author:            {author}
project_name:      {project_name}
version_increment: {version_increment}
```

### どちらも選択なし（詳細設計のみ）

後続エージェントなし。そのまま完了する。

---

## Phase 最終: クリーンアップ
[共通ルール参照](.claude/CLAUDE.md#一時ファイルの後片付け全エージェント共通)

```bash
python -c "import shutil; shutil.rmtree(r'{tmp_dir}', ignore_errors=True)"
```

---

## 完了報告

以下の形式で全体完了を報告する（sf-design.md の完了報告フォーマットに準拠）:

```
✅ 設計書生成完了

【機能一覧】（selected_steps に "機能一覧" を含み生成した場合）
  生成先: {output_dir}/01_基本設計/機能一覧.xlsx

【詳細設計】
  生成先: {output_dir}/02_詳細設計/
  生成数: {n} グループ

【プログラム設計】（selected_steps に "プログラム設計" を含み生成した場合）
  生成先: {output_dir}/03_プログラム設計/
  生成数: {n} 件

⚠️ 要確認:
- {FG-XXX}: 生成失敗の概要（例: 関連オブジェクトが特定できなかった）
- 未分類コンポーネント {n} 件
（要確認事項がない場合はこのセクションごと省略）
```

> 後続の連鎖呼び出し（step2/step3）から返された完了情報をまとめて本報告に統合すること。sf-design.md コマンドはこの完了報告をそのまま転記する。
