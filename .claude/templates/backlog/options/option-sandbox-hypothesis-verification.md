# option-sandbox-hypothesis-verification

## 何をするか

Phase 1 で立てた全仮説を Sandbox で**実際に画面を操作して**検証し、「再現する仮説」と「再現しない仮説」を分類する。
対応方針策定（Phase 2）は再現した仮説のみを対象とする。

実画面操作は `backlog-repro-runner` エージェントが担当する。`backlog.md` Phase 1.6 から委譲される。

---

## 前提条件

- `investigation.md` の「根本原因」セクションに仮説リスト（H1〜Hn）と再現条件が記載されていること
  - 再現条件には「前提データ・操作ユーザ・操作手順（1ステップずつ）・期待結果・実際の結果」が含まれること
- `option-multi-cause-hypothesis` の結果が `investigation.md` に反映済みであること
- Sandbox 環境に接続可能なこと（`backlog-repro-runner` が Step 0 で確認する）

仮説が 1 件しかない場合でも、自明なバグ（typo・null チェック漏れ等）以外は Sandbox での実証を省略しない。

---

## backlog-repro-runner が行うこと

1. **本番ガード**: `.claude/templates/common/sandbox-alias-check.md` で isSandbox 確認。本番への操作は即中止
2. **仮説・再現条件の抽出**: investigation.md を Read して H1〜Hn を読み取る
3. **各仮説を Sandbox 実画面で順次検証**（仮説ごとに独立した状態で実施）:
   - 前提データを準備する（既存レコード優先。新規作成時は `REPRO_{issueID}_H{N}_` プレフィックス付与）
   - 指定操作ユーザでログインする（Login As 対応）
   - 再現手順を 1 ステップずつ実施する
   - 各ステップで操作前後のスクリーンショットを撮影する
   - 症状が現れたタイミングでコンソールログ・ネットワークログを採取する
   - 期待結果と実測結果を記録する
4. **データクリーンアップ**: 作成した `REPRO_` プレフィックスデータを削除
5. **hypothesis-verification.md を出力**: 仮説ごとの再現判定・観察された現象・証跡パスを記録

---

## 検証判定基準

| 判定 | 条件 |
|---|---|
| ✅ 再現 | 報告された症状と同じ現象が Sandbox で観察された |
| ❌ 再現せず | 期待どおりに動作し、バグが観察されなかった |
| ⚠️ 検証不可 | Sandbox にメタデータ・データなし / 環境依存 / 前提データ準備困難 |

**重要**: **「Sandbox にないから飛ばす ＝ 確定扱い」は禁止**。検証不可は必ず ⚠️ で記録し「未検証」として扱う。原因がリポジトリ未回収のメタ要素（入力規則・カスタム設定等）に依存する場合は、`sf project retrieve` で org から取得するかユーザーに実在・内容を確認するよう求める。

---

## 結果に応じた分岐（backlog.md Phase 1.6 で処理）

- **再現仮説 ≥ 1 件** → `hypothesis-verification.md` を保存して Phase 1.6 完了
- **再現仮説 = 0 件** → 「全仮説が再現せず」と記録し、`investigation.md` の仮説立て直しを提案して Phase 1 に戻す
- **検証中に新事実発見** → `investigation.md` の仮説・再現条件を更新してから Phase 1.6 を再実施

---

## 出力: hypothesis-verification.md の構造

`docs/logs/{issueID}/hypothesis-verification.md` に以下の形式で保存する:

```markdown
# Phase 1.6 Sandbox 仮説検証結果

作成日時: {YYYY-MM-DD HH:MM}

## 対象環境
- Sandbox エイリアス: {SF_ALIAS}
- 使用レコード: {既存レコードID または "新規作成（プレフィックス: REPRO_{issueID}_）"}

## 検証対象仮説（investigation.md より）
| # | 仮説 | 採用尤度（事前） |
|---|---|---|
| H1 | ... | 高 |
| H2 | ... | 中 |

## 検証手順と結果

### H1: {仮説名}
**事前条件**: ...
**実行操作**:
  1. ...
  2. ...
**期待結果**: 症状が再現する
**実測結果**: 再現した / 再現しなかった / 検証不可
**観察された現象**: （実際に何が起きたか。エラーメッセージ・画面の状態・変化・変化のなさ）
**証跡**:
  - スクショ: docs/logs/{issueID}/repro/after/H1_xxx.png
  - コンソールログ: docs/logs/{issueID}/repro/logs/H1_console.txt
  - ネットワークログ: docs/logs/{issueID}/repro/logs/H1_network.txt

## 検証サマリー

| # | 仮説 | 検証結果 | 採用判定 |
|---|---|---|---|
| H1 | ... | 再現 | ✅ 対応方針策定対象 |
| H2 | ... | 再現せず | ❌ 除外（記録のみ） |

## 結論
- 採用候補仮説: H1（1 件）
- 除外仮説: H2（再現せず）
- 検証不可: なし
- 次フェーズ: Phase 2 で H1 の対応方針を策定する

## データクリーンアップ
- 作成レコード: {件数} 件（プレフィックス: REPRO_{issueID}_）
- 削除完了: {件数} 件 / 削除失敗: {件数} 件
```
