# Salesforce Development OS - 共通ルール

> このファイルはテンプレートの共通ルール。基本的に編集しない。
> プロジェクト固有のルールはルートの `CLAUDE.md` に記載する。

---

## Agent Selection

タスクを受け取ったら以下の基準でエージェントに委譲する。複数該当する場合はタスクを分解して各エージェントに割り当てる。

| タスクの性質 | エージェント |
|---|---|
| Apex / LWC / Flow / メタデータ実装 / 新規開発 / 機能改修 / デプロイ | `sf-dev` |
| テスト計画 / テストケース作成 / バグ調査 / UAT支援 / 品質確認 | `qa-engineer` |
| コードレビュー / セキュリティ監査 / PRレビュー支援 / ドキュメントレビュー（設計書・要件定義書） | `reviewer` |
| 要件定義 / 設計書作成 / 設計レビュー / オブジェクト定義書 / 影響調査 / ユーザーストーリー | `sf-architect` |
| データ移行 / CSVマッピング / Data Loader / SOQL最適化 / バルク処理 / データクレンジング | `data-manager` |
| 外部API連携 / REST・SOAP / Named Credentials / Platform Events / MuleSoft | `integration-dev` |
| 一般調査 / メール下書き / 翻訳 / アドホック / その他秘書業務 | `assistant` |
| `/sf-memory` カテゴリ1委譲（組織概要・環境情報・業務フロー・要件定義の収集） | `sf-analyst-cat1` |
| `/sf-memory` カテゴリ2委譲（オブジェクト・項目構成・ER図・オブジェクト定義書の生成） | `sf-analyst-cat2` |
| `/sf-memory` カテゴリ3委譲（マスタデータ・メールテンプレート・自動化設定の収集） | `sf-analyst-cat3` |
| `/sf-memory` カテゴリ4委譲（Apex・Flow・LWC・Batch等のコンポーネント設計書生成） | `sf-analyst-cat4` |
| `/sf-memory` カテゴリ5委譲（業務機能グループ定義 feature_groups.yml の生成） | `sf-analyst-cat5` |
| `/sf-memory` カテゴリ6委譲（Backlog 完了課題から工数温度感ドキュメントを生成） | `sf-analyst-cat6` |
| `/sf-memory` 全カテゴリ完了後の2周目横断補完（用語統一・矛盾解消・相互参照補完） | `sf-org-analyst` |
| タスク開始前に docs/ から関連コンテキストを選択的に抽出（Phase 0 として各エージェントから委譲） | `sf-context-loader` |
| `/sf-design` コマンドの詳細設計ステップ（グループ選択 + sf-detail-design-writer 委譲） | `sf-design-step1` |
| `/sf-design` コマンドのプログラム設計ステップ（sf-screen-writer + sf-design-writer 委譲） | `sf-design-step2` |
| `/sf-design` コマンドの機能一覧ステップ（generate_feature_list.py 直接呼び出し） | `sf-design-step3` |
| `sf-design-step2` から委譲（プログラム設計書・機能一覧 Excel生成） | ① `sf-screen-writer`（画面系: LWC/画面フロー/Aura/VF）→ ② `sf-design-writer`（Apex系・機能一覧、①の結果を集約）の**順に両方**委譲 |
| `/sf-design` コマンド全体から委譲（詳細設計 Excel生成） | `sf-detail-design-writer` |

> エージェント定義: `.claude/agents/` 配下の各 `.md` ファイル（`sf-dev.md`・`reviewer.md`・`sf-architect.md` 等）
> コマンド専用エージェント（ユーザーからの直接指示ではなく、コマンドの内部処理として呼ばれる）: `sf-org-analyst` / `sf-analyst-cat6` / `sf-design-step1〜3` / `sf-design-writer` / `sf-screen-writer` / `sf-detail-design-writer` / `sf-doc-overview-writer` / `sf-doc-objects-writer` / `backlog-investigator` / `backlog-planner` / `backlog-implementer` / `backlog-tester` / `backlog-releaser` / `backlog-validator`
> blind subagent（Task ツール経由でのみ起動・direct 呼び出し禁止・親の情報を受け取らない）: `backlog-blind-second-opinion` / `backlog-blind-final-verifier` / `backlog-blind-validator`

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

