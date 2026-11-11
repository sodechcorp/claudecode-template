# Neo4j で組織の地図を図にする（Claude が会話から出す手順）

本人に頼まれたとき（「〇〇の関係を図で見せて」「〇〇を変えたらどこに響くか見せて」）と、説明に図があると早いときに、Claude がこの手順で Neo4j Browser に図を出す。**作成・入力・実行まで Claude が行い、本人は窓を見るだけ**。操作はすべて [onto_env.py](onto_env.py)。作業環境の作り方・ソデック用にした経緯は [../README.md](../README.md) の「Neo4j で見る」。

## 出す手順

1. `python onto_env.py status` で起動しているか・入っているシステムと TTL の作成日時を見る。止まっていれば `start`。見たいシステムが入っていない・force-app より古いときは `load --root <プロジェクトのルート> --repo <識別子> --name-ja <日本語名>`（1分半ほど）
2. **決まった型に当てはまるとき**は Cypher 集（[Salesforceの見方（Cypher）.txt](Salesforceの見方（Cypher）.txt)）の枠を使う

   | 頼まれ方の例 | 枠 | 変える値（`--set 名前=値`） |
   |---|---|---|
   | 項目・機能の名前が分からない | ⓪-1・⓪-2（表） | 探す言葉 |
   | 〇〇を保存すると何が動く？ | ① | オブジェクト |
   | 〇〇（項目）の値はどこから来てどこへ行く？ | ② | 項目・段数 |
   | 〇〇（項目）を変えたらどこを見る？ | ③ | 項目 |
   | 〇〇ボタン・画面で何が動く？ | ④ | 機能 |
   | 〇〇とつながっているオブジェクトは？・全体の関係図 | ⑤ | オブジェクト（'' で全体）・段数 |
   | 〇〇（項目）に関係する自動処理を全部・項目まわりの地図 | ⑥ | 項目 |

   `python onto_env.py show --query ⑤ --set オブジェクト=商談 --shot <スクラッチパッド>/show.png`
3. **当てはまらないとき**は Cypher を組み立てる（下の「グラフの形」「図の Cypher の型」）。スクラッチパッドにファイルで書き、`query --file` で丸と線の数を確かめてから `show --cypher-file <ファイル> --shot <png>`
4. `--shot` の画面を Read で見て、図が出ているか・読める大きさかを確かめる（線が束になって読めないときは、同じ丸どうしの線をまとめる・段数を減らして出し直す）
5. 本人には「Claude 用のブラウザの窓に出した」と、何が出ているか（丸 N 個・線 M 本、見どころ）を一言で添える

`show` がすること: Claude 用のブラウザの窓（Chrome。専用のプロファイル `<作業環境>/browser-profile`・リモートデバッグのポート 9333。普段のブラウザとは別）を開く（無ければ起動。会話が終わっても残る）→ 窓を前に出して最大化 → ログイン画面ならパスワードを環境変数から入れて接続 → 左の欄を閉じる → 前の結果を片付ける（`--keep` で残す）→ Cypher を入力して実行 → 入力欄を空にして図を見せる（先に読み取りで流して 0 件なら開かない。丸が 15 個を超えるときは、縮小で名前が消えないよう右の一覧の欄を閉じて1段拡大する）。Python の `playwright` が要る（`pip install playwright`。ブラウザの取得は要らない）。無いときは `open`（クリップボードに入れて普段のブラウザで開く。本人が Ctrl+V → Ctrl+Enter）

`query` で確かめること:

- **0 行**: 名前の書き方の違い（表示ラベルか API 名か）。⓪ で探し直す
- **丸が 150 個を超える**: 図が読めない。段数を減らす・起点を絞る・表で出す（`query` の結果を会話に表で載せる）
- 図にしなくても答えが出る問い（件数・一覧）は、Browser を開かずに `query` の結果を会話に載せる

## グラフの形（早見）

値はすべて n10s の配列（`head(n.cod__physicalName)` のように先頭を取る）。日本語の名前は `表示名`（配列ではない）。

| 丸（ラベル） | 中身 | 主な値 |
|---|---|---|
| `cod__Repository` | システム（URI `https://ontology.sodech.co.jp/code-data/<識別子>/repository`） | 表示名 |
| `cod__Table` / `cod__Column` | オブジェクト / 項目（URI は `…/code-data/db/<識別子>/…`） | cod__physicalName（API 名）・cod__dataType（Lookup・MasterDetail・Currency など） |
| `cod__Program` → `cod__Function` | 部品。`cod__qualifiedName` の頭で種類が分かる | `apex:` `trigger:` `flow:` `lwc:` `aura:` `vf:` `action:Obj.名前` `vr:Obj.規則` `wf:Obj.名前` `formula:Obj.項目` `rollup:Obj.項目` |
| `cod__Screen` / `cod__Batch` / `cod__ApiEndpoint` / `cod__OtherFeature` | 機能（画面・ボタン / バッチ / API / 保存・承認プロセス）。保存は 表示名 が「<オブジェクト>の保存（保存時に動く処理）」、承認プロセスは「<ラベル>（承認プロセス）」（承認プロセスから動く項目自動更新の入口。保存では動かない） | 表示名 |
| `cod__Transfer` / `cod__Calculation` / `cod__Aggregation` / `cod__Validation` | 演算（転記・計算・集計・入力チェック） | cod__ruleText・cod__formula・cod__sourceFile・cod__lineStart |
| `cod__ScreenField` / `cod__InterfaceField` | 画面・処理で使う項目（読むだけの項目の行き先。**組織への書き込みではない**。「書く項目」を出すときは `cod__outputTo` の先を `cod__Column` に絞る） | 表示名 |
| `cod__Unresolved` | 解析しきれなかった所（全項目を読む SOQL・項目名を変数で渡す put/get） | |

