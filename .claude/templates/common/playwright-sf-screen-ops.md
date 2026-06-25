# Playwright Salesforce 画面操作 共通手順

Salesforce Sandbox での Playwright 画面操作に関する共通手順。
このファイルを Read したエージェントは以下の手順・指針に従う。

---

## 本番ガード（必須・最初に実行）

Sandbox 接続確認は `.claude/templates/common/sandbox-alias-check.md` を Read して実施する。
`isSandbox = True` でなければ即座に中止する。

---

## frontdoor 認証

```bash
sf org open --target-org "$SF_ALIAS" --url-only --json
```

JSON の `result.url` を `FRONTDOOR_URL` として取得する。

**セキュリティ（必須）**: accessToken（FRONTDOOR_URL に含まれる）は以下に絶対に出力しない:
- Write するファイル（証跡・ログ・レポート）
- コードブロックの return 値
- `browser_run_code_unsafe` の引数文字列（変数として展開した値をコードブロック文字列に埋め込む）

---

## ロケータ指針（Salesforce LWC/Aura・Shadow DOM 対応）

Salesforce の画面は LWC/Aura の Shadow DOM を持つため、固定セレクタ（`#id`・`.class`）は機能しない。以下を使う（いずれも Shadow DOM を自動貫通する）:

| ロケータ | 用途 |
|---|---|
| `page.getByText('ラベル名')` | 表示テキスト（ボタン・リンク・見出しなど） |
| `page.getByRole('button', {name: 'ラベル名'})` | ボタン・コントロール |
| `page.getByLabel('ラベル名')` | フォーム入力欄 |
| `page.locator('[aria-label="ラベル名"]')` | aria-label で特定する場合 |

`#id`・`.class` の固定セレクタは動的レンダリングで変わるため使わない。

---

## 1 コードブロック画面操作（基本骨格）

`mcp__playwright__browser_run_code_unsafe` に `async (page) => { ... }` を渡し、
navigate → 操作 → screenshot/return を**1往復（1 MCP コール）**に収める。

```javascript
async (page) => {
  // 画面に遷移（1件目のみ: await page.goto(FRONTDOOR_URL) でログインしてもよい）
  await page.goto('{対象URL}');
  await page.waitForLoadState('networkidle');
  // before 撮影
  await page.screenshot({path: '/絶対パス/xxx_before.png'});
  // 操作（ロケータ指針に従う）
  await page.getByText('{ラベル}').click();
  await page.waitForLoadState('networkidle');
  // after 撮影
  await page.screenshot({path: '/絶対パス/xxx.png'});
  // DOM return（エージェントが .txt に Write する）
  return JSON.stringify({url: page.url(), text: await page.locator('body').innerText()});
}
```

**パス指定**: `page.screenshot({path: ...})` には**絶対パス**を使う（変数を展開した実パス文字列を埋め込む）。

### 操作待機パターン

- 画面遷移後: `page.waitForLoadState('networkidle')`
- 特定要素の出現: `page.waitForSelector('[aria-label="..."]')`
- アニメーション考慮: `page.waitForTimeout(500)` （最終手段のみ）

---

## フォールバック手順（コードブロックが失敗した場合）

コードブロックがロケータ不一致・タイムアウトで失敗した場合:

1. `mcp__playwright__browser_snapshot` で現在の DOM を取得し、実際の aria-label・テキスト・ロール等を確認する
2. コードブロックのロケータ・waitFor 条件を修正して `mcp__playwright__browser_run_code_unsafe` を再実行する
3. 2 回目も失敗した場合は、個別の `mcp__playwright__browser_click` / `mcp__playwright__browser_type` 等を使って対話的に操作する

---

## Login As（複数ユーザ・権限別確認）

### 前提チェック（対象 TC/手順の最初に 1 回だけ実施）

```javascript
async (page) => {
  await page.goto('/lightning/setup/LoginAccessPolicies/home');
  await page.waitForLoadState('networkidle');
  const text = await page.locator('body').innerText();
  return text;
}
```

