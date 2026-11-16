# 使う側との突き合わせ（Apex が取る項目 ⇔ 画面の部品が表示する項目）

Apex の SOQL の取得項目・戻り値（Map のキー・ラッパークラスの項目）と、その Apex を使う Aura・LWC・Visualforce が表示する項目が合っているかを確かめる。部品の中の項目の参照は Salesforce の依存関係（MetadataComponentDependency）に出ず、デプロイもテストも通るため、ここで確かめないと本番で列が黙って空になる（実例: ASNO-44。処理クラスの取得項目を見積経由に変えたが、それを表示する Aura を変更セットに入れず、本番で7つの表の案件列が空になった）。参照元を挙げる（grep・組織の地図の `who`）だけでは、使い方が合っているかは確かめたことにならない。

## 対象

次のどれかに当たる Apex クラス（新規・変更）。スクリプトには、画面の部品の controller になるクラスを渡す。
- `@AuraEnabled`・`@RemoteAction`・Visualforce の controller / extensions に当たり、SOQL の SELECT・戻り値の Map のキー・ラッパークラスの項目のどれかが変わるもの
- 上のクラスから呼ぶサービス・セレクターのクラスの SOQL を変えたときの、呼び出し元の controller のクラス（サービスのクラスを渡しても使う部品が見つからない）
- Aura・LWC・Visualforce の側だけを変えて表示する項目を足した・変えたときの、その部品の controller のクラス（Apex を変えていなくても、取っていない項目を表示しうる）

## いつやるか

| 時点 | やること |
|---|---|
| `/backlog` Phase 3.5（[regression-guard.md](../../agents/regression-guard.md) Step 1。実装の前） | 実装計画で上の変更をする Apex を使う部品（Aura・LWC・VF）を挙げ、変更対象に入っているかを確かめる |
| `/backlog` Phase 5（[option-diff-review.md](../backlog/options/option-diff-review.md) の「4. 影響範囲再 rescan」。実装の後） | force-app で下の手順 2・3 |
| `/release` Phase 2 の4.（[release-preparer.md](../../agents/release-preparer.md)。最終資材） | デプロイする資材のとおりの組み合わせで下の手順 1〜4 |
| `/release` を使わず手作りの手順書でリリースする | 資材を確定した時点で下の手順 1〜3 を1回（[CLAUDE.md](../../CLAUDE.md) の確認項目表。`{tmp_dir}` は `docs/logs/{課題ID}/.tmp`、本番の別名は [prod-readonly-check.md](prod-readonly-check.md) で確かめたもの） |

## 手順

1. **比べるフォルダ（ルート）を用意する**（`/release` と手作りの手順書でのリリース。実装の後はルートを `force-app/main/default` にして手順 2 へ）: **デプロイする資材のとおりの組み合わせ**（資材の Apex・部品は資材の版、資材に入れない部品・controller のクラスは本番の版）で比べる。force-app の部品で比べると、「開発環境では直っているが資材に入っていない」漏れを見落とす。
   1. 前回の `{tmp_dir}/contract-prod` が残っていれば消す（[cleanup-rules.md](../../spec/cleanup-rules.md) の project_dir 配下の削除に従う。残っていると、前回取った古い部品で比べてしまう）
   2. 使う側の部品を挙げる: 対象の Apex を使う Aura・LWC・Visualforce（`cd "{project_dir}" && python scripts/python/sf-lineage/lineage.py who {クラス名}`、または force-app を `controller="{クラス名}"`・`@salesforce/apex/{クラス名}.`・`extensions=` で Grep）と、その Aura が値を渡す子コンポーネント（`<c:子 属性="{!…}"/>` の子。行・一覧・結果全体・参照先のレコードのどれを渡すものも）
   3. 2. の部品と対象の controller のクラスのうち、資材マニフェストに無いものを本番から取る（force-app には取らない。種類は AuraDefinitionBundle・LightningComponentBundle・ApexPage・ApexComponent・ApexClass）:
      ```bash
      cd "{project_dir}" && sf project retrieve start --metadata "AuraDefinitionBundle:{名前}" --metadata "ApexClass:{controller の名前}" --target-metadata-dir "{tmp_dir}/contract-prod" --unzip --target-org "$PROD_ALIAS" --json
      ```
      本番に無い・取れなかった部品は「本番の版で未確認」として記録する（`/release` は最重要警告）
   4. 取れたフォルダ（`aura/`・`classes/` がある階層。Glob で確かめる。何も取らなかった場合は `{tmp_dir}/contract-prod/root` を作る）に、資材マニフェストの Apex クラス（`.cls`）と Aura・LWC・VF を force-app からコピーする（資材の版で上書き）
   5. 2. の部品と対象の controller のクラスがルートにそろっているかを Glob で確かめ、そのフォルダをルートにする
