# option-similar-past-issue

## 何をするか

現課題と同症状・同機能領域の過去完了課題を `pattern-curator` で検索し、対応実績・採用方針・根本原因を investigation.md に記録する。

## 実行手順

1. 現課題の機能領域・症状のキーワードを 3〜5 個抽出する（課題本文・コメントから）
2. `pattern-curator` を Task ツールで起動する:
   ```
   現課題ID: {issueID}
   キーワード: {抽出した症状・機能領域キーワード 3〜5 個（スペース区切り）}
   プロジェクトルート: {project_dir}
   ```
3. `pattern-curator` から返却された結果を investigation.md の「類似過去課題」セクションに追記する

## 出力

investigation.md に追記（pattern-curator の返却フォーマットをそのまま貼り付け）:

```markdown
## 類似過去課題

{pattern-curator の返却内容をそのまま記載}
```
