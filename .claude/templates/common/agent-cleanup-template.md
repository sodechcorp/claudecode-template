# 一時ファイル後片付けテンプレート（エージェント定義用）

`tmp_dir`・作業フォルダを使うエージェントの Phase 最終に組み込む実装パターン。原則（削除タイミング・対象・`{tmp_dir}` 以外を削除する場合の注意）は [cleanup-rules.md](../../spec/cleanup-rules.md) を参照。

## エージェント定義への組み込み方

各エージェント定義の末尾に `## Phase 最終: クリーンアップ` セクションを置く:

```markdown
## Phase 最終: クリーンアップ
[共通ルール参照](../spec/cleanup-rules.md)

python -c "import shutil; shutil.rmtree(r'{tmp_dir}', ignore_errors=True)"
python -c "import os; print('削除成功' if not os.path.exists(r'{tmp_dir}') else '削除失敗（残存）')"
```

この形は `{tmp_dir}` が `tempfile.mkdtemp()` 由来のときだけ使う。project_dir 配下や、作成場所が決まっていない作業フォルダ・一時ファイルは、[cleanup-rules.md](../../spec/cleanup-rules.md) の project_dir 配下の削除に従い、絶対パスにして次の形にする（相対パスのまま `cd` して消す形は、cleanup-rules.md の実装例の release-preparer.md）:

```bash
TARGET="<作成した作業フォルダ・一時ファイルの絶対パス>" python -c "import os, shutil, sys, tempfile; p = os.environ['TARGET']; os.path.isabs(p) and os.path.splitdrive(p)[0] or sys.exit('絶対パスではありません: ' + p); n = lambda x: os.path.normcase(os.path.abspath(x)).rstrip(os.sep) + os.sep; (os.path.dirname(os.path.abspath(p)) == os.path.abspath(p) or any(n(x).startswith(n(p)) for x in (tempfile.gettempdir(), os.path.expanduser('~'), os.getcwd(), os.environ.get('SHELL') or shutil.which('sh') or sys.executable))) and sys.exit('消してはいけない場所です（ドライブ直下・一時フォルダ・ホーム・作業中のフォルダ・シェルの場所か、その親）: ' + p); os.path.lexists(p) or sys.exit('見つかりません（パスの誤りか作成していない）: ' + p); shutil.rmtree(p) if os.path.isdir(p) else os.remove(p); sys.exit('削除失敗（残存）: ' + p) if os.path.exists(p) else print('削除成功')"
```
