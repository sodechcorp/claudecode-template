# 実装裏付け・出典確認（backlog 固有 extras）

> **core（適用範囲・必須確認手順・追問/反転ガード）は `.claude/CLAUDE.md` §実装裏付け・出典確認 が正本。**
> 本ファイルは backlog 系エージェント・コマンド向けの深掘りのみを補足する。

---

## プラットフォーム標準仕様の Web 裏取り手順（backlog 補足）

`docs/knowledge/sf-standard.md` に記載がない場合:
- help.salesforce.com / developer.salesforce.com を WebFetch/WebSearch で裏取り（tools に WebSearch/WebFetch がある場合のみ）
- tools がない場合は `**[要確認: 公式仕様確認が必要]**` と明示
- **注: 「Apex の制限 = Flow の制限」と安易に同一視しない。Apex 固有の制限が宣言的 Flow には適用されないケースがある**

---

## sf-context-loader 経由の要約コンテキスト（2層ルール）

loader は行番号を保持しないため、loader 要約からの引用はファイルパス単位で出典を示せば足りる（例: `docs/catalog/Foo__c.md`）。断定・裏付けが必要な箇所は必ず原本を直接 Read して `ファイル名:行番号` を付す。

---

## エージェントでの読み込み方

新規エージェントまたは backlog 系エージェントは Phase 0 直後に本ファイルを Read する:

```markdown
Read `.claude/templates/common/verify-implementation-spec.md`（backlog 固有 extras。追加ルール記入欄まで読む）
```

既存エージェントからの参照リンク: `.claude/CLAUDE.md#実装裏付け・出典確認（全エージェント共通・常に適用）`

---

## 追加ルール記入欄

> 課題対応の精度向上のため、新規ルールはここに追記する。CLAUDE.md は変更しない。
> フォーマット: `- [日付] {ルール内容}（追加理由）`

- [2026-06-02] 同一論点への回答を撤回・反転する場合は、必ず該当する実コード/データ/Backlog を Read で再確認し `ファイル名:行番号` を新たに提示してから変える（フリップフロップ防止）
- [2026-06-02] 課題間の関係性（同一原因か・別か）を必須確認手順表に追加。両課題コードを Read して型・原因レイヤー・修正箇所を比較する（GF-327/347 での即答ミスを受けて）
- [2026-06-02] 上記 core ルールを CLAUDE.md §実装裏付け・出典確認 に正本移動。本ファイルは backlog 固有 extras 専用に整理
- [2026-06-02] CLAUDE.md §実装裏付け に穴A（承認・整形バイパス）・穴B（環境スコープ未確認）を追記。「確認して」「整えて」も検証タスク。repo/UAT ≠ 本番で断定不可（GF課題報告書の承認ミス・Flow 本番反映未確認断定を受けて）
- [2026-06-02] 組織のランタイム状態（インストール済みパッケージ・バージョン／組織設定／機能有効化／ライセンス）はコード・コメント・VF タグから推論せず、Setup / Tooling API（InstalledSubscriberPackage 等）で組織に直接問い合わせて確認する。確認対象ごとに正本が変わる＝コードに書いてある≠正本（OPROARTS Connector のバージョンをコードから推論して迷走したミスを受けて）
- [2026-06-12] 「〜すればわかる/断言できない」と書きそうになったら推論で締めず、該当手段（SOQL・WebSearch・Grep・retrieve）を実行してから答える。マーカー（`[推定]`/`[要確認]`）・「断言できません」は全調査手段を尽くした後のみ許可（Magarigawa ユビレジ税率の連携根拠を `sf data query`・WebSearch 未実行のまま推論で締めたミスを受けて）
- [2026-07-03] 「自動化の有無」（Flow/Apex 未実装）はコード grep で確定してよいが、その根拠として Sandbox のレコード件数・分布（例: 「N件中0件しか入っていない」）を業務実態の証拠として添えてはならない。Sandbox はテストデータのみで本番の入力実態を表さない。業務実態の主張は本番 SELECT 参照が必須（option-data-volume-analysis・option-user-impact-survey を強化済み）。実施できなければ `[要確認: 本番データ未確認]` を付ける（配送-商談参照の入力率調査で Sandbox 18件中0件を業務実態の根拠に使ったミスを受けて）
- [2026-07-13] Flow/Trigger/承認プロセス等の「有効/無効」は force-app/ のメタデータの `<status>` タグだけで判定してはならない。手元リポジトリは最後に retrieve した時点のスナップショットであり、組織側で後から Active 化・バージョン更新されている場合がある（環境の違いではなく同一環境内での retrieve 鮮度のズレ）。「無効なので影響なし」は必ず対象組織への `sf data query`（`FlowDefinitionView` / `ApexTrigger`）で Active/Inactive を確認してから書く（CLAUDE.md 確認項目表「自動処理の有効化状態」・option-flow-trigger-trace.md 手順2 を追加）。Link案件で investigator が「三神さん専用フロー2本は無効なので影響なし」と報告したが、実際は本番・UAT 双方で稼働中だったミスを受けて
