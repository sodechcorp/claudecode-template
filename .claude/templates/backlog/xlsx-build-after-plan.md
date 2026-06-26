# Phase 3 末尾: xlsx 一括生成手順

Phase 3（実装方針確定）後に対応記録.xlsx を一括生成する。

---

## 前提条件

> **スキップ判定**: `{xlsx_folder}` が空 / 未設定 / 変数名リテラル（`{xlsx_folder}` という形式のまま）の場合は全ステップをスキップして Phase 3.5 へ進む。

- `{xlsx_folder}` が設定されている（Phase 1.5 で「作成する」が選ばれた場合）
- 以下の 2 ファイルが全て存在すること:
  - `docs/logs/{issueID}/investigation.md`
  - `docs/logs/{issueID}/approach-plan.md`

---

## 対応記録.xlsx の生成

> **既存ファイルガード**: `{xlsx_folder}/{issueID}_対応記録.xlsx` が既に存在する場合、再生成すると Phase 4/5 で追記した Before/After・テスト結果・残対応が失われる。存在する場合は次のいずれかをテキストでユーザに確認してから進む（AskUserQuestion は使わない）:
> - `BK 退避して再生成` — 既存ファイルを `{issueID}_対応記録.bk.xlsx` にリネーム退避してから生成する
> - `再生成しない` — 既存ファイルを保持してこの Step をスキップし Phase 3.5 へ進む

```bash
python scripts/python/backlog-xlsx/create_records.py \
  --folder "{xlsx_folder}" \
  --issue-id "{issueID}" \
  --investigation docs/logs/{issueID}/investigation.md \
  --approach-plan docs/logs/{issueID}/approach-plan.md
```

**書き込まれる内容**（対応記録.xlsx のシート構成は課題と対応方針 / 対応内容 の2シートのみ）:
| シート | 書き込み内容 |
|---|---|
| 課題と対応方針 | 課題の整理（ID/件名/優先度・期限/種別/ステータス/課題の内容・詳細/原因・現状） + 経緯・対応方針（対応方針（結論）/方針決定の経緯・根拠） + 対応経緯タイムライン No1-3 |
| 対応内容 | 変更を加えた資材一覧（ヘッダー行）・Before/After 領域の初期化（Before/After 実記入は Phase 4 / implementer が `before-after` コマンドで実施） |

> **エビデンス.xlsx**: Phase 4 完了後に `/test {issueID}` が `generate_evidence_xlsx.py` で生成する。このタイミングでは生成しない。
>
> **廃止済みシート**: サマリー・経緯 / 対応方針 / 調査・影響範囲 / テスト・検証 / 残対応・懸念・保留 は廃止済み（課題と対応方針・対応内容シートに統合、または エビデンス.xlsx に集約）。これらのシートは `対応記録テンプレート.xlsx` に存在しない。

---

## スクリプト失敗時の対処

スクリプトが失敗した場合（エラー出力あり / 終了コード 非0）:
1. エラー内容をユーザに提示する
2. テキストで以下の 3 択を提示してユーザの選択を待つ（AskUserQuestion は使わない）:
   - `xlsx なしで続行` — xlsx 生成を断念して Phase 3.5 へ進む
   - `修正して再試行` — エラー原因を修正してスクリプトを再実行する
   - `中止` — コマンドを終了する
3. 「xlsx なしで続行」が選ばれた場合: `{xlsx_folder}` = null として Phase 3.5 へ進む
