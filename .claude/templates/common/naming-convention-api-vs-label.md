# API名 vs 日本語ラベルの使い分け（全 agent 共通）

| 記述対象 | 表記ルール | 例 |
|---|---|---|
| 自コンポーネント名・クラス名 | API名でOK | `requestForm`、`RequestController` |
| 他クラス・他コンポーネントへの呼び出し | クラス名はAPI名でOK。**メソッド名は書かない** | `RequestController を呼び出す`（`.createQuote()` は禁止） |
| オブジェクト名 | **日本語表示ラベル** | `Quote__c` → 「見積」、`BusinessTraveler__c` → 「出張申請」 |
| 項目名 | **日本語表示ラベル** | `Status__c` → 「ステータス」、`IsInvoiceContact__c` → 「請求先フラグ」 |
| sub_steps の SOQL/DML | API名・コードのまま | `SELECT Id FROM Quote__c WHERE ...` |
| calls / object_ref の図形ラベル | どちらでもOK | `RequestController`、`見積` |

> ❌ 禁止例: 「RequestControllerのcreateQuoteを呼び出しBusinessTraveler__cのStatus__cを更新する」
> ✅ 良い例: 「RequestControllerを呼び出し、出張申請のステータスを更新する」

---

## 自然言語テキスト項目での禁止事項

**`business_flow[].action` / `components[].responsibility` / `interfaces[].description` / `screens[].items[].validation` / `processing_purpose` / `data_flow_overview`** など、**すべての自然言語テキスト項目**で以下を禁止:

- API 名（`ContractApplication__c`・`User_portal__r` 等の `__c` / `__r` 付き識別子）
- メソッド呼び出し形式（`foo()` / `Controller.bar()` / `Site.login()` 等）
- ファイル拡張子付き名称（`.page` / `.cls` / `.trigger` / `.flow-meta.xml` / `.cmp` / `.js` / `.html`）
- コンポーネント API 名の露出（`CustomPasswordResetController` / `ChangePasswordPage` 等の CamelCase 識別子）
- 「F-XXX」等の内部機能ID

これらはすべて **日本語の業務表現**に置き換える:

| 技術表現 | 業務表現 |
|---|---|
| `CustomPasswordReset.page にアクセス` | 「パスワードリセット画面にアクセスする」 |
| `ContractApplication__c` | 「契約申込」（オブジェクト名の日本語ラベル） |
| `PasswordReset() → System.setPassword` | 「新しいパスワードを設定して保存する」 |
| `Site.validatePassword` | 「パスワードの形式・強度を検証する」 |
| `CustomSiteLogin の customSiteLogin() が契約区分に応じて URL 組立` | 「契約区分に応じた遷移先画面を組み立ててログインする」 |