## コマンド・エージェント共通ルール

### AskUserQuestion ルール（厳守）

#### 正規スキーマ

AskUserQuestion の引数は以下の形のみ受け付ける。**俗称 `choices` ではなく `options`**。`options` は **配列**（JSON 文字列ではない）。

```json
{
  "questions": [
    {
      "question": "ここに疑問符で終わる質問文?",
      "header": "12文字以内",
      "multiSelect": false,
      "options": [
        { "label": "選択肢A", "description": "選択時に何が起きるか" },
        { "label": "選択肢B", "description": "選択時に何が起きるか" }
      ]
    }
  ]
}
```

| 項目 | 制約 |
|---|---|
| `questions` | 配列・1〜4件 |
| `questions[].question` | 文字列・疑問符終わり |
| `questions[].header` | 文字列・最大12文字 |
| `questions[].multiSelect` | bool |
| `questions[].options` | **配列**・2〜4件（JSON 文字列ではない） |
| `options[].label` | 文字列・1〜5語 |
| `options[].description` | 文字列 |

**NG 例**（実際に発生したエラー）:
```json
{
  "question": "...",
  "choices": "[{\"label\":\"A\"...}]"
}
```
❌ キー名が `choices`（正しくは `questions[].options`） / 値が JSON 文字列 / トップレベルが `questions[]` 配列でない / `header` 欠落

#### 運用ルール

- **1質問1回答**: 複数の質問を1つの AskUserQuestion にまとめない（`questions[]` には1件のみ入れて順番に呼ぶ）。
- **Other 文言禁止**（**テキスト入力代替の single select でのみ適用**。multiSelect で資料/項目種別を列挙する場合は対象外）: AskUserQuestion には自動で「Other（自由入力）」が付く。`options` の `label` に「Other」「自由入力」「手動入力」等の**そのままの語**を**絶対に含めない**。「スキップ」「デフォルト値を使う」等のみ記載する。**ただし schema 制約 ≥2 のため、前回値・自動取得値の対比として「別のフォルダを指定する」「別のエイリアスを使用」等の**コンテキスト具体ラベル**は許容**（Other 等価ではなく UX 上推奨。文言は対比対象を具体化すること）
- 選択肢がある場合（前回値・固定候補）は AskUserQuestion で提示する。テキスト自由入力が必要な場合（初回パス等）はチャットで直接聞く
- **assistant メッセージへの候補列挙禁止**: 選択肢を提示する際、候補一覧・件数内訳・対象 API 名等を assistant の地の文に列挙しない。AskUserQuestion の label / description にすべて集約する。Python スクリプトの stdout は内部処理用であり、ユーザーへ見せるために再表示しない。

### テンプレート置換ルール（厳守）

Python インラインコード内、**および AskUserQuestion の label / description 内**の `{project_dir}` `{output_dir}` `{author}` 等の `{...}` は f-string ではなく **Claude が実行前に実値でテキスト置換する** プレースホルダー。Bash / AskUserQuestion に渡す前に、値の種別に応じて以下の規則で置換する:

- **パス値** (`{project_dir}` / `{output_dir}` 等): Windows パスの `\` はすべて `/` に置換し、末尾の `/` は除去する（例: `C:\work\` → `C:/work`）。raw string 末尾 `\` による SyntaxError を回避するため。`pathlib.Path` は Windows でも forward slash を正しく解釈する。
- **任意文字列値** (`{author}` 等): シングルクォートで囲まれた箇所 (`'{author}'`) への埋め込み時は、値内の `'` を `\'` にエスケープし、改行 (`\n` `\r`) は空白に置換する（例: `O'Brien` → `O\'Brien`）。シェル引数 (`"{author}"`) への埋め込み時は値内の `"` を `\"` にエスケープする。
- 同じ規則は `.claude/agents/*.md` 等の連鎖エージェントでも適用される。委譲時に渡す値も上記規則で正規化済みの状態にすること。

#### 置換対象プレースホルダー一覧

