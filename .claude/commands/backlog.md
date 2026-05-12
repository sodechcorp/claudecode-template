---
description: "Backlog課題の調査・対応・記録を一気通貫で実施する。専門エージェントを順に起動し、各フェーズ完了後にユーザ確認を取りながら進める。/backlog [課題ID] または /backlog summary で工数サマリーを出力。"
---

# /backlog [課題ID] または [summary]

**モード判定**: 引数が `summary`（大文字・小文字問わず）なら [summary] モードを実行する。それ以外は [課題ID] モードを実行する。

## 概要

保守課題の対応を5つの専門エージェントが分担する。各フェーズはエージェントに完全委譲し、フェーズ間でユーザ確認・xlsx更新を行う。

| フェーズ | エージェント | 主な成果物 |
|---|---|---|
| Phase 0: 作業フォルダ作成 | （本コマンド直接実行） | `docs/logs/{issueID}/` |
| Phase 1: 調査・理解 | `backlog-investigator` | `investigation.md` |
| Phase 1.5: xlsx フォルダ確定 | （本コマンド直接実行） | `{xlsx_folder}` 変数確定のみ |
| Phase 2: 対応方針の確定 | `backlog-planner` Phase A | `approach-plan.md` |
| Phase 3: 実装方針の確定 | `backlog-planner` Phase B | `implementation-plan.md` + xlsx 一括生成 |
| Phase 3.5: 実装前検証 | `backlog-validator` | `validation-report.md` |
| Phase 4: 実装 | `backlog-implementer`（内部: `sf-context-loader`） | 変更ファイル一覧 |
| Phase 5: テスト・検証 | `backlog-tester`（内部: `sf-context-loader`） | テスト結果レポート |
| Phase 5.5: 最終確認 | `backlog-tester`（Phase 5 と同一エージェント・オプション機構で実行） | テスト結果レポートに統合 |
| Phase 6: リリース・完了 | `backlog-releaser`（内部: `sf-context-loader`） | 完了報告 |

**各エージェントの内部構造**: 全エージェントは Step 0b でフェーズ用 `_index-phase{N}.md` + `_index-cross.md` を読んでオプション判定を行う（[à la carte 仕組み](../templates/backlog/_README.md)）。`backlog-implementer` / `backlog-tester` / `backlog-releaser` / `backlog-validator` はさらに Step 0a で `sf-context-loader` を呼び出す。`backlog-investigator` / `backlog-planner` は docs/ を直接全件読みするため Step 0a を持たない。Phase 1.5 および Phase 1.7 は本コマンドが直接実行するためエージェントを起動せず、`_index-phase1-5.md` / `_index-phase1-7.md` は存在しない（不要）。

**中間成果物の保存先**: `docs/logs/{issueID}/`
- `investigation.md` — 調査レポート
- `approach-plan.md` — 対応方針
- `implementation-plan.md` — 実装方針（全判断ポイント確定版）

**エビデンス保存先**: `{evidence_dir}` 配下（Phase 1.5 で確定）
- xlsx 作成あり: `{xlsx_folder}/evidence/{before,after}/`
- xlsx 作成なし: `docs/logs/{issueID}/evidence/{before,after}/`

---

## [summary] モード

`docs/logs/effort-log.md` を読み込み、以下の形式でサマリーを出力する。ファイルが存在しない場合は「工数ログがまだ存在しません（docs/logs/effort-log.md が未作成です）」と出力して終了する。

```
## 工数サマリー

### 全課題一覧
| 日付 | 課題ID | 対応内容 | 見込み（CC）| 見込み（非CC）| 実績（CC）| 削減効果 | 担当 |

### 集計
- 対応課題数
- 見込み（非CC）合計
- 見込み（CC）合計（記録ある分のみ）
- 実績（CC）合計（記録ある分のみ）
- 平均削減率（記録ある分のみ）
```

範囲表記（例: `4〜6h`）の集計は中央値（`(min+max)/2`）を採用する。

---

## [課題ID] モード — 実行手順

