# option-evidence-check

## 何をするか

実装前 Before エビデンス（画面キャプチャ・データ状態）を**自動採取**する。**ユーザーへの手動取得依頼は行わない**。自動採取が物理的に不可能な場合は理由を事実として記録する（Phase 4 進行のブロッカーにしない）。

## 実行手順

### A. UI 影響判定

implementation-plan.md の「変更対象ファイル」と実装方針を確認し、UI 影響の有無を判定する:

- **UI 影響あり**: 変更対象に LWC `.html`/`.js`、Aura `.cmp`、VF `.page` が含まれる、または実装方針に「画面・ラベル・文言・表示・UI」の語が含まれる
- **UI 影響なし（SOQL/Apex/Flow/設定のみ）**: Before スクリーンショットは「該当なし（非UI変更）」として記録し、Step C へスキップ

### B. Before スクリーンショット自動採取（UI 影響ありの場合のみ）

1. `sandbox-alias-check.md` の手順で Sandbox alias を解決する。
   - Sandbox 未接続・alias 不明の場合: 「自動採取不可（Sandbox 未接続）」として記録し Step C へ。ユーザーへの手動取得依頼はしない。

2. implementation-plan.md / investigation.md から変更対象 UI 画面名と遷移ヒントを抽出し、`{target_screens}` リストを組み立てる:
   ```
   - name: <画面名（スペース・記号は除去し _ 区切り）>
     nav_hint: <画面への遷移方法（例: 「コミュニティホーム → プリチェック をクリック」）>
     target_label: <変更対象の表示文言（省略可。指定時は赤枠ハイライト）>
   ```

3. `ui-evidence-runner` を `mode: before-capture` で `Agent` 委譲し、現状画面を自動撮影する:
   ```
   mode: before-capture
   issueID: {issueID}
   alias: {alias}
   evidence_dir: {project_dir}/docs/logs/{issueID}/evidence
   target_screens: {target_screens リスト}
   ```

4. `ui-evidence-runner` の返却（OK 件数・スキップ件数・証跡ファイルパス）を受け取る。
   - 全スキップ（OK 0 件）の場合: 「自動採取不可（遷移パス特定不可）」として記録する。ユーザー依頼はしない。

### C. Before データ値・ログ採取

implementation-plan.md の「対象オブジェクト・SOQL」を確認し、変更前データ状態の確認が必要な場合は SOQL / CLI で取得する:

- 必要あり（データ件数・フィールド値の変化を確認する方針）: `sf data query --query "SELECT ..." --target-org {alias}` で取得し結果を `{project_dir}/docs/logs/{issueID}/evidence/before/{issueID}_data_before.txt` に保存
- 不要（文言変更・UI 表示のみ・データ変化なし）: 「不要」として記録

## 出力

validation-report.md の Step 5 セクションに記録:

```markdown
## Step 5: Before エビデンス自動採取状況

- Before スクリーンショット（自動採取）: 取得済み（{path}） / 該当なし（非UI変更） / 自動採取不可（{理由}）
- Before データ値・ログ（SOQL/CLI）: 取得済み（{path}） / 不要 / 自動採取不可（{理由}）
```
