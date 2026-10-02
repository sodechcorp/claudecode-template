---
description: "本番リリース準備を行う。資材確定・最終資材での影響確認・チケット競合・本番環境ドリフト・差分の帰属確認とバックアップを read-only で行い、人間が実行する手順書を1ステップずつ渡す。デプロイ後はリリース後確認（read-only。本番の画面確認を含む）と記録を行う。本番へのデプロイは行わない。/release [課題ID] で個別課題対応。"
argument-hint: "[課題ID]"
---

# /release [課題ID]

**引数の解釈**: `$ARGUMENTS` の先頭トークン（`--` で始まらない最初の語）を `{issueID}` とする（`backlog.md` と同一パターン）。

## 概要

`/backlog`（Sandbox リリース）・`/test`（証跡採取）完了後の独立したライフサイクル段階として、本番リリースを丁寧に確認したうえで、人間が実行する手順を1ステップずつ渡す。**本番へのデプロイ・dry-run・書き込みは一切行わない**（本番に対しては資材の取得・SELECT・画面の閲覧の read-only のみ）。

| 担当 | 主な成果物 |
|---|---|
| （本コマンド直接実行） | 前提確認・手順の1ステップずつの引き渡し（結果の記録と次の手順の組み立て直し）・Phase 7 起動 |
| `release-preparer` | リリース前の確認（最終資材での影響・チケット競合・ドリフト・差分の帰属確認）とバックアップ取得、`release-plan.md` + `release-note.md`。デプロイ後はリリース後確認と記録（Phase 7） |
| `prod-ui-verifier` | デプロイ後の本番の画面確認（閲覧・Login As での見え方。read-only）。Phase 7 の後に Step 5 から直接起動する |
| 担当者 | 本番への dry-run・デプロイの実行、保存・代表操作を伴うリリース後確認 |

---

## 実行手順

### Step 0: 共通 CRITICAL ルールの読込（必須・コマンド起動直後）

以下を **Read で全文読み込む**（CLAUDE.md にはスタブのみ・詳細は外出し先）:

1. Read `.claude/templates/common/verify-implementation-spec.md` — 実装裏付けルール。追加ルール記入欄まで読む
2. Read `.claude/templates/common/verify-source-attribution-spec.md` — 出典確認ルール。追加ルール記入欄まで読む
3. Read `.claude/templates/common/answer-scope-spec.md` — 回答時のスコープ管理ルール（派生事項の分離・無断リファクタ禁止）
4. Read `.claude/templates/common/uncertainty-marker-spec.md` — 確証なし時のマーカー規約（[推定]/[要確認]/[出典不明]の使い分け）

**理由**: Step 4 では main thread がユーザーの自由テキスト質問・エラー報告に直接応答する（本番デプロイ可否を左右する内容を含む）。CLAUDE.md にはスタブのみ記載のため、詳細を読まないと「挙動を実コード確認せず断定」「出典を捏造」「質問外の派生事項を無断で本文に混入」のリスクがある。`release-preparer` agent 側の Step 0c と同じ spec を読み、main thread と agent の知識を揃える（`backlog.md` Step 0 と同一パターン）。

---

### Step 1: 課題ID の確認

引数がない場合、チャットで確認する: 「本番リリース準備を行う課題IDを教えてください。」

### Step 2: 前提チェック

`docs/logs/{issueID}/` が存在するか（Glob）を確認する:
   - 存在しない場合: 「`{issueID}` の作業履歴が見つかりません。先に `/backlog {issueID}` を実施してください」と案内して終了

> `test-report.md` の有無確認・テスト未完時の続行可否確認は `release-preparer` Step 0b に一本化されている。本コマンドでは重複確認しない（Step 0b が未完のまま続行を希望された場合の release-plan.md 冒頭警告まで含めて処理する）。

### Step 2b: 再起動時の意図確認

