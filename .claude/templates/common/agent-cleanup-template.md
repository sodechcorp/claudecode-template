# 一時ファイル後片付けテンプレート（エージェント定義用）

`tmp_dir` を使用するエージェントの Phase 最終に組み込む実装パターン。原則（削除タイミング・対象・`{tmp_dir}` 以外を削除する場合の注意）は [cleanup-rules.md](../../spec/cleanup-rules.md) を参照。

## エージェント定義への組み込み方

各エージェント定義の末尾に `## Phase 最終: クリーンアップ` セクションを置く:

```markdown
## Phase 最終: クリーンアップ
[共通ルール参照](../spec/cleanup-rules.md)

python -c "import shutil; shutil.rmtree(r'{tmp_dir}', ignore_errors=True)"
python -c "import os; print('削除成功' if not os.path.exists(r'{tmp_dir}') else '削除失敗（残存）')"
```
