# Phase 3 末尾: xlsx 一括生成手順

Phase 3（実装方針確定）後に対応記録.xlsx を一括生成する。

---

## 前提条件

> **スキップ判定**: `{xlsx_folder}` が空 / 未設定 / 変数名リテラル（`{xlsx_folder}` という形式のまま）の場合は全ステップをスキップして Phase 3.5 へ進む。

- `{xlsx_folder}` が設定されている（Phase 1.5 で「作成する」が選ばれた場合）
- 以下の 3 ファイルが全て存在すること:
  - `docs/logs/{issueID}/investigation.md`
  - `docs/logs/{issueID}/approach-plan.md`
  - `docs/logs/{issueID}/implementation-plan.md`

---

## 対応記録.xlsx の生成

```bash
python scripts/python/backlog-xlsx/create_records.py \
  --folder "{xlsx_folder}" \
  --issue-id "{issueID}" \
  --investigation docs/logs/{issueID}/investigation.md \
  --approach-plan docs/logs/{issueID}/approach-plan.md \
  --implementation-plan docs/logs/{issueID}/implementation-plan.md
```

**書き込まれる内容**:
| シート | 書き込み内容 |
|---|---|
| サマリー・経緯 | 課題情報（ID/件名/優先度/期限/種別/背景）+ タイムライン 3 行（Phase 1〜3） |
| 対応方針 | 案比較テーブル・採用方針・実施前確認事項・懸念事項 |
| 調査・影響範囲 | 仮説検証・コード根拠・影響範囲・関連コンポーネント |
| 対応内容 | 変更ファイル一覧・影響確認チェックリスト（Before/After は実装後に追記） |
| テスト・検証 | テスト観点一覧（実際の結果は Phase 3.5 で validator / Phase 5 で tester または judge_results.py が記入） |

> **エビデンス.xlsx**: Phase 4 完了後に `/auto-test {issueID}` が `generate_evidence_xlsx.py` で生成する。このタイミングでは生成しない。

---

## スクリプト失敗時の対処

スクリプトが失敗した場合（エラー出力あり / 終了コード 非0）:
1. エラー内容をユーザに提示する
2. テキストで以下の 3 択を提示してユーザの選択を待つ（AskUserQuestion は使わない）:
   - `xlsx なしで続行` — xlsx 生成を断念して Phase 3.5 へ進む
   - `修正して再試行` — エラー原因を修正してスクリプトを再実行する
   - `中止` — コマンドを終了する
3. 「xlsx なしで続行」が選ばれた場合: `{xlsx_folder}` = null として Phase 3.5 へ進む
