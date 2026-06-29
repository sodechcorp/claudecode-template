---
description: "Backlog課題の調査・対応・記録を一気通貫で実施する。専門エージェントを順に起動し、各フェーズ完了後にユーザ確認を取りながら進める。/backlog [課題ID] で個別課題対応。"
---

# /backlog [課題ID]

**モード判定**: `--light` フラグが付いている場合（例: `/backlog GF-123 --light`）は軽微修正ショートカットで実行する（Phase 2 / Phase 3.5 をスキップ）。それ以外は通常フローを実行する。

**引数の解釈**: `$ARGUMENTS` の先頭トークン（`--` で始まらない最初の語）を `{issueID}` とし、`--light` 等のフラグは除外する（`GF-123 --light` も `--light GF-123` も issueID=`GF-123`）。

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

**各エージェントの内部構造**: 全エージェント（`backlog-repro-runner` を除く）は Step 0b でフェーズ用 `_index-phase{N}.md` を読んでオプション判定を行う（[à la carte 仕組み](../templates/backlog/_README.md)）。`backlog-repro-runner` は Phase 1.6（バグ系のみ）専用で Step 0b を持たず、à la carte 判定の対象外。`backlog-implementer` / `backlog-tester` / `backlog-releaser` / `backlog-validator` はさらに Step 0a で `sf-context-loader` を呼び出す。`backlog-investigator` / `backlog-planner` も Step 0a で `sf-context-loader` を呼び出すが、こちらは knowledge-only モード（ナレッジ層のみ先読み・設計層のフルロードはしない。docs/ の全件読みは investigator の Step C 等で別途実施）。Phase 1.5 は本コマンドが直接実行するためエージェントを起動せず、`_index-phase1-5.md` は存在しない（不要）。

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
>   1. **フェーズ別の型は `_README.md §サマリーの書き方` に従ってチャットに提示する**（Phase 1〜3 は課題の概要・前提再掲・最終挙動を含む人間向けの日本語。技術詳細は成果物に記録しチャットに並べない。その他のフェーズは3〜5行で本質・発見・引き渡し要点を要約）
>   2. 「特に確認したい点」を **0〜3 個**テキストで挙げる。確認事項がなければ「特に確認事項はありません」と明記し、無理やり挙げない。実装詳細・テスト段取り・派生事項・スコープ自明事項は確認質問に含めず本文に記載する（責務境界の詳細は各エージェント定義を参照）。**このルールは Phase 1〜6 すべてのフェーズ末に適用する**（investigator / planner / validator / implementer / tester / releaser の全エージェント共通）。**確認に含めるもの**: 業務判断・データ運用判断・スコープ判断（例: 過去データの扱い・業務ルール解釈・受入条件・適用範囲）。**確認に含めないもの**: 実装側で自明判断できる事項（例: テストクラス追加要否・命名・既存パターン踏襲・カバレッジ要件・grep して確認するだけの調査）と採用案の最終確定そのもの（Step 4 の「Phase N に進んでよろしいですか？」で兼ねる）
>   3. ユーザの自由テキスト応答を待つ（質問・修正依頼・承認 何でも可）
>   4. 議論が落ち着いたら「Phase N に進んでよろしいですか？」とテキストで明示確認
>   5. ユーザの承認テキスト（「OK」「進んで」等）を確認してから次フェーズへ進む。**質問・相槌（「ha」「うん」等）・別タスク依頼（「工数計算して」「見積もって」等）は承認ではない**。工数・見積依頼は `sf-effort-estimator` 委譲対象で承認を兼ねない（タスク完了後に承認プロトコルを再提示する）。確信できなければ進まず確認を出し直す（詳細は `_README.md §承認判定` 参照）。
> - 実装は Phase 4 以降。それ以前に実装コードを書くことは禁止。**Phase 3.5→4 の境界はファイル編集に入る唯一のゲートであり、特に厳格に明示承認を確認すること。**
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
> - **compact 後の再開について**: 長尺セッションで /compact が発生した後に /backlog を継続する場合は、必ず /backlog コマンドを再起動して Phase 0d 経由でコンテキストを復元すること。エージェント実行途中で /compact が発生した場合も同様。investigation.md のフロントマターに記録した `issue_type` / `xlsx_folder` / `evidence_dir` / `light_mode` を Phase 0d で読み込んで変数を再設定する
> - **種別変数 `{issue_type}` の管理**: Phase 1 完了時点で `investigation.md` の「種別」欄から `{issue_type}` = `バグ` / `追加要望` / `その他` を確定し、会話の最後まで保持する。Phase 2（デフォルトスタンス）・Phase 5（テスト観点）・Phase 6（お客様確認必須度）の分岐に使用する。種別欄が空欄・不明・記載なしの場合は「種別が判断できません。バグ / 追加要望 / その他 のどれに該当しますか？」とテキストで確認してから確定する
>
> **【環境・記録】**
> - **本番環境（isSandbox=false）への直接デプロイは絶対に行わない**
> - **xlsx 更新の共通ルール**: Phase 1.5 で定義される共通ルール①（timeline 呼び出しに `--reason "{根拠}"` を追加）と共通ルール②（xlsx シート書き込みは `update_records.py cell` を使用）は Phase 2 以降の全 timeline 更新で適用すること（詳細は「Phase 1.5: 対応記録ファイルの作成」セクションの共通ルール定義を参照）
> - **中断・手動切替・リリース省略でフローが Phase 6 に到達しない場合**: `## §中断時の知見還流（部分還流）` に従い知見を `docs/knowledge/` へ部分還流してから終了する（知見取りこぼし防止）

