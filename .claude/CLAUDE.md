# Salesforce Development OS - 共通ルール

> このファイルはテンプレートの共通ルール。基本的に編集しない。
> プロジェクト固有のルールはルートの `CLAUDE.md` に記載する。

---

## Security & Permissions

### settings.json による技術的ブロック

`settings.json` は Git管理対象。`.claude/` 編集・`rm -rf .claude` は行動指示のみ。本番デプロイは deny（⚠️ `*prod*`/`*production*` エイリアスパターン依存）。`git push origin main` 等の破壊操作は未実装（チーム導入時に追加）。

テンプレート更新は `/upgrade` コマンド経由のみ。

### 本番組織接続時の絶対ルール

ルートの `CLAUDE.md` に「接続組織: 本番」と記録、または `sf org display` で `isSandbox: false` の場合は以下を **絶対に実行しない**（ユーザー指示があっても解除不可）:

- DML 操作（`sf data create/update/delete/upsert`・Apex 匿名 DML）
- デプロイ（`sf project deploy start`）
- メタデータ変更・force-app への書き込み

**許可**: SOQL SELECT・`sf project retrieve`・ファイル読み取り・docs/ への書き込み

### 共有フォルダ保護

- `G:\共有ドライブ` 削除: hook ハードブロック（bypass 不可）
- `G:\共有ドライブ` 書き込み: 実行前に日本語警告を地の文で出し、ユーザー明示承認後のみ実行（AskUserQuestion 禁止・回避経由禁止）
- 警告文体・例外パターン詳細: `.claude/templates/common/shared-folder-protection.md` 参照

### ファイル変更ルール

`.claude/` 配下は読み取りのみ。`CLAUDE.md`（ルート）/ `docs/` / `force-app/` は編集可。`.mcp.json` は .gitignore 対象（個人設定）。`.gitignore` 変更時はユーザー確認。

### 確認必須操作

Slack / メール / 外部サービスへのメッセージ送信・機密情報の出力・既存ファイルの削除・上書きは必ずユーザー確認を取る。

---

## Quality Standards

### Salesforce コード全般
- バルク処理必須（DML/SOQL はループ外）・ガバナ制限考慮（SOQL 100回・DML 150回・CPU 10秒）
- テストカバレッジ 75%以上必須（90%以上目標）・FLS/CRUD/`with sharing` をデフォルト
- ハードコード禁止（カスタムメタデータ/設定で管理）・コード変更は Before/After 形式で提示

詳細な種別ごとの規約（Apex/LWC/Flow）は `sf-dev.md` の「メタデータ種別ごとの振る舞い」を参照。

### ドキュメント / タスク管理
- ドキュメント: 結論が冒頭・読者と目的が明確・アクションが具体的
- タスク: アクション動詞で始まる・完了の定義が明確・期限が設定されている

---

## Quality Gate（品質ゲート）

作業完了前に担当エージェントのセルフレビュー → チェック担当の自動レビューを必ず実行する。

| 作業の種類 | 実行 | チェック担当 |
|---|---|---|
| Apex / LWC / トリガー / Flow | sf-dev | **reviewer** |
| テストクラス | sf-dev | **qa-engineer** |
| 設計書・要件定義書 | sf-architect | **reviewer** |
| データ移行・SOQL / 外部API連携 | data-manager / integration-dev | **reviewer** |

問題あり: 問題点一覧 → 修正案提示 → ユーザー確認（reviewer は指摘のみ。修正は担当エージェントが行う）。問題なし: 「品質チェック通過」で完了。

**例外**: 「レビュー不要」指示 / ロジック変更なし・公開 API 変更なし・データアクセス変更なしの全条件を満たす軽微修正 / 途中経過

---

## ユーザー回答時の実装裏付け（全エージェント共通）

挙動・仕様を断定するときは必ず実コードを Read で確認し `ファイル名:行番号` で根拠を明示する。記憶・推測で断定しない。確認できない箇所は `**[推定]**` / `**[要確認]**` を付ける。ユーザーに流されず「実装を確認します」と一拍置く。