> **絶対ルール**
> - 各フェーズ完了後、次へ進む前にユーザの明示的な許可を必ず取る（黙って次フェーズへ進まない）
> - **AskUserQuestion は使わない**。フェーズ承認・選択肢提示はすべてテキスト会話で行う（例外: Phase 1.5 の xlsx 作成有無・フォルダパス確定 / Phase 0 の再開方法選択（investigation.md 存在時）/ Phase 3 xlsx スクリプト失敗時の対処選択 は AskUserQuestion を使う）
> - **フェーズ末の進め方**:
>   1. 成果物の 3〜5 行サマリーをテキストで提示
>   2. 「特に確認したい点」を **0〜3 個**テキストで挙げる。確認事項がなければ「特に確認事項はありません」と明記し、無理やり挙げない（懸念点・前提の弱い箇所・複数解釈ありうる点）
>   3. ユーザの自由テキスト応答を待つ（質問・修正依頼・承認 何でも可）
>   4. 議論が落ち着いたら「Phase N に進んでよろしいですか？」とテキストで明示確認
>   5. ユーザの承認テキスト（「OK」「進んで」等）を確認してから次フェーズへ進む
> - 実装は Phase 4 以降。それ以前に実装コードを書くことは禁止
> - **xlsx 更新の共通ルール**: Phase 1.5 で定義される共通ルール①（timeline 呼び出しに `--reason "{根拠}"` を追加）と共通ルール②（xlsx シート書き込みは `update_records.py cell` を使用）は Phase 2 以降の全 timeline 更新で適用すること（詳細は「Phase 1.5: 対応記録ファイルの作成」セクションの共通ルール定義を参照）
> - **本番環境（isSandbox=false）への直接デプロイは絶対に行わない**
> - **種別変数 `{issue_type}` の管理**: Phase 1 完了時点で `investigation.md` の「種別」欄から `{issue_type}` = `バグ` / `追加要望` / `その他` を確定し、会話の最後まで保持する。Phase 1.7（再現確認）・Phase 2（デフォルトスタンス）・Phase 5（テスト観点）・Phase 6（お客様確認必須度）の分岐に使用する。種別欄が空欄・不明・記載なしの場合は「種別が判断できません。バグ / 追加要望 / その他 のどれに該当しますか？」とテキストで確認してから確定する

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

```bash
mkdir -p docs/logs/{issueID}
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

### Phase 1: 調査（backlog-investigator）

`backlog-investigator` エージェントを起動する:

```
課題ID: {issueID}
プロジェクトルート: {カレントディレクトリ}
出力先: docs/logs/{issueID}/investigation.md
```

エージェントが `investigation.md` を保存したら、内容をユーザに提示する。また、末尾の「[デプロイ適否の判定](#デプロイ適否の判定phase-1-終了時に適用)」セクションを参照してデプロイ可否を確定する。

> **次に進む条件**: ユーザが調査レポートを確認した後 — 成果物サマリーと特に確認したい点（0〜3 個・なければ「特に確認事項はありません」）をテキストで提示し、やり取りを経て「Phase 1.5 に進んでよろしいですか？」とテキストで確認する
>
> **特に確認したい点の例**: 「類似実装 X の実装パターンと異なる場合の整合性」「業務要件 Q1 への仮説が正しいか」

---

### Phase 1.5: xlsx フォルダの確定（選択式）

AskUserQuestion で作成有無を選択する:
- label: `作成する`、description: "xlsx を生成して対応記録・根拠エビデンスを管理する（推奨）"
- label: `作成しない`、description: "xlsx 生成をスキップして作業を続行する"

> **[共通ルール①]** 各フェーズの `timeline` 呼び出しで判断・選択の根拠がある場合は `--reason "{根拠}"` を追加する（記録の追跡性を高めるため積極的に使用すること）。
>
> **[共通ルール②]** xlsx への書き込みは Phase 3 末尾の一括生成（create_records.py / create_evidence.py）以降に `update_records.py cell` を使用する。Phase 4-6 の各エージェントが timeline と cell 両方の xlsx 追記を担う。

**「作成する」の場合**: 保存先フォルダパスを確定して `{xlsx_folder}` を設定する（xlsx ファイルの生成は Phase 3 末尾で実施。この時点では生成しない）。

> フォルダパス確定手順: [.claude/templates/backlog/xlsx-setup.md](../templates/backlog/xlsx-setup.md)

**「作成しない」の場合**: `{xlsx_folder}` = null、`{evidence_dir}` = `docs/logs/{issueID}/evidence` に設定する。Phase 2 以降の全 xlsx 更新ブロックはスキップする。

---

### Phase 1.7: Sandbox 再現確認（バグのみ）

`{issue_type}` が未確定の場合は `docs/logs/{issueID}/investigation.md` の「種別」欄から確定する。`{issue_type}` が `バグ` 以外（追加要望 / その他）の場合は本 Phase をスキップして Phase 2 へ。

investigation.md の「再現条件」を Sandbox 環境で実機実行する:

1. **Sandbox 確認**: `sf org display --target-org <alias> --json` で `isSandbox=true` を確認。本番接続が確認された場合は中断してユーザに Sandbox alias を質問
2. **再現手順の実行**:
   - Playwright MCP が利用可能 → 自動実行＋スクリーンショットを `{evidence_dir}/before/repro/auto_{連番}_{説明}.png` に保存
   - Playwright 不可 → ユーザに再現手順を提示し「同じ事象が出たか」をテキスト確認してもらう
3. **再現エビデンス取得**: 画面スクリーンショット・コンソールログ・対象レコード値を `{evidence_dir}/before/repro/` に保存
4. **ユーザ確認**: 「Backlog 課題と同じ事象が Sandbox でも再現しましたか？」をテキスト質問

**再現できない場合の分岐**:

| 状況 | 対応 |
|---|---|
| 別データ・別ユーザ等で再現可能性あり | Phase 1.7 を別シナリオで再試行 |
| 再現条件が investigation.md に欠落 | Phase 1 に戻り再調査 |
| そもそも Backlog と異なる事象 | ユーザに確認のうえ中止 / Phase 1 戻り |

**xlsx 更新**（`{xlsx_folder}` が設定されている場合のみ）:

```bash
python scripts/python/backlog-xlsx/update_records.py \
  --folder "{xlsx_folder}" --issue-id "{issueID}" \
  timeline --phase "再現確認" \
  --content "Sandbox 再現確認: {再現成功/失敗・対象データ}"
