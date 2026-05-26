## 品質基準（最重要）

**「読んだものは全て書く」**。ソースを読んで得た情報を端折らない。

### 推測禁止（API名・項目名・オブジェクト名）

- `force-app/` および `docs/catalog/` に**実在しない** API 名・項目名・オブジェクト名を JSON に含めない
- ソース・メタデータ・docs を読んでも特定できない場合は値を `[要確認]` とする（空文字や推測で埋めない）
- 「たぶんこの項目名だろう」「この命名規則なら〜だろう」という推測は禁止。実在を確認できないものは必ず `[要確認]` を使う

### 参照ファイルの記録（references）

Phase 1 で `docs/design/` / `docs/requirements/` / `docs/catalog/` 等を参照した場合、生成 JSON に `references` フィールドを追加して参照ファイルのパスを記録する（リスト形式）。

```json
{
  "references": [
    "docs/design/apex/SomeController.md",
    "docs/catalog/Quote__c.md"
  ]
}
```

> スクリプト（generate_feature_design.py）はこのフィールドを処理しない（unknown field として無視される）。デバッグ・監査・後続レビューで「どの docs を根拠に書いたか」を追跡するための情報。参照しなかった場合は省略してよい。

### API名 vs 日本語ラベルの使い分け（全箇所共通）

| 記述対象 | 表記ルール | 例 |
|---|---|---|
| 自クラス名 | API名でOK | `RequestController`、`CommonUtil` |
| 他クラスへの呼び出し | クラス名はAPI名でOK。**メソッド名は書かない** | `createQuoteController を呼び出す`（`createQuote()` は禁止） |
| オブジェクト名 | **日本語表示ラベル** | `Quote__c` → 「見積」、`BusinessTraveler__c` → 「出張申請」 |
| 項目名 | **日本語表示ラベル** | `Status__c` → 「ステータス」、`IsInvoiceContact__c` → 「請求先フラグ」 |
| sub_steps の SOQL/DML | API名・コードのまま | `SELECT Id FROM Quote__c WHERE ...` |
| calls / object_ref の図形ラベル | どちらでもOK | `CommonUtil`、`見積` |

> ❌ 禁止例: 「createQuoteControllerはBusinessTraveler__cのStatus__cを更新しProductListConditionDetail__cからQuoteDetail__cを生成する」
> ✅ 良い例: 「createQuoteControllerを呼び出し、出張申請のステータスを更新後、商品リスト条件明細から見積明細を生成する」

- **steps**: 処理の全ステップを記述する。「処理を実行」のような抽象的な記述は禁止
  - `title` は **日本語で何をする処理か**（自クラス名はOK・他クラスのメソッド名禁止・オブジェクト名は日本語ラベル）
  - `detail` は **日本語の説明のみ**（何をする処理か・2行以内）。コードは混入しない
  - SOQL・DML は **sub_steps に分離して記述する**（タイトル = "SOQL" / "DML"）
  - SOQL は `detail` に SELECT / FROM / WHERE / ORDER BY で改行して記述する
  - DML は `detail` に「対象: {Object} / 操作: INSERT|UPDATE|DELETE / フィールド: 〇〇, △△」形式で記述する
  - **計算・変換処理を含むステップは「計算」サブステップとして detail に日本語で記述する**
    - 例: `{ "title": "計算", "detail": "営業日加算後の日付 = 基準日 + n 営業日（土日・祝日をスキップ）" }`
    - 例: `{ "title": "計算", "detail": "合計金額 = 単価 × 数量。数量が 0 の場合は 0 として扱う" }`
    - 例: `{ "title": "変換", "detail": "日付文字列（YYYY-MM-DD）→ Date 型に変換して比較" }`
    - 四則演算・日付計算・型変換・条件による値の決定など、「何をどう計算するか」が読んで分かるレベルで記述する
  - **SOQL/DML を含むステップには必ず `object_ref: { "text": "ObjectApiName" }` を付与すること（絶対に省略しない）**
  - 条件分岐は `node_type: "decision"` + `sub_steps` で各分岐先を展開する
  - 同一ステップにSOQLとDMLが両方ある場合は sub_step を「SOQL」「DML」の順で並べる
