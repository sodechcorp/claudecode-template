# option-flow-trigger-trace

## 何をするか

フロー・トリガーの連鎖実行を追跡し、変更が引き起こす意図しない副作用を把握する。

## 実行手順

1. 変更対象のオブジェクト・フィールドに関連するフロー・トリガーを特定する:
   ```bash
   Glob: force-app/main/default/flows/*.flow-meta.xml
   Glob: force-app/main/default/triggers/*.trigger
   ```
2. **稼働状態を組織に問い合わせて確認する（ローカルファイルの `<status>` タグだけで判定しない）**:
   手元リポジトリの `flow-meta.xml` / `.trigger` は最後に retrieve した時点のスナップショットに過ぎない。ローカルで `Draft` / `Obsolete` / `<status>Inactive</status>` に見えても、組織側でその後 Active 化・バージョン更新されている可能性がある。**「無効だから対象外／影響なし」と結論づける前に必ず以下を対象組織（影響判断に使う環境。本番影響を語るなら本番、UAT 影響を語るなら UAT。両方に影響しうるなら両方）に対して実行する**:
   ```bash
   sf data query -q "SELECT ApiName, ActiveVersionId, VersionNumber, ProcessType FROM FlowDefinitionView WHERE ApiName IN ('{Flow名1}', '{Flow名2}')" --target-org <alias> --json
   sf data query -q "SELECT Name, Status FROM ApexTrigger WHERE Name IN ('{Trigger名1}', '{Trigger名2}')" --target-org <alias> --json
   ```
   `ActiveVersionId` が null（Flow）/ `Status` が `Inactive`（Trigger）の場合のみ「無効」と扱ってよい。組織に問い合わせられない場合（alias 未指定・対象組織不明等）は「無効」と断定せず `**[要確認: 稼働状態未確認（組織問い合わせ不可）]**` を付ける。
3. 各フロー・トリガーを Read して以下を確認する（稼働中と確認できたもの、および稼働状態未確認のもの全てが対象。手順2で「無効」と組織確認済みのものは連鎖評価を省略してよい）:
   - **起動条件**: オブジェクト・フィールド・タイミング（Before / After）
   - **処理内容**: DML / Callout / 別フロー起動 / Platform Event 送信
   - **連鎖**: このフロー/トリガーが別のフロー/トリガーを起動するか
4. 変更による連鎖実行の影響を評価する:
   - 変更後、意図しない DML が走る可能性
   - 無限ループ（再帰実行）のリスク
   - ガバナ制限消費の増加
5. 影響があれば investigation.md に追記する

## 出力

investigation.md「影響範囲」セクションに追記:

| フロー / トリガー名 | 稼働状態（組織確認） | 起動条件 | 処理内容 | 連鎖先 | 影響評価 |
|---|---|---|---|---|---|
| ... | Active（{組織名}で確認済み） / Inactive（{組織名}で確認済み） / [要確認: 稼働状態未確認] | オブジェクト: ... / 条件: ... | ... | なし / あり（...） | 影響なし / 要確認 |
