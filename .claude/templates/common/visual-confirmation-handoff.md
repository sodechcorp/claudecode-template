# 目視確認ハンドオフ 共通手順

ユーザーに「目視確認・再現確認・手動確認・お客様確認」を促す全ての箇所は、本テンプレートの手順で **レコードURL・レコードID・操作手順を準備した状態で渡す**。「Sandbox 上でプレフィックス検索してください」のような丸投げは禁止。

> 参照元エージェント: `backlog-repro-runner.md`（Phase 1.6）/ `auto-evidence-runner.md`・`ui-evidence-runner.md`（/test）/ `backlog-releaser.md`（Phase 6）

---

## 1. instanceUrl の取得（token を含まない組織ベースURL）

`sandbox-alias-check.md` の Sandbox 判定で既に `sf org display --target-org "$SF_ALIAS" --json` を実行済みの場合はその結果を使い回す（二重実行しない）。未取得の場合のみ以下を実行:

```bash
INSTANCE_URL=$(sf org display --target-org "$SF_ALIAS" --json | python -c "import sys,json; print(json.load(sys.stdin)['result'].get('instanceUrl',''))" 2>/dev/null || echo "")
```

**`instanceUrl` は accessToken を含まない組織ドメインのみの値**（例: `https://xxxxx--sandboxname.sandbox.my.salesforce.com`）。チャット・test-report.md・created_records.txt 等の成果物に出力してよい。

**厳禁**: `FRONTDOOR_URL`（`sf org open --url-only` が返す accessToken 込みのワンタイムURL）は `playwright-sf-screen-ops.md` の規約により証跡・ログ・return値・チャット出力のいずれにも絶対に出力しない。目視ハンドオフ用のリンクは必ず `instanceUrl` ベースの素のURLを使う。

---

## 2. レコード目視URLの組み立て

```
{instanceUrl}/lightning/r/{SObjectAPI名}/{RecordId}/view
```

- `SObjectAPI名` と `RecordId` は `created_records.txt`（`SObject,Id` または `SObject|Id|Name|TC` 形式）から取得する
- ユーザーは Sandbox に自分のブラウザセッションでログイン済みであることが前提（未ログインなら通常のログイン画面にリダイレクトされるだけで、accessToken 漏洩リスクはない）

## 3. 画面URLの秘匿処理（UI TC）

`ui-evidence-runner` が内部で取得する `page.url()` をハンドオフに使う場合は、クエリパラメータを必ず除去してから出力する:

```javascript
const cleanUrl = pageUrl.split('?')[0];
```

Salesforce の内部遷移URLはクエリにセッション関連値を含むことがあるため、`?` 以降は保持しない。

---

## 4. 標準ハンドオフブロック（出力フォーマット）

以下のブロックを、test-report.md・hypothesis-verification.md・チャット完了報告のいずれでも同一フォーマットで使う:

```markdown
## 🔎 目視確認のご案内

Sandbox（{alias}）に未ログインの場合は、リンククリック後にログイン画面が出ます。ログイン後に対象が表示されます。

| 確認対象 | 画面/レコードURL | レコードID | 対象TC | 操作手順 |
|---|---|---|---|---|
| {ラベル（日本語表示名）} | {instanceUrl}/lightning/r/{SObject}/{Id}/view | {Id} | TC-00X | ①…→②…→③… |
| {画面ラベル} | {screen_url（クエリ除去済み）} | — | TC-00Y | ①…→②… |
```

### 組み立てルール

- **確認対象**: オブジェクト・画面のラベル（日本語表示名）を先頭に書く。API名は括弧補助のみ（例: `申込レコード（BusinessTraveler__c）`）
- **操作手順**: 以下の優先順位で転記する
  1. test-spec.md の「テスト手順」列（記載があればそのまま転記）
  2. `backlog-repro-runner` の再現手順（investigation.md 由来の Step-by-step）
  3. 上記いずれも無い場合は「前提・データ準備」＋「実行アクション」列から自然文で要約する
- **行の省略**: 対象レコード・URLが存在しない項目（例: ロールバック済みで永続化されていないテストデータ）は行を出さない。空欄・ダミーURLを並べない
- 表が空になる場合（目視対象が一切無い）はブロック自体を出力しない

---

## 5. created_records.txt の統一フォーマット

Phase 1.6（backlog-repro-runner）と /test（auto-evidence-runner）で同一フォーマットに統一する:

```
{SObjectAPI名}|{RecordId}|{Name または識別値}|{関連TC/仮説番号}
```

- 区切り文字は `|`（Name にカンマが含まれるケースがあるため CSV のカンマ区切りより安全）
- 既存の `backlog-repro-runner.md`（`SObject,Id` 形式）を読む処理がある場合は、カンマ区切りとの後方互換のため `,` `|` どちらの区切りでも1行1レコードとしてパースする