詳細（適用範囲・確認手順・追加ルール記入欄）: `.claude/templates/common/verify-implementation-spec.md` 参照

---

## 引用・出典の確認（全エージェント共通）

会話で言及される文章（Backlog コメント・過去発言・議事録等）を誰が書いたか断定する前に必ず出典を確認する。確認できない場合は `**[出典不明]**` と明示。Backlog コメントは `mcp__backlog__get_issue_comments` で再取得して照合する。

詳細（適用範囲・確認手順・追加ルール記入欄）: `.claude/templates/common/verify-source-attribution-spec.md` 参照

---

## Web 検索による裏取り（全エージェント共通）

以下のいずれかに該当する場合、回答前に WebFetch / WebSearch で公式情報を確認する（tools に WebSearch/WebFetch がある場合のみ）:

| パターン | 検索先 |
|---|---|
| Salesforce 標準仕様（API・UI・ガバナ制限・トリガ順序等） | help.salesforce.com / developer.salesforce.com |
| 第三者ライブラリ・MCP・ツールの仕様 | 公式ドキュメント・GitHub README |
| バージョン依存の挙動・最新リリース情報 | release notes / changelog |
| 「最新の〜は？」「今〜できる？」型の質問 | 公式サイト・公式ブログ |

**Salesforce 標準仕様は sf-standard.md を先に Read する**: `docs/knowledge/sf-standard.md` が存在する場合は WebFetch の前に Read して照合する。記載があれば Web 検索を省略してよい（「出典: sf-standard.md §{セクション名}」と明示）。

**記憶で答えてよい範囲**: 構文・基本概念・自明な API 名等の不変知識のみ。バージョン依存事項・組織固有設定・最近の仕様変更・リリース後に変更される可能性がある情報は必ず Web 確認。

---

## 確証なし時の決定木（全エージェント・メインスレッド共通）

回答・対応の前に、自分の確証レベルを以下のフローで判定する:

| 確証レベル | 行動 |
|---|---|
| 完全に確証あり（構文・自明な API 名・基本概念等の不変知識） | そのまま回答 |
| 8 割以上確証あり（記憶に従ってもよいが裏取りすべき） | 該当ファイル 1 つを Read して確認後回答 |
| 5 割以下、または最近の仕様変更がありそう | `docs/_README.md` で所在確認 → 該当ファイル Read → 不足なら Web 検索 → それでも不明なら「わかりません。〜を確認してください」と明示 |
| プロジェクト固有事項（命名・業務ルール・組織設定・対応経緯） | 必ず `docs/` を見る。記憶で答えない |

**鉄則**: 間違った確証ある回答 > 正直なわからない回答 ではない。**逆**。判断材料の優先度: `docs/` > Web 公式ドキュメント > 記憶

---

## メインスレッド直接応答ルール（専門エージェント委譲しない時）

ユーザーからの質問・依頼にメインスレッド（または assistant エージェント）が直接答える時:

1. **質問種別の判定**（業務系 / 技術系 / 作業依頼 / 雑談）
2. **業務系・技術系の場合**: `docs/_README.md` を先に Read して情報所在を把握する
3. **[確証なし時の決定木]** に従う
4. **回答時**: 出典（参照ファイル名・行番号）を明示する
5. **わからない場合**: 推測で答えず「〜が確認できません」と明示する

雑談・コマンド呼び出し依頼・専門エージェント委譲が明確な場合は本ルールをスキップ可。

---

## 業務理解 0 モード（新規担当者支援）

ユーザーが「〜って何？」「〜の流れは？」「〜の経緯は？」「〜さんって誰？」「なぜ〜なの？」と質問してきた場合:

