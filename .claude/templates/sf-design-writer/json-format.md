# sf-design-writer 参照リファレンス

Phase 1 開始時に Read ツールで読み込む。ステップ記述ルール・種別別注意点・JSON フォーマット例を収録。

---

## ステップ記述プロトコル（全種別共通・必須）

**各ステップを書くとき、必ず以下の決定木を実行してから title / detail を書くこと。**

> **【大前提】処理とエラー判定は必ず別ステップ（絶対ルール）**
> 「〇〇を実行して、エラーなら〜」という処理は1ステップにまとめない。必ず2ステップに分割する。
> ```
> ✅ 正しい:
>   ステップN   node_type: "process"  + calls: "QuoteService.create"  （実行）
>   ステップN+1 node_type: "decision" + branch（成否確認）             （判定）
>
> ❌ 禁止:
>   ステップN   node_type: "decision" + calls: "QuoteService.create"  （実行と判定を1つに混ぜる）
> ```

```
【Q1】このステップは別クラス・別メソッド・外部APIを呼び出すか？
     （Apex クラス / ユーティリティ / HTTP Callout / Named Credential / サブフロー）
  YES →  node_type: "process"
         calls: { "text": "ClassName.method または API名" }  （20文字以内。object_ref との併用不可）
         ※ HTTP Callout も必ず calls で明示する（例: "OPROARTS API", "外部決済API"）
         ※ 呼び出し後にエラー確認がある場合は「次のステップ」として独立した decision を追加する
  NO  ↓

【Q2】このステップは SOQL / DML / レコード操作を実行するか？
  YES →  node_type: "process"
         object_ref: { "text": "ObjectApiName" }  （FROM句 or 対象オブジェクトのAPI名）
         sub_steps に SOQL / DML の詳細を記述
         ※ 操作後にエラー確認がある場合は「次のステップ」として独立した decision を追加する
  NO  ↓

【Q3】このステップは条件分岐・判定処理か？（if / switch / 成否確認 / Decisionノード）
  YES →  node_type: "decision"
         branch: { "text": "エラー/NGの結果", "node_type": "error"|"success", "label": "False" }
         main_label: "True"  （省略時は自動付与）
  NO  ↓

【Q4】このステップは正常終了・成功レスポンスを返すだけか？
  YES →  node_type: "success"  （branch の node_type として使うことが多い）
  NO  ↓

【Q5】このステップはエラー処理・例外スローか？
  YES →  node_type: "error"  （branch の node_type として使うことが多い）
  NO  ↓

→  node_type: "process"  （デフォルト。通常の処理）
```

> **「判断できないから省略」は禁止。** 必ずQ1〜Q5のどれかに答えてからステップを書く。

---

## 種別別 JSON 生成の注意点

**Apex（コントローラ・ユーティリティ）**
- 全メソッドを `steps` に展開する（private メソッドも含める）
- 各ステップの `method_name` にメソッド名（Apex の実装名）を記述する。`title` にはクラス名・メソッド名を含めない
  - 良い例: `"method_name": "createQuote"` / `"title": "見積を作成する"`
  - 悪い例: `"title": "【createQuoteController】見積を作成する"`
- **スコープ**: この設計書はあくまで対象クラスの処理を説明する。別Apexを呼び出す場合は `calls` フィールドで明示し、`detail` では「〇〇コントローラーを呼び出して見積レコードを作成する」程度の記述にとどめる。呼び出し先クラスの内部実装を詳述しない（呼び出し先には別途設計書がある）
- **外部Apex呼び出しステップのobject_ref**: `calls` と `object_ref` は同一ステップに共存できない。外部Apexが操作するオブジェクトは `detail` に文章で記述し、`object_ref` は設定しない
- SOQL クエリは SELECT/FROM/WHERE を改行して sub_steps の `detail` に書く（全フィールドを列挙。1行に詰め込まない）
- DML（INSERT/UPDATE/DELETE）は「対象: {Object} / 操作: INSERT|UPDATE|DELETE / フィールド: 〇〇, △△」形式で sub_steps に書く
- `with/without sharing` を `prerequisites` に記載する
- `@InvocableMethod` / `@AuraEnabled` はその旨を `trigger` に明記する
- `node_type: "object"` は使わない（`process` + `object_ref` に統一）