---

### Step 0: 共通 CRITICAL ルールの読込（必須・コマンド起動直後）

以下を **Read で全文読み込む**（CLAUDE.md にはスタブのみ・詳細は外出し先）:

1. Read `.claude/templates/common/verify-implementation-spec.md` — 実装裏付けルール。追加ルール記入欄まで読む
2. Read `.claude/templates/common/verify-source-attribution-spec.md` — 出典確認ルール。追加ルール記入欄まで読む

**理由**: 各フェーズ間で main thread がユーザーの自由テキスト質問に応答する。CLAUDE.md にはスタブのみ記載のため、詳細を読まないと「挙動を実コード確認せず断定」「出典を捏造」のリスクがある。backlog-* agent 側の Step 0c と同じ spec を読み、main thread と agent の知識を揃える。

---

### Phase 0: 作業フォルダの作成

**接続組織の確認**

```bash
sf config get target-org
```

```bash
sf org display --json
```

`isSandbox`・`Username`・`alias` を読み取り、以下をテキストで提示する:

```
現在の接続組織:
  alias: {alias名}
  種別: Sandbox / 本番
  Username: {user@example.com}

この組織に対して課題対応を進めてよろしいですか？
（Sandbox: 再現確認・テストにこの組織を使用します）
（本番: 参照のみ可能。データ確認の SELECT 文は都度許可を取ります）
別の組織に切り替えたい場合: sf config set target-org <alias>
```

ユーザーが確認の返答をするまで次に進まない。

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

**分割読込ルール**: investigation.md・approach-plan.md・implementation-plan.md・validation-report.md・test-report.md は、**冒頭 80 行 + 末尾 30 行**を読めば十分（ファイルが 110 行未満の場合は全文）。フルが必要なフェーズ（実装フェーズなど）はエージェント側で個別に全文 Read すること。

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

`backlog-investigator` エージェントを起動する:

```
課題ID: {issueID}
プロジェクトルート: {カレントディレクトリ}
出力先: docs/logs/{issueID}/investigation.md
```

