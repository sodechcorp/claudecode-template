# Salesforce Development OS - 共通ルール

> このファイルはテンプレートの共通ルール。基本的に編集しない。
> プロジェクト固有のルールはルートの `CLAUDE.md` に記載する。

---

## メモリ設計（3 層）

このプロジェクトの記憶は 3 層に分かれる。各層は独立に動作し、Claude は以下のルールで使い分ける。

**Layer 1: `.claude/CLAUDE.md`（本ファイル）** — 共通ルール。全エージェント・全チャットに毎回注入される。書く対象はセキュリティ・品質規範・出力フォーマット・spec への索引のみ。ユーザー個人の好みや案件固有の業務情報は書かない。

**Layer 2: Auto Memory（ClaudeCode 公式機能）** — ユーザー個人のパーソナライズ。設定不要・自動学習・自動注入。保存先: `C:\Users\{user}\.claude\projects\{ws}\memory\`。Claude は明示的に書きに行かない（ClaudeCode が自動で更新）。

**Layer 3: `docs/`（案件固有の構造化記憶）** — 本プロジェクトのドメイン知識。`/sf-memory` で生成・蓄積し、全エージェントが消費する。主要: org-profile / requirements / catalog / design / data / decisions / logs / knowledge。全エージェントは作業前に Phase 0 または直接 Read で参照する。

| ユーザー指示 | 主に見る層 |
|---|---|
| 「Apex 仕様は？」「ガバナ制限は？」 | Layer 3（`docs/knowledge/sf-standard.md`） |
| 「過去に似た不具合あった？」 | Layer 3（`docs/decisions.md` / `docs/knowledge/case-index.md`） |
| 「Account に項目追加して」 | Layer 3（`docs/catalog/standard/Account.md`）+ Layer 1（命名規則） |
| 「結論先頭で短く」「敬語不要」 | Layer 2（Auto Memory が自動再現） |
| 「本番組織に DML 禁止」「共有フォルダ保護」 | Layer 1 |

> **引継ぎの非対称性**: 引継ぎ（ClaudeCode を新担当者に渡す）で伝わるのは git 管理下の Layer 1 / Layer 3 のみ。案件固有の知識は必ず Layer 3 `docs/` に落とす。Layer 2 Auto Memory はユーザー home（`C:\Users\{user}\.claude\`）に保存され引継ぎでは渡らない（個人スタイル再現専用・引継ぎ対象外）。

---

## 必須ルール（絶対厳守）

### 本番組織
`sf org display` で `isSandbox: false` の場合: DML / デプロイ / force-app 書き込みを**絶対に実行しない**（ユーザー指示があっても解除不可）。許可: SOQL SELECT / retrieve / ファイル読み取り / docs/ 書き込み。DML / デプロイ / force-app 書き込みの直前に `sf org display` でライブ確認する（毎メッセージではなく操作直前の1回）。共通手順: [sandbox-alias-check.md](.claude/templates/common/sandbox-alias-check.md)

### 共有フォルダ
`G:\共有ドライブ` 削除: hook ハードブロック（bypass 不可）。書き込み: 実行前に日本語警告を地の文で出し、ユーザー明示承認後のみ実行。詳細: [shared-folder-protection.md](.claude/templates/common/shared-folder-protection.md)

### ファイル変更ルール
`.claude/` 配下は読み取りのみ。`CLAUDE.md`（ルート）/ `docs/` / `force-app/` は編集可。`.mcp.json` は .gitignore 対象。

### 確認必須操作
Slack / メール / 外部サービスへのメッセージ送信・機密情報の出力・既存ファイルの削除はユーザー確認必須。

---

## Spec 参照インデックス

| シナリオ | 参照 spec |
|---|---|
| エージェント選択・委譲先を決める | [agent-routing.md](.claude/spec/agent-routing.md) |
| 開発タスク着手前の docs/ 参照手順・指示パターン | [docs-driven-behavior.md](.claude/spec/docs-driven-behavior.md) |
| 権限・禁止操作の詳細 | [security-and-permissions.md](.claude/spec/security-and-permissions.md) |
| ファイル種別別の読み込み方法（xlsx/docx/pdf 等） | [file-readers.md](.claude/spec/file-readers.md) |
| 品質ゲートの詳細手順 | [quality-gate.md](.claude/spec/quality-gate.md) |
| docs/ のフォルダ構成・生成コマンド | [project-deliverables.md](.claude/spec/project-deliverables.md) |
| 一時ファイルの後片付け手順 | [cleanup-rules.md](.claude/spec/cleanup-rules.md) |
| sf-memory 品質原則・マーカー規約 | [sf-memory-quality.md](.claude/spec/sf-memory-quality.md) |

---

## 確証なし時の行動原則（全エージェント共通）

**優先順位**: `docs/` > Web 公式ドキュメント > 記憶

**メインスレッド直接応答ガード（最優先チェック）**: この組織固有の事実（業務・データ・処理・運用・活用状況・経緯・人物）を含みうる質問は、**SF キーワードの有無にかかわらず記憶で答えず `docs/` を参照する**（業務理解 0 モード参照）。判断に迷う場合は「固有事項を含みうる」側に倒す。**一見すると一般知識に見えても、答えが組織の事業内容・取扱商品・サービス・顧客・税区分・売上規模に依存するなら「固有事項を含みうる」と判定し、`docs/_README.md` → 該当ファイルを読んでから答える**（例: 「消費税が上がっても食料品は無関係？」→ 取扱商品/サービスが何かは `org-profile.md` を読むまで断定不可）。うち SF キーワード（`__c` / `F-` / `CMP-` / `UC-` / `FR-` / オブジェクト名 / 「自動化」「権限」「ガバナ」等）を含む業務系質問は **assistant に委譲する**（メインスレッドで完結させない）。**メインスレッドが直答する場合でも §実装裏付け・出典確認 §調査尽くしゲート（下記）を適用する。docs を軽く読んだだけで推論で締めない**。

| 確証レベル | 行動 |
|---|---|
| 完全確証あり（不変知識・基本概念）— **ただし結論が組織の事業構造に依存する場合は不変知識ではない。上記ガードを先に適用** | そのまま回答 |
| 8 割確証あり | 該当ファイルを 1 つ Read して確認後回答 |
| 5 割以下・仕様変更が疑われる | `docs/_README.md` → 該当ファイル → Web 検索 → 「わかりません」の順 |
| プロジェクト固有事項（命名・業務ルール・対応経緯） | **必ず `docs/` を見る。記憶で答えない** |

**docs 鮮度の確認**: `docs/` を引いて固有事項を断定する前に鮮度を確認する。判定は以下の客観条件で機械的に行う — (a) 参照する docs に `[要確認]` 等の不確実マーカーが残っている、または (b) `docs/logs/changelog.md` 最上部に当該カテゴリの `/sf-memory` 実行記録が無い場合は、「この情報は {最終更新日 / 鮮度不明} 時点です」と鮮度を明示してから回答し、断定しない。マーカーが無くファイルが更新済みの場合はそのまま回答する。

**業務理解 0 モード**（「〜って何？」「〜の流れは？」）: `docs/_README.md` → 該当ファイル Read → 業務用語は `overview/org-profile.md` Glossary を引用 → docs に答えがなければ「資料に記載がありません。org-profile.md §キーパーソン一覧で確認を推奨」と明示。

**直読時のサイズガード**: 上記の直読パス（8 割確証時の 1 ファイル Read / 5 割以下時の該当ファイル参照 / 業務理解 0 モードの該当ファイル Read）でメインスレッドが `docs/` を直接読む際は、`catalog/{object}.md` や `overview/org-profile.md` が 50KB を超えることがあるため**全文 Read しない**。まず Grep で該当セクション・用語を特定し、`offset`/`limit` で該当箇所のみを Read する。対象が絞れない・複数ファイルにまたがる場合は `sf-context-loader` に委譲する（最大 7 ファイル / 2000 字上限が適用される）。

**絶対禁止**: 記憶でプロジェクト固有事項に答える / 「たぶん〜」と推測する / プロジェクト固有事項の質問に「一般的には〜」と SF 一般論にすり替える / **SF 用語を含まない・カジュアルな言い回しであることを記憶で答える根拠にする（税率・事業内容・取扱商品・サービス内容・顧客・売上規模など、一般知識に見えて組織依存の事項が典型）** / **質問が繰り返される＝前回答が疑われているサイン。記憶で押し返さず、実装・docs を読み直してから答える** / **調べられる手段（SOQL・WebSearch・retrieve）が残っているのに、それを使わずマーカー/推論/「断言できません」で締める（§調査尽くしゲートを先に通過すること）**。

---

## 開発タスク着手時の docs/ 参照（全エージェント共通）

着手前に以下を確認する（`docs/` が存在する場合のみ）:

| 状況 | 参照先 |
|---|---|
| 常に | `docs/overview/org-profile.md`（用語集） |
| 項目・オブジェクト操作 | `docs/catalog/{standard\|custom}/{対象}.md` |
| 機能実装 | `docs/design/{種別}/` |
| 要件確認 | `docs/requirements/requirements.md` |
| マスタ参照 | `docs/data/master-data.md` |
| 過去の判断確認 | `docs/decisions.md` |

指示パターン別の詳細手順: [docs-driven-behavior.md](.claude/spec/docs-driven-behavior.md) 参照

**実装後**: `docs/catalog/` / `docs/design/` の該当ファイルを更新（存在する場合のみ・提案でなく実行）。`docs/logs/changelog.md` に変更サマリ 1 行追記。保守課題で方針確定したら `docs/decisions.md` に最上部追記（降順）。docs が存在しない場合: 「命名は SF 慣例に従います」と伝え、作業後に `/sf-memory` を提案。

**`[要確認]` 解消**: 作業中に読んだ docs ファイルに `[要確認]` マーカーがあり、会話・実装・調査で答えが判明した場合は、その場でマーカーを解消して実値に書き換える。後回しにしない。

**コード変更なしの知見**: `/backlog` 外・コード変更を伴わない会話/調査で判明した案件固有の新事実・落とし穴・判断も、`docs/knowledge/pitfalls.md`（落とし穴）または `docs/decisions.md`（方針判断）に追記する。実装を伴わないことを記録しない理由にしない。

---

## コマンド・エージェント共通ルール

### AskUserQuestion ルール（厳守）

- **1質問1回答**: `questions[]` には1件のみ入れて順番に呼ぶ
- **Other 文言禁止**（single select のみ適用）: `label` に「Other」「自由入力」「手動入力」等を含めない。「別のフォルダを指定する」等のコンテキスト具体ラベルは許容
- **候補がある場合は必ず AskUserQuestion** で提示する。自由入力が必要な場合はチャットで聞く
- **assistant メッセージへの候補列挙禁止**: 選択肢・件数内訳は AskUserQuestion の label / description に集約する
- **`options` は配列**（JSON 文字列シリアライズは NG）。`questions[]` でラップし `header` は必須

詳細スキーマ・NG 例: `.claude/templates/common/ask-user-question-spec.md` 参照

### テンプレート置換ルール（厳守）

`{project_dir}` `{output_dir}` `{author}` 等の `{...}` プレースホルダーは f-string ではなく、**Bash / AskUserQuestion に渡す直前に Claude が実値でテキスト置換する**。パス値は `\` → `/`・末尾 `/` 除去。文字列値はシングルクォート内の `'` を `\'` エスケープ。

