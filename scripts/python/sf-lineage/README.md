# sf-lineage（組織の地図）

`force-app/main/default` から「組織の地図」を作り、保守の影響調査で「この項目・部品を使っているのは誰か」「このオブジェクトを保存すると何が動くか」を数秒で引くためのスクリプト。使い方の決まり（候補として使い、ソースで裏付ける・地図に無いもの）は [option-lineage-map.md](../../../.claude/templates/backlog/options/option-lineage-map.md)。

## 使い方（プロジェクトのルートで）

```bash
python scripts/python/sf-lineage/lineage.py who Obj__c.Field__c [LWC:名前] [クラス名] ...   # 使っている部品（3段まで）
python scripts/python/sf-lineage/lineage.py save Obj__c                                      # 保存すると動くもの・その波及
python scripts/python/sf-lineage/lineage.py label 金額                                       # 表示ラベルで項目を探す
python scripts/python/sf-lineage/lineage.py uses <部品...>                                   # その部品が使っているもの（順方向）
python scripts/python/sf-lineage/lineage.py deps --manifest <package.xml>                    # リリースの資材の外にある依存（デプロイの依存漏れ）
python scripts/python/sf-lineage/lineage.py unused [--type field|apex|flow|lwc|vf]            # 使われていない部品の候補（棚卸し・削除の影響確認）
python scripts/python/sf-lineage/lineage.py status                                           # 地図の作成日時・古いか・組織との比較・レポートの取得状況
python scripts/python/sf-lineage/lineage.py build                                            # 作り直す
python scripts/python/sf-lineage/lineage.py modified --target-org <本番> [--target-org <Sandbox>]   # 部品の最終更新日・更新者（組織から読み取り）
python scripts/python/sf-lineage/lineage.py reports --target-org <本番>                      # レポート・ダッシュボードの本体（組織から読み取り）
python scripts/python/sf-lineage/lineage.py export --repo <識別子> --name-ja <日本語名>       # Neo4j で見る用の中間JSON（下記）
```

- 地図は `.lineage/`（Git では追跡しない）。who・save・label・uses・deps は、地図が無いか force-app より古いときに自動で作り直してから引く（数秒〜十数秒）
- `modified`・`reports` は組織に読み取りだけを行う（Metadata API の一覧取得・retrieve）。force-app には書かず、`.lineage/` に置く（レポートは `.lineage/extra/_proj/retrieved/`。取り込み用の仮のプロジェクトから取るので、プロジェクトのフォルダは変えない）。`modified` を取ると `who` の各行に本番・Sandbox の最終更新が付き、`deps` が本番にあるかを判定できる
- 必要な部品: `pip install -r scripts/python/requirements.txt`（Apex の解析に `tree-sitter-language-pack` を使う。無くても XML の分と SOQL の名前の出現は作れる）

## 中身

| ファイル | 役割 |
|---|---|
| `lineage.py` | 入口（build / status / who / save / label / uses / deps / unused / modified / reports / export） |
| `modified.py` | 部品の最終更新日・更新者を組織から取る（取り直しが要る部品・本番に未リリースの変更の候補も出す） |
| `reports.py` | レポート・ダッシュボードの本体を組織から取る |
| `deps.py` | 順方向の依存（uses）と、資材の外にある依存の確かめ（deps） |
| `unused.py` | 使われていない部品の候補（項目・Apex・フロー・LWC・VF。入口・保存で動くフローは除く） |
| `build_refs.py` | XML のメタデータ（項目・入力規則・画面・帳票・権限・設定・フロー・ワークフロー・メール）と、Apex・LWC・Aura・VF の参照を作る |
| `apex_refs.py` | Apex の項目の読み書き・DML・写す連鎖（変数の型の宣言から追う） |
| `who_uses.py` | 使っている部品を引く（数式・積み上げ集計、値を写した先、部品の呼び出し元・レポートタイプ → レポート → ダッシュボードを辿る。最終更新を付ける） |
| `save_chain.py` | 保存時の暗黙の連鎖（保存で動くものと、書き込み・積み上げ集計による波及。メール送信 ✉・外部呼び出し ⇄ の印） |
| `to_intermediate.py` | 地図を、項目リネージの共通基盤（DDD-Ontology の lineage-core）の中間JSONに書き出す（Salesforce 用のアダプター） |
| `neo4j/Salesforceの見方（Cypher）.txt` | Neo4j Browser に貼るだけで、保存で動くもの・項目の流れ・項目を変えるときに見る所・画面/ボタンから動く処理を図で出す |
| `neo4j/onto_env.py` | Neo4j の作業環境（DDD-Ontology）を会話から操作する（ソデック用にする・起動・停止・取り込み・オブジェクトの関係の線・ブラウザで開く・問い合わせ） |
| `neo4j/README.md` | Claude が会話から図を出す手順（決まった型・その場で組み立てる Cypher）とグラフの形の早見 |