`docs/logs/{issueID}/release-plan.md` が既に存在するか（Glob）を確認する:
- **存在する場合**: AskUserQuestion で確認する（question: 「`{issueID}` の本番リリース手順書は既に生成済みです。今回の実行は何が目的ですか？」/ header: 「実行目的」/ options: 「途中から再開する」〔`docs/logs/{issueID}/release-log.md` の最後の記録から Step 4 の引き渡しを再開する〕・「本番デプロイ完了を報告する」〔以降の Step 3・4 をスキップし、下記の通り Phase 7 のみを起動する〕・「手順書を再生成する」〔Step 3 へ進み通常どおり実施する。release-log.md に本番変更の記録（定義は `release-preparer.md` Phase 4 冒頭）がある場合は「本番は既にデプロイ後の状態の可能性があります」と先に伝える〕）
  - 「途中から再開する」を選んだ場合: release-plan.md と release-log.md を Read し、release-log.md の最後の「手順書生成:」行（release-preparer.md Phase 5 が書く）より後の記録だけで、完了済みのステップを completed として TodoWrite に復元してから（その範囲に「やり直し: Step N から」の記録があれば、それより前の Step N 以降の完了記録は使わない）、次の未完了ステップを渡す。② まで終わっている（その範囲に「Phase 7 判定:」行がある）場合は、最後の Phase 7 判定が「OK」または「担当者作業待ち」でその後に「画面確認: 完了」の記録が無ければ Step 5 の「本番の画面確認」から、それ以外（画面確認が完了済み、または Phase 7 判定が差異あり・未実施）は Step 5 の該当する扱い（差異あり／未実施の対応、または ③ の担当者確認・データのバックアップ削除の続き）から再開する
  - 「本番デプロイ完了を報告する」を選んだ場合: チャットでデプロイ日時（時刻まで）・結果を確認し、Step 5 と同じく release-log.md に1行追記してから、Task tool で `release-preparer` を起動する:
    ```
    task_description: 「/release 起動: {issueID} の Phase 7（リリース後確認と記録）のみを実施。デプロイ完了報告: {ユーザーからの報告内容}」
    project_dir: {プロジェクトルートパス}
    issueID: {issueID}
    ```
    以降は Step 5 の「完了報告を受けたら」と同じ手順で進める（Step 3・4 の手順書生成・引き渡しは実施しない）。
- **存在しない場合**: そのまま Step 3 へ進む

### Step 3: release-preparer への委譲

`mcp__backlog__get_issue` で `{issueID}` の課題タイトル（`{件名}`）を取得する（investigation.md・implementation-plan.md が共に無い場合の release-preparer Step 0a 側フォールバックに必要。取得できない場合は空のまま次に進む）。

Task tool で `release-preparer` を起動する:

```
task_description: 「/release 起動: {issueID} の本番リリース準備（資材確定・最終資材での影響確認・チケット競合・本番環境ドリフト検知・差分の帰属確認とバックアップ・release-plan.md 生成）」
project_dir: {プロジェクトルートパス}
issueID: {issueID}
issue_title: {件名}
```

### Step 4: 完了後の提示

**`release-preparer` の起動が失敗した場合**（Task エラー・完了報告が返らない場合）: 推測・要約で代替の完了報告を作成しない。エラー内容をそのままユーザーに伝えて中断する（以降の `release_plan_generated` 判定・引き渡しは行わない）。

`release-preparer` の完了報告をそのままユーザーに提示する。

完了報告に含まれる `release_plan_generated` の値で分岐する（`test-report.md` 不在時に続行を希望しなかった場合など、release-preparer が前提未達で中断した場合は `false` になる。この場合 `docs/logs/{issueID}/release-plan.md` が過去実行分として残っていても今回生成されたものではないため参照しない）:
- **`false` の場合**: 完了報告の提示のみで終了する（以降の手順は行わない）
- **`true` の場合**: `docs/logs/{issueID}/release-plan.md` を Read し、[manual-steps-todo-handoff.md](../templates/common/manual-steps-todo-handoff.md) の仕様に従って**担当者の作業を1ステップずつ**渡す（手順書全文を一度に貼らない）。release-plan.md ヘッダーの `manual_operation_mode:` 行を Grep して、管理画面操作版かどうかを先に確認する:

