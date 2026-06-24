# option-cross-record-comparison

## 何をするか

症状が出るレコードと出ない正常レコードを SOQL で抽出・比較し、差分フィールドを原因候補に昇格させる。「特定のレコードだけで発生する」「一部のユーザー/データで再現する」ケースで、差分が原因の手掛かりを提供する。

## 実行手順

### Step 1: 比較対象の特定

investigation.md と課題本文から以下を把握する:
- **症状あり**: どのレコード（ID / 条件）で症状が発生するか
- **症状なし**: 同種だが正常動作しているレコード（ID / 条件）

症状あり/なし両方が特定できない場合は SOQL で候補を抽出する（Step 2 で実施）。

### Step 2: SOQL でレコード抽出

```bash
# 症状ありレコード（課題で名指しされた条件）
sf data query --query "SELECT {調査対象フィールドリスト} FROM {Object} WHERE {症状発生条件} LIMIT 5" \
  --target-org <sandbox-alias> --json

# 症状なしレコード（正常動作する同種レコード）
sf data query --query "SELECT {調査対象フィールドリスト} FROM {Object} WHERE {正常条件} LIMIT 5" \
  --target-org <sandbox-alias> --json
```

**調査対象フィールドリスト の選び方**:
1. 課題本文・コメントで言及されたフィールド
2. investigation.md の「使用中のフィールドAPI名」セクションにあるフィールド
3. Step C で読んだコードで条件分岐に使われているフィールド
4. 不明な場合は `FIELDS(ALL)` を使うが LIMIT 5 以下にする

> Sandbox にデータが存在しない場合、本番 SELECT は `option-prod-select-reference` 準拠でユーザー許可を得てから実行する。

### Step 3: フィールド差分の比較

取得した症状あり/なしレコードを横断的に比較する:

```bash
# JSON出力を整形して差分確認
# （必要に応じて Python や jq で整形する）
python3 -c "
import json, sys
data = json.load(open('/dev/stdin'))
for r in data['result']['records']:
    print({k: v for k, v in r.items() if k != 'attributes'})
" << 'EOF'
{sf data query の JSON 出力}
EOF
```

比較観点:
| フィールド種別 | 着眼点 |
|---|---|
| Boolean / Picklist | 症状あり側だけ特定値になっていないか |
| 日付・日時 | 期限切れ・特定期間にのみ発生しないか |
| 数値 | 閾値を超えているかどうか |
| Lookup / 参照関係 | 親レコードが NULL または特定の状態 |
| オーナー / プロファイル | 担当者・プロファイルによる権限差分 |

### Step 4: 差分フィールドを仮説へ

差分が見つかったフィールドを investigation.md の「原因仮説（多角分析）」テーブルの仮説として追記または更新する:

例: 「症状ありレコードは `Status__c = 'Closed'` だが症状なしは `'Active'`。コード中で Status が 'Closed' の場合に処理をスキップするロジックがある（TriggerHandler.cls:123）→ H2 の尤度を高に更新」

## 出力

investigation.md「根本原因」セクションに追記:

```markdown
## 類似レコード比較結果

| 項目 | 症状あり（{RecordId}） | 症状なし（{RecordId}） |
|---|---|---|
| {フィールド名（API: xxx__c）} | {値} | {値} |
| ... | ... | ... |

### 差分フィールドと仮説への影響

- `{フィールド名}`: 症状ありは `{値A}`、症状なしは `{値B}` → H{N}（{仮説名}）の根拠に追加 / 尤度を {高/中/低} に更新
- 差分なし: {フィールド名リスト} は同値のため除外
```

## 禁止事項

- 本番組織での SOQL 実行は `option-prod-select-reference` 準拠でユーザー明示許可なしに実行しない
- 比較結果に個人情報（氏名・メールアドレス・電話番号等）が含まれる場合は investigation.md に記録せず、フィールド名と差分パターンのみ記録する（値はマスク: ****）
- 本番に対する INSERT / UPDATE / DELETE / UPSERT は絶対禁止