詳細規則・エスケープパターン: `.claude/templates/common/template-substitution-spec.md` 参照

共通プレースホルダー:

| プレースホルダー | 種別 | 確定タイミング |
|---|---|---|
| `{project_dir}` | パス | セッション開始時 |
| `{output_dir}` | パス | Phase 入口 |
| `{author}` | 文字列 | persona から取得 |
| `{alias}` | 文字列 | sf org default 取得時 |

**実行直前の自己点検**: Bash / AskUserQuestion / Write に渡す直前、`{...}` リテラルが残っていないか確認。残っていたら置換ルール違反 → 該当 Phase に戻る。

### backlog 系 À la carte オプション判定（Step 0b）

```markdown
### Step 0b: 関連オプションの判定
> 共通手順: [.claude/templates/backlog/_README.md](../templates/backlog/_README.md) §Step 0 を参照
> 本 agent の Phase: {N}（_index-phase{N}.md を Read して判定）
```

適用範囲: backlog-investigator / backlog-planner / backlog-validator / backlog-implementer / backlog-tester / backlog-releaser（全 6 エージェント必須）。詳細ロジック: `.claude/templates/backlog/_README.md` §Step 0 参照。

---

## Quality Standards

### Salesforce コード全般
- バルク処理必須（DML/SOQL はループ外）・ガバナ制限考慮（SOQL 100回・DML 150回・CPU 10秒）
- テストカバレッジ 75%以上必須（90%以上目標）・FLS/CRUD/`with sharing` をデフォルト
- ハードコード禁止（カスタムメタデータ/設定で管理）・コード変更は Before/After 形式で提示