返却テキストに「管理者が任意のユーザーとしてログイン」が確認できれば有効。
文言がない場合は Login As 不可として記録し、当該ユーザが必要な手順を「要手動（Login As 不可）」として記録する。

### 実ユーザ名の解決

プロファイル名から SOQL で実ユーザ名を取得する:

```bash
sf data query --target-org "$SF_ALIAS" \
  -q "SELECT Username, Name, Profile.Name FROM User WHERE Profile.Name = '{プロファイル名}' AND IsActive = true"
```

複数該当時は Name が対象と一致するものを選ぶ。組織クエリで特定できない場合のみユーザに 1 回質問する（パスワード不要）。

### Login As 操作（各ユーザに対して 1 コードブロック）

```javascript
async (page) => {
  // ユーザ管理ページに遷移（管理者セッション流用）
  await page.goto('/lightning/setup/ManageUsers/home');
  await page.waitForLoadState('networkidle');
  // ユーザ検索
  const searchBox = page.getByLabel('検索').or(page.getByPlaceholder('検索'));
  await searchBox.fill('{ユーザ名}');
  await page.keyboard.press('Enter');
  await page.waitForLoadState('networkidle');
  // ユーザ名リンクをクリックしてユーザ詳細ページへ
  await page.getByText('{ユーザ名}').first().click();
  await page.waitForLoadState('networkidle');
  // Login As ボタンをクリック
  await page.getByRole('button', {name: 'ユーザに代わってログイン'}).click();
  await page.waitForLoadState('networkidle');
  // 対象画面に遷移
  // ※ page.goto() は URL/パスのみ受け付ける。アプリ名しかない場合はアプリランチャ経由:
  //   await page.getByRole('button', {name: 'アプリケーションランチャー'}).click();
  //   await page.getByText('{アプリ名}').click();
  await page.goto('{対象画面URL}');
  await page.waitForLoadState('networkidle');
  // 操作・撮影
  await page.screenshot({path: '/絶対パス/xxx.png'});
  const text = await page.locator('body').innerText();
  // プロキシ解除（管理者セッションに戻る）― 毎ユーザ必ず実行
  await page.goto('/secur/logout.jsp');
  await page.waitForLoadState('networkidle');
  return JSON.stringify({url: page.url(), text: text});
}
```

**注意**: プロキシ解除 `/secur/logout.jsp` は**毎ユーザ必ず実行**（次ユーザのログイン前に管理者セッションに戻る）。

ユーザ名リンクの特定が難しい場合は先に `mcp__playwright__browser_snapshot` で DOM を確認してからコードブロックに組み込む。

---

## 現象観察ログ（バグ再現・調査向け）

画面操作後に JavaScript エラー・ネットワーク失敗を採取するとバグ原因の特定に直結する。

### コンソールログ（JS エラー・警告）

```tool
mcp__playwright__browser_console_messages
```

`type: 'error'` の行を優先して記録する。LWC コンポーネントエラー・Apex コールアウトエラーが出ることが多い。

### ネットワークリクエスト（失敗した API コール）

```tool
mcp__playwright__browser_network_requests
```

`status >= 400` のリクエストを確認する。SOQL エラー・REST API エラー・カスタム Apex エンドポイントのエラーが出ることが多い。

これらは**バグが現れるタイミングの直後に採取**することで、原因追跡の証跡として機能する。

---

## セキュリティ規約（全操作共通・必須）

- **FRONTDOOR_URL（accessToken 含む）をコードブロック引数に直書きしない**（エージェント変数として展開した値を文字列に埋め込む）
- `browser_run_code_unsafe` は RCE 相当のため **Sandbox セッション限定**で使う
- accessToken はいかなる形でもファイル・ログ・証跡・return 値に出力しない
- 操作完了後は必ず `mcp__playwright__browser_close` でセッションを閉じる