| 線 | 意味 |
|---|---|
| `cod__hasFunction`（Program→Function）・`cod__hasColumn`（Table→Column）・`cod__hasField`（画面・処理→その項目） | 持つ |
| `cod__hasEntryPoint`（機能→Function）・`cod__usedInFeature` / `cod__possiblyUsedInFeature`（Function→機能） | 機能の入口・その部品が動く機能 |
| `cod__calls` / `cod__possiblyCalls`（Function→Function） | 呼び出す（推定） |
| `cod__readsFrom` / `cod__writesTo`（Function→Table） | オブジェクトを読む・書く |
| `cod__sourceOf` / `cod__operandOf` / `cod__conditionOf` / `cod__lookupKeyOf` など（項目→演算）、`cod__outputTo`（演算→項目） | 値の流れ |
| `cod__definedIn`（演算→Function） | その演算を書いている部品 |
| `sf__referenceTo`（参照・主従の Column→参照先の Table） | オブジェクトの関係。共通基盤の語彙に無いので、`onto_env.py load` が取り込みのあとに足している |

**自動処理の性質**（`cod__Function` の値。共通基盤の語彙に無いので、`onto_env.py load` が取り込みのあとにメタデータから足している。値は文字列で、配列ではない）:

| 値 | 中身（例） |
|---|---|
| `種類` | レコードトリガーフロー・画面フロー・スケジュールトリガーフロー・自動起動フロー・Apex トリガ・Apex クラス・入力規則・項目自動更新・数式項目・積み上げ集計項目・クイックアクション（Flow）・LWC・Visualforce ページ |
| `動く時` | 保存前（Quote__c・作成・更新時）／保存後（…）／FeedComment: 保存後・作成／承認プロセス「〇〇承認」の最終承認時／ワークフロールール「…」（有効）の保存時／読むたびに計算（保存はしない）／子（…）の保存のあと／スケジュール（…） |
| `順番` `状態` `開始条件` | フローの triggerOrder／有効・無効・下書き／フローの開始条件の数式・条件 |
| `設定する項目` `設定する値` | 項目自動更新の項目と値（数式・固定値） |
| `呼ばれ方` | Apex クラスの入口（画面（LWC・Aura）・フロー・プロセス・スケジュール・バッチ・REST API・非同期） |
| `置ける場所` `開くもの` `データ型` `説明` `ヘルプ` `エラーの表示先` `APIバージョン` | LWC の置ける場所／クイックアクションが開くフロー・画面／数式の型／説明・ヘルプの文 など |

## 図の Cypher の型

- 丸は `apoc.create.vNode(['日本語の種類'], {name: n.表示名, 物理名: head(n.cod__physicalName), ファイル: head(n.cod__sourceFile)})`、線は `apoc.create.vRelationship(a, '日本語の線', {}, b)` で作り直し、`RETURN a, rel, b` で返す。丸の見出しは `name` に入れる（見出しに出ないときは、Browser の丸の見た目の設定で `name` を選ぶ）。Cypher 集の①④が手本
- 起点は 表示名 で引く（`t.表示名 + '.' + c.表示名 = '商談.金額'`）。システムは URI の頭で絞る（`n.uri STARTS WITH 'https://ontology.sodech.co.jp/code-data/' + システム + '/'`、オブジェクト・項目は `…/code-data/db/' + システム + '/'`）
- 広く辿るときは可変長（`*1..12`）を深くしない。経路の数が増えすぎるので、`apoc.path.subgraphNodes` / `subgraphAll` を使う（⑤が手本）
- 値を変える所は先頭の `WITH '…' AS 名前` にまとめる（`show --set`・`open --set` で差し替えられる）

## 守ること

- 問い合わせは読み取りだけ（`query` は READ_ACCESS、MCP `neo4j-sf` は読み取り専用）。中身を変えるのは `load`・`relations`・`reset-db` だけで、`reset-db` は本人に頼まれたときだけ
- パスワードを尋ねない・入力しない・表示しない・設定スクリプトを動かさない（`onto_env.py` が環境変数 `SODECH_NEO4J_PASSWORD` を読む）
- 図は候補。図に出ない＝使っていない、ではない（管理パッケージの中身・動的 SOQL・レコードのデータは入っていない）。結論を言う前にソースで確かめる
- 原本 `E:\DDD-Ontology` は操作しない