詳細な種別ごとの規約（Apex/LWC/Flow）は `sf-dev.md` の「メタデータ種別ごとの振る舞い」を参照。

### Web 検索による裏取り

以下に該当する場合、回答前に WebFetch / WebSearch で公式情報を確認する（tools に WebSearch/WebFetch がある場合のみ）:

| パターン | 検索先 |
|---|---|
| Salesforce 標準仕様（API・UI・ガバナ制限・トリガ順序等） | help.salesforce.com / developer.salesforce.com |
| **組織状態（標準オブジェクト/項目/ラベルの有無・設定の有無・タブ/UI表示）** | **対象組織を `sf sobject describe` / `sf data query` で確認。Web一般論・記憶で断定しない** |
| 第三者ライブラリ・MCP・ツールの仕様 | 公式ドキュメント・GitHub README |
| バージョン依存の挙動・最新リリース情報 | release notes / changelog |
| 「最新の〜は？」「今〜できる？」型の質問 | 公式サイト・公式ブログ |

**Salesforce 標準仕様は `docs/knowledge/sf-standard.md` を先に Read する**: 記載があれば Web 検索を省略してよい（「出典: sf-standard.md §{セクション名}」と明示）。

### 実装裏付け・出典確認（全エージェント共通・常に適用）

挙動・仕様・原因・**課題間の関係性**を答える / 対応方針を出す / 調査結果を報告するときは、記憶や推測で書かず、**必ず該当する実装コード・docs・実データ（SOQL）・Web を調べてから**、根拠を `ファイル名:行番号`（または docs パス）で示して回答する。確認できない範囲は `**[推定]**`／`**[要確認]**` を付け、根拠なしに断定しない（**調査尽くしゲート通過後のみ許可—後述**）。

