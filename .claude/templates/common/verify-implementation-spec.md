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