エージェントが `investigation.md` を保存したら、内容をユーザに提示する。また、末尾の「[デプロイ適否の判定](#デプロイ適否の判定phase-1-終了時に適用)」セクションを参照してデプロイ可否を確定する。

> **investigator の確認ゲート**: investigator は課題本文/コメント中の全URL・添付・スクショ・名指しレコードを確認（または取得不能をユーザーに委ねて承認を得る）するまで原因分析に進まない。この確認が完了するまで Step B（コード調査）以降には遷移しない。

> **次に進む条件**: ユーザが調査レポートを確認した後 — `_README.md §Phase 末尾の確認プロトコル` に従い、サマリー・確認事項をテキストで提示してやり取りを経て進む
> - `{issue_type}` = `バグ` の場合: 「Phase 1.6 に進んでよろしいですか？」と確認してから Phase 1.6 へ
> - `{issue_type}` ≠ `バグ` の場合: 「Phase 1.5 に進んでよろしいですか？」と確認してから Phase 1.5 へ
> - **バグの場合（自明バグ除く）**: Phase 1 サマリーは「最有力仮説は X（要 Sandbox 検証）」表現に留める。「根本原因は X と確定」「間違いない」等の断定は Phase 1.6 完了後まで禁止
>
> **Phase 1 典型例**: 「業務要件 Q1 への仮説が正しいか」「データ X の例外時挙動を業務側に確認したい」
> **含めてはいけない例**: 実装詳細（命名・マップキー設計）/ テスト段取り（テストユーザ・データ準備）/ 派生事項（他ファイルの同種バグ）/ スコープ自明事項

---

### Phase 1.6: Sandbox 仮説検証（バグ系のみ）

> **実行条件**: `{issue_type}` = `バグ` の場合のみ実行する。追加要望・その他はこのセクションをスキップして Phase 1.5 へ進む。スキップ時は「追加要望・その他のため Sandbox 仮説検証は不要」と 1 行通知する。
>
> **`--light` でもスキップしない**: Phase 1.6 は原因診断の正しさを確認する検証ゲートであり、light がスキップする Phase 2（方針の選択）/ Phase 3.5（実装前検証）とは性質が異なる。未検証の仮説のまま軽微修正を当てるのが最も危険なため、バグ系は light でも通常どおり実行する。

`backlog-repro-runner` エージェントを起動する（実際に Sandbox 画面を操作してバグを再現する）:

```
課題ID: {issueID}
プロジェクトルート: {カレントディレクトリ}
調査レポート: docs/logs/{issueID}/investigation.md
出力先: docs/logs/{issueID}/hypothesis-verification.md
証跡保存先: docs/logs/{issueID}/repro
```

エージェントが `hypothesis-verification.md` を保存したら内容をユーザに提示する。

**Phase 1.6 完了後の分岐**:

| 結果 | 次の動作 |
|---|---|
| 再現仮説 ≥ 1 件 | Phase 1.5 へ（再現した仮説のみを Phase 2 で対象とする） |
| 再現仮説 = 0 件 | Phase 1 に戻り investigator が新仮説を追加生成して再度 Phase 1.6 を実施（**最大 2 回まで・セッション跨ぎを含めて通算カウント**。カウントは discussion-log.md の改版履歴から復元する。3 回目は「仮説が尽きている可能性があります。業務側との打ち合わせを推奨します」とユーザーに伝え、継続・中止の判断を求める） |
| 検証中に新事実発見 | investigator が `investigation.md` を更新して再度 Phase 1.6 を実施（ループカウントに含める） |
| 仮説が「検証不可」（Sandbox にメタデータ・データなし、環境依存等） | **「未検証のまま」として記録。確定表現禁止。** 原因がリポジトリ未回収のメタ要素（入力規則・カスタム設定等）に依存する場合は、`sf project retrieve` で org から取得するかユーザーに実在・内容を確認してから Phase 2 へ。「Sandbox にないから飛ばす ＝ 確定扱い」は禁止。 |

> **次に進む条件**: `_README.md §Phase 末尾の確認プロトコル` に従い、サマリー・「Phase 1.5 に進んでよろしいですか？」をテキストで提示してやり取りを経て進む

#### Phase 1 再入（仮説補充）の起動方法

「再現仮説 = 0 件」の場合、`backlog-investigator` を以下のプロンプトで再起動する（`検証結果:` キーが追加されることで investigator が再入モードで動作する）:

```
課題ID: {issueID}
プロジェクトルート: {カレントディレクトリ}
出力先: docs/logs/{issueID}/investigation.md
検証結果: docs/logs/{issueID}/hypothesis-verification.md
```

investigator は `検証結果:` キーの有無で再入モードを自動判定する。再入モードでは hypothesis-verification.md を Read して反証済み仮説を除外し、新視点の仮説のみを investigation.md に追記する（通常フロー Step A〜H は実行しない）。通算ループカウントはこのコマンド側（discussion-log.md の改版履歴）が管理する。

---

### Phase 1.5: xlsx フォルダの確定（選択式）

> **`--light` フラグが設定されている場合**: xlsx は非対応。Phase 1.5 をスキップし `{xlsx_folder}` = null・`{evidence_dir}` = `docs/logs/{issueID}/evidence` を設定する。（理由: light は `approach-plan.md` を生成しないため Phase 3 の `create_records.py --approach-plan` が必ず失敗する）  
> その後、`xlsx-setup.md`「作成しない」の場合の手順に従い `evidence_dir` を investigation.md フロントマターに書き戻す（`/test` 起動時の保存先解決に必要）。

AskUserQuestion で作成有無を選択する:
- label: `作成する`、description: "対応記録.xlsx を生成する（推奨）"
- label: `作成しない`、description: "xlsx 生成をスキップして作業を続行する"

> **[共通ルール①]** 各フェーズの `timeline` 呼び出しで判断・選択の根拠がある場合は `--reason "{根拠}"` を追加する（記録の追跡性を高めるため積極的に使用すること）。
>
> **[共通ルール②]** xlsx への書き込みは Phase 3 末尾の一括生成（create_records.py）以降に `update_records.py cell` を使用する。Phase 4-6 の各エージェントが timeline と cell 両方の xlsx 追記を担う。

**「作成する」の場合**: 保存先フォルダパスを確定して `{xlsx_folder}` を設定する（xlsx ファイルの生成は Phase 3 末尾で実施。この時点では生成しない）。

> フォルダパス確定手順: [.claude/templates/backlog/xlsx-setup.md](../templates/backlog/xlsx-setup.md)

**「作成しない」の場合**: `{xlsx_folder}` = null、`{evidence_dir}` = `docs/logs/{issueID}/evidence` に設定する。Phase 2 以降の全 xlsx 更新ブロックはスキップする。`xlsx-setup.md`「作成しない」の場合の手順に従い `evidence_dir` を investigation.md フロントマターに書き戻す。

---

### Phase 2: 対応方針の確定（backlog-planner Phase A）

> **`--light` フラグが設定されている場合**: Phase 2 をスキップして Phase 3（実装方針）へ直接進む。対応方針は「最小修正・既存パターン踏襲」固定とし、`approach-plan.md` を作成しない。Phase 3 開始時にその旨を 1 行通知する。
>
> **xlsx 共通規則**: Phase 2 以降の全 xlsx 更新ブロックは `{xlsx_folder}` が null（Phase 1.5 で「作成しない」を選択）の場合スキップする。

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

> **次に進む条件**: ユーザが対応方針を確認した後 — `_README.md §Phase 末尾の確認プロトコル` に従い、サマリー・確認事項・「Phase 3 に進んでよろしいですか？」をテキストで提示してやり取りを経て進む
>
> **Phase 2 典型例**: 「過去 X 件のデータで項目 Y が null のレコードを許容するか / 一括補完するか」「未確定の業務ルール Q1 の回答が方針の前提と合っているか」「スコープに含めるべきか別 Backlog で起票するか」
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

エージェントが `implementation-plan.md` を保存したら提示する。  
全判断ポイントが確定するまで Phase 4 に進まない。

**xlsx 一括生成（対応記録 + エビデンス）**（`{xlsx_folder}` が設定されている場合のみ）

> **実行主体**: planner エージェントは bash を持たないため、planner 復帰後に **本コマンド（ハーネス）が直接** 以下の python スクリプトを実行する。planner には委譲しない。

全 MD ファイルが揃ったこのタイミングで xlsx を一括生成する:

```bash
python "$(pwd)/scripts/python/backlog-xlsx/create_records.py" \
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

生成完了後にファイルパスをユーザに提示する（`{xlsx_folder}` = null の場合はスキップ）:
- `{xlsx_folder}/{issueID}_対応記録.xlsx`

（エビデンス.xlsx は Phase 4 完了後に `/test {issueID}` が生成する）

> **次に進む条件**: 全判断ポイントをユーザが確認・確定した後 — `_README.md §Phase 末尾の確認プロトコル` に従い、サマリー・確認事項・「Phase 3.5 に進んでよろしいですか？」をテキストで提示してやり取りを経て進む
>
> **Phase 3 典型例**: 「類似実装と異なるパターンを採用した判断ポイントの整合性」「SOQL の LIMIT・権限制御が全ユーザ種別で正しいか」

---

### Phase 3.5: 実装前検証（backlog-validator）

> **`--light` フラグが設定されている場合**: Phase 3.5 をスキップして Phase 4（実装）へ直接進む。

`backlog-validator` エージェントを起動する:

```
実装計画: docs/logs/{issueID}/implementation-plan.md
調査レポート: docs/logs/{issueID}/investigation.md
```

エージェントが `validation-report.md` を保存したら内容をユーザに提示する。Phase 3 への戻りが提案された場合は Phase 3 に戻って実装方針を修正してから Phase 3.5 を再実施する。**Phase 3 戻りは最大 2 回まで・セッション跨ぎを含めて通算カウント**（カウントは discussion-log.md の改版履歴から復元する。詳細は `test-fail-routing.md` §ループ上限 を参照）。3 回目以降の戻り提案が出た場合は自動進行を停止し、「実装方針の見直しが繰り返されています。一度オフラインで方針再検討の打ち合わせが必要かもしれません。このまま Phase 3 に戻りますか？（続行 / 中止）」とテキストで確認する。「続行」ならば Phase 3 に戻る。「中止」ならばコマンドを終了する。

**xlsx 更新（実装前検証）**（`{xlsx_folder}` が設定されている場合のみ）

```bash
python "$(pwd)/scripts/python/backlog-xlsx/update_records.py" \
  --folder "{xlsx_folder}" --issue-id "{issueID}" \
  timeline --phase "実装前検証" \
  --content "実装前検証完了: {ドライラン/テスト/影響範囲/クロスレビュー/エビデンスの結果サマリーを1行で}"
```

> **次に進む条件**: 全検証項目 OK をユーザが確認した後 — `_README.md §Phase 末尾の確認プロトコル` に従い、サマリー・確認事項・「Phase 4 に進んでよろしいですか？ Phase 3 に戻る必要がありますか？」をテキストで提示してやり取りを経て進む
>
> **Phase 3.5 典型例**: 「新規発見した影響箇所への対処方針」「Step 1〜3 NG への対処方針」（Before エビデンスは自動採取のためブロッカーにならない）

---

### Phase 4: 実装（backlog-implementer）

`backlog-implementer` エージェントを起動する:

```
実装計画: docs/logs/{issueID}/implementation-plan.md
調査レポート: docs/logs/{issueID}/investigation.md
xlsx_folder: {xlsx_folder}
```

> `{xlsx_folder}` が null（Phase 1.5 で「作成しない」）の場合は xlsx_folder 行を省略してエージェントに渡す。

エージェントが Before/After を提示したらユーザに確認する。変更ファイルが 5 件を超える場合は以下の基準で提示を分ける:
- **詳細提示**: ロジック変更・public インターフェース変更・Apex/LWC/Flow のコード変更
- **一覧省略可**: 設定ファイル・メタデータ（field-meta.xml / layout-meta.xml 等）・テストクラス以外の補助ファイル

> xlsx 更新（timeline + バックアップ情報 + Before/After + 影響確認チェックリスト）は `backlog-implementer` が担当する（エージェント内 Step 7）。xlsx に反映されていることが Phase 5 への進行条件。

> **次に進む条件**: ユーザが実装内容を確認した後 — `_README.md §Phase 末尾の確認プロトコル` に従い、サマリー・確認事項・「Phase 5 に進んでよろしいですか？」をテキストで提示してやり取りを経て進む
>
> **Phase 4 典型例**: 「実装中に発見した計画との不整合の影響評価」「implementation-plan.md への改版履歴追記が必要なら内容の確認」

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
- **PASS** → Phase 6 へ進む（通常進行）
- **FAIL** → Phase 4 に差し戻す（明らかな壊れを修正してから再度スモーク確認）

> **Phase 5 典型例**: 「dry-run で Apex コンパイルエラーが出る・テストが失敗する」→ Phase 4 差し戻し

---

### Phase 6: Sandbox リリース・お客様確認・完了（backlog-releaser）

> **dry-run 重複排除**: Phase 5 で dry-run PASS 済みかつ force-app に変更がない場合、Phase 6 は dry-run をスキップして本デプロイへ直行する。Phase 5 以降にコード変更がある場合のみ再 dry-run を実行する。

`backlog-releaser` エージェントを起動する:

```
実装計画: docs/logs/{issueID}/implementation-plan.md
xlsx_folder: {xlsx_folder}
```

> `{xlsx_folder}` が null（Phase 1.5 で「作成しない」）の場合は xlsx_folder 行を省略してエージェントに渡す。

> xlsx 更新（最終対応サマリー + デプロイ手順 + リリース実施記録 + timeline）は `backlog-releaser` が担当する（エージェント内 Step 3.5）。

**お客様確認サインの取得**

> 種別別ルール・xlsx 更新: [.claude/templates/backlog/customer-signoff.md](../templates/backlog/customer-signoff.md)
> ファイルが存在しない場合は「種別 {issue_type} のお客様確認内容は何ですか？」とテキストで確認し、ユーザの指示に従ってサインを取得する。

完了報告を行う。

> **Phase 6 完了後**: 別セッションで `/test {issueID}` を 1 から起動して網羅的テスト・証跡採取・エビデンス Excel 生成を実施してください（`/test` はデプロイ済み Sandbox 前提・自動起動しない）。

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

**実行しないもの**: deploy 系（Step 1・2a/2b）・お客様確認サイン取得（Step 3.7）・xlsx リリース記録（Step 3.5）・完了報告（Step 4）。

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