1. `docs/_README.md` → 該当ファイル Read → 回答する
2. 業務用語が出てきたら `overview/org-profile.md` の Glossary で API 名対応を提示する
3. 過去の判断・採用方針が関わる場合は `docs/decisions.md` を引用する
4. 同類の過去案件があれば `docs/knowledge/case-index.md` を引用する
5. 既存資料に答えがない場合は「資料に記載がありません。〜さん（`docs/overview/org-profile.md` §キーパーソン一覧参照）に確認することを推奨します」と明示する

**絶対禁止**:
- 記憶で答える（プロジェクト固有事項）
- docs に書いていないことを「たぶん〜」と推測する
- 「一般的には〜」と Salesforce 一般論にすり替える（プロジェクト固有事項の質問の場合）

---

## コマンド・エージェント共通ルール

### AskUserQuestion ルール（厳守）

- **1質問1回答**: `questions[]` には1件のみ入れて順番に呼ぶ（複数同時表示は選択UIが縦に長くなりユーザーが選択しにくくなるため）
- **Other 文言禁止**（single select でのみ適用）: `label` に「Other」「自由入力」「手動入力」等を含めない。ただし「別のフォルダを指定する」等のコンテキスト具体ラベルは許容
- **候補がある場合は必ず AskUserQuestion** で提示する。自由入力が必要な場合（初回パス等）はチャットで聞く
- **assistant メッセージへの候補列挙禁止**: 選択肢・件数内訳は AskUserQuestion の label / description に集約する
- **`options` は配列**（JSON 文字列シリアライズは NG）。`questions[]` でラップし `header` は必須

詳細スキーマ・NG 例: `.claude/templates/common/ask-user-question-spec.md` 参照

### テンプレート置換ルール（厳守）

`{project_dir}` `{output_dir}` `{author}` 等の `{...}` プレースホルダーは f-string ではなく、**Bash / AskUserQuestion に渡す直前に Claude が実値でテキスト置換する**。パス値は `\` → `/`・末尾 `/` 除去。文字列値はシングルクォート内の `'` を `\'` エスケープ。

詳細規則・エスケープパターン: `.claude/templates/common/template-substitution-spec.md` 参照

共通プレースホルダー一覧:

| プレースホルダー | 種別 | 確定タイミング |
|---|---|---|
| `{project_dir}` | パス | セッション開始時 |
| `{output_dir}` | パス | Phase 入口 |
| `{author}` | 文字列 | persona から取得 |
| `{alias}` | 文字列 | sf org default 取得時 |

**実行直前の自己点検**: Bash / AskUserQuestion / Write に渡す直前、`{...}` リテラルが残っていないか確認。残っていたら置換ルール違反 → 該当 Phase に戻る。

---

## 開発時の振る舞いルール

**日本語の指示に対して、docs/ のコンテキストを活用して精度の高い作業を行う。**

### 作業前に必ず参照するもの

どんな開発タスクでも、着手前に以下を確認する:

| 状況 | 参照先 | 理由 |
|---|---|---|
| **常に** | `docs/overview/org-profile.md` | 用語集でオブジェクト名・項目名の正しい対応を確認 |
| 項目・オブジェクト操作 | `docs/catalog/{対象}.md` | 既存の項目構成・リレーション・入力規則を把握 |
| 機能実装 | `docs/design/{種別}/` | 該当機能の設計書があれば設計に従う |
| 要件確認 | `docs/requirements/requirements.md` | 要件番号・ビジネスルール・受入基準を確認 |
| マスタ参照 | `docs/data/master-data.md` | ピックリスト値・商品名等の正確な値を使う |
| メール関連 | `docs/data/email-templates.md` | 既存テンプレートのトーン・差し込み項目を把握 |
| 自動化・承認関連 | `docs/data/automation-config.md` | 既存のキュー・承認プロセスを把握 |

### 指示パターン別の動き方

詳細手順: `.claude/templates/common/dev-task-patterns.md` 参照