```

> **次に進む条件**: 再現成功 + ユーザ確認サインを得た後、「Phase 2 に進んでよろしいですか？」とテキストで確認

---

### Phase 2: 対応方針の確定（backlog-planner Phase A）

> **xlsx 共通規則**: Phase 2 以降の全 xlsx 更新ブロックは `{xlsx_folder}` が null（Phase 1.5 で「作成しない」を選択）の場合スキップする。

`backlog-planner` エージェントを起動する（Phase A: 対応方針）:

```
モード: 対応方針（Phase A）
調査レポート: docs/logs/{issueID}/investigation.md
出力先: docs/logs/{issueID}/approach-plan.md
種別: {issue_type}
default_stance: {バグ="最小修正＋既存への影響ゼロを最優先" / 追加要望="既存類似実装のパターンに合わせる" / その他="スコープ規模・本番影響・準備期間を確認のうえ方針を提示し、ユーザに選択させる"}
```

エージェントが `approach-plan.md` を保存したら提示する。  
ユーザが採用方針を確定するまで Phase 3 に進まない。

**xlsx 更新（対応方針）**（`{xlsx_folder}` が設定されている場合のみ）

```bash
python scripts/python/backlog-xlsx/update_records.py \
  --folder "{xlsx_folder}" --issue-id "{issueID}" \
  timeline --phase "方針策定" \
  --source "ユーザ" \
  --content "対応方針確定: {採用した案名と根拠を1行で}"
```

工数見込みを `docs/logs/effort-log.md` に追記する（以下の形式で最終行の後へ追記する）:

```
| {YYYY-MM-DD} | {issueID} | {対応内容を1行で} | - | {Xh または X〜Yh} | - | - | {担当者名} |
```

- 「見込み（非CC）」は backlog-planner Phase A で確定した採用案の「見込み工数（通常作業前提）」を入れる
- 「見込み（CC）」「実績（CC）」「削減効果」はこの時点では `-` を入れる（Phase 6 でユーザーから聞き取って後埋め）

ファイルが存在しない場合はヘッダー行と区切り行を先に作成してから追記する:

```
| 日付 | 課題ID | 対応内容 | 見込み（CC）| 見込み（非CC）| 実績（CC）| 削減効果 | 担当 |
|---|---|---|---|---|---|---|---|
```

> **次に進む条件**: ユーザが対応方針を確認した後 — 成果物サマリーと特に確認したい点（0〜3 個・なければ「特に確認事項はありません」）をテキストで提示し、やり取りを経て「Phase 3 に進んでよろしいですか？」とテキストで確認する
>
> **特に確認したい点の例**: 「業務要件 Q の回答が方針の前提と合っているか」「推奨案と比較した際の非採用案のリスク許容判断」

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
python scripts/python/backlog-xlsx/create_records.py \
  --folder "{xlsx_folder}" --issue-id "{issueID}" \
  --investigation docs/logs/{issueID}/investigation.md \
  --approach-plan docs/logs/{issueID}/approach-plan.md \
  --implementation-plan docs/logs/{issueID}/implementation-plan.md
```

