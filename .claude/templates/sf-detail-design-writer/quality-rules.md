# 品質基準（最重要）

**「コードを読んだエンジニアが設計意図を把握できる資料を書く」**。コードの写しでも業務説明でもなく、**設計の判断と責務の境界**を書く。

## 書くべきこと・書かないこと

| 項目 | 書くべきこと | 書かないこと（禁止） |
|---|---|---|
| `processing_purpose` | 「入力バリデーション・番号採番・レコード保存・承認フロー起動の一連の処理をこのグループが担う」 | 「QuotationRequestController.doSave()を実行する」（コードの写し） |
| `data_flow_overview` | 「VF → Controller → Service → Flow → Batch の順でデータが流れる。Controller は入力検証のみ担当し、保存責務を Service に分離している」 | 「メソッドAがメソッドBを呼ぶ」（コール順の羅列） |
| `components[].responsibility` | 「入力値の形式検証（必須・桁数・重複）と Service 呼び出しのみを担当。ビジネスロジックは持たない」 | 「doSave()、validate()、getAccount()メソッドを持つ」（メソッド列挙） |
| `interfaces[].description` | 「画面の保存ボタン押下時に呼ばれる。バリデーション後に Service に委譲し、結果に応じて遷移先を返す」 | 「String a, Id b を引数にとり Id を返す」（シグネチャの翻訳） |
| `screens[].items[].validation` | 「必須入力。100文字以内。既存見積件名との重複チェックあり（SOQL）」 | 「required=trueの場合バリデーション」 |

## 禁止: API名・メソッド名・拡張子付きファイル名を日本語テキストに混ぜない

> API名 vs 日本語ラベルの使い分け詳細: [.claude/templates/common/naming-convention-api-vs-label.md](../common/naming-convention-api-vs-label.md)

**`business_flow[].action` / `components[].responsibility` / `interfaces[].description` / `screens[].items[].validation` / `processing_purpose` / `data_flow_overview`** など、**すべての自然言語テキスト項目**で以下を禁止する:

- API 名（`ContractApplication__c`・`User_portal__r` 等の `__c` / `__r` 付き識別子）
- メソッド呼び出し形式（`foo()` / `Controller.bar()` / `Site.login()` 等）
- ファイル拡張子付き名称（`.page` / `.cls` / `.trigger` / `.flow-meta.xml` / `.cmp` / `.js` / `.html`）
- コンポーネント API 名の露出（`CustomPasswordResetController` / `ChangePasswordPage` 等の CamelCase 識別子）
- 「F-XXX」等の内部機能ID

これらはすべて **日本語の業務表現**に置き換える。対応表:

| 技術表現 | 業務表現 |
|---|---|
| `CustomPasswordReset.page にアクセス` | 「パスワードリセット画面にアクセスする」 |
| `ContractApplication__c` | 「契約申込」（オブジェクト名の日本語ラベル） |
| `PasswordReset() → System.setPassword` | 「新しいパスワードを設定して保存する」 |
| `Site.validatePassword` | 「パスワードの形式・強度を検証する」 |
| `CustomSiteLogin の customSiteLogin() が契約区分に応じて URL 組立` | 「契約区分に応じた遷移先画面を組み立ててログインする」 |

## 禁止: `business_flow[].actor` にコンポーネント名を書かない

actor は **業務上の登場人物**のみ。以下は禁止:
- `CustomPasswordResetController（F-015）` → ✗（コンポーネント名）
- `MicrobatchSelfReg` → ✗（コンポーネント名）

OK 例: 「お客様」「ポータルユーザ」「GF社担当者」「管理者」「システム」「自動フロー」

## `components[].responsibility` は完全文で書く（重要）

`responsibility` は Python が処理設計の `description` を自動生成するソースになる。
**主語欠落の断片を書かない。書けないなら空文字列にする。API 名・クラス名・メソッド名を一切含めない。**

`docs/flow/usecases.md` の「処理フロー」記述を参照し、そこに書かれた業務語を使う。

### 必須: 画面系コンポーネントは「〜画面で〜を行う」形式で書く

**VF / LWC / Aura** は必ず「**〜画面で〜を行う**」形式にすること。「〜画面」だけで止めると、処理フロー図のボックスに何をしているかが表示されない。

| NG（画面名のみ・断片・API名） | OK（「〜画面で〜を行う」の完全文） |
|---|---|
| `ポータルログイン画面。` | 「ポータルログイン画面でユーザー認証を行う。」 |
| `は、ため動作不全` | 「ポータルのパスワードリセット申請を受け付け、リセット用 URL をメール送信する。」 |
| `一致すれば または遷移` | 「入力されたユーザー名をポータルユーザーと照合し、一致した場合に次のステップへ遷移する。」 |
| `でパスワード設定 → 遷移` | 「パスワード変更画面で新しいパスワードを受け取り、保存後に完了画面へ遷移する。」 |
| `SiteLogin.cls が担当` | 「ポータルのログイン認証処理を担当する。」 |