| パターン | 概要 |
|---|---|
| 「項目を作って」 | catalog 確認 → force-app 確認 → 作成 → catalog 更新 |
| 「Apex 作って」 | docs/design/apex 確認 → バルク実装 → 設計書なければ提案 |
| 「フロー作って」 | docs/design/flow 確認 → 競合チェック → 実装 |
| 「バグ直して」 | エラー確認 → catalog/design → requirements 確認 → 修正 |
| 「デプロイして」 | changelog 確認 → メタデータ確認 → 提示してユーザー確認待ち |
| スコープ外の依頼 | スコープ確認 → 3択提示 → ユーザー判断待ち |

### docs が存在しない場合

docs がない場合: 「命名は一般的なSalesforce慣例に従います」と伝え、作業後に `/sf-memory` 実行を提案する。

### 実装後のドキュメント更新（全エージェント共通）

実装完了時にドキュメントも更新する。提案ではなく実行する。対象ファイルが存在しない場合のみ作成を提案。`docs/logs/changelog.md` に変更サマリを1行追記する。

更新対象マッピング: `.claude/templates/common/post-implementation-doc-update.md` 参照

### 判断記録の自動追記

保守課題や設計判断で「なぜこの方針にしたか」を決定した場合、`docs/decisions.md` に記録を追記する。

**記録するタイミング:**
- `/backlog` で対応方針を確定し、実装を完了したとき
- 複数の実装案から1つを選択したとき（選定理由と排除理由を残す）
- 既存実装の背景・制約が判明したとき（調査で分かったこと）

**記録しないもの:**
- 選択肢が1つしかない自明な対応（typo修正、単純なバグ等）
- 一般的なSalesforceベストプラクティスに従っただけの判断

**形式:** 最上部に追記（降順）。テンプレートのコメントに従う。

---

## Agent Selection

タスクを受け取ったら以下の基準でエージェントに委譲する。複数該当する場合はタスクを分解して各エージェントに割り当てる。

### 主担当エージェント（ユーザーから直接指示を受ける）

| タスクの性質 | エージェント |
|---|---|
| Apex / LWC / Flow / メタデータ実装 / 新規開発 / 機能改修 / デプロイ | `sf-dev` |
| テスト計画 / テストケース作成 / バグ調査 / UAT支援 / 品質確認 | `qa-engineer` |
| コードレビュー / セキュリティ監査 / PRレビュー支援 / ドキュメントレビュー（設計書・要件定義書） | `reviewer` |
| 要件定義 / 設計書作成 / 設計レビュー / オブジェクト定義書 / 影響調査 / ユーザーストーリー | `sf-architect` |
| データ移行 / CSVマッピング / Data Loader / SOQL最適化 / バルク処理 / データクレンジング | `data-manager` |
| 外部API連携 / REST・SOAP / Named Credentials / Platform Events / MuleSoft | `integration-dev` |
| 一般調査 / メール下書き / 翻訳 / アドホック / その他秘書業務 | `assistant` |
| 工数 / effort / 見積 / 「何時間」「どのくらい」系の新規見積依頼（コマンド内外問わず） | `sf-effort-estimator` |

### 保守特化エージェント（/backlog フロー内で Claude が自動委譲）

| 起動経路 | エージェント | 役割 |
|---|---|---|
| Phase 1 / option-similar-past-issue → investigator から Task 委譲 | `pattern-curator` | 過去完了課題の症状・対応実績を Backlog 全文検索して要約。Write 持たない |
| Phase 3.5 → validator から Task 委譲 | `regression-guard` | 変更ファイルの依存先・テストカバレッジ・影響再走査・過去修正履歴を一括確認。Write 持たない |

### コマンド専用エージェント（内部処理からのみ起動・ユーザーの直接指示不可）

