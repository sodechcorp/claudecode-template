# option-git-blame-history

## 何をするか

git blame で変更対象ファイルの過去変更履歴と変更理由を確認し、現在の実装に至った経緯を把握する。

## 実行手順

1. 対象行が分かっている場合は git blame でその行を最後に変更したコミットを確認し、git log -L でその行範囲の修正回数を数える（繰り返し修正の判定に使う）:
   ```bash
   git blame -L <start>,<end> -- {ファイルパス}
   git log -L <start>,<end>:{ファイルパス} --oneline -s
   ```
   ハッシュが `00000000`（Not Committed Yet）の行は未コミットの変更のため、git show では確認できない（作業ツリーを直接確認する）。

   対象行が不明な場合（ファイル全体の変更経緯を把握したい場合）は git log にフォールバックする:
   ```bash
   git log --oneline -20 -- {ファイルパス}
   ```
2. 関連する過去コミットを特定して詳細を確認する:
   ```bash
   git show {コミットハッシュ}
   ```
3. 以下を確認する:
   - 現在の実装はいつ・なぜ変更されたか
   - 過去の変更コメントに意図的な設計選択の記録があるか
   - 同じ箇所が繰り返し修正されていないか（問題の再発パターン）
   - 現在のバグ・問題が過去の修正によって引き起こされた可能性
4. **force-app が git で管理されていない・履歴が浅い場合（標準の構成では force-app は .gitignore 対象）**: git blame・log は空になるので、組織での最終更新で代える。`python scripts/python/sf-lineage/lineage.py modified --target-org <本番> [--target-org <Sandbox>]`（読み取りだけ）のあと `lineage.py who <対象>` を引くと、部品ごとに「最終更新 本番 日付 更新者／Sandbox 日付 更新者」が付く。不具合の出始めた時期と、そのころに更新された部品・更新者を突き合わせる（変更理由は分からないので、課題・作業ログで確かめる。[option-lineage-map.md](option-lineage-map.md)）
5. 重要な知見があれば investigation.md に追記する

## 出力

investigation.md に追記（有意な発見がある場合のみ）:

## git 履歴から判明した事項

- {ファイルパス}: {日付} に {変更理由}（コミット: {hash}）
- 繰り返し修正の形跡: あり（{件数}回） / なし
- 現在の実装の意図: {把握できた場合}