断片を書かず、以下の形式で書く:
- **述語まで完結させること**（「〜する。」「〜を担当する。」で終わる形）
- **コンポーネント API 名・クラス名・メソッド名を含めない**（業務語で説明する）
- **「（Experience Cloud 標準テンプレート）」等の技術注記を responsibility に含めない**（responsibility は業務動作を書く欄）
- **空文字列 `""` にしてよいのは、標準 VF ボイラープレート（CommunitiesLogin 等）のみ**（Python 側が既定文を補完する。ただし補完結果は「〜処理を担当する。」という機械生成文になる）
- 処理が分からない・把握できない場合も、「〜担当」「〜処理する」程度で構わないので何か書く。**完全な空 `""` は禁止**（空で提出すると Excel 備考欄に「〜処理を担当する。」プレースホルダーが機械挿入され、設計書として無意味になる）

### 重要: 複数 components を書く場合は業務フロー（business_flow）と同じ上から時系列順に並べる

処理フロー図は components の順序で描画される。`business_flow` の actor/action 順と合わせること。

## `components[].role` は一行の日本語で書く

`role` は「関連コンポーネント」シートの役割欄に直接表示される。
- **API 名・クラス名を含めない**（「〜画面コントローラ」「〜処理担当の Apex クラス」等）
- 10〜30 文字程度の一行で書く
- `responsibility` と同じ言葉にしない（role は名詞句、responsibility は動詞文）
- **「〜画面で〜を担当する」等の自然な日本語で書く。断片や技術注記は入れない**

## `components[].flow_label` は処理フロー図用の一言まとめ（重要・必須）

`flow_label` は **処理フロー図の PNG ボックス内に表示する一言まとめ**。`responsibility` の全文を埋め込むと図が読めないため、必ず短く要約する。業務フロー図 `business_flow[].label` と同じ文体で書く。

| フィールド | 用途 | 書き方 |
|---|---|---|
| `responsibility` | 関連コンポーネント／処理設計の文章。30〜80字の完全文 | 「〜画面で〜を行う」「〜処理を担当する」等の述語完結文 |
| `flow_label` | **処理フロー図 PNG ボックス内の一言まとめ** | **6〜10字の体言止め・短い述語**。responsibility の主語/目的語/動詞を圧縮した名詞句 |

- `responsibility` と `flow_label` で **同じ文字列を使ってはいけない**（図と表で冗長）
- API 名・メソッド名・拡張子付きファイル名・コンポーネント API 名は **絶対に入れない**（同じ禁止規則を適用）
- 「〜画面」だけで止めてもよい（処理フロー図ではアクションよりスコープ表示が分かりやすいケース多）

**responsibility / flow_label のペア例**:

| responsibility | flow_label |
|---|---|
| ポータルログイン画面でユーザー認証を行う | ログイン認証 |
| パスワード変更画面で新しいパスワードを受け取り、保存後に完了画面へ遷移する | パスワード変更 |
| ポータルのパスワードリセット申請を受け付け、リセット用 URL をメール送信する | リセット申請受付 |
| 入力されたユーザー名をポータルユーザーと照合し、一致した場合に次のステップへ遷移する | ユーザー名照合 |
| 取引先責任者の有効化操作を起点にポータルユーザを新規作成し、初期パスワードを通知する | ポータルユーザ作成 |
| ポータル会員のセルフ登録を受け付け、コミュニティライセンスでユーザーを発行する | セルフ登録受付 |
| ログイン後にポータル会員が自身のプロフィール情報（氏名・メール・電話）を閲覧し編集・保存する | プロフィール編集 |

**悪い例（絶対に書かない）**:
- `flow_label: "Experience"` ← 単語切れ・意味不明
- `flow_label: "バックエンド"` ← 抽象すぎて識別不能
- `flow_label: "パスワードリセット申"` ← 末尾切れ
- `flow_label: "ログイン認証処理を担当する"` ← responsibility と同文。体言止めにする
- `flow_label: "CustomSiteLogin"` ← API 名混入

## process_steps は書かなくてよい

`process_steps` は Python 側の `_build_process_steps` が `components[].responsibility` および `components[].flow_label` から自動生成する。**JSON に `process_steps` を含める必要はない**（含めてもクリーニングはされるが、書かないほうがクリーン）。ただし **`components[].flow_label` は必須**（処理フロー図の品質に直結）。

## インターフェース定義の対象

全メソッドを書く必要はない。以下を優先する:
1. **外部から呼ばれるメソッド**（`@AuraEnabled` / `@InvocableMethod` / VF アクション / Batch execute 等）
2. **コンポーネント間の主要な呼び出し**（Controller → Service の委譲メソッド等）
3. **複雑なロジックを持つメソッド**（採番・計算・外部連携）

内部ユーティリティメソッドや単純な getter/setter は省略してよい。

## 画面仕様の対象

UI コンポーネント（Visualforce / LWC / Aura）が含まれるグループのみ記述する。  
Apex バッチ・サービスのみのグループは `screens: []` として空にする。