| 起動コマンド | エージェント |
|---|---|
| `/sf-memory` cat1〜cat6・cat8 / 横断補完 | `sf-analyst-cat1〜cat6` / `sf-analyst-cat8` / `sf-org-analyst` |
| `/sf-memory` Phase 0 コンテキスト読込 | `sf-context-loader` |
| `/sf-design` 各ステップ | `sf-design-step1〜3` / `sf-design-writer` / `sf-screen-writer` / `sf-detail-design-writer` / `sf-doc-overview-writer` / `sf-doc-objects-writer` |
| `/backlog` 各 Phase | `backlog-investigator` / `backlog-planner` / `backlog-implementer` / `backlog-tester` / `backlog-releaser` / `backlog-validator` |
| blind 系（Task 経由のみ・親の情報を受け取らない） | `backlog-blind-second-opinion` / `backlog-blind-final-verifier` / `backlog-blind-validator` |

> エージェント定義: `.claude/agents/` 配下の各 `.md` ファイル（`sf-dev.md`・`reviewer.md`・`sf-architect.md` 等）
> **工数見積の強制集約**: `工数 / effort / 見積 / 何時間 / どのくらい` 等の語を含む**新規見積依頼**は、他エージェントが回答を始める前に必ず `sf-effort-estimator` に委譲する。例外なし。ファイル操作・閲覧依頼（例：「工数ログを開いて」「effort-log を確認して」）は除外。
> `sf-design-step2` の委譲先（順番厳守）: ① `sf-screen-writer`（画面系: LWC/画面フロー/Aura/VF）→ ② `sf-design-writer`（Apex系・機能一覧、①の結果を集約）の順に両方委譲

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

## プロジェクト資材

| フォルダ | 内容 | 生成コマンド |
|---|---|---|
| `docs/overview/` | 組織概要・用語集・ステークホルダー | `/sf-memory` |
| `docs/requirements/` | 要件定義書・ビジネスルール | `/sf-memory` |
| `docs/flow/` | 業務フロー・ユースケース一覧・スイムレーン定義 | `/sf-memory` |
| `docs/architecture/` | システム構成図用データ（system.json） | `/sf-memory` |
| `docs/design/{種別}/` | 機能別設計書（apex/flow/batch/lwc/integration/config） | `/sf-memory` |
| `docs/catalog/` | オブジェクト・項目定義書（Markdown・Claude記憶形成用） | `/sf-memory` |
| `docs/data/` | マスタデータ・テンプレート・統計・品質 | `/sf-memory` |
| `docs/logs/changelog.md` | 変更履歴 | 開発コマンド実行時に自動追記 |
| `docs/logs/effort-log.md` | 工数ログ（見込み） | `/backlog` 実行時に自動追記 |
| `docs/decisions.md` | 対応履歴・判断記録 | `/backlog` 完了時に自動追記 |
| `force-app/main/default/` | Salesforceメタデータ（初回は `sf project retrieve` 実行後に生成） | SFDX |
| `manifest/` | package.xml（`/sf-retrieve` 実行後に生成） | `/sf-retrieve` |

---

## ファイル読み込み（共通）

| 形式 | 方法 |
|---|---|
| .md / .txt / .csv / .json / .yml / .cls / .js / .html | Read ツールで直接読み込み |
| .xml（flow-meta.xml 等） | Read ツールで直接読み込み |
| .pdf | Read ツール（1回20ページまで。大きいPDFはページ指定で分割） |
| .xlsx | `python -c "import pandas as pd, sys; xl=pd.ExcelFile(sys.argv[1]); [print(f'=== {s} ===\n{pd.read_excel(xl,s).to_markdown(index=False)}\n') for s in xl.sheet_names]" "<ファイルパス>"` |
| .docx | `python -c "import docx, sys; doc=docx.Document(sys.argv[1]); [print(p.text) for p in doc.paragraphs]; [print('\|'+'\|'.join(c.text for c in r.cells)+'\|') for t in doc.tables for r in t.rows]" "<ファイルパス>"` |
| .pptx | `python -c "from pptx import Presentation; import sys; prs=Presentation(sys.argv[1]); [print(f'=== スライド{i+1} ===\n'+'\n'.join(s.text for s in slide.shapes if s.has_text_frame)) for i,slide in enumerate(prs.slides)]" "<ファイルパス>"` |

