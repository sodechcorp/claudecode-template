---
description: "Backlog課題の調査・対応・記録を一気通貫で実施する。専門エージェントを順に起動し、各フェーズ完了後にユーザ確認を取りながら進める。/backlog [課題ID] で個別課題対応。"
argument-hint: "[課題ID]"
---

# /backlog [課題ID]

**モード判定**: `--light` フラグが付いている場合（例: `/backlog GF-123 --light`）は軽微修正ショートカットで実行する（Phase 2 / Phase 3.5 をスキップ）。それ以外は通常フローを実行する。この判定結果を `{light_mode}` = `true`（--light 時）/ `false`（通常）として会話の最後まで保持する（investigation.md フロントマターへの記録に使用）。

**`--reconfigure` フラグ**: `.backlog_config.yml` に `xlsx_default` / `report_dir` が既に設定されていても、Phase 1.5 の xlsx 作成有無・フォルダパス確定を再確認し、回答で設定を上書きする（例: `/backlog GF-123 --reconfigure`）。手動での YAML 編集を不要にするための再設定用フラグ。

**引数の解釈**: `$ARGUMENTS` の先頭トークン（`--` で始まらない最初の語）を `{issueID}` とし、`--light` / `--reconfigure` 等のフラグは除外する（`GF-123 --light` も `--light GF-123` も issueID=`GF-123`）。

## 概要

保守課題の対応を7つの専門エージェントが分担する。各フェーズはエージェントに完全委譲し、フェーズ間でユーザ確認・xlsx更新を行う。

| フェーズ | エージェント | 主な成果物 |
|---|---|---|
| Phase 0: 作業フォルダ作成 | （本コマンド直接実行） | `docs/logs/{issueID}/` |
| Phase 1: 調査・理解 | `backlog-investigator` | `investigation.md` |
| Phase 1.6: Sandbox 仮説検証 | `backlog-repro-runner` | `hypothesis-verification.md`（バグ系のみ） |
| Phase 1.5: xlsx フォルダ確定 | （本コマンド直接実行） | `{xlsx_folder}` 変数確定のみ |
| Phase 2: 対応方針の確定 | `backlog-planner` Phase A | `approach-plan.md` |
| Phase 3: 実装方針の確定 | `backlog-planner` Phase B | `implementation-plan.md` + xlsx 一括生成 |
| Phase 3.5: 実装前検証 | `backlog-validator` | `validation-report.md` |
| Phase 4: 実装 | `backlog-implementer`（内部: `sf-context-loader`） | 変更ファイル一覧 |
| Phase 5: スモーク確認 | `backlog-tester`（内部: `sf-context-loader`） | スモーク結果（PASS で Phase 6 へ進む） |
| Phase 6: Sandbox リリース・完了 | `backlog-releaser`（内部: `sf-context-loader`） | 完了報告 |

> **実行順の注記**: 表・見出し番号は歴史的経緯により Phase 1.6 が Phase 1.5 より先に実行される（実行順: Phase 1 → 1.6 → 1.5 → 2。表の行順・見出しの並び順は実行順と一致している）。フェーズ番号の大小と実行順が一致しない点に注意すること。

> **種別が「問い合わせ」の場合**: 実装を伴わないため、Phase 1 完了後に Phase 1.6・1.5・3〜6 をスキップし、Phase 2 で `backlog-planner` が回答ドラフト（`answer-draft.md`）を生成して完了する（詳細は Phase 2 セクション参照）。

**各エージェントの内部構造**: 全エージェント（`backlog-repro-runner` を除く）は Step 0b でフェーズ用 `_index-phase{N}.md` を読んでオプション判定を行う（[à la carte 仕組み](../templates/backlog/_README.md)）。`backlog-repro-runner` は Phase 1.6（バグ系のみ）専用で Step 0b を持たず、à la carte 判定の対象外。`backlog-implementer` / `backlog-tester` / `backlog-releaser` / `backlog-planner` はさらに Step 0a で `sf-context-loader` を呼び出す（`backlog-planner` は digest 優先で実運用上ほぼ発火しない）。Phase 1.5 は本コマンドが直接実行するためエージェントを起動せず、`_index-phase1-5.md` は存在しない（不要）。

> **サブエージェントの二段ネストを避ける（`backlog-validator` は完全 leaf agent・`backlog-investigator` は部分的）**: サブエージェントがさらに別のサブエージェントを起動する二段ネストのうち、「同一メッセージでの複数 Agent/Task 同時発行」を伴う箇所は不安定化要因と特定し、本コマンド（メインスレッド）に引き上げた。単発・非並列の呼び出し（`backlog-planner → sf-effort-estimator` / `backlog-investigator → pattern-curator・backlog-blind-second-opinion` 等）は `auto-evidence-runner → ui-evidence-runner`（`/test`）と同型の安定パターンのため据え置いている。
> - `backlog-validator`: `regression-guard`・`ui-evidence-runner`（Before-only）を本コマンドが Phase 3.5 開始時に直接 Task 起動（詳細は Phase 3.5 セクション参照）
> - `backlog-planner`: `backlog-blind-validator`（`option-validator-blind` 採用時のみ）を本コマンドが Phase 3 完了直後に直接 Task 起動（詳細は Phase 3 セクション参照）
> - `backlog-investigator`: `sf-context-loader`（knowledge-only + 通常モード。旧設計では同一メッセージ並列発行しており不安定化要因だった）を本コマンドが Phase 1 開始時に逐次 Task 起動（詳細は Phase 1 セクション参照）。詳細は [agent-routing.md](../spec/agent-routing.md) 参照

**中間成果物の保存先**: `docs/logs/{issueID}/`
- `investigation.md` — 調査レポート
- `approach-plan.md` — 対応方針
- `implementation-plan.md` — 実装方針（全判断ポイント確定版）

**エビデンス保存先**: `{evidence_dir}` 配下（Phase 1.5 で確定）
- xlsx 作成あり: `{xlsx_folder}/evidence/{before,after}/`
- xlsx 作成なし: `docs/logs/{issueID}/evidence/{before,after}/`

---

## 実行手順

