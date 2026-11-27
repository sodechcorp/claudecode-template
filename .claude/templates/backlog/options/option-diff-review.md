# option-diff-review

## 何をするか

実装後の diff を起点に、計画整合性・計画外変更の混入・影響範囲再走査を最終チェックする。

Phase 5 Step 2（実装レビュー）が「ガバナ・FLS・ハードコード」等の観点リストベースのコードレビューであるのに対し、本オプションは **実 diff を implementation-plan.md と物理的に突き合わせ、計画通りに・計画の範囲だけ実装されたかを確かめること** が核となる。

## 実行手順

### 1. diff の取得

変更前後の差分を取得する。

**force-app が Git 管理対象の場合**（`git check-ignore -q force-app/` の終了コードが 1）:

base コミットの決定手順は [deploy-manifest-base.md](../_partials/deploy-manifest-base.md) の「base 取得」を参照する（`option-progressive-commits` 採用時は段階コミット一覧の先頭コミットの親を base にし、未採用時は `HEAD` を base にする。`git diff HEAD~1 HEAD` は複数コミットのうち直近 1 件しか見えず、中間コミットのみで変更されたファイルが diff から漏れるため使わない）。

```bash
{ git diff --name-only {base} -- 'force-app/**'; git ls-files --others --exclude-standard -- 'force-app/**'; } | sort -u
git diff {base} -- <変更ファイル>
```

`{base}` は上記手順で決定した値（段階コミット一覧が存在しない標準フローでは `{base}` = `HEAD`）。`git diff` は未追跡の新規ファイルを出さないので、一覧は `git ls-files --others` で補い、未追跡のファイルは `git diff --no-index /dev/null <変更ファイル>` で比べる（終了コード 1 は差分ありでエラーではない）。

**それ以外の場合**（force-app が `.gitignore` 対象〔テンプレート既定の構成〕・git 管理外のプロジェクト）:

実装前の控え `docs/logs/{issueID}/before-snapshot/`（[backlog-implementer.md](../../../agents/backlog-implementer.md)「### 3. 実装」。force-app のファイルを変える前に同じ相対パスで写す）の下の全ファイルと、`find force-app -type f -newer docs/logs/{issueID}/implementation-start.md` に出たファイルを合わせて比べる対象にし、1つずつ `git diff --no-index {控えのパス} {force-app/… のパス}` で比べる（force-app に無いもの＝削除は force-app の側を `/dev/null` にする。控えに無いものは、パスの最後のファイル名を implementation-plan.md「## 関連コンポーネント一覧」と照合し（`-meta.xml` は本体と同じ扱い、LWC・Aura はバンドルのフォルダ名が一致すれば同じ扱い）、変更種別が「新規」のものは控えの側を `/dev/null` にして比べる。それ以外は比べる対象から外し、出力の「### 計画外変更の検出」に「控えに無く計画の新規にも無い」として1行ずつ書く（前回の対応の変更か、計画外の新規かを確かめる）。終了コード 1 は差分ありでエラーではない）。控えも implementation-start.md も無いプロジェクト（GAS 等）では、investigation.md の「現状実装」または `docs/logs/{issueID}/evidence/before/` と照合して擬似 diff を作る。

---

### 2. 計画整合チェック（正統性）

`docs/logs/{issueID}/implementation-plan.md` の「実装方針まとめ」と「判断ポイント一覧」を読み、diff と1件ずつ突き合わせる。**判断ポイントが0件のケース**（backlog-planner B-3 の設計により「### 実装方針まとめ」「### 判断ポイント一覧」の代わりに「### 判断ポイントなし（全カテゴリ一意確定）」が出力されている場合）は、代わりに「## 関連コンポーネント一覧（変更対象ファイル）」を diff との突き合わせ対象とする。

確認する観点:

| 観点 | 確認内容 |
|---|---|
| 実装漏れ | 各判断ポイントが diff に反映されているか |
| 計画外変更 | 無関係な lint fix・空白整形・debug code 残り・コメント追加が紛れていないか（implementation-plan.md の「採用したオプション」に記録された、Phase 4 のオプション〔_index-phase4.md〕による今回の変更箇所〔[backlog-implementer.md](../../../agents/backlog-implementer.md) の鉄則の例外〕の修正は計画外にしない） |
| スコープ逸脱 | 計画で「変更しない」とした箇所が変更されていないか |

---

### 3. コード品質再チェック

diff の追加行（+行）に対して以下を Grep で検出する:

**Apex の場合**:
```bash
Grep pattern: System\.debug\(
対象: 変更ファイル
```