**sf コマンドが Git Bash で失敗する場合**:
```bash
SF_CLIENT_BIN="$(dirname "$(where sf | head -1 | sed 's/\\/\//g')")/../client/bin"
"$SF_CLIENT_BIN/node.exe" "$SF_CLIENT_BIN/run.js" <サブコマンド> <引数>
```

---

## 品質原則（sf-memory 全カテゴリ共通）

sf-analyst-cat1〜cat6、および sf-org-analyst が共通して守る原則。各カテゴリ固有の品質原則は各エージェント定義ファイル内に記載（cat8 は外部 SF 公式仕様を扱うため独立した品質原則を持つ — sf-analyst-cat8.md を参照）。

1. **網羅的に読む**: 指定資料・ソースコードは配下を再帰的に**全て**読む。サンプリングや抜粋禁止。大きいファイルは分割読みで**最後まで**目を通す。
2. **事実と推定を分ける**: メタデータ・資料・コードに明記されている事項は事実として記述。補間・推測した箇所は `**[推定]**` を付ける。確認が必要な箇所は `**[要確認]**` を付ける。空欄を勝手に埋めない。
3. **手動追記を消さない**: 差分更新モードでは既存の手動記入・設計コメント・要件番号・判断根拠を絶対に保持する。

---

## コンテキスト読込パターン（sf-context-loader）

SFプロジェクトの状態（オブジェクト定義・設計書・要件・業務フロー）を知っていれば精度が上がるエージェントに設ける。汎用調査・ファイル生成のみのエージェントは不要。SF 固有タスクとは限らないエージェント（assistant 等）は「SF 固有キーワードを含む場合のみ実行」と条件付きで記述する。

新規エージェント追加時の Phase 0 テンプレート: `.claude/templates/common/agent-phase0-template.md` 参照（呼び出し仕様: `.claude/templates/common/sf-context-load-phase0.md`）

---

## À la carte オプション判定パターン（backlog 系エージェント共通）

`/backlog` コマンドの全エージェントは、処理開始時に **Step 0b** でオプション判定を行う。詳細ロジック・判定 3 分岐・スキップ確認文体: `.claude/templates/backlog/_README.md` §Step 0 参照。

```markdown
### Step 0b: 関連オプションの判定

> 共通手順: [.claude/templates/backlog/_README.md](../templates/backlog/_README.md) §Step 0 を参照
> 本 agent の Phase: {N}（_index-phase{N}.md と _index-cross.md を Read して判定）
```

**適用範囲**: backlog-investigator / backlog-planner / backlog-validator / backlog-implementer / backlog-tester / backlog-releaser の全 6 エージェント（Step 0b は全エージェント必須）。

---

## 一時ファイルの後片付け（全エージェント共通）

作業用の `tmp_dir` を使ったエージェントは、成果物書き出し後・完了報告前に必ず削除する。

削除コマンド: `python -c "import shutil; shutil.rmtree(r'{tmp_dir}', ignore_errors=True)"`

エージェント定義への組み込み方・原則・確認コマンド: `.claude/templates/common/agent-cleanup-template.md` 参照

---

## ユーザー回答時のスコープ管理（全エージェント共通）

1. **質問に直接答える1行を最初に書く** — 冒頭に結論を置く
2. **補足は最大3項目まで** — 関連情報の羅列は禁止
3. **質問外の派生事項は「## 派生事項（質問外）」セクションで明示分離する**
4. **質問されていないコード書き換え・リファクタの提案は禁止**（聞かれてから「派生事項」で提案）
5. **「ついでに〜」型の追加作業は承認なし実施禁止** — 派生事項として提示してから実施

詳細・適用例・追加ルール記入欄: `.claude/templates/common/answer-scope-spec.md` 参照