- **sub_steps**: SOQL / DML / 各分岐先など、コードや詳細項目を1行ずつ展開する
- **input_params / output_params**: 全パラメーターを漏れなく記述する。型・必須/任意・説明を揃える
- **trigger**: 起動タイミングをコードから特定する（`@InvocableMethod` / `@AuraEnabled` / Flow のイベント / バッチスケジューラー等）
- **overview**: エントリーポイントから終了まで一気に説明する。**2〜3文・200文字以内**を目安にする（機能一覧の処理概要としてもそのまま使用される）
  - クラス名はAPI名でOK。オブジェクト名・項目名は**日本語ラベル**で記述する
  - 他クラスへの言及はクラス名のみ（メソッド名まで書かない）
  - **禁止**: javadoc の1行抜粋・「XXXコントローラー」「XXXユーティリティ」のような種別名のみ・空文字
  - 必ずソースコードを読んで**具体的な処理内容・連携先**を含めること
- **prerequisites**: 前提条件がなければ「特になし」。ある場合は設定・認証・他機能の実行順序を明記する

---

## スケルトンモード（Apex解析スクリプト経由）

`extract_apex_skeleton.py` が生成したスケルトン JSON を受け取った場合は、このモードで動作する。

渡された JSON に `"_parser_meta"` フィールドが存在する場合 = スケルトンモード。

**禁止フィールド（スクリプトが確定済み）**: `node_type` / `calls` / `object_ref` / `branch` / `sub_steps[].title（SOQL/DML）` / `sub_steps[].detail` / `api_name`

**記述するフィールド**: `name`（日本語）/ `overview.*` / 各 `steps[].title` と `steps[].detail`（日本語のみ）/ `params` / `_parser_meta`（**削除する**）

スケルトンモード適用手順（sf-design-writer.md の Phase 0.5 参照）:
- Phase 1 では、このスケルトンを**ベース**として使い、`title` / `detail` / `overview` を補完する
- **⚠️ 補完必須・スケルトンのまま終了禁止**: スケルトン JSON（`_parser_meta` を含む状態）は中間成果物であり最終成果物ではない。`name`（日本語）/ `overview.*` / `steps[].title` / `steps[].detail` を全て補完し、完了後は必ず `_parser_meta` フィールドを削除してから Phase 1.5 チェックへ進む。補完せずにスケルトンのまま Phase 1.5 / Phase 2 へ進むことを**明示的に禁止する**。
- **`calls` / `object_ref` / `branch` / `node_type` は上書き禁止**（機械的に確定済み）
- スケルトンのステップ数が明らかに不足している場合（大型クラスで主要ロジックが欠落）は、不足分のステップのみ追加してよい

スケルトンが生成できなかった場合（.cls ファイルが存在しない・構文が解析不能等）は Phase 1 で通常通り生成する。

---

## 吸収コンポーネントの処理ルール

feature_list に `"absorb_into"` フィールドがある機能は**単独の設計書を作らない**。
代わりに、吸収先（親）の設計書を生成するときにそのソースも読んで内容を取り込む。

| 種別 | 吸収先 | 取り込む内容 |
|---|---|---|
| **Trigger** | `absorb_into` に指定されたハンドラークラス | 起動タイミング（before/after, オブジェクト名）→ハンドラーの `prerequisites` に記載。ハンドラー呼び出し条件 → ハンドラーの最初の step として記載 |
| **LWC モーダル** | `absorb_into` に指定された親LWC | モーダルの JS・HTML を読んで完全なフローを親の `usecases` に展開して追加。「開く」だけでなく「{モーダル名}を開く → 確認画面を表示 → [OK/キャンセル]ボタン押下 → 実行処理 or キャンセル」まで各ステップを書く。入出力プロパティ → 親の `param_sections` に追記 |

**吸収コンポーネントの処理手順**:
1. feature_list を一覧したとき `absorb_into` が設定されている feature は「吸収対象」と記録しておく
2. 親コンポーネントを処理するとき、その親の `absorb_into` 元となっている feature のソースも**必ず**読む
3. 読んだ内容を親の JSON に取り込む（上表参照）
4. 吸収対象の feature については Phase 2 でスクリプトを呼ばない（xlsx を作らない）

> **例**: `consultationModal` の `absorb_into = "consultation"` → `consultation` を処理するとき `consultationModal/` も読み、「コンサルテーションモーダルを開く」ユースケースを `consultation` の画面設計書 JSON に追加する。モーダル単体の xlsx は作らない。