**JavaScript / LWC の場合**:
```bash
Grep pattern: console\.(log|error|warn)\(
対象: 変更ファイル
```

**共通**:
```bash
Grep pattern: (TODO|FIXME|XXX|HACK|BUG)
対象: 変更ファイル
```

コメントアウトされた旧コードが diff に含まれている場合（`//` で始まる行が連続している等）は残存として記録する。ただし元から存在していたコメントを変更したものは対象外。

---

### 4. 影響範囲再 rescan（Phase 3.5 からの追加分）

Phase 3.5 の `option-impact-rescan` は「実装計画書を起点とした事前走査」であるのに対し、本ステップは「実装後の実 diff を起点とした再走査」を行う。実装中に追加した内部 API・private→public 化したメソッド・新規クラス等を検出できる。

1. diff の touch ファイルから**新規追加・変更された API 名・メソッド名**を全て抽出する
2. investigation.md の「関連コンポーネント一覧」と突き合わせて「Phase 3.5 時点で走査済み」のものを除く
3. 差分（新規追加分）について逆参照 grep を再実行する:

```bash
Grep pattern: {新規 API 名 / メソッド名}
対象: force-app/
```

   組織の地図があれば、先に `python scripts/python/sf-lineage/lineage.py who <新規・変更した API 名…>` で参照元（レイアウト・権限・レポート・呼び出し元の2〜3段目を含む）を出し、grep はメソッド名と地図の確かめに使う。地図は force-app より古ければ自動で作り直す（[option-lineage-map.md](option-lineage-map.md)）

4. ヒット箇所を確認して影響を評価する
5. **画面の部品が Apex の取っていない項目を表示していないか**: diff が [consumer-contract-check.md](../../common/consumer-contract-check.md) の「対象」に当たる（画面の部品の controller になる Apex の SOQL の SELECT・戻り値の Map のキー・ラッパークラスの項目を変えた、それが呼ぶサービスのクラスの SOQL を変えた、Aura・LWC・Visualforce の表示する項目を変えた）ときは、そのクラスについて同手順の 2・3 を force-app（ルートは `force-app/main/default`）で実施する。NG（取っていない項目を表示していると確かめたもの）は、本節の次の「### 5. 問題発見時の戻り判定」で、直す部品・Apex が implementation-plan.md の変更対象に入っていれば「新規影響箇所を発見したが対処可能」（Phase 4）、入っていなければ「影響範囲が拡大した」（Phase 3。変更対象に加える）にする（backlog-implementer は計画に無い部品を変えないため）。結果は出力の「### 影響範囲再 rescan」に「使う側との突き合わせ: NG なし／NG {部品:行 項目}／要目視 {照合結果}」と書く

---

### 5. 問題発見時の戻り判定

| 問題の種類 | 戻り先 |
|---|---|
| 計画外変更の混入・debug コード残り | Phase 4（実装を修正して不要変更を除去） |
| 実装漏れ（計画したが diff に反映されていない） | Phase 4（不足実装を追加） |
| 計画自体が誤っていた・影響範囲が拡大した | Phase 3（implementation-plan.md を改版して再実装へ） |
| 新規影響箇所を発見したが対処可能 | Phase 4（対処を加えて再テストへ） |

問題発見時は内容を具体的に提示し、上記テーブルに従って戻り先をユーザに提案してから進む。

---

## 出力

test-report.md に追記:

```markdown
## diff レビュー（最終確認）

### 計画整合チェック

| 計画項目（判断ポイント） | diff 反映 | 判定 |
|---|---|---|
| {判断ポイント1} | {確認した diff の内容} | OK / NG |

### 計画外変更の検出

| ファイル | 変更内容 | 計画外の根拠 | 対応 |
|---|---|---|---|
| （なし） | — | — | — |
| {ファイル} | 比べる対象から外した | 控えに無く計画の新規にも無い | 要確認 |

### コード品質再チェック

- debug 出力残存: なし / あり（{箇所}）
- コメントアウト旧コード: なし / あり（{箇所}）
- 新規 TODO/FIXME: なし / あり（{箇所}）

### 影響範囲再 rescan（Phase 3.5 からの追加分）

| 変更対象（新規追加） | ヒットファイル | 影響評価 | 対応 |
|---|---|---|---|
| （追加発見なし） | — | — | — |

### 総合判定

PASS（リリース準備へ） / 計画修正が必要（Phase 3 戻り）/ 実装修正が必要（Phase 4 戻り）/ 計画外変更の除去が必要（Phase 4 戻り）
```
