# Phase 2: 詳細設計 JSON スキーマ

読み込んだ情報をもとに、以下スキーマの JSON を `{tmp_dir}/{group_id}_detail.json` に書き出す。

```json
{
  "feature_id": "FG-001",
  "name_ja": "見積依頼",
  "name_en": "QuotationRequest",
  "project_name": "{project_name}",
  "author": "{author}",
  "date": "YYYY-MM-DD",
  "processing_purpose": "このグループが担うシステム処理の目的（エンジニア向け。2〜3文）",
  "data_flow_overview": "コンポーネント間のデータと処理の流れ（矢印で表現。責務分離の意図も含める）",
  "prerequisites": "技術的な前提条件（Named Credential 設定・カスタムメタデータ等）",
  "notes": "設計上の注意点・技術的負債・将来の拡張方針など",
  "business_flow": [
    {
      "step": 1,
      "actor": "GF社担当者",
      "action": "取引先責任者情報を確認し、ユーザー発行画面から発行を申請する",
      "label": "ユーザー発行を申請",
      "next": [{"to": 2}]
    },
    {
      "step": 2,
      "actor": "自動フロー",
      "action": "ユーザー作成・仮パスワード発行・メール送信を実行する",
      "label": "ユーザー作成・通知",
      "next": [{"to": 3}]
    },
    {
      "step": 3,
      "actor": "お客様",
      "action": "初期パスワードメールを受信し、Experience Cloudポータルにアクセスする",
      "label": "ポータルへアクセス",
      "next": []
    }
  ],
  "components": [
    {
      "api_name": "QuotationRequestController",
      "type": "Apex",
      "responsibility": "担当処理の説明（何をする・何をしない）",
      "role": "10〜30字の一行日本語（例: 見積依頼画面コントローラ）",
      "flow_label": "6〜10字の一言まとめ（処理フロー図ボックス用）",
      "inputs": "入力データの概要（型・形式）",
      "outputs": "返却データの概要",
      "error_handling": "エラー処理の方針"
    }
  ],
  "interfaces": [
    {
      "component": "QuotationRequestController",
      "method": "doSave",
      "description": "処理内容の説明（呼び出しタイミング・目的・後続処理）",
      "input_params": "パラメータ名: 型（説明）のカンマ区切り。なければ「なし」",
      "return_value": "型（説明）",
      "exceptions": "例外クラス名"
    }
  ],
  "screens": [
    {
      "component": "QuotationRequestPage",
      "screen_name": "見積依頼入力画面",
      "items": [
        {
          "label": "見積件名",
          "api_name": "Name",
          "ui_type": "テキスト|テキストエリア|数値|日付|日時|参照|選択リスト|チェックボックス|ボタン",
          "data_type": "String|Integer|Decimal|Date|DateTime|Boolean|Id",
          "required": true,
          "default_value": "",
          "validation": "バリデーションルールの説明"
        }
      ]
    }
  ]
}
```

## `business_flow[]` の書き方（重要）

> **🚨 スキーマ厳守（最重要）**: `business_flow[]` の各要素のキー名は必ず `step` / `actor` / `action` / `label` / `next` の **5 つだけ**にすること。
>
> - **`description` キーを使用してはならない**（`process_steps[]` のスキーマと混同しない）
> - `description` キーで書くと **業務フロー Excel シートと業務フロー図 PNG が両方とも空白**になる
> - `process_steps[]` は `{step, title, description}` 形式、`business_flow[]` は `{step, actor, action, label, next}` 形式。**両者は別スキーマ**

業務フローは**アクター（誰が）・業務アクション（何をするか）**を業務担当者視点で記述する。

**`action` と `label` は役割が違う。必ず両方書くこと**:

| フィールド | 用途 | 書き方 |
|---|---|---|
| `action` | **Excel の「処理内容」欄**。読み手が業務の流れを理解できる丁寧な文章 | 30〜80字の日本語。主語・目的語・動詞を省略せず完結した文で書く。末尾は動詞終止形（「〜する」「〜を受け取る」等）|
| `label` | **業務フロー図の PNG ボックス内に表示する一言まとめ** | 10〜20字の体言止め・短い述語。action の全文を埋め込むと図が横長になって読めないので必ず要約する |

