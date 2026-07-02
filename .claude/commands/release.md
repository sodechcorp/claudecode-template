---
description: "本番リリース準備を行う。資材確定・影響範囲・チケット競合・本番環境ドリフトを read-only で確認し、人間が実行する本番リリース手順書を生成する。本番へのデプロイは行わない。/release [課題ID] で個別課題対応。"
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

以下を確認する:

1. `docs/logs/{issueID}/` が存在するか（Glob）
   - 存在しない場合: 「`{issueID}` の作業履歴が見つかりません。先に `/backlog {issueID}` を実施してください」と案内して終了
2. `docs/logs/{issueID}/test-report.md` が存在するか
   - 存在しない場合: 「Sandbox でのテスト証跡（test-report.md）が見つかりません。`/test {issueID}` を先に実施することを推奨します。テスト未完のまま本番リリース準備を進めますか？」とテキストで確認する
   - 「進める」の場合は `light_precheck: true` として release-preparer に伝え、release-plan.md 冒頭に警告を明記させる
   - 「先にテストする」の場合は終了

### Step 3: release-preparer への委譲

Task tool で `release-preparer` を起動する:

```
task_description: 「/release 起動: {issueID} の本番リリース準備（資材確定・影響範囲・チケット競合・本番環境ドリフト検知・release-plan.md 生成）。{light_precheck が true の場合: 'test-report.md 未確認のまま進行。release-plan.md 冒頭に警告を明記すること'}」
project_dir: {プロジェクトルートパス}
issueID: {issueID}
```

### Step 4: 完了後の提示

`release-preparer` の完了報告をそのままユーザーに提示する。ユーザーの自由テキスト応答を待つ（質問・修正依頼 何でも可）。やり取りが落ち着いたら終了する。

---

## 注意事項

- **本番デプロイは本コマンドの範囲外**。`release-plan.md` に記載された CLI コマンドは人間が手動で実行する
- 課題間の並行対応でチケット競合が検出された場合、または本番環境ドリフトで「競合・要人間判断」が検出された場合は、release-preparer の完了報告で明示的に警告される。警告を無視してデプロイしないこと
- 本番組織への接続確認は `release-preparer` 内部（Phase 4）で行う。本コマンド自体は組織に接続しない