出力の `refs.jsonl` は1行1参照（参照元の種類・名前・ファイル・行・役割・対象・確度）。

## Neo4j で見る（任意。説明・理解用）

普段の課題対応は who・save で引く。つながりを図で見せる・探るときだけ、DDD-Ontology の作業環境（原本から `new-onto-env.cmd` で作ったもの）の Neo4j に入れる。

操作は `neo4j/onto_env.py`（作業環境は `--env` か環境変数 `ONTO_ENV`。無ければ `C:\work\Onto-sf-lineage` → `E:\Onto-sf-lineage` の順に探す）:

1. 初回だけ: 原本の Neo4j を止めて `new-onto-env.cmd` で作業環境を作る → `onto_env.py setup`（作業環境の中のパスを実際の場所に、名前空間をソデック用 `https://ontology.sodech.co.jp/` に、パスワードの環境変数を作業環境専用の `SODECH_NEO4J_PASSWORD` にし、show 用の playwright を作業環境の .venv に入れる）→ `onto_env.py start` → `onto_env.py reset-db --yes --password-env LINEAGE_NEO4J_PASSWORD`（原本からコピーした中身を消す）→ **利用者が**作業環境の `set-neo4j-password.cmd` で新しいパスワードを決める
2. `onto_env.py load --root <プロジェクトのルート> --repo <識別子> --name-ja <日本語名>`（地図 → 中間JSON → TTL → 取り込み → SHACL 検証。識別子は英数字・`_`・`-`。`t_` で始めない）
3. `onto_env.py show --query ② --set 項目=<オブジェクト.項目>`（Claude 用のブラウザの窓で、ログイン・`neo4j/Salesforceの見方（Cypher）.txt` の枠の入力・実行まで行い、図がそのまま出る）。その場で組み立てた Cypher は `show --cypher-file`。`onto_env.py query "<Cypher>"` で表でも引ける

- **E: ドライブ・PC 起動時のコマンドは要らない**。new-onto-env は `E:\<作業環境>`（`subst E: C:\work`。再起動で外れる）を前提にパスを書き込むので、`setup` が中のパス（start-neo4j.cmd・cypher-shell.cmd・tools の config.yaml など）を実際の場所に書き換える。Neo4j は止まっていても `show`・`query`・`load` が自分で起動する（30秒ほど）
- 名前空間は、設定の baseIri だけ変えると語彙・検証の規則（既定の名前空間で決め打ち）と合わず SHACL が空振りになる。`setup` が作業環境の中の語彙・規則・設定・テスト・ビュー定義をまとめて書き換える
- パスワードは Claude が尋ねない・入力しない・表示しない（作業環境の決まり）
- テストクラス・管理パッケージの項目・Id への代入は書き出さない。全項目を読む SOQL・項目名を変数で渡す put/get は「未解決」として残る

## 試作の結果

グリーンフィールドの過去課題29件で答え合わせをし、/backlog の再走査で初めて見つかった影響の約6割、調査で拾えていた影響の約8割を、変更対象から最初から出せた（2026-11-11。日常業務 WS の docs/reports/lineage-value-study-20261111/）。