```bash
python scripts/python/backlog-xlsx/create_evidence.py \
  --folder "{xlsx_folder}" --issue-id "{issueID}" \
  --implementation-plan docs/logs/{issueID}/implementation-plan.md
```

**スクリプト失敗時の対処**（エラー出力あり / 終了コード 非0）:
1. エラー内容をユーザに提示する
2. AskUserQuestion で対処方法を選択する:
   - label: `xlsx なしで続行`、description: "xlsx 生成を断念して Phase 3.5 へ進む"
   - label: `修正して再試行`、description: "エラー原因を修正してスクリプトを再実行する"
   - label: `中止`、description: "コマンドを終了する"
3. 「xlsx なしで続行」が選ばれた場合: `{xlsx_folder}` = null として Phase 3.5 へ進む

生成完了後にファイルパスをユーザに提示する（`{xlsx_folder}` = null の場合はスキップ）:
- `{xlsx_folder}/{issueID}_対応記録.xlsx`
- `{xlsx_folder}/{issueID}_エビデンス.xlsx`

**実装前エビデンスの取得依頼**（Phase 4 の実装着手前に必ず案内する）:

- **バグの場合**: 再現手順を実機で実施し、画面スクリーンショット・コンソールログ・対象レコード値を取得し `{evidence_dir}/before/` 配下に保存（ファイル名は連番付き）
  - `{xlsx_folder}` が設定されている場合は `{xlsx_folder}/{issueID}_エビデンス.xlsx` の「実装前エビデンス」シートの貼付枠にも保存
- **追加要望の場合**: 変更前の現状画面・データの状態をスクリーンショット保存（変更後との比較用）。`{evidence_dir}/before/` 配下に保存（+ xlsx 貼付枠）
- **その他の場合**: 変更前の現状を記録しておくことを推奨する。`{evidence_dir}/before/` 配下に保存
- **Playwright が利用可能な場合**: 対象画面のスクリーンショットを自動取得し `{evidence_dir}/before/auto_{連番}_{説明}.png` に保存

エビデンスは Phase 3.5（実装前検証）と Phase 5（クロステスト）で参照される。

> **次に進む条件**: 全判断ポイントをユーザが確認・確定した後 — 成果物サマリーと特に確認したい点（0〜3 個・なければ「特に確認事項はありません」）をテキストで提示し、やり取りを経て「Phase 3.5 に進んでよろしいですか？」とテキストで確認する
>
> **特に確認したい点の例**: 「類似実装と異なるパターンを採用した判断ポイントの整合性」「SOQL の LIMIT・権限制御が全ユーザ種別で正しいか」

---

### Phase 3.5: 実装前検証（backlog-validator）

`backlog-validator` エージェントを起動する:

```
実装計画: docs/logs/{issueID}/implementation-plan.md
調査レポート: docs/logs/{issueID}/investigation.md
```

エージェントが `validation-report.md` を保存したら内容をユーザに提示する。Phase 3 への戻りが提案された場合は Phase 3 に戻って実装方針を修正してから Phase 3.5 を再実施する。Phase 3 への戻りは最大 2 回まで（セッション内カウント。途中再開時はリセット）。3 回目の戻り提案が出た場合は処理を中断し、「実装方針の見直しが繰り返されています。ユーザ判断が必要です。」とテキストで確認する。

**xlsx 更新（実装前検証）**（`{xlsx_folder}` が設定されている場合のみ）

```bash
python scripts/python/backlog-xlsx/update_records.py \
  --folder "{xlsx_folder}" --issue-id "{issueID}" \
  timeline --phase "実装前検証" \
  --content "実装前検証完了: {ドライラン/テスト/影響範囲/クロスレビュー/エビデンスの結果サマリーを1行で}"
```