> **絶対ルール**
>
> **【フェーズ進行】**
> - 各フェーズ完了後、次へ進む前にユーザの明示的な許可を必ず取る（黙って次フェーズへ進まない）
> - **フェーズ末の進め方**:
>   1. **フェーズ別の型は [_README.md §サマリーの書き方](../templates/backlog/_README.md) に従ってチャットに提示する**（Phase 1〜3 は課題の概要・前提再掲・最終挙動を含む人間向けの日本語。技術詳細は成果物に記録しチャットに並べない。その他のフェーズは3〜5行で本質・発見・引き渡し要点を要約）
>   2. 「特に確認したい点」を **0〜3 個**テキストで挙げる。確認事項がなければ「特に確認事項はありません」と明記し、無理やり挙げない。実装詳細・テスト段取り・スコープ自明事項は確認質問に含めず本文に記載する（責務境界の詳細は各エージェント定義を参照）。**このルールは Phase 1〜6 すべてのフェーズ末に適用する**（investigator / planner / validator / implementer / tester / releaser の全エージェント共通）。何を確認事項に書いてよい／書かないかの基準は [_README.md §確認事項の選定基準](../templates/backlog/_README.md) を正本とする。
>   3. ユーザの自由テキスト応答を待つ（質問・修正依頼・承認 何でも可）
>   4. 議論が落ち着いたら「Phase N に進んでよろしいですか？」とテキストで明示確認
>   5. ユーザの承認テキスト（「OK」「進んで」等）を確認してから次フェーズへ進む。**質問・相槌（「ha」「うん」等）・別タスク依頼（「工数計算して」「見積もって」等）は承認ではない**。工数・見積依頼は `sf-effort-estimator` 委譲対象で承認を兼ねない（タスク完了後に承認プロトコルを再提示する）。確信できなければ進まず確認を出し直す（詳細は [_README.md §承認判定](../templates/backlog/_README.md) 参照）。
> - 実装は Phase 4 以降。それ以前に実装コードを書くことは禁止。**Phase 3.5→4 の境界はファイル編集に入る唯一のゲートであり、特に厳格に明示承認を確認すること。**
> - **軽量承認モード（低不可逆ゲート限定）**: 以下の条件を **全て満たす場合のみ**、フェーズ末の明示承認待ちを「異議がなければ次へ」に緩和してよい。1つでも崩れたら通常の明示承認プロトコル（上記 1〜5）に戻す。
>   - **適用条件**: ③ 次フェーズが read-only 解析または dry-run（永続副作用なし）の低不可逆ゲートであることを常に必須とする。加えて **Phase 4（実装）着手後の遷移**（現状 Phase 4→5 のみ該当）では ① 課題が [_README.md §典型的自明ケース定義](../templates/backlog/_README.md) に該当（自明ケース判定 ON） ② [quality-gate.md §軽微修正の4条件](../spec/quality-gate.md) を全て満たす、の2条件もAND必須（実装で確定した差分を人間が確認しないまま次フェーズへ進めないため）。**Phase 4着手前の遷移**（Phase 1→1.6→1.5→2→3→3.5。コード・メタデータへの変更が一切発生していない）は①②不要、③のみで判定する
>   - **挙動**: フェーズ末サマリー＋「特に確認したい点」を提示した上で、末尾に「**異議がなければこのまま Phase N に進みます**」と明示し、明示承認テキストを待たず次フェーズへ進んでよい（ユーザーはいつでも会話で異議・修正を差し込める）
>   - **ループ上限（必須）**: 軽量承認による連続自動進行は**最大 2 フェーズまで**（`discussion-log.md` の改版履歴から通算カウント）。上限到達時は必ず通常の明示承認プロトコルへ戻す。軽量承認で進んだ際は discussion-log.md の該当エントリ冒頭に `[軽量承認]` タグを付記し、Phase 1.6／Phase 3 戻りループのカウントと混同しないようにする
>   - **適用除外ゲート（軽量承認を絶対に適用しない・常に明示承認）**: Phase 3.5→4／Phase 5→6・Phase 6（Sandbox デプロイ）／本番デプロイ（後述）／お客様サイン（`customer-signoff.md`）／Backlog 投稿（`pre-operation.js` がハードブロック）
>
> **【AskUserQuestion】**
> - **AskUserQuestion は使わない**。フェーズ承認・選択肢提示はすべてテキスト会話で行う（例外: Phase 1.5 の xlsx 作成有無・フォルダパス確定 / Phase 0 の再開方法選択（investigation.md 存在時）/ Phase 3 xlsx スクリプト失敗時の対処選択 は AskUserQuestion を使う）
>
> **【ユーザー応答時】**
> - **ユーザー応答受信時の必須3点セット**:
>   1. ユーザーの返答が「差し込み・指摘・方針変更」を含む場合、次のアクション前に discussion-log.md に追記する
>   2. discussion-log.md 追記後に成果物に影響があれば修正する
>   3. Phase 末尾の確認プロトコルを実行する
>
> **【再開・変数】**
> - **compact 後の再開について**: 長尺セッションで /compact が発生した後に /backlog を継続する場合は、必ず /backlog コマンドを再起動して Phase 0d 経由でコンテキストを復元すること。エージェント実行途中で /compact が発生した場合も同様。investigation.md のフロントマターに記録した `issue_type` / `xlsx_folder` / `evidence_dir` / `light_mode` を Phase 0d で読み込んで変数を再設定する（フロントマター更新の義務・スキップ禁止・復元手順の詳細は [_README.md §compact 跨ぎ復元プロトコル](../templates/backlog/_README.md) を参照）
> - **種別変数 `{issue_type}` の管理**: Phase 1 完了時点で `investigation.md` の「種別」欄から `{issue_type}` = `バグ` / `追加要望` / `その他` / `問い合わせ` を確定し、会話の最後まで保持する。Phase 2（デフォルトスタンス／問い合わせ時は回答ドラフトモード分岐）・Phase 5（テスト観点）・Phase 6（お客様確認必須度）の分岐に使用する。種別欄が空欄・不明・記載なしの場合は「種別が判断できません。バグ / 追加要望 / その他 / 問い合わせ のどれに該当しますか？」とテキストで確認してから確定する
>
> **【環境・記録】**
> - **本番環境（isSandbox=false）への直接デプロイは絶対に行わない**
> - **xlsx 更新の共通ルール**: Phase 1.5 で定義される共通ルール①（timeline 呼び出しに `--reason "{根拠}"` を追加）と共通ルール②（xlsx シート書き込みは `update_records.py cell` を使用）は Phase 2 以降の全 timeline 更新で適用すること（詳細は「Phase 1.5: xlsx フォルダの確定」セクションの共通ルール定義を参照）
> - **中断・手動切替・リリース省略でフローが Phase 6 に到達しない場合**: `## §中断時の知見還流（部分還流）` に従い知見を `docs/knowledge/` へ部分還流してから終了する（知見取りこぼし防止）

---

### Step 0: 共通 CRITICAL ルールの読込（必須・コマンド起動直後）

以下を **Read で全文読み込む**（CLAUDE.md にはスタブのみ・詳細は外出し先）:

1. Read `.claude/templates/common/verify-implementation-spec.md` — 実装裏付けルール。追加ルール記入欄まで読む
2. Read `.claude/templates/common/verify-source-attribution-spec.md` — 出典確認ルール。追加ルール記入欄まで読む
3. Read `.claude/templates/common/answer-scope-spec.md` — 回答時のスコープ管理ルール（派生事項の分離・無断リファクタ禁止）
4. Read `.claude/templates/common/uncertainty-marker-spec.md` — 確証なし時のマーカー規約（[推定]/[要確認]/[出典不明]の使い分け）

**理由**: 各フェーズ間で main thread がユーザーの自由テキスト質問に応答する。CLAUDE.md にはスタブのみ記載のため、詳細を読まないと「挙動を実コード確認せず断定」「出典を捏造」「質問外の派生事項を無断で本文に混入」のリスクがある。backlog-* agent 側の Step 0c と同じ spec を読み、main thread と agent の知識を揃える。

---

### Phase 0: 作業フォルダの作成

**接続組織の確認**

```bash
sf config get target-org
```

```bash
sf org display --json
```

`isSandbox`・`Username`・`alias` を読み取る。

