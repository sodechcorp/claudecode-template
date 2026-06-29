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

## 高速待機（networkidle 禁止）

**`waitForLoadState('networkidle')` は Salesforce Lightning で使わない。**

Salesforce Lightning は EMP/CometD のロングポーリングにより通信が途切れず、`networkidle` がほぼ成立しない。毎遷移で既定タイムアウト（Playwright デフォルト 30 秒）まで空待ちし、UI ケース数 × 遷移数 × 数十秒で線形に膨らむ。

代わりに **`waitSfReady`** ヘルパーを使う。各コードブロック内で以下のように定義して呼び出す:

```javascript
async function waitSfReady(page) {
  // domcontentloaded で DOM 確定後、Lightning スピナーが消えるまで待つ
  await page.waitForLoadState('domcontentloaded');
  await page.locator('.slds-spinner, lightning-spinner')
    .first().waitFor({ state: 'hidden', timeout: 15000 }).catch(() => {});
}
```

- 各コードブロックの冒頭で `page.setDefaultTimeout(15000)` を設定し、ロケータ不一致を 15 秒で fail-fast させる
- 目的画面のアンカー要素が分かる場合は `waitSfReady` の後に `await page.waitForSelector('<アンカー>', { timeout: 15000 })` を併用する（より確実）
- `waitForTimeout` は引き続き最終手段のみ（アニメーション等で他に手がない場合）

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
  page.setDefaultTimeout(15000);
  async function waitSfReady(page) {
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.slds-spinner, lightning-spinner')
      .first().waitFor({ state: 'hidden', timeout: 15000 }).catch(() => {});
  }
  // 画面に遷移（1件目のみ: await page.goto(FRONTDOOR_URL) でログインしてもよい）
  await page.goto('{対象URL}');
  await waitSfReady(page);
  // before 撮影（fullPage: true で観点が viewport 外でも写る）+ before DOM 取得
  await page.screenshot({path: '/絶対パス/xxx_before.png', fullPage: true});
  const beforeText = await page.locator('body').innerText();
  // 操作（ロケータ指針に従う）
  await page.getByText('{ラベル}').click();
  await waitSfReady(page);
  // after 撮影（fullPage: true）
  await page.screenshot({path: '/絶対パス/xxx.png', fullPage: true});
  // DOM return（エージェントが after .txt に Write する。beforeText は before .txt に Write する）
  return JSON.stringify({url: page.url(), beforeText, text: await page.locator('body').innerText()});
}
```

**パス指定**: `page.screenshot({path: ...})` には**絶対パス**を使う（変数を展開した実パス文字列を埋め込む）。

### 操作待機パターン

- 画面遷移後: `await waitSfReady(page)`（domcontentloaded＋スピナー消滅を待つ）
- 特定アンカー要素の出現: `await page.waitForSelector('[aria-label="..."]', { timeout: 15000 })`（目的画面固有要素が分かる場合に `waitSfReady` と併用）
- アニメーション考慮: `await page.waitForTimeout(500)`（最終手段のみ）
- ❌ `page.waitForLoadState('networkidle')` — Salesforce Lightning では成立しないため使用禁止（→「高速待機」セクション参照）

---

## 先読み snapshot（ロケータ確定の事前確認）

Salesforce の画面は LWC/Aura の Shadow DOM レンダリングが動的なため、ロケータが事前に確定できない場合がある。**ロケータが不確実・動的な画面**では、コードブロックを書く前に `mcp__playwright__browser_snapshot` を 1 回取得して実際の aria-label・テキスト・ロールを確認してからロケータを確定することで、失敗→snapshot→再実行の往復を削減できる。

- 先読み snapshot は `waitSfReady(page)` 後（DOM 確定後）に取得する
- **固定 aria-label が既知の画面（設定画面・標準 UI 等）では先読みを省略してよい**（乱発抑制）
- 先読みした DOM から実際の aria-label・ロール・テキストを確認し、それをコードブロックに埋め込む
- 先読み snapshot は証跡として保存しない（参照のみ）

```javascript
// 先読み snapshot の例（ロケータ確定前・証跡保存なし）
async (page) => {
  page.setDefaultTimeout(15000);
  async function waitSfReady(page) {
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.slds-spinner, lightning-spinner')
      .first().waitFor({ state: 'hidden', timeout: 15000 }).catch(() => {});
  }
  await page.goto('{対象URL}');
  await waitSfReady(page);
  // DOM を確認してロケータを確定する（参照のみ）
  return await page.locator('body').innerText();
}
```

この後 `mcp__playwright__browser_snapshot` でのスナップショット確認、または上記コードブロックの返却テキストからロケータを確定し、本番操作コードブロックに組み込む。

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
  page.setDefaultTimeout(15000);
  async function waitSfReady(page) {
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.slds-spinner, lightning-spinner')
      .first().waitFor({ state: 'hidden', timeout: 15000 }).catch(() => {});
  }
  await page.goto('/lightning/setup/LoginAccessPolicies/home');
  await waitSfReady(page);
  // アンカー要素（設定ページ固有テキスト）の出現で遷移完了を確認
  await page.waitForSelector('text=ログインアクセスポリシー', { timeout: 15000 }).catch(() => {});
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

### Login As 操作（ユーザ単位バッチ — 1 Login As → 全 TC → 1 logout）

**バッチ化の原則**: 同じユーザが対象の TC を全てまとめて 1 コードブロックで実行する。TC ごとに Login As/logout を往復しない。

```javascript
async (page) => {
  page.setDefaultTimeout(15000);
  async function waitSfReady(page) {
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.slds-spinner, lightning-spinner')
      .first().waitFor({ state: 'hidden', timeout: 15000 }).catch(() => {});
  }

  // ─── Login As（このユーザの TC 群を開始する前に 1 回だけ実行）───
  await page.goto('/lightning/setup/ManageUsers/home');
  await waitSfReady(page);
  const searchBox = page.getByLabel('検索').or(page.getByPlaceholder('検索'));
  await searchBox.fill('{ユーザ名}');
  await page.keyboard.press('Enter');
  await waitSfReady(page);
  await page.getByText('{ユーザ名}').first().click();
  await waitSfReady(page);
  await page.getByRole('button', {name: 'ユーザに代わってログイン'}).click();
  await waitSfReady(page);

  // ─── 当該ユーザの TC を連続撮影（TC が増えてもここに追加するだけ）───
  // TC-XXX: {観点}
  await page.goto('{対象画面URL_1}');
  await waitSfReady(page);
  // before 撮影（fullPage: true）+ before DOM 取得
  await page.screenshot({path: '/絶対パス/{No}_xxx_before.png', fullPage: true});
  const beforeText1 = await page.locator('body').innerText();
  // （操作があれば）
  await page.getByText('{ラベル}').click();
  await waitSfReady(page);
  // after 撮影（fullPage: true）
  await page.screenshot({path: '/絶対パス/{No}_xxx.png', fullPage: true});
  const text1 = await page.locator('body').innerText();

  // TC-YYY: {観点} — 同ユーザの次 TC はそのまま続ける（再ログイン不要）
  await page.goto('{対象画面URL_2}');
  await waitSfReady(page);
  await page.screenshot({path: '/絶対パス/{No2}_yyy_before.png', fullPage: true});
  const beforeText2 = await page.locator('body').innerText();
  await page.screenshot({path: '/絶対パス/{No2}_yyy.png', fullPage: true});
  const text2 = await page.locator('body').innerText();

  // ─── プロキシ解除（このユーザの全 TC 完了後に 1 回だけ実行）───
  await page.goto('/secur/logout.jsp');
  await waitSfReady(page);

  // エージェントは text → after .txt に、beforeText → before .txt に Write する
  return JSON.stringify([
    {no: '{No}',  url: page.url(), beforeText: beforeText1, text: text1},
    {no: '{No2}', url: page.url(), beforeText: beforeText2, text: text2},
  ]);
}
```

**注意**:
- プロキシ解除 `/secur/logout.jsp` は**当該ユーザの全 TC 完了後に 1 回だけ**実行（次ユーザの Login As 前に管理者セッションに戻る）
- 複数ユーザがいる場合は**ユーザ分コードブロックを繰り返す**（1ユーザ = 1コードブロック、TC 数は各コードブロック内で吸収）
- ユーザ名リンクの特定が難しい場合は先に `mcp__playwright__browser_snapshot` で DOM を確認してからコードブロックに組み込む

---

## Login As（コミュニティ / Experience Cloud ユーザー）

お客様ユーザー（Experience Cloud／コミュニティライセンス）は**内部の ManageUsers 経由 Login As と操作が異なる**。  
コミュニティ / お客様ユーザーへの Login As は**必ず `自動`**で実施する（`要手動` 扱い禁止）。

### 前提確認（コミュニティ Login As の可否）

```bash
# コミュニティ Contact（外部ユーザー）を SOQL で確認する
sf data query --target-org "$SF_ALIAS" \
  -q "SELECT Id, Username, Name, Profile.Name, ContactId, IsActive FROM User
      WHERE Profile.Name LIKE '%Customer%'
         OR Profile.Name LIKE '%コミュニティ%'
         OR Profile.Name LIKE '%Community%'
         OR Profile.Name LIKE '%Partner%'
         OR Profile.Name LIKE '%Portal%'
      AND IsActive = true LIMIT 10"