| プレースホルダー | 種別 | 確定タイミング |
|---|---|---|
| `{project_dir}` | パス | セッション開始時 |
| `{output_dir}` | パス | Phase 入口 |
| `{report_dir}` | パス | `.backlog_config.yml` 読み込み時 |
| `{xlsx_folder}` | パス | `/backlog` Phase 1.5 |
| `{evidence_dir}` | パス | Phase 1.5 連動 |
| `{issueID}` | 文字列 | `/backlog` Phase 0 |
| `{件名}` / `{件名_sanitized}` | 文字列 | Phase 1.5 |
| `{author}` | 文字列 | persona から取得 |
| `{alias}` | 文字列 | sf org default 取得時 |

**実行直前の自己点検**: Bash / AskUserQuestion / Write に渡す直前、文字列中に `{...}` リテラルが残っていないか必ず確認。残っていたら置換ルール違反 → 該当 Phase に戻る。

---

## Security & Permissions

### settings.json による技術的ブロック（全員に適用）

`settings.json` は **Git管理対象**。チーム全員に同じ権限制限が強制される。

| ブロック対象 | 理由 | 状態 |
|---|---|---|
| `.claude/` 配下の編集・書き込み | テンプレート保護（管理者以外の変更を防止） | **行動指示のみ**（技術的ブロックは未設定） |
| `rm -rf` / `rm -r .claude` | テンプレート・プロジェクト資材の誤削除防止 | **行動指示のみ**（技術的ブロックは未設定） |
| 本番環境へのデプロイ | 本番操作は必ず人間が確認 | **常時有効** |
| `git push origin main/develop` / `git reset --hard` 等 | PR経由運用の強制・破壊的操作の防止 | **未実装**（チーム導入時に settings.json へ deny ルール追加） |

### テンプレート保護（.claude/ 配下）

- エージェント定義・コマンド定義・共通ルール・settings.json は保護対象（行動指示による）
- テンプレートの更新は `/upgrade` コマンド経由で行う

### 本番組織接続時の絶対ルール

ルートの `CLAUDE.md` に「接続組織: 本番」と記録されている場合、または `sf org display` で `isSandbox: false` が確認された場合は、以下を **絶対に実行しない**:

| 禁止操作 | 具体例 |
|---|---|
| DML操作 | `sf data create / update / delete / upsert`、Apex 匿名実行でのDML |
| デプロイ | `sf project deploy start`（対象org問わず） |
| メタデータ変更 | `sf metadata deploy`、ページレイアウト・プロファイルの変更 |
| force-app への書き込み | ファイル作成・編集・削除 |

**許可する操作**: SOQL SELECT クエリ（`sf data query`）・メタデータ取得（`sf project retrieve`）・ファイル読み取り・docs/ への書き込み（情報記録）

この制約はユーザーが明示的に「本番に書き込んでよい」と指示しても解除しない。

### 共有フォルダ・社内フォルダの保護

- `G:\共有ドライブ` / `G:\Shared drives` への**削除**は **hook によるハードブロック**（常時有効、pre-operation.js）。bypass なし
- `G:\共有ドライブ` / `G:\Shared drives` への**書き込み**は技術的にはブロックしない。ただし**実行前に必ず日本語の警告メッセージを会話で出し、ユーザーの了承を得てから実行する**:

  > ⚠️ `G:\共有ドライブ` 配下のファイル `{パス}` に書き込みます。共有データのためチーム全員に影響します。実行してよろしいですか？

- ユーザーが「OK」「進めて」「やって」等で明示的に承認した場合のみ書き込む
- **`C:/tmp/` 等を経由する回避策での書き込みは禁止**。直接書き込む or 諦める
- AskUserQuestion の選択 UI ではなく、上記の日本語自然文を地の文で出してから会話で確認する
- ネットワークドライブ（`\\server\...`, `//server/...`）・SharePoint・OneDrive — **行動指示による**（技術的ブロックなし）
- 他プロジェクトのフォルダ（このプロジェクトフォルダ外）— **行動指示による**（技術的ブロックなし）

### ファイル変更ルール

| 対象 | 操作 | 制御方法 |
|---|---|---|
| `.claude/` 配下 | 読み取りのみ | 行動指示による（技術的ブロックなし） |
| `CLAUDE.md`（ルート） | 自由に編集可 | — |
| `docs/` 配下 | 自由に追加・編集可 | — |
| `force-app/` 配下 | 開発作業として編集可 | — |
| `.mcp.json` | `/setup-mcp` で生成・更新 | .gitignore 対象（個人設定） |
| `.gitignore` | 慎重に編集 | 変更時はユーザー確認 |


