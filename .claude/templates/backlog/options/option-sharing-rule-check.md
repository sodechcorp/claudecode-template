# option-sharing-rule-check

## 何をするか

共有ルール・組織共有設定（OWD）への影響を確認する。特にデータ参照・編集権限に関係する変更時に必須。

## 実行手順

1. 変更対象オブジェクトの OWD（組織共有設定）を確認する:
   ```bash
   Glob: force-app/main/default/sharingRules/*.sharingRules-meta.xml
   ```
   または `sf sobject describe` の `sharingModel` フィールドを確認する

2. 共有ルールを Read して以下を確認する:
   - どのユーザー・ロールがどのレコードにアクセスできるか
   - 変更対象フィールド・オブジェクトが共有ルールの条件に含まれていないか

3. 変更による影響を評価する:
   - 新規フィールドを共有ルールの条件に含める必要があるか
   - 変更によってレコードアクセス範囲が意図せず変わらないか
   - `with sharing / without sharing` の設定と整合しているか

4. Apex クラスの `with sharing / without sharing` 宣言を確認する（変更対象クラスのみ）

## 出力

investigation.md「## 影響範囲」の末尾（次の「## 」見出しの前）に追記:

### 共有ルール・OWD 確認

- OWD 設定: {Private / PublicRead / PublicReadWrite}
- 関連共有ルール: なし / あり（{ルール名}）
- 変更による影響: なし / あり（{詳細}）
- Apex sharing 宣言: with sharing / without sharing / なし（{クラス名}）