2. **スクリプトで突き合わせる**:
   ```bash
   cd "{project_dir}" && python -I scripts/python/sf-lineage/contract_check.py "{ルート}" {対象の controller のクラス名…}
   ```
   終了コードは 0 = NG なし、1 = NG あり、2 = 指定したクラス・`classes/` がルートに無い（資材に無い controller は手順 1 の3. で本番から取って置き、やり直す）、3 = 読めないファイル（UTF-16 等）・処理の失敗（結果は使わず、原因を直してやり直す）。「対象の Apex」の行に、画面に返すキーの数・追えない経路のあるキーの数・使う部品の数（Aura・LWC・VF）が出る
3. **判定**:
   - **NG（取っていない項目を表示）**: 該当の Apex と部品の箇所を開いて確かめる。本当に取っていなければ止める。`/backlog` では option-diff-review の戻り判定に従う（直す部品が実装計画の変更対象に入っていれば Phase 4、入っていなければ Phase 3）。`/release` では最重要警告にし、部品を資材に加えるか、Apex の取得項目を戻すかを担当者が決める。スクリプトの誤検知（下の「スクリプトが追えるもの・追えないもの」の「誤って NG にしうる形」）と確かめたら、根拠（`ファイル名:行番号`）を書いて OK にしてよい
   - **要目視**: Apex の該当箇所と部品の該当箇所を開いて照合し、結果を記録する（`/backlog` は option-diff-review の結果、`/release` は release-plan.md「## 影響範囲サマリー」）。「静的に追えない」を OK として扱わない。LWC は `.html` の `{item.項目}`・`.js` の `record.項目`・`getFieldValue`、Visualforce は `{!…}` の項目を照合する。「使う部品がルートに1つも無い」は、使う部品の置き忘れ（手順 1 の 2.）か、サービスのクラスを渡していないか（上の「対象」）を見直す
4. **画面確認に入れる**（`/release` のみ）: その部品を置いた画面（タブ・Lightning ページ）を、本番の画面確認の表に入れる（release-preparer の画面確認の表の (c)）。使い終わった `{tmp_dir}/contract-prod` は release-preparer「Phase 最終: クリーンアップ」で消す

## スクリプトが追えるもの・追えないもの

作りの決まり: 部品の中の式（`{!…}`・`{#…}`）を全部たどり、項目らしい参照（カスタムは `__` を含み、標準は大文字で始まる名前）は、必ず「判定する（NG）」か「要目視に出す」のどちらかにする。どちらにも当たらない参照は残さない。

- **追える（判定して NG を出す）**:
  - Apex 側（メソッドごと）: 変数の出どころを「= [SELECT …]」「.addAll(…)」「for (型 a : …) の中の .add(a)」「= 別の変数」ごとに持つ。画面に返すものは `.put('キー', …)`・`new Map<…>{'キー' => …}`・ラッパーの項目（`r.opp = …`）・Map で返さないメソッドの戻り値。子問い合わせは「リレーション名.項目」、集計・別名は別名、`toLabel()`・`format()`・`convertCurrency()` は中の項目として扱う
  - Aura 側（controller の `.cmp`・`.app`）: 属性は同じ名前の Map のキー、または JS の `component.set('v.属性', 結果.キー)` で結ぶ。`{!v.A.キー.項目}` は途中のキーで、繰り返しの変数（`items` の `{!…}`・`{#…}`、入れ子の `{!親の変数.子リレーション}`）、子コンポーネントに渡した値（行・一覧・結果全体・参照先のレコード）は渡した元の出どころで判定する。LWC の子は `.html` の `{属性.項目}`、datatable 等の `data="{!…}"` は JS の列の `fieldName` を照らす。単引用符・`<!-- -->` の中・大文字小文字の違いも扱う
- **要目視に出す**: 出どころを追えない（`Database.query`・サービスの戻り値・中かっこの無い for）、一部の経路を追えない（同じ変数・キーに SOQL 以外からも入る）、経路（SOQL）によって項目が違い一部に無い、属性と結ぶ Map のキーが無い（Map で返さないメソッドがあればその取得項目を添える）、子リレーションの項目を SOQL から追えない、`FIELDS()` の SOQL、子コンポーネントがルートに無い、LWC の子の JS で使う値、Apex を直接 import する LWC と Visualforce、使う部品がルートに1つも無いクラス
- **見ない**: 項目らしくない名前（小文字で始まり `__` を含まない。JS で足した値・`length` 等）、JS の中で組み立てる表示（`component.set` の後に加工した値・JS で作る列）、標準の部品（`lightning:` 等）に渡した値。子コンポーネントの入れ子が4段より深いもの・自分を入れ子にするものは要目視に出して先を追わない。変更の内容がこれに当たるときは目視で照合する
- **誤って NG にしうる形**: 大文字で始まるが Apex から来ない値（JS で `Total` などを足した値）。逆に、`TYPEOF` の参照先の下の項目は全部あるものと見なす（ここだけは取り忘れを見逃しうる）