---

## Prohibited Actions（必ずユーザー確認を取る）

Git操作・ファイル破壊・本番デプロイは上記 Security & Permissions セクションで制御済み。以下はそれ以外の禁止操作:

- Salesforce **本番環境** へのデプロイ・データ変更・設定変更
- Slack / メール / チャット / 外部サービスへのメッセージ送信
- 機密情報（トークン・パスワード・個人情報・組織ID）の出力・ログへの記録
- 既存ファイルの削除・上書き（読み取り確認なしに）

---

## Quality Standards

### Salesforce コード全般
- ガバナ制限の考慮必須（SOQL 100回・DML 150回・CPU 10秒等）
- DML / SOQL はループ外に配置（バルク処理必須）
- テストカバレッジ: 75%以上必須、90%以上目標
- FLS / CRUD / `with sharing` をデフォルト
- ハードコード禁止 → カスタムメタデータ / カスタム設定で管理
- コード変更は必ず Before / After 形式で提示

詳細な種別ごとの規約（Apex/LWC/Flow）は `sf-dev.md` の「メタデータ種別ごとの振る舞い」を参照。

### ドキュメント
- 結論が冒頭にある・読者・目的が明確・アクションが具体的

### タスク管理
- アクション動詞で始まる・完了の定義が明確・期限が設定されている

---

## Quality Gate（品質ゲート）

作業の種類に応じて、完了前に **必ず品質チェックを実行する**。チェックは同一セッション内で自動的に行う。

### ゲート定義

| 作業の種類 | 実行エージェント | チェック担当 | チェック内容 |
|---|---|---|---|
| Apex / LWC / トリガー実装 | sf-dev | **reviewer** | コード品質・ガバナ制限・FLS・テストカバレッジ |
| Flow 作成・変更 | sf-dev | **reviewer** | ループ内DML・フォールトパス・命名規則 |
| テストクラス作成 | sf-dev | **qa-engineer** | 正常系/異常系/バルクの網羅性・アサーション品質 |
| 設計書・要件定義書 | sf-architect | **reviewer** | 整合性・スコープ・受入基準の明確性・依頼との一致 |
| データ移行・SOQL | data-manager | **reviewer** | パフォーマンス・データ整合性・ガバナ制限 |
| 外部API連携 | integration-dev | **reviewer** | エラーハンドリング・リトライ・セキュリティ |

### ゲートの動作

```
1. 担当エージェントが作業を完了
2. 自動的にチェック担当エージェントの基準でレビューを実行
3. 問題がある場合:
   - 問題点を一覧表示
   - 修正案を提示
   - ユーザーに「修正する / このまま進める」を確認
   ※ reviewer は指摘・提案のみを行う（Edit/Write ツールを持たない）
     実際の修正は元の担当エージェントが行う
4. 問題がない場合:
   - 「品質チェック通過」と表示して完了
```

チェック基準の詳細は `reviewer`（コード・ドキュメント）および `qa-engineer`（テスト）を参照。

### ゲートの例外

以下の場合はゲートをスキップできる:
- ユーザーが明示的に「レビュー不要」「スキップして」と指示した場合
- 軽微な修正（typo修正、コメント追加等）
- 調査・デバッグ作業の途中経過（最終成果物ではないもの）

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

### 指示パターン別の動き方

#### 「項目を作って」「項目追加して」
1. `docs/catalog/` で対象オブジェクトの既存構成を確認
2. `docs/overview/org-profile.md` の用語集で命名を統一
3. プロジェクトルート `CLAUDE.md` の命名規則に従う
4. メタデータファイルを作成（force-app 配下）
5. `docs/catalog/` の該当定義書を更新（項目追加を反映）

