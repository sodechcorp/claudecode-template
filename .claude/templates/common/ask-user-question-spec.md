# AskUserQuestion 詳細スキーマ仕様

## 正規スキーマ

AskUserQuestion の引数は以下の形のみ受け付ける。**俗称 `choices` ではなく `options`**。`options` は **配列**（JSON 文字列ではない）。

```json
{
  "questions": [
    {
      "question": "ここに疑問符で終わる質問文?",
      "header": "12文字以内",
      "multiSelect": false,
      "options": [
        { "label": "選択肢A", "description": "選択時に何が起きるか" },
        { "label": "選択肢B", "description": "選択時に何が起きるか" }
      ]
    }
  ]
}
```

| 項目 | 制約 |
|---|---|
| `questions` | 配列・1〜4件（**運用上は1件のみ使用**、複数は選択UXが悪化するため） |
| `questions[].question` | 文字列・疑問符終わり |
| `questions[].header` | 文字列・最大12文字 |
| `questions[].multiSelect` | bool |
| `questions[].options` | **配列**・2〜4件（JSON 文字列ではない） |
| `options[].label` | 文字列・1〜5語 |
| `options[].description` | 文字列 |

**NG 例**（実際に発生したエラー）:
```json
{
  "question": "...",
  "choices": "[{\"label\":\"A\"...}]"
}
```
❌ キー名が `choices`（正しくは `questions[].options`） / 値が JSON 文字列 / トップレベルが `questions[]` 配列でない / `header` 欠落

## 運用ルール詳細

- **1質問1回答**: `questions[]` には1件のみ入れて順番に呼ぶ。schema は1〜4件対応だが、複数質問を同時に表示すると選択UIが縦に長くなりユーザーが選択しにくくなるため。
- **Other 文言禁止**（テキスト入力代替の single select でのみ適用。multiSelect で資料/項目種別を列挙する場合は対象外）: AskUserQuestion には自動で「Other（自由入力）」が付く。`options` の `label` に「Other」「自由入力」「手動入力」等の**そのままの語**を**絶対に含めない**。「スキップ」「デフォルト値を使う」等のみ記載する。**ただし options 配列は最低2件必要なため、前回値・自動取得値の対比として「別のフォルダを指定する」「別のエイリアスを使用」等のコンテキスト具体ラベルは許容**（Other 等価ではなく UX 上推奨。文言は対比対象を具体化すること）
- 選択肢がある場合（前回値・固定候補）は AskUserQuestion で提示する。テキスト自由入力が必要な場合（初回パス等）はチャットで直接聞く
- **assistant メッセージへの候補列挙禁止**: 選択肢を提示する際、候補一覧・件数内訳・対象 API 名等を assistant の地の文に列挙しない。AskUserQuestion の label / description にすべて集約する。Python スクリプトの stdout は内部処理用であり、ユーザーへ見せるために再表示しない。
