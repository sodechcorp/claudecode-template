# 一時ファイル後片付けテンプレート（エージェント定義用）

`tmp_dir` を使用するエージェントの Phase 最終に組み込む実装パターン。

## 実行コマンド

```bash
python -c "import shutil; shutil.rmtree(r'{tmp_dir}', ignore_errors=True)"
```

## 確認コマンド

```bash
python -c "import os; print('削除成功' if not os.path.exists(r'{tmp_dir}') else '削除失敗（残存）')"
```

## 原則

1. **削除タイミング**: 最終 Phase の成果物書き出し完了後、完了報告の直前
2. **成功時のみ削除**: 途中でエラー終了した場合は残してデバッグに使う
3. **対象**: 自エージェントが作成した `tmp_dir` のみ。他エージェントの作業フォルダや `output_dir`・`project_dir` 直下の既存ファイルには触れない
4. **確認**: 削除後に `os.path.exists(tmp_dir)` が False であることを確認してから完了報告

## エージェント定義への組み込み方

各エージェント定義の末尾に `## Phase 最終: クリーンアップ` セクションを置く:

```markdown
## Phase 最終: クリーンアップ
[共通ルール参照](../spec/cleanup-rules.md)

python -c "import shutil; shutil.rmtree(r'{tmp_dir}', ignore_errors=True)"
```
