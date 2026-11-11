# 専用テストクラスの命名規則

Apex クラス・トリガーの専用テストクラスは、次のどれかの名前で探す（トリガーはファイル名〔拡張子を除く〕を `{ClassName}` とする。探す場所は使う側が決める）:

- `{ClassName}Test.cls`
- `{ClassName}_Test.cls`
- `Test{ClassName}.cls`

組織の地図があれば、`python scripts/python/sf-lineage/lineage.py who <クラス名・トリガー名…>` の「テストクラス」区分も候補に足す（Bash を持つ使う側だけ）。名前の規則に合わないテストクラスと、変更する項目・オブジェクトで引けば、そのデータを作る（入力規則の追加などで壊れうる）テストクラスも出る。地図に出たテストクラスは、テストメソッドで対象を本当に呼ぶかを読んで確かめてから加える（[option-lineage-map.md](../options/option-lineage-map.md)）。