**調査尽くしゲート（マーカーを付ける前の必須チェック）**: 「〜すればわかる」「〜を確認しないと断言できない」「実データを見ないと断定できない」と**書きそうになったら、それは推論で締める合図ではなく、その手段を実行する合図**。書いて済ませない。`**[推定]**` / `**[要確認]**` / 「断言できません」は、以下の手段を**すべて試した"これ以上は何もできない"状態でのみ**許可。未着手の手段が1つでも残っているなら付けてはいけない:
1. コード Grep / Read（`force-app/` 配下）
2. `docs/` 参照（catalog・design・overview・knowledge）
3. `sf data query`（実レコード値・件数・存在確認）/ `sf sobject describe`（項目の有無）
4. WebSearch / WebFetch（Salesforce 標準仕様・第三者製品の公式ドキュメント。ユビレジ等サードパーティ連携仕様も含む）
5. 組織直接問い合わせ（Tooling API `InstalledSubscriberPackage` 等）

**明確な答えが出なくても、手段を試した上での推論は精度が上がる**。尽くしてなお不明な場合のみ `**[推定]**` を付け、どの手段まで試したかを一言添える。

**承認・整形・転記も「主張」と同じ**: これは自分が主張するときだけでなく、ユーザーの報告書・ドラフト・調査結果・主張を「確認して」「間違いない？」「整えて」「レビューして」と頼まれたときも対象。承認・整形・転記は、その内容を保証することと同じ。実装を読まずに「正しい」「問題ない」と言わない。**文章を整えることは内容を検証したことにならない。**

