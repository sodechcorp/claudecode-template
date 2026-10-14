# Phase 1: usecase ステップの決定木 + JSON フォーマット

## usecase 内ステップの決定木（必須）

**各 usecase の steps を書くとき、必ず以下を実行してから title / detail を書くこと。**

> **【大前提】処理とエラー判定は必ず別ステップ（絶対ルール）**
> 「〇〇を実行して、エラーなら〜」という処理は1ステップにまとめない。必ず2ステップに分割する。
> ```
> ✅ 正しい:
>   ステップN   node_type: "process"  + calls: "updateController"  （実行）
>   ステップN+1 node_type: "decision" + branch（成否確認）           （判定）
>
> ❌ 禁止:
>   ステップN   node_type: "decision" + calls: "updateController"  （実行と判定を1つに混ぜる）
> ```

```
【Q1】このステップは別クラス・別コンポーネント・外部APIを呼び出すか？
     （Apex / 子LWC / カスタムイベント / HTTP Callout / Named Credential）
  YES →  node_type: "process"
         calls: { "text": "ClassName または ClassName.method または API名" }
         ※ **クラス名はAPI名のまま記述する（"ConsultationController" → "ConsultationCtrl" のような省略は禁止）**
           図形側で CamelCase 境界または limit+3 文字で自動折り返しするため文字数制限は不要
         ※ HTTP Callout も必ず calls で明示する（例: "OPROARTS API", "外部決済API"）
         ※ 呼び出し後にエラー確認がある場合は「次のステップ」として独立した decision を追加する
  NO  ↓

【Q2】このステップは SOQL / DML / レコード操作を実行するか？
  YES →  node_type: "process"
         object_ref: { "text": "ObjectApiName" }
         sub_steps に SOQL / DML の詳細を記述
         ※ 操作後にエラー確認がある場合は「次のステップ」として独立した decision を追加する
  NO  ↓

【Q3】このステップは条件分岐・判定処理か？（if / switch / 成否確認）
  YES →  node_type: "decision"
         branch: { "text": "エラー/NGの結果", "node_type": "error"|"success", "label": "NG" }
         main_label: "OK"
  NO  ↓

【Q4】このステップは正常終了・成功を返すだけか？
  YES →  node_type: "success"
  NO  ↓

【Q5】このステップはエラー処理・例外表示か？
  YES →  node_type: "error"
  NO  ↓

→  node_type: "process"  （デフォルト）
```

> **エラー処理の配置ルール（必須）**: エラー処理・例外表示は**必ずその直前の判定ステップ（decision）の `branch` として配置する**。メイン処理フローの独立したステップとして書いてはならない。メインフローに `node_type: "error"` のステップが並んでいる場合は設計ミス。
> ```
> ✅ 正しい: decision ステップの branch.node_type = "error"
> ❌ 誤り:  メインフロー末尾に「7. エラー処理」というステップを置く
> ```

> **コントローラー呼び出しのスコープ**: Apex コントローラーを呼び出すステップは `calls` で明示し、`detail` には「〇〇コントローラーを呼び出して〇〇レコードを更新する」程度の記述にとどめる。コントローラー内部の処理詳細（SOQL / DML 内容・ロジック）は書かない。呼び出し先に別途機能設計書がある。

---

## JSON 生成フォーマット（画面設計書）

```json
{
  "id": "F-XXX（feature_list の id。なければ TBD）",
  "type": "LWC | 画面フロー | Aura | Visualforce",
  "name": "機能名（日本語。コードコメント・要件定義書から取得）",
  "api_name": "ComponentApiName または FlowApiName",
  "project_name": "{project_name}",
  "system_name": "",
  "author": "{author}",
  "version": "1.0",
  "date": "YYYY-MM-DD",
  "purpose": "本コンポーネントの目的（誰が・何のために使うか）",
  "overview": "処理概要（エントリーから終了まで一気に説明。具体的な画面名・操作・連携先を含める）",
  "features": [
    "主要機能1（箇条書きで3〜5件）",
    "主要機能2"
  ],
  "prerequisites": "前提条件（必要な権限・カスタム設定・親コンポーネントなど）",
  "transition": "画面遷移・表示場所（例: 取引先レコードページ → 保存後に取引先一覧へ遷移）",
  "items": [
    {
      "no": "1",
      "label": "項目ラベル",
      "api_name": "fieldName__c",
      "ui_type": "テキスト入力 | 選択 | ボタン | 表示のみ | チェックボックス | 日付 | 数値",
      "type": "String | Integer | Boolean | Date | Decimal",
      "required": true,
      "default": "",
      "validation": "バリデーション条件（あれば）",
      "note": "備考"
    }
  ],
  "usecases": [
    {
      "title": "ユースケース名（例: 「保存ボタンを押す」「初期表示」）",
      "trigger": "操作契機（例: ボタンクリック / ページロード / 項目変更）",
      "steps": [
        {
          "no": "1",
          "title": "バリデーション",
          "node_type": "decision",
          "detail": "必須項目が未入力の場合はエラーメッセージを表示して中断する。",
          "branch": { "text": "エラー表示", "node_type": "error", "label": "NG" },
          "main_label": "OK",
          "sub_steps": [
            { "no": "1.1", "title": "NG条件", "detail": "accountName == null || accountName == ''" }
          ]
        },
        {
          "no": "2",
          "title": "Apex メソッド呼び出し",
          "node_type": "process",
          "calls": { "text": "AccountCtrl.save" },
          "detail": "saveAccount() を呼び出して Account レコードを更新する。",
          "sub_steps": []
        }
      ]
    }
  ],
  "param_sections": [
    {
      "title": "入力プロパティ（LWC の場合: @api / 画面フローの場合: 入力変数）",
      "items": [
        {
          "no": "1",
          "key": "recordId",
          "type": "String",
          "required": true,
          "desc": "対象レコードのID",
          "default": "",
          "note": ""
        }
      ]
    },
    {
      "title": "出力イベント（LWC の場合: CustomEvent / 画面フローの場合: 出力変数）",
      "items": [
        {
          "no": "1",
          "key": "save",
          "type": "CustomEvent",
          "required": false,
          "desc": "保存成功時に発火。detail に savedRecordId を含む",
          "default": "",
          "note": ""
        }
      ]
    }
  ],
  "business_context": "この画面が担う業務上の役割（どのドメイン・業務フローの一部か。誰が・どの操作で使うか）",
  "apex_calls": [
    {"name": "AccountCtrl", "operation": "imperative", "trigger": "保存ボタンクリック", "note": "レコード更新"},
    {"name": "AccountDetailCtrl", "operation": "@wire", "trigger": "connectedCallback", "note": "レコード取得"}
  ],
  "events": [
    {"event": "onclick", "element": "保存ボタン", "handler": "handleSave", "description": "入力内容を検証してApexを呼び出し保存する", "note": ""},
    {"event": "onchange", "element": "担当者項目", "handler": "handleOwnerChange", "description": "担当者変更時に関連項目をリセット", "note": ""}
  ]
}
```
