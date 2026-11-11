# option-lineage-map（組織の地図で影響・依存・最終更新を引く）

## 何をするか

`force-app/main/default` から作る「組織の地図」（`.lineage/`）で、変更対象を**使っている部品**（逆方向）、部品が**使っているもの**（順方向）、オブジェクトを**保存すると動くもの**を数秒で引く。組織から読み取りで取った**部品の最終更新**と**レポート本体**も地図に入れられる。Grep の前に引き、Grep は地図に無いものの補完と裏付けに使う。地図の使い方の決まりはこのファイルにまとめ、各手順からはここを指す。

地図に入っているもの（詳細は [scripts/python/sf-lineage/README.md](../../../../scripts/python/sf-lineage/README.md)）:
- 部品 → 項目・選択肢の値・部品の参照: 項目（数式・積み上げ集計・参照の絞り込み・連動）・入力規則・リストビュー・レコードタイプ・ページレイアウト（項目・アクションの配置）・Lightning ページ・パス・レポートタイプ・レポート・ダッシュボード・アクション・ワークフロー（項目自動更新・メールアラート）・承認プロセス・割り当てルール・重複ルール・権限セット・プロファイル・リード変換・フロー・メールテンプレート・カスタムメタデータのレコード
- Apex の項目の読み書き・DML（変数の型の宣言から追う）、LWC・Aura・VF の参照、組織の外に出る動き（メール送信 ✉・外部呼び出し／イベント発行 ⇄）
- 値を写す連鎖（フロー・Apex が項目の値を別の項目へ入れる）と、部品の呼び出しの連鎖（画面部品 → それを埋め込むフロー → それを呼ぶアクション → それを置くレイアウト、レポートタイプ → レポート → ダッシュボードなど）
- 保存時の暗黙の連鎖（保存で動く入力規則・トリガー・レコードトリガーフロー〔保存前・保存後・順番〕・ワークフロー・重複ルールと、書き込み・積み上げ集計による親や別オブジェクトへの波及）。項目自動更新は、ワークフローのルールから呼ばれるものだけを「保存で動く」に入れ、承認プロセスから呼ばれるもの（申請・承認・却下・取り下げで動く）は別に出す
- テストクラス（`@isTest` と、名前に Test を含みテストからしか呼ばれないクラス）は「テストクラス」区分に分けて出す

## 引き方

プロジェクトのルートで実行する（地図が無いか force-app より古いときは、自動で作り直してから引く。書き込むのは `.lineage/` だけ）:

```bash
python scripts/python/sf-lineage/lineage.py who Obj__c.Field__c [LWC:名前] [クラス名] [フロー名] ...   # 使っている部品（逆方向・3段まで）
python scripts/python/sf-lineage/lineage.py save Obj__c                                              # 保存すると動くもの・波及・✉⇄の印
python scripts/python/sf-lineage/lineage.py uses <部品...>                                           # その部品が使っているもの（順方向）
python scripts/python/sf-lineage/lineage.py deps --manifest <package.xml>                            # 資材の外にある依存（デプロイの依存漏れ）
python scripts/python/sf-lineage/lineage.py label 表示ラベルの一部                                   # API 名が分からないとき
python scripts/python/sf-lineage/lineage.py status                                                   # 地図・最終更新・レポートの取得状況
# 組織から読み取りで取る（組織は変えない。本番でもよい）
python scripts/python/sf-lineage/lineage.py modified --target-org <本番> [--target-org <Sandbox>]     # 部品の最終更新日・更新者
python scripts/python/sf-lineage/lineage.py reports --target-org <本番>                              # レポート・ダッシュボードの本体（.lineage/ にだけ置く）
```

- 対象の書き方: `Obj__c.Field__c` ／ `LWC:名前`（Aura も）／ `QuickAction:Obj.名前` ／ `EmailTemplate:フォルダ/名前` ／ `EmailAlert:Obj.名前` ／ `Label:名前`（カスタム表示ラベル）／ `ReportType:名前` ／ `Report:フォルダ/名前` ／ クラス名 ／ フロー名 ／ オブジェクト名。選択肢の値は `--value 値`
- `who` の出力の区分: 「この対象に書き込む部品」／処理（2段目まで全部）／処理の3段目以降／全項目・どの項目か不明の読み書きをする部品（全項目の複製・項目名を変数で渡す処理）／画面・帳票（レイアウト・ページ・リストビュー・レポート・ダッシュボード・メール）／権限・レコードタイプ／確度が低い候補／テストクラス。画面・帳票などは先頭8件だけ出るので、全部見るときは `--all`
- 各行の `[N段]` は辿った段の数、`← …` は経由（数式・積み上げ、値を写した先、呼び出し元）、`(mid)`・`(low)` は確度。`modified` を取ってあれば、行の末尾に `〔最終更新 本番 日付 更新者／Sandbox 日付 更新者（本番より新しい）〕` が付く
- `save` の ✉ はメール送信（メールアラート・メール送信アクション・Apex の Messaging）、⇄ は外部呼び出し（HTTP・Web サービス）・プラットフォームイベントの発行。その処理が呼ぶクラス・フローの分も3段まで含む
- `deps` は、資材の部品が使うカスタムの部品のうち資材に無いものを出す。`modified` で本番の一覧を取ってあれば「✗ 本番に無く資材にも無い（入れないとデプロイが失敗する）」「？ 本番にも手元にも無い（名前の違い・標準・管理パッケージの可能性）」「○ 本番にある」に分ける
- `modified` は、手元の force-app より組織のほうが新しい部品（取り直しが要る）・組織にあって手元に無い部品・Sandbox のほうが本番より新しい部品（本番に未リリースの変更の候補）も出す

