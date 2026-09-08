# 知見還流 追記フォーマット定義

> このファイルは `backlog-releaser.md` と `backlog.md §中断時の知見還流` が共有する追記フォーマットの単一ソースです。
> フォーマット変更は必ずこのファイルに対して行い、両エージェントに即反映させてください。

---

## decisions.md エントリ

`docs/decisions.md` の**最上部に先頭挿入**するエントリのフォーマット（降順管理・最新が先頭。下流の sf-context-loader.md 等が先頭 N 行のみ Read/Grep する前提のため末尾追加は不可）:

```markdown
## {issueID}: {件名}（{YYYY-MM-DD}）

採用方針: [案X]
実装の主な判断: （判断ポイントと採用選択肢のサマリー）
業務要件への回答: （approach-plan.md の Q 回答欄から転記。なければ省略）
排除した案と理由:
リリース予定日 / 担当:
再発防止策: （同種課題の再発を防ぐための措置。なければ省略）
引き継ぎ事項: （次回担当者への注意点・未解決の懸念・関連課題。なければ省略）
```

---

## effort-log.md 追記フォーマット

`docs/logs/effort-log.md` への追記行（末尾追加・昇順）:

```
| {YYYY-MM-DD} | {issueID} | {種別} | {対応内容60字以内} | {N}h | {実績（未確定なら空欄）} | {対応者種別} | {担当} |
```

`docs/logs/effort-log.md` が存在しない場合の新規作成ヘッダー:

```markdown
# 工数記録

課題対応ごとの工数を記録するファイル。`/backlog` Phase 6（backlog-releaser）が自動追記する。

見込み: sf-effort-estimator 算出値（単一値・信頼度は approach-plan.md 参照）
実績: 完了後に後埋め（`/sf-memory` 保守履歴カテゴリ等でヒアリング）

| 日付 | 課題ID | 種別 | 対応内容 | 見込み | 実績 | 対応者種別 | 担当 |
|---|---|---|---|---|---|---|---|
```

> **禁止**: 「見込み（CC）/見込み（非CC）」の2列分離、または対応内容欄への「手動対応見積内訳: 調査Xh/実装Yh/テストZh…」のような作業分解の再掲。工数は必ず sf-effort-estimator が返す単一値のみを転記する。**既存ファイルのヘッダーがこの形式と異なる場合（旧2列形式等）は、追記前にヘッダー行自体を現行フォーマットへ書き換える**。既存ヘッダーの列構成に引きずられて旧形式を踏襲しない。

---

## pitfalls.md 追記フォーマット

`docs/knowledge/pitfalls.md` への追記行（最新行を先頭挿入）:

```
| {YYYY-MM-DD} | {issueID} | {カテゴリ（例: LWC×Apex / 数式項目）} | {何をするとどうなるか（全角60字以内）} | {対処・回避策（全角40字以内）} | [fallback] |
```

> 検出方法列: Phase 3.6 経由の追記は常に `[fallback]`（discussion-log.md から抽出のため）。

**verify-*.md / answer-scope-spec.md 追加ルール記入欄への追記フォーマット**:

```
- [{YYYY-MM-DD}] {ルール内容}（由来: {issueID}）
```

---

## case-index.md 追記フォーマット

`docs/knowledge/case-index.md` の表への追記行（最新行を先頭挿入・ヘッダー行の直後）:

```
| {YYYY-MM-DD} | {issueID} | {種別} | {症状60字} | {根本原因60字} | {採用方針40字} | {教訓40字} | {対象コンポーネント} | {関連用語} | - | [cases/{issueKey}.md](cases/{issueKey}.md) |
```

`docs/knowledge/case-index.md` が存在しない場合の新規作成ヘッダー:

```markdown
# 対応事例インデックス
| 日付 | 課題ID | 種別 | 症状/要件（60字） | 根本原因（60字） | 採用方針（40字） | 教訓（40字） | 対象コンポーネント | 関連用語 | 工数(h) | 詳細 |
|---|---|---|---|---|---|---|---|---|---|---|
```

---

## test-prerequisites.md 追記フォーマット

`docs/knowledge/test-prerequisites.md` への追記ルール。このファイルは **`/upgrade`（docs-scaffold）が初回配布**する（既存は上書きしない）。`ui-evidence-runner`（§1）・`auto-evidence-runner`（§2/§4）・`backlog-repro-runner`（§1/§4 のみ。詳細は下記）が実測値を **Edit で差分追記**する。**Write による全文上書きは禁止**。

### ファイル不在時の create-if-absent（runner フォールバック）

追記しようとしたとき `docs/knowledge/test-prerequisites.md` が存在しない場合:

1. `.claude/templates/docs-scaffold/knowledge/test-prerequisites.md` を Read する（skeleton の唯一の正本）
2. `docs/knowledge/` ディレクトリが無ければ作成する
3. Read した内容を `docs/knowledge/test-prerequisites.md` として Write する
4. 作成後、通常の3分岐追記フローに進む

### 重複判定 — 3分岐ルール（Read→Grep→Edit）

追記は必ず **Read→Grep→Edit** の順で行う（Write による全文上書き禁止）。キー列で既存行を検索し、以下の3分岐を適用する:

| 判定 | 条件 | 操作 |
|---|---|---|
| 新規追記 | キー列に一致する行なし | 表ヘッダー直後に先頭挿入（Edit） |
| 無記載（スキップ） | キー列一致 + **非キー列が既存行に完全に含まれる** | **何もしない**（確認日も更新しない） |
| マージ更新 | キー列一致 + **追加情報または差分あり** | 既存行を Edit で置換・新情報マージ・確認日更新 |