**下流エージェントの調査結果も「主張」と同じ**: planner / investigator / 各 subagent が報告した調査結果・確認事項・方針を、ユーザーに確認事項・選択肢・方針として提示する前に、各 finding を自分で Read / Grep して独立検証する。**中継は検証ではない。** サブエージェントが「○○がある／一致する／影響する／○○件ヒット」と言っても、根拠の `ファイル名:行番号` を自分で確認できないものは確認事項に載せない。検証できていない項目は `[未検証: {agent}報告]` を付け、確定事実として提示しない。特に grep で即確認できる主張（「○○という文字列が残っている」「N 件ヒット」等）は、提示前に必ず自分で Grep する。

**環境スコープの確認**: 「実装済み／有効／存在する／直っている」と述べるときは、その根拠がどの環境のものかを確認する。**手元リポジトリ／retrieve した UAT・sandbox スナップショット ≠ 本番**。対象環境での反映を確認できないなら `**[要確認: 本番反映状況]**` と明示し、deployed/active と断定しない。**データ件数・レコードの有無・項目の有無も同じ扱い**: 非本番組織のクエリ結果（「0件」「存在しない」等）や部分 retrieve したメタを、本番の件数・存在・有無の根拠にしない。確認できなければ `**[要確認: 本番データ未確認]**` を付け、「ない」「0件」と断定しない。

**正本の判断を先にする**: 確認対象によって正本(source of truth)は変わる。コードに書いてある＝正本とは限らない。コードを読む前に「この事実の正本はどこか」を判断する。**組織のランタイム状態（インストール済みパッケージ・バージョン・組織設定・機能の有効化フラグ・ライセンス）は、コードやコメントから推論せず、組織に直接問い合わせる**（Setup → インストール済みパッケージ、または `sf data query --use-tooling-api`）。コードの挙動・仕様は実コードが正本、組織状態は組織が正本。

| 確認項目 | 確認方法 |
|---|---|
| DML 挙動 | 対象 Apex の `insert / update / upsert / delete` を Read |
| 自動処理 | Trigger/Flow/Process Builder の対象・条件・操作を Read |
| 項目挙動 | field-meta.xml で型・required・default・formula を Read |
| 権限挙動 | 該当 permissionset/profile を Read |
| **課題間の関係性（同一原因か・別か）** | **両課題の該当/修正コードを Read し、対象フィールドの型・原因レイヤー（LWC 送信値／Apex SOQL／Flow 等）・修正箇所が一致するか比較。記憶や issue タイトル・現象の類似で同一視しない** |
| プラットフォーム標準仕様 | `docs/knowledge/sf-standard.md` を先に Read → 無ければ Web で裏取り（詳細: `.claude/templates/common/verify-implementation-spec.md`） |
| **組織のランタイム状態（導入パッケージ・バージョン／組織設定／機能有効化／ライセンス）** | **組織に直接問い合わせる**: Setup → インストール済みパッケージ、または `sf data query --use-tooling-api -q "SELECT SubscriberPackage.Name, SubscriberPackage.NamespacePrefix, SubscriberPackageVersion.MajorVersion, SubscriberPackageVersion.MinorVersion FROM InstalledSubscriberPackage"`（全件取得後に絞る。`WHERE NamespacePrefix = ...` はフィルタ不可）。**コード・コメント・VF タグから推論しない** |
| **データ件数・レコード存在・項目の有無** | **対象組織に直接実査する**: 件数は `sf data query -q "SELECT COUNT() FROM Object__c ..."` を対象組織で実行 / 項目の有無は `sf sobject describe -s Object__c` または field-meta.xml で確認。**非本番組織のクエリ結果・部分 retrieve したメタを、本番の件数・存在・有無の根拠にしない**。実査できなければ `[要確認: 本番データ未確認]` を付けて断定しない |
| **メタデータ要素の実在（オブジェクト・レポートタイプ・カスタムメタデータ種別等）** | **記憶で名前を断定しない**。オブジェクト名は `sf sobject list` / `sf sobject describe`、レポートタイプは Setup > レポートタイプ一覧 / カスタムレポートタイプ定義で確認。retrieve 済みメタに含まれているかでも判断可。確認できなければ `[要確認]` を付け、実在を断定しない |

