# 一時ファイルの後片付け（全エージェント共通）

作業用の `tmp_dir` を使ったエージェントは、成果物書き出し後・完了報告前に必ず削除する。

## 削除コマンド

```bash
python -c "import shutil; shutil.rmtree(r'{tmp_dir}', ignore_errors=True)"
```

## 原則

1. **削除タイミング**: 最終 Phase の成果物書き出し完了後、完了報告の直前
2. **成功時のみ削除**: 途中でエラー終了した場合は残してデバッグに使う
3. **対象**: 自エージェントが作成した `tmp_dir` のみ。`output_dir`・`project_dir` 直下の既存ファイルには触れない

エージェント定義への組み込み方・確認コマンド: `.claude/templates/common/agent-cleanup-template.md` 参照