- `action` と `label` で **同じ文字列を使ってはいけない**（図と表で冗長になる）
- `action` には**技術用語**（`画面フロー`・`Apex`・`Flow`・`Controller`・`Service`・`Handler`・メソッド名・クラス名）を書かない
- 「画面フロー」は Salesforce の構成要素名であって業務アクションではない。アクションには「画面から〇〇を入力し、申請する」のように業務視点で書く
- アクターは「お客様」「GF社担当者」「管理部門」「承認者」「自動フロー」「ポータル会員」「ゲスト」等の業務上の登場人物。コンポーネント名を入れない
- ステップ件数は **FG の業務範囲を網羅できる数**（通常 **5〜8 件程度**）。特定 UC の詳細化ではなく、**FG 配下の複数機能にまたがる actor × 主要動作を上から時系列で広く列挙**する
- 単機能しか含まない FG の場合のみ 3〜5 件でよい。複数シナリオ（認証・エラー・移行方針など）を含む FG では無理に 5 件に収めず 7〜8 件書く

### 業務フローは FG 全体を俯瞰、process_steps は UC 詳細

**役割分担を明確にする**:

| 項目 | スコープ | 粒度 |
|---|---|---|
| `business_flow[]` | **FG 全体の業務範囲**。複数 UC・複数画面・複数 actor を俯瞰して列挙 | 5〜8 件の主要ステップ |
| `process_steps[]` | **各コンポーネントの個別処理**。UC の処理フロー（docs/flow/usecases.md）を参考に各コンポーネント単位で詳細化 | コンポーネント数と同じ |

`docs/flow/usecases.md` の処理フロー記述は**特定 UC の詳細**であり、`business_flow` の情報源としてそのまま使うと FG 配下の他 UC や周辺機能が欠落する。usecases.md は `components[].responsibility` / `process_steps[].description` の基礎情報として使い、`business_flow` は FG 全体を俯瞰して書くこと。

**action / label のペア例（FG 横断の広い例）**:

| actor | action（処理内容欄） | label（図形ラベル） |
|---|---|---|
| 顧客 | 再申込依頼メール等に記載された契約申込 URL から認証画面へアクセスし、ユーザー名とパスワードを入力する | 契約申込 URL からアクセス |
| システム | URL パラメータから対象契約申込を特定し、関連する取引先責任者とユーザー情報を取得して認証対象を確定する | 契約申込を特定 |
| 顧客 | パスワード忘却時は新パスワード設定画面へ遷移し、新しいパスワードと確認入力を送信する | 新パスワード設定 |
| システム | ユーザ名・パスワードを入力しログインボタン押下でシステムがユーザー情報と照合して認証を実行する | ログイン認証 |
| ポータル会員 | ログイン後にポータル会員が自身の取引先責任者・ユーザー情報（氏名・メール・電話等）を閲覧し編集・保存する | プロフィール編集 |
| ゲスト | 認証エラー発生時は対応する標準エラーテンプレートに遷移し、利用者にエラー内容を表示する | エラーページ表示 |
| Salesforce 標準 Experience Cloud | 実運用のポータル UI は標準 Experience Cloud が提供するため、本カスタム VF 群は段階的に廃止する方針で運用する | Experience Cloud 移行 |

この例は **1 つの FG に 7 ステップ、actor は 5 種類**（顧客／システム／ポータル会員／ゲスト／標準 EC）の横断構成。「認証・リセット・プロフィール編集・エラー表示・移行方針」の**複数シナリオを網羅**しており、特定 UC に寄せていない。

**情報源の優先順位**:
1. 基本設計 JSON の `business_flow` がある場合 → それを**そのまま流用**（表現だけ詳細設計向けに微調整してよい）
2. ない場合は `screens[]` + `processing_purpose` + `prerequisites` + FG 配下の全 components から組み立てる
3. `docs/flow/usecases.md` は**特定 UC の詳細フロー**。business_flow の source にする場合は、**FG 配下の全 UC を俯瞰して各 UC 1〜2 件ずつ**拾う
4. `data_flow_overview` の矢印トークンは**Step1のアクション文として直接使わない**（技術フローの表現であり業務アクションではない）

**悪い例**:
- Step1: GF社担当者 / **「画面フロー」** ← 技術用語、業務アクションになっていない
- Step1: GF社担当者 / 「Create_CustomerUser.createUser() を呼び出す」 ← メソッド名、業務視点でない
- **1 つの UC しか書いていない**（FG 配下に複数機能があるのに、パスワードリセットの 4 ステップだけで閉じる等）← FG 俯瞰になっていない
- **`{"step": 1, "description": "..."}` 形式で書く** ← `description` キーは `process_steps[]` 専用。`business_flow[]` で使うと Excel と PNG が空になる。必ず `actor` / `action` / `label` を分けて書く

## `data_flow_overview` の書き方

矢印記法で左から右へ流れを表現する:
```
例: 見積依頼画面 → 入力検証担当のコントローラ → 番号採番・保存担当のサービス → 承認起動の自動フロー
    コントローラは入力検証のみを担い、保存責務をサービスに分離している設計。
```