1. **最重要警告の確認**: release-plan.md 冒頭の最重要警告ブロック（何を警告に含めるかは release-preparer.md Phase 4 の9. が正本）に1件でも記載があれば、最初にそれだけを提示し、担当者の判断を得るまで次に進まない。判断を `docs/logs/{issueID}/release-log.md` に記録する。判断によっては先に進まず戻る:
   - 「他の変更が混入している疑い（手元側）」で「取り除く」→ force-app を直してから `/release {issueID}` を再実行するよう案内して終了
   - 「本番の変更を上書きする疑い」で「force-app に取り込む」→ `/backlog {issueID}` に戻る（実装・テストのやり直し）よう案内して終了
   - 本番未接続でバックアップ等が未実施 → 担当者に再認証（`sf org login web`）を依頼し、`release-preparer` を下記の再取得モードで起動してから進む:
     ```
     task_description: 「/release 起動: {issueID} の Phase 4 のバックアップ・差分の帰属確認のみ再実施（理由: {本番未接続からの復旧 / バックアップ取得後の本番の変更}）」
     project_dir: {プロジェクトルートパス}
     issueID: {issueID}
     ```
2. **Claude が確認済みの項目**: ① の【Claude確認済】（テスト完了・資材マニフェスト・影響確認・チケット競合・ドリフト・差分の帰属確認・バックアップ〔取得した項目・件数・保存先・削除予定を含む〕）は、結果を3〜5行にまとめて一度だけ伝える（Todo にしない）
3. **担当者の作業を Todo にする**: ① の【担当者】→ ② の `### Step N: ...`（通常経路では Step 1 は Claude が実行するため除く。**管理画面操作版は Step 1 から担当者の操作なので全て含める**）＋管理画面手動操作 の順に TodoWrite でタスク化する（③ はデプロイ完了後に Step 5 で扱う）
4. **② Step 1（バックアップの最新確認）は Claude が実行する**（通常経路のみ）: **dry-run のステップを渡す直前と、本番デプロイ（Step 3）のステップを渡す直前**に、[prod-readonly-check.md](../templates/common/prod-readonly-check.md) で本番接続を確認し、資材マニフェストの本番コンポーネントの最終更新日時（`sf org list metadata`）が release-plan.md「事前記録」のコンポーネントごとの `lastModifiedDate` と一致するかを確認する。あわせて、資材マニフェスト分の force-app が `docs/logs/{issueID}/release-snapshot/` と一致するかも確認する（手順書作成後に force-app が取り直されていないか）。
   - 本番の最終更新日時が一致しない → `release-preparer` を上記1.の再取得モードで起動し、取り直した結果（差分の帰属確認・データの再取得を含む）を伝える。**新たな最重要警告が返ってきたら 1. と同じく担当者の判断を取ってから進む**。Step 3 の直前に不一致を検知した場合は、dry-run（Step 2）からやり直す（release-log.md に「やり直し: Step 2 から」と記録する）
   - force-app が release-snapshot と一致しない → 手順書作成後に force-app が変わっているため、そこで止めて `/release {issueID}` の再実行（手順書の再生成）を案内する
   - 本番に接続できない → 次に進まず、担当者に再認証を依頼する
5. 先頭の未完了ステップのみ内容（コマンド）を提示し、「実行結果を教えてください」と添える
6. **報告を受けたら**: 結果を `docs/logs/{issueID}/release-log.md` に1行追記し（日時・ステップ・報告内容・次の対応）、**結果に合わせて次のステップを組み立て直す**:
   - 成功が明確 → Todo を completed にして次のステップへ（成否が不明瞭な報告は completed にせず確認する）
   - dry-run でエラー → エラー文を読み、release-plan.md「dry-run/デプロイが失敗した場合の切り分け」に従って原因を特定し、本番デプロイのステップは出さない。本番固有の原因なら解消後に `/release {issueID}` を再実行、実装起因なら `/backlog` への差し戻しを案内する
   - 本番デプロイ（Step 3）でエラー → 本番へのデプロイは全体が取り消されるため本番は変わっていない。dry-run のエラーと同じ切り分けに進む（ロールバックは不要）
   - Step 3 成功後に Step 3b（削除）でエラー → 新規/変更だけが反映された状態のため、release-plan.md「ロールバック手順」を次のステップにするか、削除だけ再実行するかを原因とあわせて提示する
   - 状況が変わって不要になったステップは理由を記録して飛ばす