```bash
python scripts/python/backlog-xlsx/update_records.py \
  --folder "{xlsx_folder}" --issue-id "{issueID}" \
  test-precheck --report "docs/logs/{issueID}/validation-report.md"
```

> **次に進む条件**: 全検証項目 OK をユーザが確認した後 — 成果物サマリーと特に確認したい点（0〜3 個・なければ「特に確認事項はありません」）をテキストで提示し、やり取りを経て「Phase 4 に進んでよろしいですか？ Phase 3 に戻る必要がありますか？」とテキストで確認する
>
> **特に確認したい点の例**: 「新規発見した影響箇所への対処方針」「エビデンスが取れていない項目の扱い」

---

### Phase 4: 実装（backlog-implementer）

`backlog-implementer` エージェントを起動する:

```
実装計画: docs/logs/{issueID}/implementation-plan.md
調査レポート: docs/logs/{issueID}/investigation.md
xlsx_folder: {xlsx_folder}（設定されている場合）
```

エージェントが Before/After を提示したらユーザに確認する。変更ファイルが 5 件を超える場合は以下の基準で提示を分ける:
- **詳細提示**: ロジック変更・public インターフェース変更・Apex/LWC/Flow のコード変更
- **一覧省略可**: 設定ファイル・メタデータ（field-meta.xml / layout-meta.xml 等）・テストクラス以外の補助ファイル

> xlsx 更新（timeline + 対応内容シート Before/After）は `backlog-implementer` が担当する（エージェント内 Step 7）。

> **次に進む条件**: ユーザが実装内容を確認した後 — 成果物サマリーと特に確認したい点（0〜3 個・なければ「特に確認事項はありません」）をテキストで提示し、やり取りを経て「Phase 5 に進んでよろしいですか？」とテキストで確認する
>
> **特に確認したい点の例**: 「実装中に発見した計画との不整合の影響評価」「implementation-plan.md への改版履歴追記が必要なら内容の確認」

---

### Phase 5: テスト・検証（backlog-tester）

`backlog-tester` エージェントを起動する:

```
調査レポート: docs/logs/{issueID}/investigation.md
実装計画: docs/logs/{issueID}/implementation-plan.md
種別: {issue_type}
xlsx_folder: {xlsx_folder}（設定されている場合）
```

テスト結果をユーザに報告する。NG 項目があれば以下を参照して戻り先を判断する:

> NG 戻り先テーブル: [.claude/templates/backlog/test-fail-routing.md](../templates/backlog/test-fail-routing.md)
> ファイルが存在しない場合は NG の原因を 1 行で提示し「Phase 3（実装方針修正）と Phase 4（実装修正）のどちらに戻りますか？」とテキストで確認する。

> xlsx 更新（timeline + テスト・検証記録シート 実際の結果・判定）は `backlog-tester` が担当する（エージェント内 Step 8）。

> **次に進む条件**: 全テスト PASS かつユーザ確認サインがあった後 — 成果物サマリーと特に確認したい点（0〜3 個・なければ「特に確認事項はありません」）をテキストで提示し、やり取りを経て「Phase 6 に進んでよろしいですか？」とテキストで確認する
>
> **特に確認したい点の例**: 「ユーザ合同確認が取れていないシナリオの扱い」「Before/After エビデンスが対になっているか」

---

### Phase 6: リリース・お客様確認・完了（backlog-releaser）

`backlog-releaser` エージェントを起動する:

```
実装計画: docs/logs/{issueID}/implementation-plan.md
xlsx_folder: {xlsx_folder}（設定されている場合）
```

> xlsx 更新（timeline + リリース・ロールバックシート リリース実施記録）は `backlog-releaser` が担当する（エージェント内 Step 3.5）。

**お客様確認サインの取得**

> 種別別ルール・xlsx 更新: [.claude/templates/backlog/customer-signoff.md](../templates/backlog/customer-signoff.md)
> ファイルが存在しない場合は「種別 {issue_type} のお客様確認内容は何ですか？」とテキストで確認し、ユーザの指示に従ってサインを取得する。

完了報告を行う。

---

## デプロイ適否の判定（Phase 1 終了時に適用）

> 判定基準: [.claude/templates/backlog/deploy-skip-judgment.md](../templates/backlog/deploy-skip-judgment.md)

---

## 使用例

```
/backlog GF-327     # GF-327 の対応を実施
/backlog summary    # 全課題の工数サマリーを出力
```
