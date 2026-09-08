# 途中フェーズからの再開ルーティング

`docs/logs/{issueID}/` 配下の既存成果物の有無に応じて再開可能フェーズをテキストで列挙して選択を促す:

**`prod-release-issue.md` が存在する場合（本番リリース段階の差し戻し。`release-issue.md` より優先して判定し、存在すればこちらのみ処理する。両方存在する場合、`release-issue.md` は Sandbox 段階で既に解消済みの過去記録のため案内対象にしない）**: 本ファイルの他の分岐と異なり `/backlog` 内のフェーズではなく別コマンド（`/release`）への案内になるため、末尾の「選択されたフェーズの該当節へ進む」の対象にせずここで完結させる:
- `prod-release-issue.md` を Read し、記録されている差し戻し先（本番固有の失敗／実装起因の失敗。release-preparer.md Phase 5 Step 2/3 の切り分けと同じ区分）を確認する
- **本番固有の失敗**（org drift・権限不足・API バージョン不整合等）: 「原因を解消した上で `/release {issueID}` を再実行してください（release-preparer が資材マニフェスト・ドリフト確認を再チェックします）」と案内する。`/backlog` の再開は行わない
- **実装起因の失敗**（デプロイ対象コード自体のロジック・カバレッジ不足等）: 「Phase 4（実装修正）から / 中止 のどれにしますか？」と確認する。選択後は Phase 4 実施 → 完了後 `/test {issueID}` → `/release {issueID}` の順で再実施するよう案内する
- 分岐を提示する前に `docs/logs/{issueID}/` 配下の `prod-release-issue.R{N}.md` の最大回次番号 N（＝本番リリースからの過去の差し戻し回数。欠番があってもファイル数ではなく最大値を基準にする）を確認する。現在の `prod-release-issue.md`（今回分）を含めた通算差し戻し回数（N + 今回分）が4回目以上に達している場合は「本番リリースの差し戻しが繰り返されています。業務担当者との打ち合わせを推奨します」を添えて提示する

`prod-release-issue.md` が存在しない場合、以下の分岐（いずれも `/backlog` 内のフェーズへの再開）に進む:

- `release-issue.md` 存在 → まず `release-issue.md` を Read し、記録されている差し戻し先 Phase（Phase 4 または Phase 5）を確認したうえで選択肢を出す（**Sandbox リリース段階〔backlog-releaser.md〕の差し戻し専用。本番リリース段階〔release-preparer.md〕の差し戻しは上記 `prod-release-issue.md` を参照**）:
  - 差し戻し先が Phase 4（実装ロジック起因の挙動不良） → 「Phase 4（実装修正）から / Phase 5（スモーク確認）から / Phase 6（リリース）から再試行 / 中止 のどれにしますか？」
  - 差し戻し先が Phase 5（デプロイ失敗等・dry-run で検知可能な問題） → 「Phase 5（スモーク確認）から / Phase 6（リリース）から再試行 / 中止 のどれにしますか？」
  - 分岐を提示する前に `docs/logs/{issueID}/` 配下の `release-issue.R{N}.md` の最大回次番号 N（＝ Phase 6 からの過去の差し戻し回数。欠番があってもファイル数ではなく最大値を基準にする）を確認する。現在の `release-issue.md`（今回分）を含めた通算差し戻し回数（N + 今回分）が4回目以上に達している場合は「Phase 6 からの差し戻しが繰り返されています。業務担当者との打ち合わせを推奨します」を添えて提示する。
  - 選択後: 把握済みの差し戻し理由・現象・ログを踏まえて該当フェーズを実施する
- `test-report.md` 存在 **かつ** `### 総合判定` の直後の行が `FAIL` で始まる → 「Phase 4（/test NG 修正）から / 中止 のどれにしますか？」
  - 分岐を提示する前に `test-fail-routing.md §ループ上限` のループ回次を確認する（`docs/logs/{issueID}/` 配下の `judgment-result.R{N}.json` の最大回次番号 N = これまでの NG 修正回数。欠番があってもファイル数ではなく最大値を基準にする）。既に上限（3回）に達している場合は「差し戻し上限に達しています。業務担当者との打ち合わせを推奨します」を添えて提示する。
  - 選択後: Phase 4 で修正 → Phase 5（dry-run）→ Phase 6（軽量再デプロイ）→ `/test` 再実行
- `test-report.md` 存在 **かつ** `### 総合判定` の直後の行が `条件付きPASS` で始まる → 「Phase 4（受入基準再確認を踏まえた再実装）から / Phase 6（リリース、要確認を許容して進める）から / 中止 のどれにしますか？」
- `test-report.md` 存在 **かつ** `### 総合判定` の直後の行が `PASS` で始まる → 「Phase 6（リリース）から再試行 / 中止 のどれにしますか？」
- `validation-report.md` 存在（test-report.md なし） → 「Phase 4（実装）から / Phase 3.5（実装前検証）から / 中止 のどれにしますか？」
- `implementation-plan.md` 存在（validation-report.md なし） → 「Phase 3.5（実装前検証）から / Phase 3（実装方針確定）から / 中止 のどれにしますか？」
- `approach-plan.md` 存在（implementation-plan.md なし） → 「Phase 3（実装方針確定）から / Phase 2（対応方針確定）から / 中止 のどれにしますか？」
- `investigation.md` のみ存在 → `investigation.md` フロントマターの `issue_type` を確認し、以下の通り選択肢を提示する:
  - `issue_type` = `バグ` → 「Phase 1.6（Sandbox 仮説検証）から / 中止 のどれにしますか？」
  - `issue_type` = `問い合わせ` → 「Phase 2（対応方針確定）から / 中止 のどれにしますか？」
  - `issue_type` = `追加要望` / `その他` → 「Phase 1.5（xlsx フォルダ確定）から / 中止 のどれにしますか？」

選択されたフェーズの該当節へ進む。前フェーズの成果物は再生成せず保持する。

### Phase 5/6 から Phase 1 完全やり直し

Phase 5 または Phase 6 で根本的な問題（原因誤特定・スコープ根本見直し等）が発覚し、Phase 1 からの再調査が必要な場合:

1. **既存成果物のアーカイブ**:
   - `docs/logs/{issueID}/` 配下の全 MD を `docs/logs/{issueID}/archive/v{N}/` に移動する
   - `N` は既存の archive フォルダ数 + 1（初回は v1）
   - `docs/logs/{issueID}/discussion-log.md` はアーカイブせず残存させ、「v{N} やり直し理由: {理由}」を追記してから続行

2. **Phase 1 から再起動**:
   - /backlog コマンドを再起動し、「既存 investigation.md が見当たらない場合の新規フロー」として Phase 1 から実施
   - やり直し理由は discussion-log.md に記録済みのため、investigator は冒頭で discussion-log.md を Read して経緯を把握してから調査を開始する

3. **ループ上限への影響**:
   - アーカイブした回数（v{N}-1）を discussion-log.md から算出してループ上限の通算カウントに含める
   - 通算で Phase 1 完全やり直しが 2 回以上に達した場合は、ユーザーに「課題の根本的な見直しが必要な可能性があります」と案内してから続行する
