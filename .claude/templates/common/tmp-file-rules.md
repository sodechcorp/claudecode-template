# 一時ファイルの禁止ルール（厳守）

> **一時ファイルの禁止ルール（厳守）**:
> - 処理中に作成する全ての一時ファイル（`.json` / `.txt` / `.py` / その他）は **必ず `{tmp_dir}` 配下のみ** に置くこと
> - `{tmp_dir}` の標準パスは `{output_dir}/.tmp` サブディレクトリ。`{output_dir}` 直下への一時ファイル配置は禁止だが、`{output_dir}/.tmp` は許容範囲
> - **例外**: sf-design系エージェント（sf-screen-writer / sf-design-writer / sf-detail-design-writer）は共有ドライブへの書き込みを避けるため、呼び出し元（sf-design-step1 / sf-design-step2）が `tempfile.mkdtemp()` で生成したOSローカルパスを `{tmp_dir}` として使用する。この3エージェントに限り `{tmp_dir}` は `{output_dir}/.tmp` ではない
> - スクリプトの実行結果（stdout / stderr）を `.txt` や任意ファイルにリダイレクト保存してはならない。出力は Claude が直接読む
> - カレントディレクトリ（プロジェクトルート）・`output_dir` 直下への一時ファイル作成は全て禁止