**取得に失敗した場合（sf CLI 未認証・組織未接続等）**: エラー内容をユーザーに提示し、「接続組織を確認できません。`sf org login web --alias <alias>` 等で認証済みの組織を指定してください」とテキストで依頼してから次に進む（自動リトライ・推測での続行はしない）。

**Sandbox 接続時（通知のみ・非ブロッキング）**: Backlog課題対応は Sandbox での実装・動作確認までがスコープであり、実データへの危険操作（DML・匿名Apex 実行等）自体は `sandbox-alias-check.md` の Sandbox 判定と settings.json/hook が別途ブロックする。よってここでのブロッキング確認は行わず、以下を一行通知して即座に次へ進む（ユーザーの返答を待たない）:

```
接続組織: {alias}（Sandbox）で課題対応を開始します。切り替える場合は sf config set target-org <alias>
```

**本番接続時（ブロッキング確認・必須）**: 本番組織は参照のみ可能（SELECT は都度許可）という重い制約があるため、引き続き確認が取れるまで次に進まない。

**同一セッション内スキップ（本番のみ対象）**: 本会話内で直前に確認・承認済みの alias と今回の alias が一致する場合、下記のブロッキング確認は省略し「接続組織確認済み（{alias} / 本番）」と一行だけ通知して次に進んでよい。alias が変わっている場合、または本会話内でまだ確認していない場合（会話開始直後の初回実行等）は必ず以下の全文確認を行う。

初回確認（または alias 変更時）は以下をテキストで提示する:

```
現在の接続組織:
  alias: {alias名}
  種別: 本番
  Username: {user@example.com}

この組織に対して課題対応を進めてよろしいですか？
（本番: 参照のみ可能。データ確認の SELECT 文は都度許可を取ります）
別の組織に切り替えたい場合: sf config set target-org <alias>
```

ユーザーが確認の返答をするまで次に進まない。確認が得られたら、その alias を本会話内で保持し、以降の同一セッション内スキップ判定に使う。

```powershell
New-Item -ItemType Directory -Force -Path "docs/logs/{issueID}" | Out-Null
```

`docs/logs/{issueID}/investigation.md` が既に存在する場合は AskUserQuestion で再開方法を選択する:
- label: `Phase 1 から再調査`、description: "既存の investigation.md を上書きして最初から調査をやり直す"
- label: `途中フェーズから再開`、description: "既存の調査結果を活かして指定フェーズから続行する"
- label: `中止`、description: "コマンドを終了する"

**「途中フェーズから再開」が選ばれた場合**:

> 再開ルーティング: [.claude/templates/backlog/resume-phase-routing.md](../templates/backlog/resume-phase-routing.md)
> ファイルが存在しない場合は「現在どのフェーズから再開しますか？（例: Phase 3）」とテキストで確認し、回答されたフェーズから処理を続行する。

**「中止」が選ばれた場合**: コマンドを終了する。

---

### Phase 0d: 既存ログの読み込み

`docs/logs/{issueID}/` 配下に既存ファイルがある場合（「途中フェーズから再開」「Phase 1 から再調査」いずれでも）、以下の順で必ず Read する:

1. `discussion-log.md` — 過去の議論・ユーザー指摘・却下案の経緯
2. `investigation.md` — 調査済み内容
3. `approach-plan.md` — 確定済み対応方針
4. `implementation-plan.md` — 確定済み実装方針
5. `validation-report.md` — 実装前検証結果
6. `test-report.md` — テスト結果

investigation.md を Read した際はフロントマター（`---` で囲まれた部分）から `issue_type` / `xlsx_folder` / `evidence_dir` / `light_mode` を変数として読み取り、以降のフェーズで使用する。

