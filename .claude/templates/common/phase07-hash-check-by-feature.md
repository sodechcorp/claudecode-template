# Phase 0.7: ハッシュチェック（コンポーネント単位）

> **目的**: 変更のないコンポーネントをスキップして LLM 呼び出しと Excel 生成を節約する。

対象コンポーネント全件に対して以下を実行し、スキップリストを作成する。

> **`feat_id`** は feature_list 各要素の `id` フィールド値（例: `F-001`）。呼び出し元から渡されるパラメータではなく、feature_list を反復するループ内で各要素から取得する変数。

```bash
# 既存 Excel の自動検出（feature_id = feat_id フィールド）
python -c "
import pathlib, sys
feat_id = '{feat_id}'
out = pathlib.Path(r'{output_dir}')
for sub in out.iterdir():
    if sub.is_dir():
        for f in sub.glob(f'【{feat_id}】*.xlsx'):
            print(f)
            sys.exit()
print('')
"
```

```bash
# ハッシュチェック（source_file は feature_list の source_file フィールド）
python "{project_dir}/scripts/python/sf-doc-mcp/source_hash_checker.py" \
  --source-paths "{source_file}" \
  --existing-excel "{detected_excel_or_empty}"
```

| stdout の status | 終了コード | 対応 |
|---|---|---|
| `status:MATCH` | 0 | このコンポーネントをスキップリストに追加（Phase 0.5 / Phase 1 / Phase 2 全てスキップ） |
| `status:CHANGED` / `NEW` / `NO_HASH` | 1 | 通常どおり処理する。`hash:XXXX` の値を `{source_hash}` として記録する |

全コンポーネントのチェック完了後、スキップしない対象だけを以降の Phase で処理する。