```

`ContactId` が存在するユーザーはコミュニティ外部ユーザー。

### コミュニティ Login As 操作手順

```javascript
async (page) => {
  page.setDefaultTimeout(20000);
  async function waitSfReady(page) {
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.slds-spinner, lightning-spinner')
      .first().waitFor({ state: 'hidden', timeout: 20000 }).catch(() => {});
  }

  // ─── ステップ1: 対象コミュニティユーザーの Contact ページへ遷移 ───
  // 事前 SOQL で取得した ContactId を使う
  await page.goto('/lightning/r/Contact/{ContactId}/view');
  await waitSfReady(page);

  // ─── ステップ2: 「Experience Cloud ユーザー」または「ユーザーとしてログイン」ボタンをクリック ───
  // 表示されるボタン名は SF 組織設定・言語により異なる
  const loginAsBtn = page.getByRole('button', {name: 'ユーザーとしてログイン'})
    .or(page.getByRole('button', {name: 'Log in to Experience as User'}))
    .or(page.getByRole('button', {name: 'Experience でユーザーとしてログイン'}));
  // ボタンが直接見えない場合は Actions メニュー経由
  if (!(await loginAsBtn.isVisible().catch(() => false))) {
    await page.locator('.actionsMenu, [title="Show 1 more action"], button:has-text("...")').first().click().catch(() => {});
    await page.waitForTimeout(500);
  }
  await loginAsBtn.first().click();
  await waitSfReady(page);

  // ─── ステップ3: コミュニティ画面（お客様ユーザー視点）での TC 操作 ───
  // ログイン後は Lightning ではなくコミュニティサイト URL に遷移する
  // 対象フロー（例: CopyQuoteByCustomer）はコミュニティのホームから起動する
  const currentUrl = page.url();
  // TC-XXX: {観点}
  // 例: CopyQuoteByCustomer フローを起動する場合
  //   await page.goto(currentUrl.replace('/s/', '/s/') + '?flowName=CopyQuoteByCustomer');
  await page.screenshot({path: '/絶対パス/evidence/before/{No}_before.png', fullPage: true});
  const beforeText = await page.locator('body').innerText();
  // （フロー操作）
  await page.screenshot({path: '/絶対パス/evidence/after/screen/{No}_xxx.png', fullPage: true});
  const afterText = await page.locator('body').innerText();

  // ─── ステップ4: コミュニティセッション終了 → 管理者に戻る ───
  // コミュニティ上で管理者に戻るには以下のいずれかを使う
  // 方法A: SF 管理者 URL に直接移動（セッションが管理者に戻る）
  await page.goto('/lightning/setup/home');
  await waitSfReady(page);
  // 方法B: コミュニティヘッダーに「管理者に戻る」リンクがある場合はクリック
  // await page.getByText('管理者として戻る').or(page.getByText('Return to Admin')).click().catch(() => {});

  return JSON.stringify({no: '{No}', beforeText, text: afterText});
}
```

**コミュニティ Login As 特有の注意点**:
- ログイン後の遷移先は **Lightning ではなくコミュニティサイトの URL**（例: `https://xxx.force.com/s/`）
- 内部ユーザー向け `/secur/logout.jsp` での管理者復帰はコミュニティセッションでは効かない場合あり → `/lightning/setup/home` への直接遷移で管理者セッションに戻る
- 「ユーザーとしてログイン」ボタンが Contact ページに表示されない場合は、組織の「Experience Cloud サイト管理」で「ユーザーとしてログイン」を有効化する必要がある（Settings → Digital Experiences → Settings）
- 判定は必要なければボタンを探さず `mcp__playwright__browser_snapshot` で DOM を先に確認してから操作コードを組む

