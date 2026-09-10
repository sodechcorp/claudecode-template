---
description: "本番リリース準備を行う。資材確定・影響範囲・チケット競合・本番環境ドリフトを read-only で確認し、人間が実行する本番リリース手順書を生成する。本番へのデプロイは行わない。/release [課題ID] で個別課題対応。"
argument-hint: "[課題ID]"
---

# /release [課題ID]

**引数の解釈**: `$ARGUMENTS` の先頭トークン（`--` で始まらない最初の語）を `{issueID}` とする（`backlog.md` と同一パターン）。

## 概要

`/backlog`（Sandbox リリース）・`/test`（証跡採取）完了後の独立したライフサイクル段階として、本番リリース準備を `release-preparer` に一気通貫で委譲する。**本番へのデプロイ・dry-run・書き込みは一切行わない**。成果物は人間が実行する手順書（`release-plan.md`）。

| 担当 | 主な成果物 |
|---|---|
| （本コマンド直接実行） | 前提確認・手順書の逐次引き渡し・Phase 7 起動判定 |
| `release-preparer` | `docs/logs/{issueID}/release-plan.md` + `release-note.md` |

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
- **存在する場合**: AskUserQuestion で確認する（question: 「`{issueID}` の本番リリース手順書は既に生成済みです。今回の実行は何が目的ですか？」/ header: 「実行目的」/ options: 「本番デプロイ完了を報告する」〔以降の Step 3・4 をスキップし、下記の通り Phase 7 のみを起動して終了する〕・「手順書を再生成する」〔Step 3 へ進み通常どおり実施する〕）
  - 「本番デプロイ完了を報告する」を選んだ場合: チャットでデプロイ日時・結果を確認したうえで Task tool で `release-preparer` を起動する:
    ```
    task_description: 「/release 起動: {issueID} の Phase 7（リリース実施後の記録）のみを実施。デプロイ完了報告: {ユーザーからの報告内容}」
    project_dir: {プロジェクトルートパス}
    issueID: {issueID}
    ```
    完了報告をそのままユーザーに提示して終了する（以降の Step は実施しない）。
- **存在しない場合**: そのまま Step 3 へ進む

### Step 3: release-preparer への委譲

`mcp__backlog__get_issue` で `{issueID}` の課題タイトル（`{件名}`）を取得する（investigation.md・implementation-plan.md が共に無い場合の release-preparer Step 0a 側フォールバックに必要。取得できない場合は空のまま次に進む）。

Task tool で `release-preparer` を起動する:

```
task_description: 「/release 起動: {issueID} の本番リリース準備（資材確定・影響範囲・チケット競合・本番環境ドリフト検知・release-plan.md 生成）」
project_dir: {プロジェクトルートパス}
issueID: {issueID}
issue_title: {件名}
```

### Step 4: 完了後の提示

**`release-preparer` の起動が失敗した場合**（Task エラー・完了報告が返らない場合）: 推測・要約で代替の完了報告を作成しない。エラー内容をそのままユーザーに伝えて中断する（以降の `release_plan_generated` 判定・引き渡しは行わない）。

`release-preparer` の完了報告をそのままユーザーに提示する。

完了報告に含まれる `release_plan_generated` の値で分岐する（`test-report.md` 不在時に続行を希望しなかった場合など、release-preparer が前提未達で中断した場合は `false` になる。この場合 `docs/logs/{issueID}/release-plan.md` が過去実行分として残っていても今回生成されたものではないため参照しない）:
- **`false` の場合**: 完了報告の提示のみで終了する（以降の手順は行わない）
- **`true` の場合**: `docs/logs/{issueID}/release-plan.md` を Read し、[manual-steps-todo-handoff.md](../templates/common/manual-steps-todo-handoff.md) の仕様に従って引き渡しを行う（**手順書全文を一度に貼らない**）:

1. 「① リリース前チェック」セクションをそのまま一度に提示する（チェックリスト。実行順序を強制しないため分解しない）
2. 「② リリース実行」冒頭の共通説明段落（`### Step 1` より前の本文。--test-level の判定根拠・今回の判定・実行方針）をそのまま一度に提示する（`### Step N:` 単位の逐次提示では見出し前のこの部分が対象に含まれず、以降ずっとユーザーの目に入らないため、ここで一度だけ提示する）
3. 「② リリース実行」内の `### Step N: ...` 各項目（+ 管理画面手動操作の記載があればそれも1項目）を TodoWrite でタスク化する
4. 先頭の未完了ステップのみ内容（コマンド）を提示し、「実行結果を教えてください」と添える。ユーザーの自由テキスト応答を待つ（質問・修正依頼 何でも可）
5. ユーザーの報告を確認する: **実行結果が成功したと明確に確認できる報告**（例:「完了しました」「成功しました」等、エラーが無いことを示す内容）を受けた場合のみ該当 Todo を completed にし、次のステップへ進む。**成否が不明瞭な報告**（エラー有無に触れていない等）は completed にせず、成否を確認する質問を返す。エラー・失敗の報告なら Todo を進めずその場で回答する
6. ② の全 Todo が completed になったら「③ リリース後チェック」セクションを一度に提示する
7. ③ 提示後、「本番デプロイが完了したら教えてください（Phase 7 のリリース実施記録を行います）」と改めて一言添える

やり取りが落ち着いたら終了する。

### Step 5: 本番デプロイ完了報告を受けての Phase 7 起動

**本番デプロイ完了の報告を受けた場合**（本セッション継続中のみ。`/release {issueID}` 再起動時は Step 2b で判定済み）: Task tool で `release-preparer` を再起動し、Phase 7（リリース実施後の記録）のみを実施させる:
```
task_description: 「/release 起動: {issueID} の Phase 7（リリース実施後の記録）のみを実施。デプロイ完了報告: {ユーザーからの報告内容}」
project_dir: {プロジェクトルートパス}
issueID: {issueID}
```

---

## 注意事項

- **本番デプロイは本コマンドの範囲外**。`release-plan.md` に記載された CLI コマンド（`deploy_route: manual-operation` の場合は管理画面操作ステップ）は人間が手動で実行する
- 課題間の並行対応でチケット競合が検出された場合、または本番環境ドリフトで「競合・要人間判断」が検出された場合は、release-preparer の完了報告で明示的に警告される。警告を無視してデプロイしないこと
- 本番組織への接続確認は `release-preparer` 内部（Phase 4）で行う。本コマンド自体は組織に接続しない
- `docs/logs/` は `.gitignore` 対象のため、`release-plan.md` / `release-note.md` は生成した本人のローカル環境にのみ存在する。他メンバーと共有する場合は手動でファイルを渡す必要がある
