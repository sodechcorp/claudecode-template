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
| 「Account に項目追加して」 | Layer 3（`docs/catalog/Account.md`）+ Layer 1（命名規則） |
| 「結論先頭で短く」「敬語不要」 | Layer 2（Auto Memory が自動再現） |
| 「本番組織に DML 禁止」「共有フォルダ保護」 | Layer 1 |

---

## 必須ルール（絶対厳守）

### 本番組織
ルートの `CLAUDE.md` に「接続組織: 本番」または `sf org display` で `isSandbox: false` の場合: DML / デプロイ / force-app 書き込みを**絶対に実行しない**（ユーザー指示があっても解除不可）。許可: SOQL SELECT / retrieve / ファイル読み取り / docs/ 書き込み。

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

| 確証レベル | 行動 |
|---|---|
| 完全確証あり（不変知識・基本概念） | そのまま回答 |
| 8 割確証あり | 該当ファイルを 1 つ Read して確認後回答 |
| 5 割以下・仕様変更が疑われる | `docs/_README.md` → 該当ファイル → Web 検索 → 「わかりません」の順 |
| プロジェクト固有事項（命名・業務ルール・対応経緯） | **必ず `docs/` を見る。記憶で答えない** |

**メインスレッド直接応答ガード**: SF キーワード（`__c` / `CMP-` / `UC-` / `FR-` / オブジェクト名 / 「自動化」「権限」「ガバナ」等）を含む業務系質問は **assistant に委譲する**（メインスレッドで完結させない）。

**業務理解 0 モード**（「〜って何？」「〜の流れは？」）: `docs/_README.md` → 該当ファイル Read → 業務用語は `overview/org-profile.md` Glossary を引用 → docs に答えがなければ「資料に記載がありません。org-profile.md §キーパーソン一覧で確認を推奨」と明示。

**絶対禁止**: 記憶でプロジェクト固有事項に答える / 「たぶん〜」と推測する / プロジェクト固有事項の質問に「一般的には〜」と SF 一般論にすり替える。

---

## 開発タスク着手時の docs/ 参照（全エージェント共通）

着手前に以下を確認する（`docs/` が存在する場合のみ）:

| 状況 | 参照先 |
|---|---|
| 常に | `docs/overview/org-profile.md`（用語集） |
| 項目・オブジェクト操作 | `docs/catalog/{対象}.md` |
| 機能実装 | `docs/design/{種別}/` |
| 要件確認 | `docs/requirements/requirements.md` |
| マスタ参照 | `docs/data/master-data.md` |
| 過去の判断確認 | `docs/decisions.md` |

指示パターン別の詳細手順: [docs-driven-behavior.md](.claude/spec/docs-driven-behavior.md) 参照

**実装後**: `docs/catalog/` / `docs/design/` の該当ファイルを更新（存在する場合のみ・提案でなく実行）。`docs/logs/changelog.md` に変更サマリ 1 行追記。保守課題で方針確定したら `docs/decisions.md` に最上部追記（降順）。docs が存在しない場合: 「命名は SF 慣例に従います」と伝え、作業後に `/sf-memory` を提案。

**`[要確認]` 解消**: 作業中に読んだ docs ファイルに `[要確認]` マーカーがあり、会話・実装・調査で答えが判明した場合は、その場でマーカーを解消して実値に書き換える。後回しにしない。

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
| 第三者ライブラリ・MCP・ツールの仕様 | 公式ドキュメント・GitHub README |
| バージョン依存の挙動・最新リリース情報 | release notes / changelog |
| 「最新の〜は？」「今〜できる？」型の質問 | 公式サイト・公式ブログ |

**Salesforce 標準仕様は `docs/knowledge/sf-standard.md` を先に Read する**: 記載があれば Web 検索を省略してよい（「出典: sf-standard.md §{セクション名}」と明示）。

### 実装裏付け・出典確認

挙動・仕様を断定するときは必ず実コードを Read で確認し `ファイル名:行番号` で根拠を明示する。詳細: `.claude/templates/common/verify-implementation-spec.md` / `verify-source-attribution-spec.md` 参照

---

## Output Format

| コンテキスト | フォーマット |
|---|---|
| タスク / TODO | マークダウンチェックリスト（アクション動詞で始める） |
| コード | ファイルパス付きコードブロック（Before / After 形式） |
| ドキュメント | 結論先頭 → 詳細 → 参考情報 |
| 分析・調査 | TL;DR → 根拠 → 詳細 |
| 会議・議事録 | 決定事項 / アクションアイテム（担当・期限付き） / 背景 |
| エラー・障害報告 | 影響 → 原因 → 暫定対応 → 恒久対応 → 再発防止 |
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