**分割読込ルール**: investigation.md・approach-plan.md・implementation-plan.md・validation-report.md・test-report.md は、**冒頭 80 行 + 末尾 30 行**を読めば十分（ファイルが 110 行未満の場合は全文）。フルが必要なフェーズ（実装フェーズなど）はエージェント側で個別に全文 Read すること（[共通ルール参照](../CLAUDE.md#中間成果物の分割読込全下流エージェント共通)）。

横断ファイル（フォルダが空・新規対応の場合も必ず Read する）:
- `docs/decisions.md` 冒頭 20 件（降順記録のため冒頭が直近。存在し、かつ雛形のみ・実エントリ 0 件でなければ）
- `docs/logs/changelog.md` 末尾 20 件

**読み込みの目的**: 同じ調査・同じ質問・同じ却下済み方針を繰り返さない。読み込み後、ユーザーへ以下をテキストで簡潔に報告する:

```
過去ログ読み込み済み（{読み込んだファイル名を列挙}）
前回: {最後に完了した Phase} まで完了。{discussion-log.md に記録された主な指摘・却下案を 1〜2 行で要約}
```

過去ログが一切ない場合（新規・フォルダ空）は「新規対応として進めます」とのみ報告し、通常の Phase 1 へ進む。

---

### Phase 1: 調査（backlog-investigator）

> **サブエージェントの二段ネストを避ける**: `backlog-investigator` は sf-context-loader を自ら起動しない。本コマンド（メインスレッド）が事前に取得し、結果を investigator の起動パラメータとして渡す。

**Step A: 課題本文の先行取得 + sf-context-loader（本コマンドが直接実行）**

1. `mcp__backlog__get_issue` で課題のタイトル・本文を取得する（本文はコンテキスト生成用の先読み。`investigation.md` への逐語転記は `backlog-investigator` が Step A で別途取得する。重複取得は意図的な設計のため許容する）。
   - **取得に失敗した場合（MCP サーバーダウン等）**: 「Backlog MCP が応答しません。課題本文（タイトル・詳細）をここに貼り付けてください」とユーザーに依頼し、貼り付けられた内容を課題タイトル・本文として扱って以降の手順を続行する（`backlog-investigator.md` の MCP フォールバックと同じ会話パターン）。
2. `sf-context-loader` を **knowledge-only モード**で起動する:
   ```
   task_description: 「{課題タイトル + 本文の最初の200字}」
   project_dir: {プロジェクトルートパス}
   focus_hints: ["knowledge-only"]
   ```
   結果を `{knowledge_context}` として保持する。
3. `sf-context-loader` を**通常モード**で起動する（2 の完了後に逐次実行。二段ネスト・並列多重発行を避けるため同一メッセージでは発行しない）:
   ```
   task_description: 「{課題タイトル + 本文の最初の200字}」
   project_dir: {プロジェクトルートパス}
   focus_hints: ["{課題タイトル・本文から抽出した F-番号・機能名・オブジェクト名等のキーワード}"]
   ```
   結果を `{design_context}` として保持する。

**Step B: backlog-investigator 起動**

`backlog-investigator` エージェントを起動する:

```
課題ID: {issueID}
プロジェクトルート: {カレントディレクトリ}
出力先: docs/logs/{issueID}/investigation.md
知識層コンテキスト: {knowledge_context}
設計層コンテキスト: {design_context}
```

エージェントが `investigation.md` を保存したら、内容をユーザに提示する。また、末尾の「[デプロイ適否の判定](#デプロイ適否の判定phase-1-終了時に適用)」セクションを参照してデプロイ可否を確定する。

> **investigator の確認ゲート**: investigator は課題本文/コメント中の全URL・添付・スクショ・名指しレコードを確認（または取得不能をユーザーに委ねて承認を得る）するまで原因分析に進まない。この確認が完了するまで Step B（コード調査）以降には遷移しない。

> **Phase 1 完了時のフロントマター記録（必須・スキップ不可）**: `{issue_type}` 確定後（上記「種別変数の管理」参照）、/compact 跨ぎ復元用に `issue_type` / `light_mode` を investigation.md フロントマターへ書き込む(詳細は [_README.md §compact 跨ぎ復元プロトコル](../templates/backlog/_README.md) を参照):
> ```bash
> python - <<'PYEOF'
> import pathlib, re
> invest = pathlib.Path('docs/logs/{issueID}/investigation.md')
> text = invest.read_text(encoding='utf-8') if invest.exists() else ''
> keys = {'issue_type': '{issue_type}', 'light_mode': '{light_mode}'}
> if text.startswith('---'):
>     end = text.index('---', 3)
>     front = text[3:end]
>     body = text[end+3:]
>     for k, v in keys.items():
>         if re.search(rf'^{k}:', front, re.MULTILINE):
>             front = re.sub(rf'^{k}:.*$', f'{k}: {v}', front, flags=re.MULTILINE)
>         else:
>             front = front.rstrip('\n') + f'\n{k}: {v}\n'
>     invest.write_text(f'---\n{front}---{body}', encoding='utf-8')
> else:
>     fm = '\n'.join(f'{k}: {v}' for k, v in keys.items())
>     invest.write_text(f'---\n{fm}\n---\n\n{text}', encoding='utf-8')
> print('[OK] investigation.md issue_type/light_mode 記録完了')
> PYEOF
> ```

> **次に進む条件**: ユーザが調査レポートを確認した後 — [_README.md §Phase 末尾の確認プロトコル](../templates/backlog/_README.md) に従い、サマリー・確認事項をテキストで提示してやり取りを経て進む
> - `{issue_type}` = `バグ` の場合: 「Phase 1.6 に進んでよろしいですか？」と確認してから Phase 1.6 へ
> - `{issue_type}` = `問い合わせ` の場合: 「Phase 2（回答ドラフト生成）に進んでよろしいですか？」と確認してから Phase 1.6・1.5 をスキップして Phase 2 へ直接進む
> - `{issue_type}` = `追加要望` / `その他` の場合: 「Phase 1.5 に進んでよろしいですか？」と確認してから Phase 1.5 へ
> - **バグの場合（自明バグ除く）**: Phase 1 サマリーは「最有力仮説は X（要 Sandbox 検証）」表現に留める。「根本原因は X と確定」「間違いない」等の断定は Phase 1.6 完了後まで禁止
>
> **Phase 1 典型例（該当時のみ・0件が原則）**: 「業務要件 Q1 への仮説が正しいか」「データ X の例外時挙動を業務側に確認したい」
> **含めてはいけない例**: 実装詳細（命名・マップキー設計）/ テスト段取り（テストユーザ・データ準備）/ 派生事項（他ファイルの同種バグ）/ スコープ自明事項
> **ただし例外（必ず含める）**: 根本原因の共有元を経由して**報告症状そのものが別入口でも再現する**「兄弟入口」は派生事項ではなく影響範囲（区分 S）。Phase 1 サマリーで必ずユーザーに提示する（backlog-investigator.md Step C-2 参照）。

> **Q 回答の書き戻し（必須・スキップ不可）**: 上記のやり取りでユーザーが investigation.md「業務要件の不確実点」の Q（Q1・Q2…）に回答した場合、次の Phase へ進む前に Edit ツールで該当 Q の直下に `- 回答: {ユーザーの回答を1〜2行で要約}` を追記する。未回答のまま保留された Q には追記しない。既に `- 回答:` 行がある Q には再追記しない（重複防止）。**目的**: `backlog-planner` Step A-1 が「回答済み Q」と「未回答 Q」を区別できるようにするため。回答欄がないと、Phase 1 で解決済みの業務要件の不確実点を planner が「未確認」とみなし approach-plan.md で再度 Q として起票してしまう（二重生成）。

---

### Phase 1.6: Sandbox 仮説検証（バグ系のみ）

> **実行条件**: `{issue_type}` = `バグ` の場合のみ実行する。追加要望・その他はこのセクションをスキップして Phase 1.5 へ進む。スキップ時は「追加要望・その他のため Sandbox 仮説検証は不要」と 1 行通知する。問い合わせは Phase 1 完了時点で Phase 2 へ直接進むため通常ここに到達しない（誤って到達した場合も本セクションをスキップし Phase 2 へ進む）。

`{issue_type}` = `バグ` の場合、詳細手順（エージェント起動パラメータ・完了後の分岐・Phase 1 再入方法）を Read する: [.claude/templates/backlog/phase1-6-sandbox-verification.md](../templates/backlog/phase1-6-sandbox-verification.md)

---

### Phase 1.5: xlsx フォルダの確定（選択式・設定済みなら自動継続）

> **種別が「問い合わせ」の場合**: Phase 1 完了時点で Phase 2 へ直接進むため本フェーズは実行しない（回答ドラフトは xlsx 化しない・`{xlsx_folder}` は使用しない）。誤って到達した場合も本セクションをスキップし Phase 2 へ進む。
>
> **`--light` フラグが設定されている場合**: xlsx は非対応。Phase 1.5 をスキップし `{xlsx_folder}` = null・`{evidence_dir}` = `docs/logs/{issueID}/evidence` を設定する（`.backlog_config.yml` の `xlsx_default` は変更しない）。（理由: light は `approach-plan.md` を生成しないため Phase 3 の `create_records.py --approach-plan` が必ず失敗する）  
> その後、`xlsx-setup.md`「作成しない」の場合の手順に従い `evidence_dir` を investigation.md フロントマターに書き戻す（`/test` 起動時の保存先解決に必要）。

**Step 1.5.0: config デフォルト読込**（`--light` 時は実行しない）

`docs/.backlog_config.yml` の `xlsx_default` を確認する:

```bash
python -c "import yaml,pathlib; p=pathlib.Path('docs/.backlog_config.yml'); d=yaml.safe_load(p.read_text(encoding='utf-8')) if p.exists() else {}; v=d.get('xlsx_default',''); print(v)"
```

- **出力が `True` または `False` かつ `--reconfigure` 未指定**: 下記 AskUserQuestion をスキップし、出力値を `{xlsx_create}`（作成する/作成しない）に採用する。チャットに1行通知する:
  > xlsx: {作成する|作成しない}（プロジェクト設定 `xlsx_default` により自動継続。再選択は `--reconfigure`）
  そのまま「`{xlsx_create}` に応じた分岐」へ進む（config への再書き込みは不要）。
- **出力が空・`--reconfigure` 指定時・または `True`/`False` 以外の値**: 下記 AskUserQuestion を実行する。値が `True`/`False`/空 のいずれでもない場合は実行前に「`xlsx_default` の値が不正のため再選択します」と1行通知する。

AskUserQuestion で作成有無を選択する:
- label: `作成する`、description: "対応記録.xlsx を生成する（推奨）"
- label: `作成しない`、description: "xlsx 生成をスキップして作業を続行する"

選択結果を `{xlsx_create}` に格納し、`docs/.backlog_config.yml` の `xlsx_default` に永続化する（既存エントリを保持してマージ。次回以降のデフォルト値になる）:

```bash
python -c "import yaml, pathlib; p = pathlib.Path('docs/.backlog_config.yml'); d = yaml.safe_load(p.read_text(encoding='utf-8')) if p.exists() else {}; d['xlsx_default'] = {選択結果が「作成する」なら True、「作成しない」なら False}; p.write_text(yaml.dump(d, allow_unicode=True), encoding='utf-8')"
```

> **[共通ルール①]** 各フェーズの `timeline` 呼び出しで判断・選択の根拠がある場合は `--reason "{根拠}"` を追加する（記録の追跡性を高めるため積極的に使用すること）。
>
> **[共通ルール②]** xlsx への書き込みは Phase 3 末尾の一括生成（create_records.py）以降に `update_records.py cell` を使用する。Phase 4-6 の各エージェントが timeline と cell 両方の xlsx 追記を担う。

**`{xlsx_create}` = 作成する の場合**: 保存先フォルダパスを確定して `{xlsx_folder}` を設定する（xlsx ファイルの生成は Phase 3 末尾で実施。この時点では生成しない）。

> フォルダパス確定手順: [.claude/templates/backlog/xlsx-setup.md](../templates/backlog/xlsx-setup.md)

**`{xlsx_create}` = 作成しない の場合**: `{xlsx_folder}` = null、`{evidence_dir}` = `docs/logs/{issueID}/evidence` に設定する。Phase 2 以降の全 xlsx 更新ブロックはスキップする。`xlsx-setup.md`「作成しない」の場合の手順に従い `evidence_dir` を investigation.md フロントマターに書き戻す。

---

### Phase 2: 対応方針の確定（backlog-planner Phase A）

> **`--light` フラグが設定されている場合**: 種別が「問い合わせ」の場合は本分岐を適用しない（下記「種別が「問い合わせ」の場合」節を優先し、回答ドラフトを生成して Phase 2 で完了する）。それ以外の種別では Phase 2 をスキップして Phase 3（実装方針）へ直接進む。対応方針は「最小修正・既存パターン踏襲」固定とし、`approach-plan.md` を作成しない。Phase 3 開始時にその旨を 1 行通知する。
>
> **xlsx 共通規則**: Phase 2 以降の全 xlsx 更新ブロックは `{xlsx_folder}` が null（Phase 1.5 で「作成しない」を選択）の場合スキップする。

#### 種別が「問い合わせ」の場合（回答ドラフト・Phase A/B とは別モード）

`{issue_type}` = `問い合わせ` の場合、詳細手順（`backlog-planner` 起動パラメータ・回答提示手順・完了報告文言）を Read する: [.claude/templates/backlog/phase2-inquiry-mode.md](../templates/backlog/phase2-inquiry-mode.md)

---

`backlog-planner` エージェントを起動する（Phase A: 対応方針）:

```
モード: 対応方針（Phase A）
調査レポート: docs/logs/{issueID}/investigation.md
仮説検証レポート: docs/logs/{issueID}/hypothesis-verification.md（バグ系のみ。ファイルが存在する場合）
出力先: docs/logs/{issueID}/approach-plan.md
種別: {issue_type}
default_stance: {バグ="最小修正＋既存への影響ゼロを最優先" / 追加要望="既存類似実装のパターンに合わせる" / その他="スコープ規模・本番影響・準備期間を確認のうえ方針を提示し、ユーザに選択させる"}
```

エージェントが `approach-plan.md` を保存したら提示する。  
ユーザが採用方針を確定するまで Phase 3 に進まない。

> **対応方針のタイムライン行は Phase 3 末尾の `create_records.py` が自動生成する**（この時点では xlsx 未生成のため追記しない）。

> **次に進む条件**: ユーザが対応方針を確認した後 — [_README.md §Phase 末尾の確認プロトコル](../templates/backlog/_README.md) に従い、サマリー・確認事項・「Phase 3 に進んでよろしいですか？」をテキストで提示してやり取りを経て進む
>
> **Phase 2 典型例（該当時のみ・0件が原則）**: 「過去 X 件のデータで項目 Y が null のレコードを許容するか / 一括補完するか」「未確定の業務ルール Q1 の回答が方針の前提と合っているか」「スコープに含めるべきか別 Backlog で起票するか」
> **含めてはいけない例**: 「テストクラスを追加するか」（実装側で判断）「採用案を確定してください」（次へ確認で兼ねる）「命名はこれで良いか」（実装側で判断）

---

### Phase 3: 実装方針の確定（backlog-planner Phase B）

`backlog-planner` エージェントを起動する（Phase B: 実装方針）:

```
モード: 実装方針（Phase B）
採用方針: {承認された案名}
調査レポート: docs/logs/{issueID}/investigation.md
出力先: docs/logs/{issueID}/implementation-plan.md
種別: {issue_type}
default_stance: {Phase 2 と同じ値を引き継ぐ}
```

> **`--light` の場合**: 採用方針 = 「最小修正・既存パターン踏襲」固定（Phase 2 をスキップしているため `{承認された案名}` は存在しない）。

エージェントが `implementation-plan.md` を保存したら提示する。  
全判断ポイントが確定するまで Phase 4 に進まない。

**`option-validator-blind` 採用時のみ（本コマンドが直接実行）**: implementation-plan.md の「Step 0b オプション判定結果」で `option-validator-blind` が採用されている場合、以下を実行する（二段ネストを避けるため backlog-planner ではなく本コマンドが直接行う）:
1. investigation.md の「課題原文」セクションから課題本文の全文・全コメントのテキストを取得する（既に disk 上にあるため Read で取得。MCP 再取得は不要）。
2. approach-plan.md の「採用方針:」行の1行のみを取得する（それ以外の内容は一切含めない。blind 性維持のため）。
3. `.claude/templates/backlog/blind-prompts/validator.md` の Task prompt テンプレートを Read し、プレースホルダー（`{issueID}` `{課題本文の全文}` `{全コメントのテキスト}` `{investigation.md のテキスト}` `{採用方針テキスト}`）を実行時の値で置換して `backlog-blind-validator` を起動する。
4. 返却されたテキストを `## blind 実装案レビュー` セクションとして implementation-plan.md の末尾に追記する。

**xlsx 一括生成（対応記録 + エビデンス）**（`{xlsx_folder}` が設定されている場合のみ）

> **実行主体**: planner エージェントは bash を持たないため、planner 復帰後に **本コマンド（ハーネス）が直接** 以下の python スクリプトを実行する。planner には委譲しない。

全 MD ファイルが揃ったこのタイミングで xlsx を一括生成する:

```bash
python "$(pwd -W)/scripts/python/backlog-xlsx/create_records.py" \
  --folder "{xlsx_folder}" --issue-id "{issueID}" \
  --investigation docs/logs/{issueID}/investigation.md \
  --approach-plan docs/logs/{issueID}/approach-plan.md
```

> **エビデンス.xlsx の扱い**: 上記 create_records.py は対応記録.xlsx のみ生成する。エビデンス.xlsx は Phase 4 完了後に `/test {issueID}` が generate_evidence_xlsx.py で生成するため、このタイミングでは実行しない。

**スクリプト失敗時の対処**（エラー出力あり / 終了コード 非0）:
1. エラー内容をユーザに提示する
2. AskUserQuestion で対処方法を選択する:
   - label: `xlsx なしで続行`、description: "xlsx 生成を断念して Phase 3.5 へ進む"
   - label: `修正して再試行`、description: "エラー原因を修正してスクリプトを再実行する"
   - label: `中止`、description: "コマンドを終了する"
3. 「xlsx なしで続行」が選ばれた場合: `{xlsx_folder}` = null として Phase 3.5 へ進む。create_records.py が途中成功してファイルが残っている可能性があるため、`{xlsx_folder}` 配下に生成済み xlsx（`{issueID}_対応記録.xlsx`）が存在する場合は削除する（破損ファイルが後続 Phase で誤参照されるのを防ぐため。エビデンス.xlsx はこの Phase では生成しないため削除対象外）
4. この対処結果（選ばれた対応・エラー概要）は会話内で保持しておく（Phase 4 以降の xlsx スクリプト失敗ゲートで、同種のエラーが再発した際に文脈提示するために使う。新たな変数管理・永続化は不要）。

生成完了後にファイルパスをユーザに提示する（`{xlsx_folder}` = null の場合はスキップ）:
- `{xlsx_folder}/{issueID}_対応記録.xlsx`

（エビデンス.xlsx は Phase 4 完了後に `/test {issueID}` が生成する）

> **次に進む条件**: 全判断ポイントをユーザが確認・確定した後 — [_README.md §Phase 末尾の確認プロトコル](../templates/backlog/_README.md) に従い、サマリー・確認事項・「Phase 3.5 に進んでよろしいですか？」をテキストで提示してやり取りを経て進む
>
> **Phase 3 典型例（該当時のみ・0件が原則）**: 「類似実装と異なるパターンを採用した判断ポイントの整合性」「SOQL の LIMIT・権限制御が全ユーザ種別で正しいか」

---

### Phase 3.5: 実装前検証（backlog-validator）

> **`--light` フラグが設定されている場合**: Step A（regression-guard）・Step C（backlog-validator）はスキップして Phase 4（実装）へ直接進む。**ただし Step B（Before エビデンス自動採取）はスキップしない**。UI 影響判定（Step B 冒頭の判定基準）に該当する場合は light でも実行してから Phase 4 へ進む（Before 撮影は実装前限定・不可逆のため。Phase 1.6 の Sandbox 仮説検証と同じ扱い）。

> **サブエージェントの二段ネストを避ける**: `backlog-validator` はサブエージェントを起動しない leaf agent。Phase 3.5 で必要な `regression-guard`（リグレッション確認）と `ui-evidence-runner`（Before エビデンス自動撮影）は、本コマンド（メインスレッド）が validator の起動前に直接 Task 起動し、結果を validator へ渡す。

**Step A: regression-guard 起動（本コマンドが直接実行）**

`regression-guard` エージェントを起動する:

```
現課題ID: {issueID}
プロジェクトルート: {プロジェクトルートパス}
```

返却結果（依存先・テストカバレッジ・影響再走査・過去修正履歴）を `{regression_result}` として保持する。

**Step B: Before エビデンス自動採取（UI 影響ありの場合のみ・本コマンドが直接実行）**

`docs/logs/{issueID}/implementation-plan.md` の「変更対象ファイル」を確認し、LWC（`.html`/`.js`）・Aura（`.cmp`）・VF（`.page`）が含まれる、または実装方針に「画面・ラベル・文言・表示・UI」の語が含まれる場合のみ、[option-evidence-check.md](../templates/backlog/options/option-evidence-check.md) の B・C 手順を実行する（Sandbox alias 解決 → `ui-evidence-runner` を `mode: before-capture` で Task 起動 → Before データ値採取）。該当しない場合は本 Step 全体をスキップし `{evidence_result}` = 「該当なし（非UI変更）」とする。

> **権限・FLS・レイアウト・RecordType・共有ルール変更の場合**: 本 Step（Before エビデンス自動採取）の対象外（`{evidence_result}` = 「該当なし（非UI変更）」）でも証跡取得が免除されるわけではない。`backlog-tester`（Phase 5）は dry-run のみでは完了と判定せず、Phase 6（`backlog-releaser`）の完了チェックリストで異なる権限経路の実ユーザーによる Login As 確認を必須とする（CLAUDE.md 「権限系の『できない／直った』の完了判定」参照）。

**Step C: backlog-validator 起動**

`backlog-validator` エージェントを起動する:

```
実装計画: docs/logs/{issueID}/implementation-plan.md
調査レポート: docs/logs/{issueID}/investigation.md
regression-guard確認結果: {regression_result}
Beforeエビデンス採取結果: {evidence_result}
```

エージェントが `validation-report.md` を保存したら内容をユーザに提示する。Phase 3 への戻りが提案された場合は Phase 3 に戻って実装方針を修正してから Phase 3.5 を再実施する（Step A・B も再実行する）。**Phase 3 戻りは最大 2 回まで・セッション跨ぎを含めて通算カウント**（カウントは discussion-log.md の改版履歴から復元する。詳細は `test-fail-routing.md` §ループ上限 を参照）。3 回目以降の戻り提案が出た場合は自動進行を停止し、「実装方針の見直しが繰り返されています。一度オフラインで方針再検討の打ち合わせが必要かもしれません。このまま Phase 3 に戻りますか？（続行 / 中止）」とテキストで確認する。「続行」ならば Phase 3 に戻る。「中止」ならばコマンドを終了する。

**xlsx 更新（実装前検証）**（`{xlsx_folder}` が設定されている場合のみ）

```bash
python "$(pwd -W)/scripts/python/backlog-xlsx/update_records.py" \
  --folder "{xlsx_folder}" --issue-id "{issueID}" \
  timeline --phase "実装前検証" \
  --content "実装前検証完了: {ドライラン/テスト/影響範囲/クロスレビュー/エビデンスの結果サマリーを1行で}"
```

> **次に進む条件**: 全検証項目 OK をユーザが確認した後 — [_README.md §Phase 末尾の確認プロトコル](../templates/backlog/_README.md) に従い、サマリー・確認事項・「Phase 4 に進んでよろしいですか？ Phase 3 に戻る必要がありますか？」をテキストで提示してやり取りを経て進む
>
> **Phase 3.5 典型例（該当時のみ・0件が原則）**: 「新規発見した影響箇所への対処方針」「Step 1〜3 NG への対処方針」（Before エビデンスは自動採取のためブロッカーにならない）

---

### Phase 4: 実装（backlog-implementer）

`backlog-implementer` エージェントを起動する:

```
実装計画: docs/logs/{issueID}/implementation-plan.md
調査レポート: docs/logs/{issueID}/investigation.md
実装前検証結果: docs/logs/{issueID}/validation-report.md
xlsx_folder: {xlsx_folder}
```

> `{xlsx_folder}` が null（Phase 1.5 で「作成しない」）の場合は xlsx_folder 行を省略してエージェントに渡す。

エージェントが Before/After を提示したらユーザに確認する。変更ファイルが 5 件を超える場合は以下の基準で提示を分ける:
- **詳細提示**: ロジック変更・public インターフェース変更・Apex/LWC/Flow のコード変更
- **一覧省略可**: 設定ファイル・メタデータ（field-meta.xml / layout-meta.xml 等）・テストクラス以外の補助ファイル

**xlsx 一括記入（対応内容）**（`{xlsx_folder}` が設定されている場合のみ）

> **実行主体**: implementer エージェントが `implementation-summary.md` を書き出した後、**本コマンド（ハーネス）が直接** 以下のスクリプトを実行する。create_records.py（Phase 3）と同型。

```bash
python "$(pwd -W)/scripts/python/backlog-xlsx/update_records.py" \
  --folder "{xlsx_folder}" --issue-id "{issueID}" \
  content-from-md --summary docs/logs/{issueID}/implementation-summary.md --force
```

> スキップ判定: [.claude/templates/backlog/_partials/xlsx-skip-guard.md](../templates/backlog/_partials/xlsx-skip-guard.md) に従う（`{xlsx_folder}` null = 正規スキップ）。

スクリプト失敗時の対処（エラー出力あり / 終了コード 非0）:
1. エラー内容をユーザに提示する
2. **Phase 3 の xlsx スクリプト失敗ゲートが既にこのセッションで発生している場合**、そのときの対処結果を一言添える（例:「Phase3でも同種のエラーが発生し『修正して再試行』を選択済みです」）。判断の自動適用ではなく、ユーザが状況を思い出しやすくする文脈提示のみ。該当がなければこの手順は省略する。
3. テキストで選択を確認する:「xlsx なしで続行」（xlsx_folder = null に変更して続行）/「修正して再試行」/「中止」

**xlsx 充足確認（verify）**（`{xlsx_folder}` が設定されている場合のみ）

```bash
python "$(pwd -W)/scripts/python/backlog-xlsx/update_records.py" \
  --folder "{xlsx_folder}" --issue-id "{issueID}" \
  verify --stage pre-release
```

verify 結果が **NG（exit 2）** の場合: 未充足枠を提示する。**Phase 3 または直前の xlsx 一括記入ゲートが既にこのセッションで発生している場合**は、その経緯を一言添えてから（判断の自動適用ではなく文脈提示のみ）、テキストで対処を確認する:
- 「自動補完」: `content-from-md` を再実行する（implementation-summary.md が存在する場合のみ）
- 「手動修正後続行」: ユーザが xlsx を手動で修正してから続行
- 「xlsx なしで続行」: `{xlsx_folder}` = null として Phase 5 へ進む

> **次に進む条件**: ユーザが実装内容を確認した後 — [_README.md §Phase 末尾の確認プロトコル](../templates/backlog/_README.md) に従い、サマリー・確認事項・「Phase 5 に進んでよろしいですか？」をテキストで提示してやり取りを経て進む
>
> **Phase 4 典型例（該当時のみ・0件が原則）**: 「実装中に発見した計画との不整合の影響評価」「implementation-plan.md への改版履歴追記が必要なら内容の確認」

---

### Phase 5: スモーク確認（backlog-tester）

> **目的**: dry-run デプロイでコンパイル可能か・Apex テストが通るかを永続化せずに検証する。証跡採取・エビデンス xlsx 生成・Sandbox への本デプロイは行わない。PASS で Phase 6 へ進む。Phase 5 の dry-run PASS 記録は Phase 6 の dry-run 省略判定に使われる（force-app 無変更なら Phase 6 は dry-run をスキップして本デプロイへ直行）。

`backlog-tester` エージェントを起動する:

```
調査レポート: docs/logs/{issueID}/investigation.md
実装計画: docs/logs/{issueID}/implementation-plan.md
種別: {issue_type}
xlsx_folder: {xlsx_folder}
```

> `{xlsx_folder}` が null（Phase 1.5 で「作成しない」）の場合は xlsx_folder 行を省略してエージェントに渡す。

スモーク確認の結果を報告する:
- **PASS** → Phase 6 へ進む候補（下記「次に進む条件」の明示承認を経て進む。自動進行しない）
- **条件付きPASS（NoTestRun フォールバック発生）** → 自動で Phase 6 に進めない。dry-run はコンパイル成功だが対応テストクラス未整備でカバレッジ未検証。ユーザーに「テスト追加（Phase 4 戻り）」または「カバレッジ未検証を承知で本デプロイ明示承認」を求めてから進む
- **FAIL** → Phase 4 に差し戻す（明らかな壊れを修正してから再度スモーク確認）

> **次に進む条件**: PASS の場合、[_README.md §Phase 末尾の確認プロトコル](../templates/backlog/_README.md) に従い、サマリー・確認事項・「Phase 6（Sandbox リリース）に進んでよろしいですか？」をテキストで提示し、明示承認を得てから進む（Phase 5→6 は軽量承認の適用除外ゲート。「異議がなければ次へ」への緩和は行わない）
>
> **Phase 5 典型例（該当時のみ・0件が原則）**: 「dry-run で Apex コンパイルエラーが出る・テストが失敗する」→ Phase 4 差し戻し

---

### Phase 6: Sandbox リリース・お客様確認・完了（backlog-releaser）

> **dry-run 重複排除**: Phase 5 で dry-run PASS 済みかつ force-app に変更がない場合、Phase 6 は dry-run をスキップして本デプロイへ直行する。Phase 5 以降にコード変更がある場合のみ再 dry-run を実行する。

> **デプロイ失敗・問題発生時**: `backlog-releaser` がデプロイ失敗またはリリース後動作確認で問題を検知した場合、原因の種別（デプロイ失敗 → Phase 5 / 実装ロジック起因の挙動不良 → Phase 4 / 切り分け困難 → ユーザー確認）に応じて差し戻し先を判定し、`docs/logs/{issueID}/release-issue.md` に差し戻し理由・現象・ログ・差し戻し先を記録した上で該当 Phase への差し戻しを提案する（`backlog-releaser.md` §2a. Sandbox の場合 参照）。ユーザーは `/backlog` を再実行し「途中フェーズから再開」で対応する。

`backlog-releaser` エージェントを起動する:

```
実装計画: docs/logs/{issueID}/implementation-plan.md
xlsx_folder: {xlsx_folder}
```

> `{xlsx_folder}` が null（Phase 1.5 で「作成しない」）の場合は xlsx_folder 行を省略してエージェントに渡す。

**お客様確認サインの取得**

> 種別別ルール・xlsx 更新: [.claude/templates/backlog/customer-signoff.md](../templates/backlog/customer-signoff.md)
> ファイルが存在しない場合は「種別 {issue_type} のお客様確認内容は何ですか？」とテキストで確認し、ユーザの指示に従ってサインを取得する。

> **「完了」の意味範囲**: ここで書き込む「完了」は `backlog-releaser` 内部の完了チェックリスト（デプロイ成功確認・種別別エビデンス取得。権限・FLS等は Login As 確認を含む。`backlog-releaser.md` §2a. Sandbox の場合 参照）を通過した上での、Sandbox実装・動作確認までの完了を意味する（Phase 0 で確認したスコープ通り）。お客様確認サインはブロッキングゲートではなく完了報告の「残作業」チェックボックスで管理する（未取得でも本ステータス更新をブロックしない。取得報告後に xlsx タイムライン「お客様確認」欄へ別途追記する）。`/test`（次アクション案内）による網羅的テスト・証跡採取・エビデンス Excel 生成は追加の構造化証跡であり、本ステータスの前提条件ではない。

**ステータスを「完了」に更新**（`{xlsx_folder}` が設定されている場合のみ）

> **実行主体**: releaser の xlsx 更新はハーネスが直接実行する（Phase 3 と同型）。

```bash
python "$(pwd -W)/scripts/python/backlog-xlsx/update_records.py" \
  --folder "{xlsx_folder}" --issue-id "{issueID}" \
  cell --sheet "課題と対応方針" --label "ステータス" --col 2 --value "完了" --force
```

> スキップ判定: [.claude/templates/backlog/_partials/xlsx-skip-guard.md](../templates/backlog/_partials/xlsx-skip-guard.md) に従う。

**xlsx 最終充足確認（verify final）**（`{xlsx_folder}` が設定されている場合のみ）

```bash
python "$(pwd -W)/scripts/python/backlog-xlsx/update_records.py" \
  --folder "{xlsx_folder}" --issue-id "{issueID}" \
  verify --stage final --status-expected 完了
```

verify 結果が **NG（exit 2）** の場合: 完了報告に「⚠ xlsx 未充足あり（詳細は上記 verify 出力を参照）」を付記する（リリース済みのためブロックしない・警告のみ）。

完了報告を行う。

> **管理画面操作手順書（2b）がある場合**: `docs/logs/{issueID}/manual-operation-steps.md` が存在する場合、完了報告に続けて [manual-steps-todo-handoff.md](../templates/common/manual-steps-todo-handoff.md) の仕様に従い引き渡しを行う（**手順書全文を一度に貼らない**）。同ファイルを Read し、「操作ステップ」内の番号付き各項目を TodoWrite でタスク化し、先頭の未完了ステップのみ内容を提示して「実行結果を教えてください」と添える。ユーザーの実行報告を受けたら該当 Todo を completed にし次のステップへ進む。エラー・質問ならその場で回答し Todo は進めない。全 Todo 完了後、「確認事項」セクションを一度に提示する。

> **📋 本番リリース後 TODO**: 本フローは Sandbox リリースまで。**本番リリースは人間が手動で実施する**ため、本番デプロイ後は `/release {issueID}` を起動（または継続）し、デプロイ完了を報告すること。`/release` Phase 7 が decisions.md「リリース予定日 / 担当」欄・changelog.md への記録を代行する（対応記録.xlsx にはリリース実施記録用のシートは存在しない）。

> **Phase 6 完了後の次アクション（テスト・証跡採取）**: 完了報告の末尾に、次の1行を **`{issueID}` を実際の課題IDに展開した状態** でコードブロックとして提示し、そのままコピペで別セッションに貼れるようにする。併せて1行案内する:「上記を **別セッション（クリーンな会話）で起動** してください。網羅的テスト・証跡採取・エビデンス Excel 生成を実施します（`/test` はデプロイ済み Sandbox 前提。clean session 分離の設計意図により自動起動はしません）。」
>
> ```
> /test {issueID}
> ```

---

## §中断時の知見還流（部分還流）

> フローが Phase 6 に到達しない場合（クライアント都合中断・手動対応切替・リリース省略等）に `docs/knowledge/` への構造化還流が失われることを防ぐ。

### トリガー

main スレッドが「この課題は Phase 6 に到達しない」と判断したとき。具体的なシグナル:

- 「客都合で中断」「手動対応に切り替える」「リリースは省略 / 別途」「この課題はここで止める」等のユーザー明示
- Phase 4 以降完了後に「次フェーズには進まない」旨が確定した場合

### 前提条件

`docs/logs/{issueID}/` に approach-plan.md / investigation.md 等が 1 つ以上存在すること。Phase 1 完了前の超早期中断（成果物が何もない状態）はスキップする。

### 実行手順（deploy 系は一切行わない）

> 各 Step の詳細手順は `backlog-releaser.md` の対応節を参照して実行する（ロジックのコピーではなく参照）。追記フォーマットの定義は [../templates/common/knowledge-reflux-formats.md](../templates/common/knowledge-reflux-formats.md) に集約されている（単一ソース）。

1. **decisions.md** — Phase 5 まで到達済みか確認する。`option-knowledge-extraction`（Phase 5 always-run）が実行済みなら `docs/decisions.md` に既にエントリがあるため**重複追記しない**。Phase 5 未到達の場合のみ `backlog-releaser.md` §ドキュメント更新 の手順で `docs/logs/{issueID}/approach-plan.md` / `implementation-plan.md` を読んで追記する（前工程ファイルなしフォールバック内蔵）。

2. **pitfalls.md** — `backlog-releaser.md` §知見の自動還流 の手順で実行する:
   - `docs/logs/{issueID}/discussion-log.md` から落とし穴パターンを抽出
   - ユーザー確認後に `docs/knowledge/pitfalls.md` へ先頭挿入（類似度 dedup 適用）
   - discussion-log.md が存在しない場合はフォールバック（approach-plan.md + test-report.md を Grep）

3. **cases/{issueKey}.md** — `backlog-releaser.md` §cases/{issueKey}.md 詳細ファイル生成 の手順で実行する:
   - `docs/knowledge/cases/{issueKey}.md` が既存ならスキップ
   - `docs/logs/{issueID}/` 内の現存ファイルから生成（前工程ファイルなしフォールバック内蔵）

4. **case-index.md** — `backlog-releaser.md` §case-index.md への自動追記 の手順で実行する:
   - パスは **`docs/knowledge/case-index.md`**（`cases/` 配下ではない）
   - 工数列は `-` 固定で追記する
   - 既存行ありならスキップ（dup 防止）

**実行しないもの**: deploy 系（Step 1・2a/2b）・お客様確認サイン取得（Step 3.7）・xlsx リリース記録の全量（Step 3.5②タイムライン等）・**全社共有ナレッジ登録（Step 3.9。Phase 6 正常完了時限定のフックのため中断パスでは実行しない）**・完了報告（Step 4）。

**ステータスを「中断中」に更新**（`{xlsx_folder}` が設定されている場合のみ）

> Phase 6 未完了のまま終了するため、ステータスが「対応中」のまま放置されないよう更新する。

```bash
python "$(pwd -W)/scripts/python/backlog-xlsx/update_records.py" \
  --folder "{xlsx_folder}" --issue-id "{issueID}" \
  cell --sheet "課題と対応方針" --label "ステータス" --col 2 --value "中断中" --force
```

> スキップ判定: [.claude/templates/backlog/_partials/xlsx-skip-guard.md](../templates/backlog/_partials/xlsx-skip-guard.md) に従う（null = 正規スキップ）。

### 終了報告

以下を一言テキストで報告して終了する:
```
中断時部分還流を実施しました（decisions / pitfalls / cases / case-index）。
リリース再開時は Phase 6 で既存エントリを確認し重複追記しないこと。
```

---

## デプロイ適否の判定（Phase 1 終了時に適用）

> 判定基準: [.claude/templates/backlog/deploy-skip-judgment.md](../templates/backlog/deploy-skip-judgment.md)

---

## 使用例

```
/backlog GF-327     # GF-327 の対応を実施
```
