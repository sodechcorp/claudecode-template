# option-user-impact-survey

## 何をするか

変更の影響を受けるユーザー数・部署を見積もる。影響規模の把握がリリース計画・周知範囲の判断に使われる。

## 実行手順

1. 変更対象の機能・オブジェクトを使用しているユーザーの属性を特定する:
   - どのプロファイル・権限セットを持つユーザーが対象か（組織の地図があれば、`python scripts/python/sf-lineage/lineage.py who <変更した項目・部品…>` の「権限・レコードタイプなど」区分に、その項目・クラス・ページに権限を与えるプロファイル・権限セットの候補が出る。[option-lineage-map.md](option-lineage-map.md)）
   - `docs/overview/` の組織概要・ユーザー構成を参照
2. **影響ユーザー数は本番で確認する（Sandbox のユーザーはテストデータ・代替不可）**: Sandbox のユーザーマスタは検証用アカウントのみで本番の実在ユーザー数を表さない。`option-prod-select-reference` 準拠（読み取りは許可不要）で本番を確認する。プロファイルが複数でも数える問い合わせは1回にまとめる。名前のまま数えず、先に本番の id に直す（force-app のファイル名〔`lineage.py who` が出す名前〕は URL エンコード〔`%EF%BC%88` 等〕や標準の別名〔`Admin` →「システム管理者」等〕で画面の名前〔`Profile.Name`〕と違う）: ファイル名は `sf org list metadata --metadata-type Profile --target-org {prod-alias} --json` で `fullName` が一致するものの `id`、画面の名前は `SELECT Id, Name FROM Profile WHERE Name IN ('{プロファイル名}', …)` の `Id`:
   ```bash
   sf data query --query "SELECT ProfileId, Profile.Name, COUNT(Id) FROM User WHERE ProfileId IN ('{プロファイルの id}', …) AND IsActive = true GROUP BY ProfileId, Profile.Name" --target-org {prod-alias} --json
   ```
   結果に行の無い id と、今回のリリースで新しく作るプロファイルは0人。それ以外で id に直せなかったプロファイル（本番に無いか名前が違う。似た名前に置き換えて数えない）は、その人数と推定影響ユーザー数に `[要確認: プロファイル名未確認]` を付け、合計は確かめた分の下限（N 人以上）にして、影響規模も断定しない。
   本番参照が実施できない場合は Sandbox 件数を**参考値として補足するのみ**とし、推定影響ユーザー数は `[要確認: 本番データ未確認]` を付けて断定しない。
3. 影響部署・担当者を特定する:
   - 変更が業務フローの特定ステップに影響する場合、その担当者
   - 課題の依頼者・コメント者の所属部署
4. 影響規模を分類する:
   - **限定的**: 特定ユーザー 1〜数人
   - **部署内**: 特定部署の全メンバー
   - **全社**: 全ユーザーまたは複数部署にまたがる

## 出力

**呼び出し元によって出力先が異なる**:
- `/backlog` Phase 1（backlog-investigator.md）から実行した場合: investigation.md に追記
- `/release`（release-preparer.md Phase 2 ③）から実行した場合: investigation.md への追記は行わず、release-plan.md「## 影響範囲サマリー」に直接反映する（下の見出しは付けず、同節内の要約として書く）

## 影響ユーザー調査

- 対象プロファイル: {プロファイル名（人数）}
- 推定影響ユーザー数: {N} 人（本番で確認） / {N} 人以上 `[要確認: プロファイル名未確認]` / `[要確認: 本番データ未確認]`（Sandbox の参考値 {N} 人）
- 影響部署: {部署名}
- 影響規模: 限定的 / 部署内 / 全社（推定影響ユーザー数に `[要確認: …]` が付くときは `{分類}以上 [要確認: …]`）
- 周知必要性: 低 / 中 / 高
