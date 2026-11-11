# Phase 1: ソース読み込み（グループごとに繰り返す）

## 1-1. グループのコンポーネント取得

feature_groups.yml から対象グループの `feature_ids` を確認する。

## 1-2. 各コンポーネントのソースを読む

| 種別 | 読むファイル | 詳細設計で注目する点 |
|---|---|---|
| Apex | `.cls` | クラスコメント / `public`・`@AuraEnabled`・`@InvocableMethod` メソッド / try-catch 構造 |
| LWC | `.js` + `.html` | `@wire` / `@api` プロパティ / `connectedCallback` / テンプレート内の入力要素と条件 |
| Flow | `.flow-meta.xml` | `<screens>` / `<recordCreates>` / `<actionCalls>` / 分岐条件 |
| Visualforce | `.page` | `<apex:form>` 内の入力項目 / controller / action メソッド |
| Aura | `.cmp` + `.js` | コントローラー / ヘルパー / `<aura:attribute>` |
| Trigger | `.trigger` | トリガーイベント（before/after insert/update 等）/ ハンドラークラスへの委譲 |

**読み方の優先順位**:
1. クラス・コンポーネントの冒頭コメント（役割説明）
2. public / @AuraEnabled / @InvocableMethod メソッドのシグネチャとコメント
3. 入力受取から出力返却までの主な流れ
4. try-catch と例外の種類

## 1-2.5. 画面コンポーネントの扱い（必読）

`screens[]` は UI コンポーネント全般を対象とする。LWC / Aura / Visualforce に加え、**画面フロー（Screen Flow）も必ず含めること**。

**画面フローの判定**: `.flow-meta.xml` の中に以下の両方が含まれるものは画面フロー:
- `<processType>Flow</processType>`
- `<screens>` タグ（1つ以上）

## 1-2.6. VF/LWC/Aura の controller 紐付け Apex を components に必ず含める（必読）

**UI コンポーネント（VF/LWC/Aura）は単独で動かない。その背後にある Apex Controller／Helper／Service／Handler を `components[]` に必ず含めること**。グループ内に UI しか無いように見えても、以下を辿って Apex を展開する：

| 起点 | 辿り方 | components に追加する Apex |
|---|---|---|
| Visualforce `.page` | `<apex:page controller="XxxCtrl">` / `<apex:page extensions="YyyExt">` / `<apex:page standardController="ZZZ">`（標準コントローラ利用時は extensions 側のみ） | `XxxCtrl` / `YyyExt` |
| Visualforce `.page` | body 内の `{!action.method()}` / `{!controller.xxx}` / `{!$RemoteAction.Class.method}` | 参照先 Apex クラス |
| LWC `.js` | `import xxxMethod from '@salesforce/apex/ClassName.methodName'` | `ClassName` |
| LWC `.js` | `@wire(xxxMethod, {...})` の import 先 | `ClassName` |
| Aura `.cmp` + `.js` | `<aura:component controller="ClassName">` / helper 内の `$A.enqueueAction` 経由の AuraEnabled | 参照先 Apex クラス |
| Apex Class | 本体で呼び出している他 Apex クラス（`Service`・`Handler`・`Selector` 等の委譲先） | 呼び出し先 Apex クラス |
| Apex Trigger | `.trigger` → Handler クラス委譲 | Handler クラス |

**組織の地図があれば**: 上の表の辿りの候補を、プロジェクトのルートで `python scripts/python/sf-lineage/lineage.py uses <起点>`（VF は `VF:名前`、LWC は `LWC:名前`、Aura は `Aura:名前`、Apex クラス・トリガーは名前。複数まとめて渡せる）の「呼ぶ・埋め込む部品」から取り、出た Apex を同じく `uses` で辿って Controller → Service → Selector まで広げる。手で辿った結果と突き合わせ、地図にだけ出たものはソースで確かめてから `components[]` に入れる（地図は候補。[option-lineage-map.md](../backlog/options/option-lineage-map.md)）。同じ出力の「書き込むオブジェクト」「読むオブジェクト」は `responsibility` の R/W を書くときの確かめにも使える。

**ポイント**:
- UI コンポーネントだけを `components[]` に並べると「関連コンポーネント」シートが VF/LWC ばかりになり、業務のデータ更新が見えない（object_access が参照のみになる）。これは**設計書として不十分**。必ず Apex まで展開する
- Apex Class の `responsibility` には **R/W どちらの操作をするか**が読み取れる説明を書く（例: 「契約申込の照合結果に応じて `User` / `Contact` を更新する」）。これが `object_access` の W 判定に使われる
- ただし、本当に UI のみで Apex 連携が存在しない標準ボイラープレートの VF（`SiteLogin` / `FileNotFound` / `Exception` / `Unauthorized` 等）は Apex 展開不要
- `<c:xxx>` 等の埋込カスタムコンポーネント（`.component` ファイル）も独立コンポーネントとして `components[]` に入れる

画面フローを `screens[]` に入れる時の書き方:
- `component`: Flow の API 名（例: `Create_CustomerUser`）
- `screen_name`: `<label>` タグの値 or `<screens><name>` の値を使い、業務的な名前にする（例: 「取引先責任者ユーザー発行画面」）
- `items[]`: `<screens>` 内の `<fields>` を走査して1つずつ登録（`<dataType>` → data_type, `<isRequired>` → required, `<fieldText>` → label）

> **禁止**: 画面フローなのに `screens: []` で出してはいけない。その場合、業務フロー Step1 が「画面フロー」というゴミ文字列になる。

## 1-3. 既存設計資料の確認（あれば）

```
docs/requirements/         — 要件定義
docs/design/               — 既存の機能別設計書 MD（プログラム設計）
```

プログラム設計書がある場合は `steps` から `interfaces` の内容を一部転用できる。
