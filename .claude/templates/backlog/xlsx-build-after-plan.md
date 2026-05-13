# Phase 3 末尾: xlsx 一括生成手順

Phase 3（実装方針確定）後に対応記録・エビデンス xlsx を一括生成する。

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
| テスト・検証記録 | テスト方針・テストケース一覧（実際の結果・判定は Phase 5 で追記） |
| リリース・ロールバック | リリース対象・前確認・デプロイ手順・後確認・注意事項・ロールバック手順 |

---

## エビデンス.xlsx の生成

```bash
python scripts/python/backlog-xlsx/create_evidence.py \
  --folder "{xlsx_folder}" \
  --issue-id "{issueID}" \
  --implementation-plan docs/logs/{issueID}/implementation-plan.md
```

**書き込まれる内容**:
| シート | 書き込み内容 |
|---|---|
| テスト仕様 | テストケース全件（implementation-plan.md の「テスト仕様」セクションから抽出） |
| 実装前エビデンス | タイミング=「実装前」のテストケースのチェックリスト + スクリーンショット貼付枠 |
| 実装後エビデンス | タイミング=「実装後」のテストケースのチェックリスト + スクリーンショット貼付枠 |

**重要**: エビデンス.xlsx に画像を貼り付けた後は再生成しない。テストケースを追加する場合は `create_evidence_v2.py` で v2 ファイルを別発行する。

---

## スクリプト失敗時の対処

どちらかのスクリプトが失敗した場合（エラー出力あり / 終了コード 非0）:
1. エラー内容をユーザに提示する
2. AskUserQuestion で対処方法を選択する:
   - label: `xlsx なしで続行`、description: "xlsx 生成を断念して Phase 3.5 へ進む"
   - label: `修正して再試行`、description: "エラー原因を修正してスクリプトを再実行する"
   - label: `中止`、description: "コマンドを終了する"
3. 「xlsx なしで続行」が選ばれた場合: `{xlsx_folder}` = null として Phase 3.5 へ進む

---

## テストケース追加時の対応（Phase 5 以降）

テスト実施中に新規テストケースが追加された場合は `create_evidence_v2.py` で v2 を発行する（v1 の貼付画像を保護するため）:

```bash
python scripts/python/backlog-xlsx/create_evidence_v2.py \
  --v1 "{xlsx_folder}/{issueID}_エビデンス.xlsx" \
  --folder "{xlsx_folder}" \
  --issue-id "{issueID}" \
  --implementation-plan docs/logs/{issueID}/implementation-plan.md
```

出力: `{xlsx_folder}/{issueID}_エビデンス_v2.xlsx`
