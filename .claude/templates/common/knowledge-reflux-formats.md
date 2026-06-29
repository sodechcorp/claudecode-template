# 知見還流 追記フォーマット定義

> このファイルは `backlog-releaser.md` と `backlog.md §中断時の知見還流` が共有する追記フォーマットの単一ソースです。
> フォーマット変更は必ずこのファイルに対して行い、両エージェントに即反映させてください。

---

## decisions.md エントリ

`docs/decisions.md` に追記するエントリのフォーマット:

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

## pitfalls.md 追記フォーマット

`docs/knowledge/pitfalls.md` への追記行（最新行を先頭挿入）:

```
| {YYYY-MM-DD} | {issueID} | {カテゴリ（例: LWC×Apex / 数式項目）} | {何をするとどうなるか（全角60字以内）} | {対処・回避策（全角40字以内）} | [fallback] |
```

> 検出方法列: Phase 3.6 経由の追記は常に `[fallback]`（discussion-log.md から抽出のため）。

**verify-*.md 追加ルール記入欄への追記フォーマット**:

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

`docs/knowledge/test-prerequisites.md` への追記ルール。このファイルは **`/upgrade`（docs-scaffold）が初回配布**する（既存は上書きしない）。`ui-evidence-runner`（§1）・`auto-evidence-runner`（§2/§4）が実測値を **Edit で差分追記**する。**Write による全文上書きは禁止**。

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
- 追記は `## {セクション見出し}` の直後・表ヘッダーの直後に先頭挿入（最新が先頭）。
- Edit 直前に機密チェック（frontdoor URL・accessToken・パスワードが含まれていないことを確認）。
- ファイルが不在の場合は上記 create-if-absent 手順でファイルを生成してから追記する。
