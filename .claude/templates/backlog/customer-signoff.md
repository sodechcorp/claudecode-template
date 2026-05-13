# お客様確認サインの種別別ルール

| `{issue_type}` | 取り扱い |
|---|---|
| バグ | **必須**。修正後の再現テスト結果（Phase 5 の 4.5-A エビデンスを含む Before/After 対）を顧客に提示し、確認サインを得る（Backlog コメント返信・メール等）。サイン未取得の状態で完了報告しない |
| 追加要望 | 推奨。UAT 実施予定があれば顧客に確認サインを案内する |
| その他 | 任意 |

**xlsx 更新（お客様確認）**（`{issue_type}` が `バグ` かつ `{xlsx_folder}` が設定されていて変数名のまま展開されていない場合のみ実行。`{xlsx_folder}` がリテラルのままならスキップ）

```bash
python scripts/python/backlog-xlsx/update_records.py \
  --folder "{xlsx_folder}" --issue-id "{issueID}" \
  timeline --phase "お客様確認" \
  --source "顧客" \
  --content "確認サイン取得: {取得日・確認手段（Backlog コメント / メール等）}"
```
