---
description: "本番リリース準備を行う。資材確定・影響範囲・チケット競合・本番環境ドリフトを read-only で確認し、人間が実行する本番リリース手順書を生成する。本番へのデプロイは行わない。/release [課題ID] で個別課題対応。"
argument-hint: "[課題ID]"
---

# /release [課題ID]

**引数の解釈**: `$ARGUMENTS` の先頭トークンを `{issueID}` とする。

## 概要

`/backlog`（Sandbox リリース）・`/test`（証跡採取）完了後の独立したライフサイクル段階として、本番リリース準備を `release-preparer` に一気通貫で委譲する。**本番へのデプロイ・dry-run・書き込みは一切行わない**。成果物は人間が実行する手順書（`release-plan.md`）。

| 担当 | 主な成果物 |
|---|---|
| （本コマンド直接実行） | 前提確認 |
| `release-preparer` | `docs/logs/{issueID}/release-plan.md` + `release-note.md` |

---

## 実行手順

### Step 1: 課題ID の確認

引数がない場合、チャットで確認する: 「本番リリース準備を行う課題IDを教えてください。」

### Step 2: 前提チェック

`docs/logs/{issueID}/` が存在するか（Glob）を確認する:
   - 存在しない場合: 「`{issueID}` の作業履歴が見つかりません。先に `/backlog {issueID}` を実施してください」と案内して終了

> `test-report.md` の有無確認・テスト未完時の続行可否確認は `release-preparer` Step 0b に一本化されている。本コマンドでは重複確認しない（Step 0b が未完のまま続行を希望された場合の release-plan.md 冒頭警告まで含めて処理する）。

### Step 3: release-preparer への委譲

Task tool で `release-preparer` を起動する:

```
task_description: 「/release 起動: {issueID} の本番リリース準備（資材確定・影響範囲・チケット競合・本番環境ドリフト検知・release-plan.md 生成）」
project_dir: {プロジェクトルートパス}
issueID: {issueID}
```

### Step 4: 完了後の提示

`release-preparer` の完了報告をそのままユーザーに提示する。

`docs/logs/{issueID}/release-plan.md` の有無を確認する（`test-report.md` 不在時に続行を希望しなかった場合など、release-preparer が前提未達で中断した場合は生成されない）:
- **存在しない場合**: 完了報告の提示のみで終了する（以降の手順は行わない）
- **存在する場合**: 続けて Read し、[manual-steps-todo-handoff.md](../templates/common/manual-steps-todo-handoff.md) の仕様に従って引き渡しを行う（**手順書全文を一度に貼らない**）:

1. 「① リリース前チェック」セクションをそのまま一度に提示する（チェックリスト。実行順序を強制しないため分解しない）
2. 「② リリース実行」内の `### Step N: ...` 各項目（+ 管理画面手動操作の記載があればそれも1項目）を TodoWrite でタスク化する
3. 先頭の未完了ステップのみ内容（コマンド）を提示し、「実行結果を教えてください」と添える。ユーザーの自由テキスト応答を待つ（質問・修正依頼 何でも可）
4. 実行完了の報告を受けたら該当 Todo を completed にし、次のステップへ進む。質問・エラー報告なら Todo を進めずその場で回答する
5. ② の全 Todo が completed になったら「③ リリース後チェック」セクションを一度に提示する
6. ③ 提示後、「本番デプロイが完了したら教えてください（Phase 7 のリリース実施記録を行います）」と改めて一言添える

やり取りが落ち着いたら終了する。

**本番デプロイ完了の報告を受けた場合**（本セッション継続中・`/release {issueID}` 再起動のいずれでも）: Task tool で `release-preparer` を再起動し、Phase 7（リリース実施後の記録）のみを実施させる:
```
task_description: 「/release 起動: {issueID} の Phase 7（リリース実施後の記録）のみを実施。デプロイ完了報告: {ユーザーからの報告内容}」
project_dir: {プロジェクトルートパス}
issueID: {issueID}
```

---

## 注意事項

- **本番デプロイは本コマンドの範囲外**。`release-plan.md` に記載された CLI コマンドは人間が手動で実行する
- 課題間の並行対応でチケット競合が検出された場合、または本番環境ドリフトで「競合・要人間判断」が検出された場合は、release-preparer の完了報告で明示的に警告される。警告を無視してデプロイしないこと
- 本番組織への接続確認は `release-preparer` 内部（Phase 4）で行う。本コマンド自体は組織に接続しない
