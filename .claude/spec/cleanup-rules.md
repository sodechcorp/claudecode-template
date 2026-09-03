# 一時ファイルの後片付け（全エージェント共通）

作業用の `tmp_dir` を使ったエージェントは、成果物書き出し後・完了報告前に必ず削除する。

## 削除コマンド

```bash
python -c "import shutil; shutil.rmtree(r'{tmp_dir}', ignore_errors=True)"
```

## 原則

1. **削除タイミング**: 最終 Phase の成果物書き出し完了後、完了報告の直前
2. **成功時のみ削除**: 途中でエラー終了した場合は残してデバッグに使う
3. **対象**: 自エージェントが作成した `tmp_dir` のみ。他エージェントの作業フォルダや `output_dir`・`project_dir` 直下の既存ファイルには触れない。**例外**: コマンド（`/backlog` Phase 6 等）が成果物ライフサイクル上明示的に指示する project_dir 配下の削除は、下記「`{tmp_dir}` 以外を削除する場合の注意」に従うことを条件に許可する
4. **確認**: 削除後に `os.path.exists(tmp_dir)` が False であることを確認してから完了報告

> 本ファイルが後片付け原則の正本。エージェント定義への埋め込み雛形・確認コマンドは `.claude/templates/common/agent-cleanup-template.md` が管理する。

## `{tmp_dir}` 以外（`{log_dir}` 等 project_dir 配下）を削除する場合の注意（2026-09-03）

上記の標準コマンド（`ignore_errors=True`）が安全なのは、`{tmp_dir}` が `tempfile.mkdtemp()` 由来のシステム一時ディレクトリで、存在しない・削除済みでも実害がないケースに限定されるからである。`{log_dir}`／`{project_dir}` 配下など、**実データを含み削除失敗を必ず検知すべきパス**では `ignore_errors=True` を使わない。

実際に日本語ディレクトリ名を含む project_dir で、`python -c` のソースコード文字列にパスを直接埋め込んだ削除が「何も削除されないまま成功したように見えた」事例が発生した（GF-369 等 7 課題の `docs/logs/{issueID}/repro/` 削除、2026-09-03）。原因が Git Bash の引数展開の文字化けそのものかは確定していないが、`ignore_errors=True` がその失敗を握りつぶし、完了報告と実体が食い違う結果になった点は実測で確認済み。

project_dir 配下を削除する場合は必ず:
1. **`ignore_errors=True` を使わない**。削除後に `os.path.exists()` で成功を確認し、失敗時は警告を出す（最も重要）
2. パスは環境変数経由で渡すことを推奨する（`TARGET="{path}" python -c "...os.environ['TARGET']..."`）。ソースコード文字列への直接埋め込みで文字化けが起きる場合の回避策になる

実装例: [backlog.md](../commands/backlog.md) Phase 6 完了時の `repro/` 削除処理を参照。