| セクション | 重複キー（第1列） |
|---|---|
| § 1. ログイン・画面アクセス手順 | 「対象画面」列の値（完全一致） |
| § 2. テストデータ作成レシピ | 「オブジェクト」列のAPI名（完全一致） |
| § 4. テストで繰り返し踏む前提的落とし穴 | 落とし穴の1文（先頭50字の類似判定。類似なら回避策・確認日のみ更新） |

### § 1. ログイン・画面アクセス手順 追記行

```
| {対象画面} | {コミュニティURL or 組織URL（例: /s/hogehoge/）} | {アクセス方法（例: Login As・直接ログイン）} | {Login As 対象プロファイル名 or ContactId 取得 SOQL} | {YYYY-MM-DD} | {issueID} |
```

> **機密保護ルール**: frontdoor URL・accessToken・実 ContactId・パスワードは**絶対に書かない**。Login As 対象は「プロファイル名」か「ContactId を取得する SOQL のみ」を記載。URL のドメイン部分はマスク禁止（org-profile.md に既出の公開情報のため）。

### § 2. テストデータ作成レシピ 追記行

```
| {オブジェクトAPI名} | {必須項目の概要（例: Name, Status__c='未申請', 参照先Id）} | {AnonApex スニペット要点（例: insert new BusinessTraveler__c(...)）} | AUTOTEST_{issueID}_{TC_No}_ | {クリーンアップ SOQL 要点（例: SELECT Id FROM X__c WHERE Name LIKE 'AUTOTEST_%'）} | {YYYY-MM-DD} | {issueID} |
```

### § 4. 前提的落とし穴 追記行

```
| {落とし穴の1文（全角60字以内）} | {回避策（全角40字以内）} | {YYYY-MM-DD} | {issueID} |
```

### 追記上限・安全弁

- **1回の /test で最大5行**（§1/§2/§4 合算）。超過した場合は優先度の高いもの（§1 > §2 > §4）を選んで残りは次回以降。
- **1回の /backlog Phase 1.6（backlog-repro-runner）で最大2行**（§1/§4 合算。§2 は対象外 — §2 の追記フォーマットは `AUTOTEST_{issueID}_{TC_No}_` という /test 側の命名規則が前提で、Phase 1.6 は `REPRO_{issueID}_H{仮説番号}_` 命名・H 番号管理のため § 2 とはキー体系が合わない）。**/test の 5 行クォータとは独立**（Phase 1.6 と /test は同一課題内でも別タイミングで実行されるため合算しない）。
- 追記は `## {セクション見出し}` の直後・表ヘッダーの直後に先頭挿入（最新が先頭）。
- Edit 直前に機密チェック（frontdoor URL・accessToken・パスワードが含まれていないことを確認）。
- ファイルが不在の場合は上記 create-if-absent 手順でファイルを生成してから追記する。

---

## decisions.md / pitfalls.md / case-index.md のサイズ上限・アーカイブ運用

> いずれも先頭挿入（最新が先頭）で追記専用のため、案件対応が積み重なると無制限に肥大化する。以下の閾値・通知ルールは `backlog-releaser.md` §3（decisions.md）・§3.6（pitfalls.md）・§4.5（case-index.md）の追記処理の**直後**に適用する。

**閾値**（超過時の挙動は自動アーカイブではなく**ユーザーへの一行通知**に留める。案件蓄積の実績が薄い現時点で自動でのファイル分割・行移動を機械的に行うと、閾値付近の判定誤りや大量差分の誤操作リスクが実利より大きいため）:

| ファイル | 閾値 | 根拠 |
|---|---|---|
| `docs/decisions.md` | 50 エントリ（`## {issueID}: ...` 単位） | sf-context-loader.md 等が「先頭200行・直近10件」に限定して読む前提のため他2ファイルより緊急度は低いが、無制限放置は避ける |
| `docs/knowledge/pitfalls.md` | 100 行 | sf-org-analyst.md は行数制限なしで全文 Read するため、肥大化がそのままコンテキスト消費増に直結する |
| `docs/knowledge/case-index.md` | 200 行 | pattern-curator.md / regression-guard.md / sf-effort-estimator.md / sf-org-analyst.md が行数制限なしで全文 Grep/Read するため、肥大化が全消費者のコストに波及する |

**通知タイミング**: 上記追記処理で1行（またはエントリ）を追加した直後、ファイルの現在の行数（またはエントリ数）を数え、閾値に達している場合のみ以下を完了報告に一行付記する（閾値未満なら何もしない・通知不要）:

```
⚠ {ファイル名} が {現在件数}{件|行} に達しました（閾値 {閾値}）。docs/knowledge/archive/ 配下への手動アーカイブを検討してください。
```

**手動アーカイブ時の格納先**（実施は人間判断・本ルールは通知のみで自動実行しない）:
- `docs/decisions.md` → `docs/decisions-archive.md`
- `docs/knowledge/pitfalls.md` → `docs/knowledge/archive/pitfalls-archive.md`
- `docs/knowledge/case-index.md` → `docs/knowledge/archive/case-index-archive.md`

閾値を超えた古い（＝ファイル末尾側の）エントリ・行を上記アーカイブ先の**先頭**に移し、元ファイルからは削除する（先頭挿入運用と対称に、アーカイブ側も最新超過分が先頭に来る）。`case-index.md` の行を移しても `cases/{issueKey}.md` 本体は削除しない（インデックス行の格納場所が変わるだけ）。