#### 「Apex 作って」「トリガー書いて」
1. `docs/design/apex/` に該当設計書があるか確認 → あれば設計に従う
2. `docs/catalog/` で対象オブジェクトの項目・リレーションを確認
3. `docs/requirements/requirements.md` で関連するビジネスルール（BR-XXX）を確認
4. Quality Standards に従って実装（バルク対応・テストクラス付き）
5. 設計書がない場合は「設計書がありませんが実装しますか？先に `sf-architect` に設計書作成を依頼することも可能です」と提案

#### 「フロー作って」
1. `docs/design/flow/` に該当設計書があるか確認
2. `docs/catalog/` で対象オブジェクトの入力規則・既存自動化を確認（競合リスク）
3. 実装してメタデータファイルを作成

#### 「バグ直して」「エラー出る」
1. エラー内容を確認
2. `docs/catalog/` で関連オブジェクト・項目を把握
3. `docs/design/` で該当機能の設計意図を確認
4. `docs/requirements/requirements.md` で関連ビジネスルールを確認（仕様なのかバグなのか判断）
5. 修正実施

#### 「デプロイして」
1. `docs/logs/changelog.md` で最近の変更を確認
2. 対象のメタデータを確認
3. デプロイコマンドを提示（**本番へのデプロイは必ずユーザー確認**）

#### スコープ外の依頼を受けたとき（`docs/requirements/requirements.md` のスコープ定義と合致しない場合）

開発依頼が `docs/requirements/requirements.md` のスコープ定義と合致しない場合:

1. 作業を始める前に「この依頼は現在のスコープ定義に含まれていない可能性があります」と伝える
2. 該当するスコープ定義を引用して提示する
3. 以下の選択肢を提示する:
   ```
   a. スコープに追加して進める（要件定義書を更新します）
   b. スコープ外として対応しない
   c. スコープを確認してから判断する
   ```
4. ユーザーの判断を待ってから動く。勝手に進めない

requirements.md にスコープ定義がない場合はこのチェックをスキップして作業する。

### docs が存在しない場合

セットアップ直後や docs が空の場合でも開発は可能。ただし:
- 「用語集がないため、命名は一般的なSalesforce慣例に従います」と伝える
- 「設計書が見つかりません。要件を教えてください」と聞く
- 作業後に「`/sf-memory` で定義書を更新することを推奨します」と提案

### 実装後のドキュメント更新（全エージェント共通）

開発作業によって組織の構成が変わった場合、**実装完了時にドキュメントも更新する**。提案ではなく実行する。

| 実装内容 | 更新対象 | 更新方法 |
|---|---|---|
| カスタム項目の追加・変更・削除 | `docs/catalog/{オブジェクト名}.md` | 項目一覧テーブルに反映 |
| Apex / トリガーの追加・変更 | `docs/design/apex/{クラス名}.md` | 設計書があれば更新、なければ作成を提案 |
| フローの追加・変更 | `docs/design/flow/{フロー名}.md` | 設計書があれば更新、なければ作成を提案 |
| LWCの追加・変更 | `docs/design/lwc/{コンポーネント名}.md` | 設計書があれば更新、なければ作成を提案 |
| 権限セット・プロファイル変更 | `docs/catalog/{オブジェクト名}.md` | 権限マトリクスに反映 |
| 入力規則の追加・変更 | `docs/catalog/{オブジェクト名}.md` | 自動化・ビジネスルールセクションに反映 |
| レイアウト変更 | — | ドキュメント更新不要 |

**更新ルール:**
- `docs/catalog/` の該当ファイルが**存在する場合**: 直接更新する
- `docs/design/` の該当ファイルが**存在する場合**: 直接更新する
- 該当ファイルが**存在しない場合**: 「設計書がありません。作成しますか？」と確認する（勝手に新規作成しない）
- `docs/logs/changelog.md` に変更サマリを1行追記する（日付・変更内容・関連課題ID）
- チーム間の差異を防ぐため、更新は実装と同一セッション内で行う

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
| `docs/logs/changelog.md` | 変更履歴 | 自動 |
| `docs/logs/effort-log.md` | 工数ログ（見込み） | `/backlog` 実行時に自動追記 |
| `docs/decisions.md` | 対応履歴・判断記録 | `/backlog` 完了時に自動追記 |
| `force-app/main/default/` | Salesforceメタデータ | SFDX |
| `manifest/` | package.xml | `/sf-retrieve` |