### ユーザー種別の判定フロー

```
対象ユーザーのプロファイルを確認
│
├─ 社内プロファイル（標準 / システム管理者 / カスタム内部）
│  → 通常 Login As（ManageUsers → ユーザに代わってログイン）
│
└─ 外部プロファイル（Customer Community / Partner / コミュニティ / Portal 系）
   → コミュニティ Login As（Contact ページ → ユーザーとしてログイン）
```

---

## 並列 UI 証跡（複数コンテキスト）

**読み取り専用かつユーザ切替なし**の TC のみが対象。データ作成/更新を伴うケースと Login As ケースは逐次を維持する。

### 仕組み

`page.context().browser().newContext()` で TC ごとに独立したブラウザコンテキストを作成し、各コンテキストが自前で `goto(FRONTDOOR_URL)` ログイン → 割当 TC を撮影 → コンテキストを閉じる。`max_workers_ui`（デフォルト3）件ずつ `Promise.all` でチャンク処理する。

### 骨格コード

```javascript
async (page) => {
  const MAX_WORKERS = 3; // max_workers_ui を展開
  const FRONTDOOR = 'FRONTDOOR_URL_HERE'; // 変数展開で埋め込む（accessToken は直書き禁止）

  async function waitSfReady(p) {
    await p.waitForLoadState('domcontentloaded');
    await p.locator('.slds-spinner, lightning-spinner')
      .first().waitFor({ state: 'hidden', timeout: 15000 }).catch(() => {});
  }

  // 並列可 TC のリスト（エージェントが TC 分だけ定義する）
  const tasks = [
    { no: 'TC-001', url: '{対象URL_1}', beforePath: '/絶対パス/TC-001_xxx_before.png', afterPath: '/絶対パス/TC-001_xxx.png', txtPath: '/絶対パス/TC-001_xxx.txt' },
    { no: 'TC-003', url: '{対象URL_2}', beforePath: '/絶対パス/TC-003_yyy_before.png', afterPath: '/絶対パス/TC-003_yyy.png', txtPath: '/絶対パス/TC-003_yyy.txt' },
    // ... TC 数だけ追加
  ];

  const results = [];
  // MAX_WORKERS 件ずつチャンク処理
  for (let i = 0; i < tasks.length; i += MAX_WORKERS) {
    const chunk = tasks.slice(i, i + MAX_WORKERS);
    const chunkResults = await Promise.all(chunk.map(async (t) => {
      let ctx;
      try {
        ctx = await page.context().browser().newContext();
        const p = await ctx.newPage();
        p.setDefaultTimeout(15000);
        await p.goto(FRONTDOOR);
        await waitSfReady(p);
        await p.goto(t.url);
        await waitSfReady(p);
        // before 撮影（fullPage: true）+ before DOM 取得
        await p.screenshot({ path: t.beforePath, fullPage: true });
        const beforeText = await p.locator('body').innerText();
        // ケース固有操作があればここに挿入
        // after 撮影（fullPage: true）
        await p.screenshot({ path: t.afterPath, fullPage: true });
        const text = await p.locator('body').innerText();
        return { no: t.no, ok: true, beforeText, text, url: p.url() };
      } catch (e) {
        return { no: t.no, ok: false, error: String(e) };
      } finally {
        if (ctx) await ctx.close();
      }
    }));
    results.push(...chunkResults);
  }
  return JSON.stringify(results);
}
```

### newContext 不可時のフォールバック

`page.context().browser().newContext()` が Playwright MCP の制約で使えない場合は、単一セッションの逐次処理に自動フォールバックする。その場合でも Tier 1（`waitSfReady`）と Tier 2（Login As バッチ化）の高速化は有効。

### accessToken 秘匿（並列時も同じ規約）

`FRONTDOOR_URL` は変数として展開した値をコードブロック文字列に埋め込む。return 値・ファイル・ログに含めない。複数コンテキストに渡す場合も同様。

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