7. ② の全 Todo が completed になったら「本番デプロイが完了したら教えてください（Claude がリリース後確認を行います）」と一言添える

### Step 5: 本番デプロイ完了報告を受けての Phase 7 起動

**本番デプロイ完了の報告を受けた場合**（本セッション継続中のみ。`/release {issueID}` 再起動時は Step 2b で判定済み）: 報告内容を `docs/logs/{issueID}/release-log.md` に「本番デプロイ完了の報告」として1行追記してから（形式は Step 4 の6.。報告内容にデプロイ日時・結果を書く）、Task tool で `release-preparer` を再起動し、Phase 7（リリース後確認と記録）のみを実施させる:
```
task_description: 「/release 起動: {issueID} の Phase 7（リリース後確認と記録）のみを実施。デプロイ完了報告: {ユーザーからの報告内容}」
project_dir: {プロジェクトルートパス}
issueID: {issueID}
```

**完了報告を受けたら**: リリース後確認（資材の一致・削除の反映・状態確認・想定外の変更）の結果を伝える。
- **差異あり**: ロールバックの要否を担当者に確認する（release-plan.md「ロールバック手順」を1ステップずつ渡す）。ロールバックを実施したら、その結果を `prod-release-issue.md` と `docs/decisions.md` の当該課題エントリ（「ロールバック状況」）に追記する。画面確認（下記）は行わない
- **未実施（本番未接続）**: 担当者に再認証を依頼し、認証後に Phase 7 をやり直す。画面確認（下記）は行わない
- **OK・担当者作業待ち**: 下記「本番の画面確認」を実施してから、release-plan.md「③ リリース後チェック」の担当者の確認項目（担当者作業待ちの内容〔フローの有効化等〕を含む）を Step 4 と同じ方式で1つずつ渡し、結果を release-log.md に記録する
- **既に本番リリース実施記録済み**（同じデプロイの Phase 7 が記録済み）: release-log.md の最後の Phase 7 判定より後に「画面確認: 完了」の記録が無ければ下記「本番の画面確認」から、あれば ③ の担当者確認・データのバックアップ削除の残りの続きから進める