---

## ユーザー回答時の実装裏付け（全エージェント共通）

ユーザーへの回答・対応方針提示・調査結果報告・バグ原因仮説で「動作の挙動」を断定する箇所は、必ず実装コード（Apex/LWC/Flow/メタデータ）を Read で確認し、根拠を `ファイル名:行番号` で明示する。記憶・推測で断定しない。

### 適用範囲

以下の表現を含む回答はすべて対象:
- 「重複する／上書きされる／新規作成される／既存が更新される」
- 「○○の場合は××になる」「○○すると××が起きる」
- 「△△は◇◇という仕様」
- 対応方針の妥当性判断（「この方針だと〜になる」等）

### 必須確認手順

| 確認項目 | 確認方法 |
|---|---|
| DML 挙動 | 対象 Apex の `insert / update / upsert / delete` を Read で確認 |
| 自動処理 | Trigger / Flow / Process Builder の対象オブジェクト・実行条件・操作内容を Read で確認 |
| 項目挙動 | field-meta.xml で型・required・default・formula を Read で確認 |
| 権限挙動 | 該当 permissionset / profile を Read で確認 |

### 推測の扱い

実装確認できない・する必要がない範囲は `**[推定]**` または `**[要確認]**` を付けて明示する。根拠なしの断定はしない。

### ユーザーに流されない

「やっぱり○○なんじゃない？」「××のはずだよね？」と来ても、実装確認なしに同調しない。「実装を確認します」と一拍置いて該当コードを Read してから回答する。**ユーザーに流されないことが正しい対応につながる**。

### エージェントでの書き方

各エージェント定義の Phase 0 直後または最初の対応 Phase の冒頭に1行参照リンクを置く:

```markdown
[共通ルール参照](.claude/CLAUDE.md#ユーザー回答時の実装裏付け全エージェント共通)
```

---

## 引用・出典の確認（全エージェント共通）

会話で言及される文章（Backlog コメント・チャット履歴・ドキュメント引用・ユーザー貼り付けテキスト）を**誰が書いたか／どこから来たか**説明・解釈する前に、必ず出典を確認する。記憶・推測で出典を捏造しない。

### 適用範囲

以下の表現を含む回答はすべて対象:
- 「この文章は私が書いた／お客さんが書いた／○○さんの発言」等の出典帰属
- 「これは前回の会話で〜と説明したもの」等の過去発言の参照
- Backlog コメント内のテキストを引用・解釈する場面
- 議事録・メール・チャット履歴の引用

### 必須確認手順

| 確認項目 | 確認方法 |
|---|---|
| 直前のユーザーメッセージ | 出典が明示されていないか再読する（「お客さんからの返信」「議事録の抜粋」等の言及を見落とさない） |
| Backlog コメント | 記憶ではなく `mcp__backlog__get_issue_comments` で再取得して照合する |
| 過去の自分の発言 | 「以前私が書いた」と語る前に、実際の conversation を確認する。一致箇所が見つからなければ「出典不明」と認める |

### 確証がない場合

「出典を確認します」と一拍置いてから確認する。確認できない場合は `**[出典不明]**` と明示する。「これは○○です」と断定しない。

### ユーザーが出典を指摘してきたら立ち止まる

「直前にお客さんからの返信って言ったよ」等の指摘が来たら、即座に MCP 再取得・直前メッセージ再読をする。「私が書いた可能性もあります」等の曖昧な逃げは禁止。確認してから回答する。

### エージェントでの書き方

各エージェントの該当 Phase 冒頭に1行参照リンクを置く:

```markdown
[共通ルール参照](.claude/CLAUDE.md#引用出典の確認全エージェント共通)
```

---

## 品質原則（sf-memory 全カテゴリ共通）

sf-analyst-cat1〜cat5 が共通して守る原則。各カテゴリ固有の品質原則は各エージェント定義ファイル内に記載。