## 使う場面

| 場面 | 引くもの |
|---|---|
| /backlog Phase 1 investigator Step C (2) 3.（保存時に連動する処理・書き込み元の名前を挙げる）・Step C-2（兄弟入口） | `who <変更しそうな項目・部品／根本原因の共有部品>`・`save <更新するオブジェクト>` |
| Phase 3 backlog-planner B-1 0.（スコープ内の全量読込の列挙）。B-2 の副作用・表示条件・既存項目の流用の確認は B-1 0. で引いた結果を使い回す | 決定方針の変更対象で `who`・`save`・`label` |
| Phase 3.5 regression-guard Step 1・3（変更対象の依存先・副作用） | 変更対象の項目・部品で `who`、更新するオブジェクトで `save` |
| 逆参照（[option-reverse-grep.md](option-reverse-grep.md)・[option-diff-review.md](option-diff-review.md)） | `who`（Grep はメソッド名と確かめに使う） |
| 保存で動くもの・連鎖（[option-flow-trigger-trace.md](option-flow-trigger-trace.md)・[option-impact-scope-grep.md](option-impact-scope-grep.md)・[option-data-migration-plan.md](option-data-migration-plan.md)） | `save`・`who` の「処理」区分 |
| 権限・影響ユーザー（[option-permission-fls-check.md](option-permission-fls-check.md)・[option-user-impact-survey.md](option-user-impact-survey.md)） | `who` の「権限・レコードタイプなど」区分（値は XML・組織で確かめる） |
| 画面の証跡（[option-evidence-check.md](option-evidence-check.md)） | `who` の「画面・帳票」区分（項目・Apex・フローの変更でも画面に出るか） |
| テストクラス（[option-test-class-impact.md](option-test-class-impact.md)） | `who` の「テストクラス」区分（名前の規則で拾えないもの・変更する項目のデータを作るもの） |
| 回帰テスト（/test Phase B-0 → test-spec-builder 軸2・軸3、[option-regression-test.md](option-regression-test.md)） | 変更した部品・項目で `who --depth 2`・`save --depth 1` |
| リリース（[option-deployment-dependency-check.md](option-deployment-dependency-check.md)・[option-org-drift-check.md](option-org-drift-check.md)） | `deps --manifest`・`who` / `uses LWC:名前`（親子）・`modified`（本番と Sandbox） |
| いつ・誰が変えたか（[option-git-blame-history.md](option-git-blame-history.md)。force-app が git 管理外で履歴が無いとき） | `modified` のあと `who` |

## 守ること

- **地図は候補。** investigation.md・implementation-plan.md・validation-report.md・test-spec.md・release-plan.md に「影響あり／なし」を書く前に、該当するファイル・行をソースで確かめる（`refs.jsonl` にファイルと行がある）
- **地図はクラス単位。** メソッド単位の呼び出し元は出ない。メソッドを本当に呼ぶかは、呼び出し元のファイルで確かめる（メソッド名の Grep）
- **有効／無効は組織で確かめる。** 地図は最後に取得した force-app の写しから作る。「無効だから影響なし」は [option-flow-trigger-trace.md](./option-flow-trigger-trace.md) 手順2 で組織に問い合わせてから
- **鮮度。** 地図は force-app より古ければ自動で作り直すが、force-app 自体が組織より古いことは、`modified` を取らないと分からない。`status` で「手元より組織のほうが新しい部品」が多いときは、/sf-retrieve で取り直してから引く
- **確度が低い候補**（同名の項目の出現など）は、確かめてから使う。確かめずに影響ありとも影響なしとも書かない
- **書き込むのは `.lineage/` だけ。** 読み取り専用の役割（ファイルを作らない決まりのエージェント）でも、地図の作り直し・`modified`・`reports` の保存先 `.lineage/`（Git では追跡しない）への書き込みは例外として許す。`modified`・`reports` が組織に対して行うのは読み取り（一覧の取得・retrieve）だけで、force-app には書かない
- 引いた結果は、記録先の節に1行で残す: `地図（{作成日時}）: 処理 {N}（{主な名前}）・画面帳票 {N}・権限 {N}・保存で動くもの {N}`

## 地図に無いもの（Grep・組織で補う）

| 無いもの | 補い方 |
|---|---|
| 取得していない部品（force-app に無いものは地図にも無い。レポート・ダッシュボードは `reports` で取れる） | 取得範囲を確かめる。`modified` の「組織にあって手元に無い部品」も見る |
| 本番だけにある部品・取得の後の変更 | `modified` と、対象組織での確認（option-org-drift-check） |
| メソッド単位の呼び出し関係 | メソッド名の Grep |
| 管理パッケージの中身 | 名前空間付きの部品は中身が見えない。提供元の資料で |
| 文字列で組み立てる SOQL の項目・項目名を変数で渡す処理の具体的な項目 | 「全項目・どの項目か不明」の区分に出た部品を読んで確かめる |
| カスタム設定の値・データ・件数 | 組織で確かめる |
| 変更の理由 | 課題・作業ログ（`modified` は日付と更新者だけ） |
| 組織の外（外部システム・帳票ツールのテンプレート） | 資料・担当者 |