**非画面フロー（AutoLaunchedFlow / RecordTriggeredFlow 等）**
- 機能設計書 JSON フォーマットを使う（generate_feature_design.py）
- flow-meta.xml の全ノードを解析し、全ての処理ノードを `steps` に記述する
- 入力変数（`variables` タグの `isInput: true`）を `input_params`、出力変数（`isOutput: true`）を `output_params` に記載する

**Flow XML ノード → steps 変換ルール（必須・省略禁止）**

| XML 要素 | node_type | 追加フィールド |
|---|---|---|
| `<recordLookups>` | process | object_ref + SOQL sub_step |
| `<recordUpdates>` / `<recordCreates>` / `<recordDeletes>` | process | object_ref + DML sub_step |
| `<decisions>` | decision | branch（条件式を detail に必ず記述） |
| `<actionCalls>` | process | calls（`<actionName>` = Apex クラス名） |
| `<subflows>` | process | calls（サブフローのAPI名） |
| `<assignments>` | process | 代入内容を detail に記述 |

**XML ノードの具体的な読み方:**

`<recordLookups>` → SOQL sub_step:
- `<object>` → `object_ref.text`
- `<filters>` の `<field>` / `<operator>` / `<value>` → WHERE条件（全フィルターを列挙）
- `<queriedFields>` または `<outputReference>` → SELECT句
- SOQL sub_step detail 例: `"SELECT Id, Name, BillingAddress\nFROM Account\nWHERE Id = {recordId}（{フィルター説明}）"`

`<recordUpdates>` / `<recordCreates>` → DML sub_step:
- `<object>` → `object_ref.text`
- `<inputAssignments>` の `<field>` / `<value>` → 更新フィールド（全件列挙）
- DML sub_step detail 例: `"対象: Account / 操作: UPDATE / フィールド: Memo__c={変数名}, Status__c='完了'"`

`<decisions>` → decision step:
- `<rules>` の `<conditions>` を読んで条件式を日本語で detail に記述する
- `<leftValueReference>` / `<operator>` / `<rightValue>` から条件内容を読む
- **「条件分岐: [ラベル名]」だけでは禁止。必ず「何と何をどう比較しているか」を detail に書くこと**
- detail 例: `"承認者（Approver__c）が null でないか判定"`、`"エラーフラグ（isError__c）が true か確認"`
- `<defaultConnector>` → False側（`branch` に配置）、True側 → メインフロー続行

`<actionCalls>` → calls:
- `<actionName>` → `calls.text`（Apex クラス名 or InvocableMethod のクラス名）
- `<inputParameters>` → detail に渡す引数を記述
- detail 例: `"CreateQueueMember Apex アクションを呼び出し、対象レコードにキューメンバーを追加する。引数: queueId, targetSobjectId"`

**Apex（トリガーハンドラー）**
- feature_list で `absorb_into = {このクラス名}` となっている Trigger が存在する場合、そのトリガーファイルを読む
- トリガーの起動条件（オブジェクト名・before/after・insert/update/delete）を `prerequisites` に追記する
- 例: `prerequisites: "OpportunityTrigger（after insert）から呼び出される。with sharing。"`
- ハンドラー呼び出しのメソッド分岐（afterInsert / beforeUpdate 等）は steps の最初に記述する

**Integration（外部API連携）**
- Named Credential / HTTP Callout を使うクラス。処理ルールは Apex に準じる
- **HTTP リクエスト送信は `calls` で明示する（必須）**
  - `calls.text` = Named Credential 名 または エンドポイント概要（20文字以内）
  - 例: `"calls": { "text": "OPROARTS API" }` / `"calls": { "text": "外部決済API" }`
  - `detail` に「〇〇 API へ HTTP POST リクエストを送信し、ドキュメント生成結果を取得する」と記述
  - リクエスト/レスポンスの組み立て（ヘッダー設定・body構築・JSON deserialize 等）は `sub_steps` に記述
- HTTP 送信後のステータスコード確認は **別の `decision` ステップ**として記述（処理/判定分離ルール遵守）
  - 例: `"title": "HTTPレスポンスのステータスを確認する"` + `branch: { "text": "ステータス != 200、例外スロー", "node_type": "error" }`
- Named Credential の設定名を `prerequisites` に記載する

**Batch / Schedule**
- `start` / `execute` / `finish` の3フェーズをそれぞれ `steps` の大項目にする
- `trigger` に以下を記載する:
  - スコープサイズ（`Database.executeBatch` の第2引数）
  - スケジュール設定（cron 式）— 同フォルダに対応するSchedulableクラス（`implements Schedulable`）があれば読んで取得する。`execute()` メソッドの `System.scheduleBatch` または `System.schedule` 呼び出しからcron式を特定する