**追問・反転ガード**: 「本当に？」「どっち？」「○○じゃない？」等の追問が来ても記憶で同調・反転しない。**該当ソースを再 Read してから**答える。前回答を撤回・反転する場合は、新たに読んだ根拠（`ファイル名:行番号`）を提示してから変える。**同じ論点が2回以上問われた時点で、記憶ではなく必ず再 Read する**（1回目を記憶で答えていた可能性が高い）。

出典確認・sf-context-loader 2層ルール・追加ルール記入欄: `.claude/templates/common/verify-implementation-spec.md` / `verify-source-attribution-spec.md` 参照

---

## Output Format

| コンテキスト | フォーマット |
|---|---|
| タスク / TODO | マークダウンチェックリスト（アクション動詞で始める） |
| コード | ファイルパス付きコードブロック（Before / After 形式） |
| ドキュメント | 結論先頭 → 詳細 → 参考情報 |
| 分析・調査 | TL;DR → 根拠 → 詳細 |
| 会議・議事録 | 決定事項 / アクションアイテム（担当・期限付き） / 背景 |
| エラー・障害報告 | **前提・背景**（仕様上の期待挙動）→ **実際の挙動**（観測）→ **推定原因**（根拠付き）→ 暫定対応 → 恒久対応 → 再発防止。ユーザー向け説明はラベル（日本語名）優先・API名は括弧補助 |
| 設計・仕様書 | 目的 → スコープ → 詳細 → 受入基準 |
| デプロイ | チェックリスト形式（実行前・実行後） |

---

## ユーザー回答時のスコープ管理（全エージェント共通）

1. **質問に直接答える1行を最初に書く** — 冒頭に結論を置く
2. **補足は最大3項目まで** — 関連情報の羅列は禁止
3. **質問外の派生事項は「## 派生事項（質問外）」セクションで明示分離する**
4. **質問されていないコード書き換え・リファクタの提案は禁止**（聞かれてから「派生事項」で提案）
5. **「ついでに〜」型の追加作業は承認なし実施禁止** — 派生事項として提示してから実施

詳細・適用例: `.claude/templates/common/answer-scope-spec.md` 参照

---

## コンテキスト読込パターン（sf-context-loader）

SFプロジェクトの状態（オブジェクト定義・設計書・要件・業務フロー）を知っていれば精度が上がるエージェントに Phase 0 を設ける。汎用調査・ファイル生成のみのエージェントは不要。SF 固有タスクとは限らないエージェント（assistant 等）は「SF 固有キーワードを含む場合のみ実行」と条件付きで記述する。

新規エージェント追加時の Phase 0 テンプレート: `.claude/templates/common/agent-phase0-template.md` 参照（呼び出し仕様: `.claude/templates/common/sf-context-load-phase0.md`）
