# Phase 1.6: Sandbox 仮説検証 詳細手順（バグ系のみ）

> `backlog.md` Phase 1.6 から `{issue_type}` = `バグ` の場合のみ Read される。エージェント起動パラメータ・完了後の分岐・Phase 1 再入手順を含む。

`backlog-repro-runner` エージェントを起動する（実際に Sandbox 画面を操作してバグを再現する）:

```
課題ID: {issueID}
プロジェクトルート: {カレントディレクトリ}
調査レポート: docs/logs/{issueID}/investigation.md
出力先: docs/logs/{issueID}/hypothesis-verification.md
証跡保存先: docs/logs/{issueID}/repro
```

エージェントが完了報告（フェーズ完了の提示）を返したら、下の分岐に進む（`hypothesis-verification.md` の内容はここでユーザーに提示しない。検証結果は Phase 2 の提示「■ 原因・現状」にまとめて報告する）。それ以外（中断報告・`[FATAL]`・Phase 1 差し戻し等）を返した場合は、途中までの同ファイルに下の分岐を当てはめず、その報告を提示して担当者の判断を待つ。中断報告の後に再実行すると、Step 2 の再入判定により未検証の仮説だけが続きから検証される。

**Phase 1.6 完了後の分岐**（上から順に判定し、最初に該当した行を採用する。各条件は相互排他）:

| 結果 | 次の動作 |
|---|---|
| ① 検証中に新事実発見 | investigator が `investigation.md` を更新して再度 Phase 1.6 を実施（ループカウントに含める） |
| ② 再現仮説 ≥ 1 件 | Phase 2 へ（再現した仮説のみを Phase 2 で対象とする。検証不可の仮説が混在する場合は「未検証のまま」と記録し対象外とする） |
| ③ 再現仮説 = 0 件、かつ仮説が「検証不可」（Sandbox にメタデータ・データなし、環境依存等）が1件以上 | **「未検証のまま」として記録。確定表現禁止。** 原因がリポジトリ未回収のメタ要素（入力規則・カスタム設定等）に依存する場合は、`sf project retrieve` で org から（`--output-dir docs/logs/{issueID}/repro/org-retrieve` に）取得するかユーザーに実在・内容を確認してから Phase 2 へ。「Sandbox にないから飛ばす ＝ 確定扱い」は禁止。 |
| ④ 再現仮説 = 0 件、かつ検証不可の仮説もなし（全仮説が「再現せず」） | Phase 1 に戻り investigator が新仮説を追加生成して再度 Phase 1.6 を実施（**最大 2 回まで・セッション跨ぎを含めて通算カウント**。カウントは discussion-log.md の改版履歴から復元する。3 回目は investigator を再起動せず、investigator が新仮説なしを返した場合は Phase 1.6 を再実施せず、いずれも「仮説が尽きている可能性があります。業務側との打ち合わせを推奨します」とユーザーに伝え、継続・中止の判断を求める） |

> **次に進む条件（自動進行）**: ② と ③（retrieve が不要、または retrieve で確認できた場合）は、Phase 1.6 単独のサマリーを出さず、承認を待たず同一ターンで Phase 2 へ進む（報告は Phase 2 の提示に1回でまとめる。`backlog.md`【フェーズ進行】参照）。③ で retrieve できずユーザーへの確認が要る場合は、その確認だけを1〜2行で聞いて待つ。① の再検証中と ④ の再入中（上限内）は「新しい仮説で再調査します」程度の1行の進捗だけ伝える。④ で止まる場合は、それまでの検証結果を短く添えて担当者の判断を待つ

#### Phase 1 再入（仮説補充）の起動方法

④に従って Phase 1 に戻る場合、`backlog-investigator` を以下のプロンプトで再起動する（`検証結果:` キーが追加されることで investigator が再入モードで動作する）。**Step A（課題本文の先行取得 + sf-context-loader）は再実行しない**（context-digest.md が既に存在するため investigator が自分で Read する。`知識層コンテキスト`/`設計層コンテキスト` パラメータは渡さない）:

```
課題ID: {issueID}
プロジェクトルート: {カレントディレクトリ}
出力先: docs/logs/{issueID}/investigation.md
検証結果: docs/logs/{issueID}/hypothesis-verification.md
```

investigator は `検証結果:` キーの有無で再入モードを自動判定する。再入モードでは hypothesis-verification.md を Read して反証済み仮説を除外し、新視点の仮説のみを investigation.md に追記する（通常フロー Step A〜H は実行しない）。通算ループカウントはこのコマンド側（discussion-log.md の改版履歴）が管理する。