1. **網羅的に読む**: 指定資料・ソースコードは配下を再帰的に**全て**読む。サンプリングや抜粋禁止。大きいファイルは分割読みで**最後まで**目を通す。
2. **事実と推定を分ける**: メタデータ・資料・コードに明記されている事項は事実として記述。補間・推測した箇所は `**[推定]**` を付ける。確認が必要な箇所は `**[要確認]**` を付ける。空欄を勝手に埋めない。
3. **手動追記を消さない**: 差分更新モードでは既存の手動記入・設計コメント・要件番号・判断根拠を絶対に保持する。

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
SF_CLIENT_BIN="$(dirname "$(where sf | head -1)")/../client/bin"
"$SF_CLIENT_BIN/node.exe" "$SF_CLIENT_BIN/run.js" <サブコマンド> <引数>
```

---

## コンテキスト読込パターン（sf-context-loader）

新規エージェントを追加する際は、以下のパターンに従って **Phase 0** を冒頭に設ける。

```markdown
## Phase 0: SFコンテキスト読込（sf-context-loader 経由）

タスク開始前に sf-context-loader を呼び出し、関連 docs の要約を取得する。

\`\`\`
task_description: 「{ユーザー指示 / タスク概要}」
project_dir: {プロジェクトルートパス。不明な場合はカレントディレクトリ}
focus_hints: []
\`\`\`

- **「該当コンテキストなし」が返った場合**: スキップして次フェーズへ（docs/ 未整備または SF 無関係）
- **関連コンテキストが返った場合**: 関連オブジェクト・CMP・UC・注意点を以降の作業の判断材料として保持する

---
```

**適用基準**: SFプロジェクトの状態（オブジェクト定義・設計書・要件・業務フロー）を知っていれば精度が上がるエージェントに設ける。汎用調査・ファイル生成のみのエージェントは不要。

**SF 固有タスクとは限らないエージェント**（assistant 等）は、「SF 固有キーワードを含む場合のみ実行」と条件付きで記述する。

---

## À la carte オプション判定パターン（backlog 系エージェント共通）

`/backlog` コマンドの全エージェントは、処理開始時に **Step 0b** でオプション判定を行う。

```markdown
### Step 0b: 関連オプションの判定

> 共通手順: [.claude/templates/backlog/_README.md](../templates/backlog/_README.md) §Step 0 を参照
> 本 agent の Phase: {N}（_index-phase{N}.md と _index-cross.md を Read して判定）
```

**判定 3 分岐**:

| 判定 | 条件 | 挙動 |
|---|---|---|
| 実行 | `auto-execute-when` マッチ / グレー | 黙って実行 |
| スキップ確認 | `auto-skip-when` 明確マッチ | `ask-user-prompt` で自然な日本語確認 |
| 実行（不明） | 評価不能 | 実行に倒す |

**オプション定義**: `.claude/templates/backlog/` 配下の `_index-phase{N}.md`（Phase 別判定情報）+ `options/option-*.md`（実行手順）の 2 層構造。詳細は [_README.md](.claude/templates/backlog/_README.md) を参照。

**適用範囲**: backlog-investigator / backlog-planner / backlog-validator / backlog-implementer / backlog-tester / backlog-releaser の全 6 エージェント（Step 0b は全エージェント必須）。

---

## 一時ファイルの後片付け（全エージェント共通）

作業用の `tmp_dir` を作成・使用したエージェントは、**成果物を最終出力先に書き出した後、完了報告の前に必ず削除する**。

### 実行コマンド

```bash
python -c "import shutil; shutil.rmtree(r'{tmp_dir}', ignore_errors=True)"
```

### 原則

1. **削除タイミング**: 最終 Phase の成果物書き出し完了後、完了報告の直前
2. **成功時のみ削除**: 途中でエラー終了した場合は残してデバッグに使う
3. **対象**: 自エージェントが作成した `tmp_dir` のみ。他エージェントの作業フォルダや `output_dir`・`project_dir` 直下の既存ファイルには触れない
4. **確認**: 削除後に `os.path.exists(tmp_dir)` が False であることを確認してから完了報告

### エージェントでの書き方

各エージェント定義の末尾に `## Phase 最終: クリーンアップ` セクションを置き、本セクションを参照する:

```markdown
## Phase 最終: クリーンアップ
[共通ルール参照](.claude/CLAUDE.md#一時ファイルの後片付け全エージェント共通)

python -c "import shutil; shutil.rmtree(r'{tmp_dir}', ignore_errors=True)"
```