**本番の画面確認（release-log.md の最後の Phase 7 判定が「OK」または「担当者作業待ち」のときのみ・確認不要で自動実行）**: release-plan.md「③ リリース後チェック」の「Claude が実施する確認（画面…）」表を Read する。表が 1 行以上あり、release-log.md の最後の Phase 7 判定より後に「画面確認: 完了」の記録がまだ無い場合に、Task tool で `prod-ui-verifier` を起動する（表が「該当なし」なら起動しない。「画面確認: 未実施」の記録は完了ではないので起動する）。担当者作業待ちの内容（フローの有効化等）に依存する行は、その作業が済むまで実行しない（担当者の確認に回す）:
```
task_description: 「/release 起動: {issueID} のリリース後画面確認（read-only）」
project_dir: {プロジェクトルートパス}
issueID: {issueID}
prod_alias: {release-plan.md ② の --target-org の値。manual_operation_mode: true の場合は「対象環境:」行の値。Phase 7 の完了報告の「対象環境」と同じ}
checks_source: docs/logs/{issueID}/release-plan.md
evidence_dir: docs/logs/{issueID}/release-verification
```
起動が失敗した場合は、推測で結果を作らず、エラー内容をそのまま伝え、画面確認の全行を ③ の担当者の確認に加えて渡す（「画面確認: 未実施（起動失敗）」と記録する）。返却を受けたら結果を `docs/logs/{issueID}/release-log.md` に次の形式で 1 行追記し、次のとおり扱う（`[SKIP]` が返った場合も、理由を「画面確認: 未実施（対象項目なし／Sandbox）」の形で記録するだけで、以降の処理は不要）:
- 記録形式: 「画面確認: 完了（OK a / NG b / 要手動 c）」または「画面確認: 未実施（理由）」
- **OK**: 件数と証跡の保存先だけを一度伝える
- **NG**: 画面・期待・実際の差の種類を伝え、Phase 7 の「差異あり」と同じく担当者にロールバックの要否を確認する。あわせて `docs/logs/{issueID}/prod-release-issue.md`（既存があれば `prod-release-issue.R{N}.md` へ退避してから新規作成。release-preparer.md 7-4 の「それ以外」と同じ規約）に NG の内容を記録し、`docs/decisions.md` の当該課題エントリに「本番リリース後の画面確認で NG（{V番号・画面名・差の種類}）。詳細は prod-release-issue.md 参照」と追記する（リリース予定日／担当欄・changelog.md の本番リリース行は実施済みのまま変更しない。ロールバックを実施した場合は、その旨を decisions.md に追記する）。**decisions.md には V 番号・画面名・差の種類だけを書き、レコードの値・氏名は書かない**
- **要手動**: 理由（Login As 不可・ユーザー特定不可・遷移不可・状態変更を伴う）を伝え、その項目を ③ の担当者の確認に加えて 1 つずつ渡す
- **未実施（本番未接続）**: 担当者に再認証を依頼し、認証後に画面確認だけをやり直す
- スクリーンショットには実顧客のデータが写る可能性がある旨を、初回の結果報告で一言添える（個人情報の扱いは [prod-readonly-check.md](../templates/common/prod-readonly-check.md)「本番 UI 確認」の証跡の扱いに従う）

**③ の担当者確認が全て終わったら**: データのバックアップ（`docs/logs/{issueID}/backup/data/` と、再生成で退避した `backup/data.R*/`）が存在する場合は削除する（個人情報を含みうるため残さない）。[cleanup-rules.md](../spec/cleanup-rules.md) に従い `ignore_errors=True` を使わずに削除し、削除後に存在しないことを確認してから「データのバックアップを削除しました」と伝える（削除に失敗した場合はパスを示して担当者に手動削除を依頼する）。メタデータの `rollback-backup/`・`release-snapshot/` は個人情報を含まないため残す。画面確認の証跡（`release-verification/`）は削除せず残すが、実顧客のデータが写る可能性があるため、チャット・Backlog・共有ドライブへ載せる前に写り込みを確認する（`docs/logs/` は git 管理外）。

---

## 注意事項

- **本番デプロイは本コマンドの範囲外**。`release-plan.md` に記載された CLI コマンド（`deploy_route: manual-operation` の場合は管理画面操作ステップ）は人間が手動で実行する
- 課題間の並行対応でチケット競合が検出された場合、または本番環境ドリフトで「競合・要人間判断」が検出された場合は、release-preparer の完了報告で明示的に警告される。警告を無視してデプロイしないこと
- 本番組織への接続は read-only に限る。`release-preparer` 内部（Phase 1・Phase 4・Phase 7・バックアップ再取得モード）と `prod-ui-verifier`（Step 5 の画面確認。閲覧・Login As のみ）のほか、本コマンドも Step 4 の4.（バックアップの最新確認）でのみ `prod-readonly-check.md` を通して `sf org list metadata` を実行する
- `docs/logs/` は `.gitignore` 対象のため、`release-plan.md` / `release-note.md` / `release-log.md` / バックアップ（`rollback-backup/`・`backup/data/`）は生成した本人のローカル環境にのみ存在する。他メンバーと共有する場合は手動でファイルを渡す必要がある。データのバックアップ（CSV）は個人情報を含みうるため、③ の担当者確認が全て終わった後に Step 5 で削除する
