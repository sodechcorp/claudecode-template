# Phase 1.6: Sandbox 仮説検証 詳細手順（バグ系のみ）

> `backlog.md` Phase 1.6 から `{issue_type}` = `バグ` の場合のみ Read される。エージェント起動パラメータ・完了後の分岐・Phase 1 再入手順を含む。

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

「再現仮説 = 0 件」の場合、`backlog-investigator` を以下のプロンプトで再起動する（`検証結果:` キーが追加されることで investigator が再入モードで動作する）。**Step A（課題本文の先行取得 + sf-context-loader）は再実行しない**（context-digest.md が既に存在するため investigator が自分で Read する。`知識層コンテキスト`/`設計層コンテキスト` パラメータは渡さない）:

```
課題ID: {issueID}
プロジェクトルート: {カレントディレクトリ}
出力先: docs/logs/{issueID}/investigation.md
検証結果: docs/logs/{issueID}/hypothesis-verification.md
```

investigator は `検証結果:` キーの有無で再入モードを自動判定する。再入モードでは hypothesis-verification.md を Read して反証済み仮説を除外し、新視点の仮説のみを investigation.md に追記する（通常フロー Step A〜H は実行しない）。通算ループカウントはこのコマンド側（discussion-log.md の改版履歴）が管理する。