- Schedulableクラス単体は設計書を作らない（Batchの `trigger` に吸収済み）

---

## JSON 生成フォーマット

```json
{
  "id": "F-XXX（docs/feature_ids.yml より取得。なければ TBD）",
  "type": "Apex | Batch | Flow | 画面フロー | LWC | Integration（上表の「type値」列と完全一致させること）",
  "name": "機能名（日本語。コードコメント・要件定義書から取得）",
  "api_name": "ClassName または FlowApiName",
  "project_name": "{project_name}",
  "system_name": "",
  "author": "{author}",
  "version": "1.0",
  "date": "YYYY-MM-DD",
  "purpose": "本書の目的（何のために・誰のために・どのような問題を解決するか）",
  "overview": "処理概要（エントリーから終了まで一気に説明。具体的なオブジェクト名・API名・外部サービス名を含める）",
  "prerequisites": "前提条件（with/without sharing・認証・依存コンポーネント・実行順序など）",
  "trigger": "処理契機（具体的な起動タイミング。@InvocableMethod / @AuraEnabled / Flow の起動条件 / Scheduler cron 式 など）",
  "steps": [
    {
      "no": "1",
      "method_name": "validateInput",
      "title": "引数を検証する",
      "node_type": "decision",
      "detail": "accountId が null または空の場合は例外をスローして処理を中断する。",
      "branch": { "text": "AuraHandledException\nをスロー", "node_type": "error", "label": "NG" },
      "main_label": "OK",
      "sub_steps": [
        { "no": "1.1", "title": "NG条件", "detail": "accountId == null || accountId == ''" }
      ]
    },
    {
      "no": "2",
      "method_name": "fetchAccount",
      "title": "取引先データを取得する",
      "node_type": "process",
      "object_ref": { "text": "Account" },
      "detail": "条件に一致するAccountを検索し、後続の更新処理に渡す。",
      "sub_steps": [
        {
          "no": "2.1",
          "title": "SOQL",
          "detail": "SELECT Id, Name, Status__c\nFROM Account\nWHERE Id = :accountId\n  AND IsDeleted = false"
        }
      ]
    },
    {
      "no": "3",
      "method_name": "updateStatus",
      "title": "ステータスを更新する",
      "node_type": "process",
      "object_ref": { "text": "Account" },
      "detail": "取得したAccountのStatus__cを「処理済み」に更新してコミットする。",
      "sub_steps": [
        {
          "no": "3.1",
          "title": "DML",
          "detail": "対象: Account / 操作: UPDATE\nフィールド: Status__c = '処理済み'"
        }
      ]
    }
  ],
  "_node_type_guide": {
    "process": "通常の処理（デフォルト）→ フロー図で角丸長方形（青系）",
    "decision": "条件分岐（if/switch/Decisionノード）→ フロー図で菱形。必ず branch でFalse/エラー側を右に出す。True/False ラベルは自動付与",
    "error": "エラー処理・例外スロー → フロー図で黄色枠（branch の node_type に使用）",
    "success": "正常終了・成功レスポンス → フロー図で緑枠（branch の node_type に使用）",
    "call": "（直接使用不可。calls フィールドで自動描画される）",
    "start": "処理開始（自動付与されるため通常不要）",
    "end": "処理終了（同上）"
  },
  "_object_ref_guide": "SOQLでクエリするオブジェクト・DMLで操作するオブジェクトは object_ref に記述する。フロー図でステップの右側に円柱（Salesforceオブジェクト）が矢印で表示される。object_ref はオブジェクトの API 名（例: Account / Contact / Opportunity__c）を text に入れる。SOQL/DML を含むステップには必ず付与すること。",
  "_calls_guide": "別クラス・別メソッドを呼び出すステップには calls を付与する。フロー図でステップの右側に紫の箱が矢印で表示される。text は短く（20文字以内）、クラス名.メソッド名（例: EstimateHelper.create）形式にする。長いクラス名は略称で可（例: CommonAuthCallout.get）。object_ref・branch との同時使用は不可。",
  "input_params": [
    { "key": "param1", "type": "String", "required": true, "description": "説明（単位・形式・制約を含める）" }
  ],
  "output_params": [
    { "key": "result", "type": "Boolean", "description": "説明" }
  ]
}
```

**JSON を書き出したら即座にファイルに保存する**:
```bash
# 保存先: {tmp_dir}/{api_name}_design.json
```
