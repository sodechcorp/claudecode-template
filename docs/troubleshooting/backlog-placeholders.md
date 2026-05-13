# トラブルシュート: /backlog プレースホルダー問題

---

## 症状: `{xlsx_folder}` がリテラルのままファイルパスに使われている

**例**:
```
{xlsx_folder}/GF-340_対応記録.xlsx     ← 誤
C:/work/backlog_records/GF-340_件名/GF-340_対応記録.xlsx  ← 正
```

**原因**: Claude が `/backlog` の Phase 1.5 でテンプレート置換ルールを遵守せず、
`{xlsx_folder}` を実値に置き換えないまま後続の処理に渡した。

**対処**:

1. `/backlog` コマンドを再実行して Phase 1.5 まで進める
2. `{xlsx_folder}` の値（`{report_dir}/{issueID}_{件名_sanitized}` の形）を明示的に計算してチャットに表示させる
3. Phase 1.5.2 の値検証（v が含まれないか・絶対パスか・親ディレクトリ存在か）が OK になることを確認
4. その値を記憶した上で Phase を進める

---

## 症状: 「Bash の stdout が表示されない」「Bash が動かない」

**原因候補**:
1. **プレースホルダー未置換** が最多。`{xlsx_folder}` が `{` を含む状態で Python に渡されてスクリプトが `SystemExit` している
2. Python スクリプトが `[FATAL] placeholder not resolved` を出して終了している（exit code 1）
3. `.claude/hooks/` が存在しない / node が見つからない

**対処**:
1. Claude に「最後に実行した Bash コマンドを見せて」と頼んでコマンド文字列を確認
2. `{xlsx_folder}` などがリテラルのままなら Phase 1.5 に戻る
3. Python スクリプトに直接同じ引数を渡して `[FATAL]` メッセージを確認:
   ```bash
   python scripts/python/backlog-xlsx/create_records.py --folder "{xlsx_folder}" ...
   # → [FATAL] placeholder not resolved: '{xlsx_folder}' と出れば置換漏れが確定
   ```

---

## 症状: `{xlsx_folder}` のパスに `{xlsx_folder}` がネストしている

**例**:
```
{xlsx_folder}/evidence/before/{xlsx_folder}/evidence/after/
```

**原因**: Phase 1.5 で確定した `{xlsx_folder}` の値が再度テンプレート内で展開されてしまった（2 重展開）。

**対処**: Phase 1.5 に戻り、`{xlsx_folder}` を**一度だけ**確定する。値が確定したら `xlsx_folder = C:/work/...` の形でチャットの記憶に持ち、それ以降のコマンド内では確定値（文字列）を直接使うよう Claude に促す。

---

## 症状: `.claude/hooks/pre-operation.js` not found

**原因**: プロジェクトの `.claude/hooks/` ディレクトリが存在しない（clone / upgrade 漏れ）。

**対処**:
```bash
# プロジェクトフォルダで実行
/upgrade
```

または手動で `pre-operation.js` を [claude-temp](..) から `cp` する。

---

## 予防策

- `/backlog` 実行時は Phase 1.5 で `xlsx_folder =` の値が画面に表示されることを確認する
- 値に `{` が含まれていたら即 STOP → Phase 1.5 やり直し
- 表示された値が絶対パスであること・親ディレクトリが存在することを目視確認
