# Playwright Salesforce 画面操作 共通手順

Salesforce Sandbox での Playwright 画面操作に関する共通手順。
このファイルを Read したエージェントは以下の手順・指針に従う。

---

## 本番ガード（必須・最初に実行）

Sandbox 接続確認は `.claude/templates/common/sandbox-alias-check.md` を Read して実施する。
`isSandbox = True` でなければ即座に中止する。

---

## 未検証 URL への navigate 前チェック（必須・実績インシデント由来）

**実績インシデント（2026-08-12・GF案件）**: 「トークン取得オプションが表示されないこと」を確認する目的で `/_ui/system/security/ResetApiTokenConfirm` に `page.goto()` した。URL 名に `Confirm` が含まれるため確認ダイアログを挟むと判断したが、実際には **遷移した時点でセキュリティトークンのリセットが実行され**、新トークンが対象ユーザーのメールに送信された。Sandbox 内で完結したため実害はなかったが、本番相当の操作が無警告で走った。

Salesforce Setup 配下（`/_ui/`・`/lightning/setup/` 等）の URL は、**名前が「Confirm」「Verify」等の確認系に見えても、`page.goto()` した時点で処理が実行される（GET 相当に見えて実質 POST）ケースが存在する**。「確認画面だろう」という見た目の判断だけで実行対象を決めない。

**適用対象**: 過去にこのファイルで手順化されていない Setup URL、または初めて扱う画面・操作（既知の定型手順として本ファイルに記載済みの URL・Login As 等は対象外）。

**実行前に確認する内容**（いずれかを満たしてから `page.goto()` する）:
1. 対象 URL の挙動を help.salesforce.com 等の公式ドキュメントで確認し、「確認ダイアログを挟む画面」か「遷移＝即時実行」かを判定する
2. 公式ドキュメントで確認できない場合は、**URL 直打ちを避け、正規の Setup メニュー操作（`browser_click` でボタン・リンクをクリックする通常のナビゲーション）で遷移し、実際に確認ダイアログが挟まるかを目視してから次の操作に進む**
3. 上記いずれも実施できず、かつ操作の結果が不可逆（トークン再発行・パスワードリセット・権限変更・レコード削除等）である可能性を排除できない場合は、実行せずユーザーに確認を取る

「Sandbox だから」「開くだけだから」は実行を正当化する理由にならない。Sandbox 限定であっても、対象ユーザーへのメール送信・認証情報の無効化等、影響が Sandbox 内に閉じない副作用がありうる。

---

## frontdoor 認証

**前提**: 対象エイリアスが sf CLI に有効な状態で認証済みであること。未確認の場合は `sandbox-alias-check.md` の「認証状態の確認」を先に実施する（未認証・期限切れのまま実行すると本コマンドが失敗する）。

**1件目の遷移先（相対パス）が判明している場合（推奨）**: `--path` に渡すと `FRONTDOOR_URL` の `retURL` にその画面が埋め込まれ、ログイン直後に対象画面へ直接着地する（`--path` 省略時は既定の Lightning ホームに着地してから別途アプリ内遷移が必要になり、その分の画面読み込みが毎回無駄になる）。

```bash
sf org open --target-org "$SF_ALIAS" --url-only --json --path "{1件目の対象画面の相対パス}"
```

**1件目の遷移先が未確定、またはクリック操作でしか到達できない場合**: `--path` を省略する。

```bash
sf org open --target-org "$SF_ALIAS" --url-only --json
```

JSON の `result.url` を `FRONTDOOR_URL` として取得する。`--path` 指定時は `page.goto(FRONTDOOR_URL)` の1回で1件目の対象画面まで到達するため、直後に続けていた個別ナビゲーションは不要になる。

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
  // 15 秒でタイムアウトした場合は catch で例外を握りつぶし、そのまま処理を続行する（fail-safe設計・呼び出し元への通知はない）
  await page.waitForLoadState('domcontentloaded');
  await page.locator('.slds-spinner, lightning-spinner')
    .first().waitFor({ state: 'hidden', timeout: 15000 }).catch(() => {});
}
```

- 各コードブロックの冒頭で `page.setDefaultTimeout(15000)` を設定し、ロケータ不一致を 15 秒で fail-fast させる
- 目的画面のアンカー要素が分かる場合は `waitSfReady` の後に `await page.waitForSelector('<アンカー>', { timeout: 15000 })` を併用する（より確実。**`waitSfReady` は 15 秒超過時にタイムアウトを無条件で握りつぶすため、判定が必要な遷移ではこの併用が必須**）
- `waitForTimeout` は引き続き最終手段のみ（アニメーション等で他に手がない場合）

---

## DOM テキストの直接保存（saveText・LLM 経由の書き戻し回避）

`browser_run_code_unsafe` の実行環境には `fs`/`require`/`process` が一切なく（実機確認済み: `require('fs')` → `require is not defined`、`import('node:fs')` → `A dynamic import callback was not specified`、`globalThis` 走査でも該当グローバルなし）、コードブロック内から直接ファイル書き込みはできない。DOM 全文（`page.locator('body').innerText()`）を `return` してエージェント(LLM)が `Write` する従来方式は、DOM 全文が毎回 LLM の入力トークン（tool result 受信）・出力トークン（Write 引数として再生成）の両方を経由し、TC 数×採取回数分のコストが線形に積み上がる（テスト実行全体のボトルネックの主要因）。

代わりに Playwright の download API（`Blob` 生成 → `<a download>` クリック → `page.waitForEvent('download')` → `download.saveAs(path)`）を使うと、DOM 全文を LLM のコンテキストへ一度も渡さずファイルへ直接保存できる。download イベントが発火しなかった場合のみ `false` を返し、呼び出し側は `text`（`beforeText`）を `results`/`return` に積んでエージェントに Write でフォールバックさせる（**保存経路が変わるだけで証跡が失われることはない**）。

各コードブロックの冒頭で `waitSfReady` と同様にインラインで定義して使う:

```javascript
const ERROR_SIGNATURES = ['問題が発生しました', '問題が発生しているようです', 'is malformed',
  '関連リストはレイアウトにありません', '権限が不十分です', 'Insufficient Privileges',
  'このページには到達できません', 'URL No Longer Exists', '予期しないエラーが発生しました', 'Unexpected Error'];

async function saveText(p, text, path) {
  try {
    const downloadPromise = p.waitForEvent('download', { timeout: 8000 }).catch(() => null);
    await p.evaluate(({ text, filename }) => {
      const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.download = filename;
      a.href = url;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    }, { text, filename: path.split(/[\\/]/).pop() });
    const download = await downloadPromise;
    if (!download) return false; // 発火しなかった → 呼び出し側で text をフォールバック返却
    await download.saveAs(path);
    return true;
  } catch (_) {
    return false; // 例外時も同様にフォールバック
  }
}
```

**使い方**: `const saved = await saveText(page, text, '/絶対パス/xxx.txt'); results.push({..., ...(saved ? {} : { text })});`（`saved` が `false` の要素だけ、呼び出し元エージェントが受け取った `text` を Write する）。`errorSignature: ERROR_SIGNATURES.find(s => text.includes(s)) || null` と `thinDom: text.length < 200` もこの時点で計算し `results` に積む（旧来「エージェントが `text` を読んで Write 前に判定する」方式は、`text` がエージェントに渡らなくなったため機能しない。判定は必ずコードブロック側で行う）。

**frontdoor 認証後、最初の Salesforce（Lightning）画面へ遷移した状態で 1 回だけ probe を実行して発火確認する**（`newContext` 不可時のフォールバックと同じ考え方）。**about:blank 等の CSP が適用されない画面で probe すると必ず `OK` になり検証にならない**ため、必ず対象組織の実画面上で実行すること。probe は他のコードブロックと独立したスコープで評価されるため `saveText` 定義をそのまま貼り込んで自己完結させる（外部定義への参照は不可。定義を省略すると `saveText is not defined` で必ず失敗する）:
```javascript
async (page) => {
  async function saveText(p, text, path) {
    try {
      const downloadPromise = p.waitForEvent('download', { timeout: 8000 }).catch(() => null);
      await p.evaluate(({ text, filename }) => {
        const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.download = filename;
        a.href = url;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
      }, { text, filename: path.split(/[\\/]/).pop() });
      const download = await downloadPromise;
      if (!download) return false;
      await download.saveAs(path);
      return true;
    } catch (_) {
      return false;
    }
  }
  // 保存先は証跡ディレクトリ外（各エージェントのログ／作業ディレクトリ: {log_dir} や {証跡保存先}/logs 等）にする。
  // evidence 配下だと .txt 索引・Step 4 の find に混入するため
  const ok = await saveText(page, 'probe', '{log_dir}/_saveText_probe.txt');
  return ok ? 'saveText: OK' : 'saveText: NG（download 不発火。以降は text を直接 return してエージェント側 Write に統一する）';
}
```
probe が NG だった場合、そのセッション内では `saveText` の呼び出し自体を省略し、最初から `text`/`beforeText` を `results` に積む（毎回 8 秒のタイムアウト待ちを繰り返さないため）。**Salesforce Lightning の実画面での発火は claude-temp 側では未検証**（about:blank での実機検証のみ実施済み）。CSP・iframe 構成等で発火しない場合はこの probe とフォールバックで自動的に旧方式（LLM 経由 Write）に切り替わり、性能は改善しないが証跡欠落は起きない。

---

## DOM 本文取得（getPageText・グローバルヘッダーノイズの除去）

`page.locator('body').innerText()` は画面全体を無条件取得するため、Lightning 共通ヘッダー（グローバルナビ・検索・通知等。ARIA ランドマーク `role="banner"`）が毎回のスナップショットに定型ノイズとして混入し、判定対象の肥大化や（`saveText` の download 不発火時フォールバックでの）LLM 再入力コスト増につながる。

代わりに body を複製した DOM 上で `role="banner"` 要素を除去してから `innerText` を取得する `getPageText` を使う。対象要素が存在しない画面（Setup／Flow／コミュニティ等）では除去が空振りするだけで、除去前と同じ全文がそのまま返る（実機確認済み: `data:` URL 上で複製 DOM の除去挙動と、`role="banner"` 非存在時に無変化であることの両方を確認済み）。

```javascript
async function getPageText(page) {
  try {
    return await page.evaluate(() => {
      const clone = document.body.cloneNode(true);
      clone.querySelectorAll('[role="banner"]').forEach(el => el.remove());
      return clone.innerText;
    });
  } catch (_) {
    return await page.locator('body').innerText(); // 失敗時は従来どおりの全文取得にフォールバック
  }
}
```

**適用範囲・既知の限界**: 除去対象は `role="banner"` のみ。標準レコードページの Chatter フィードパネル等は安定した共通セレクタが未確認のため対象外（画面種別ごとに DOM 構造が異なり、採用には実機 Sandbox でのセレクタ検証が別途必要）。以降の各コードブロック例では、DOM 本文取得に `page.locator('body').innerText()` の代わりに `getPageText(page)`（並列コンテキストでは `getPageText(p)`）を使う。`waitSfReady`/`saveText` と同様、コードブロックごとにインラインで定義する。

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
  const ERROR_SIGNATURES = ['問題が発生しました', '問題が発生しているようです', 'is malformed',
    '関連リストはレイアウトにありません', '権限が不十分です', 'Insufficient Privileges',
    'このページには到達できません', 'URL No Longer Exists', '予期しないエラーが発生しました', 'Unexpected Error'];
  async function saveText(p, text, path) {
    // DOM 全文を LLM 経由で書き戻さず直接保存する（「DOM テキストの直接保存」節参照）
    try {
      const downloadPromise = p.waitForEvent('download', { timeout: 8000 }).catch(() => null);
      await p.evaluate(({ text, filename }) => {
        const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.download = filename;
        a.href = url;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
      }, { text, filename: path.split(/[\\/]/).pop() });
      const download = await downloadPromise;
      if (!download) return false;
      await download.saveAs(path);
      return true;
    } catch (_) {
      return false;
    }
  }
  async function getPageText(page) {
    // グローバルヘッダー（role="banner"）ノイズを除去して取得する（「DOM 本文取得」節参照）
    try {
      return await page.evaluate(() => {
        const clone = document.body.cloneNode(true);
        clone.querySelectorAll('[role="banner"]').forEach(el => el.remove());
        return clone.innerText;
      });
    } catch (_) {
      return await page.locator('body').innerText();
    }
  }
  // 画面に遷移（1件目かつ --path 指定済みなら FRONTDOOR_URL 自体が対象画面。それ以外は対象URLへ直接遷移）
  await page.goto('{対象URL}');
  await waitSfReady(page);
  // before 撮影（fullPage: true で観点が viewport 外でも写る）+ before DOM 取得
  await page.screenshot({path: '/絶対パス/xxx_before.png', fullPage: true, animations: 'disabled', scale: 'css'});
  const beforeText = await getPageText(page);
  const beforeSaved = await saveText(page, beforeText, '/絶対パス/xxx_before.txt');
  // 操作（ロケータ指針に従う）
  await page.getByText('{ラベル}').click();
  await waitSfReady(page);
  // after 撮影（fullPage: true）
  await page.screenshot({path: '/絶対パス/xxx.png', fullPage: true, animations: 'disabled', scale: 'css'});
  const text = await getPageText(page);
  const afterSaved = await saveText(page, text, '/絶対パス/xxx.txt');
  // saveText が true を返した分は保存済み。false の分だけエージェントが受け取って Write する
  return JSON.stringify({
    url: page.url(),
    textLen: text.length, thinDom: text.length < 200,
    errorSignature: ERROR_SIGNATURES.find(s => text.includes(s)) || null,
    ...(beforeSaved ? {} : { beforeText }),
    ...(afterSaved ? {} : { text }),
  });
}
```

**重要**: この return には（保存に成功した通常ケースでは）**DOM 全文が含まれない**。呼び出し元エージェントが DOM 本文そのもの（症状再現ログ等・.txt に保存済みの内容）を判定・分析に使う必要がある場合は、return の `textLen`/`thinDom`/`errorSignature` だけでは情報が足りないことがある。その場合は保存先の `.txt` を **`Read` ツールで読む**（`saveText` が `false` を返した要素は return の `beforeText`/`text` をそのまま使う）。DOM 全文を再び `browser_run_code_unsafe` の return やコードブロック引数に載せて渡す設計に戻さないこと（今回の性能改修の前提が崩れる）。

**パス指定**: `page.screenshot({path: ...})` には**絶対パス**を使う（変数を展開した実パス文字列を埋め込む）。

**撮影オプション（必須）**: `page.screenshot()` は常に `{fullPage: true, animations: 'disabled', scale: 'css'}` を付ける。`animations` は既定値 `'allow'` のままだと Lightning のトースト・スピナー等の CSS アニメーションが収まるまで撮影内部の安定化待ちが発生する（`'disabled'` で即座に確定状態にして待ちを回避）。`scale` は既定値 `'device'` のままだと実行環境の `deviceScaleFactor`（HiDPI ディスプレイ等）がそのまま反映され、PNG が不要に大きくなる（`'css'` で CSS ピクセル基準に固定し肥大化を防ぐ）。

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
  async function getPageText(page) {
    // グローバルヘッダー（role="banner"）ノイズを除去して取得する（「DOM 本文取得」節参照）
    try {
      return await page.evaluate(() => {
        const clone = document.body.cloneNode(true);
        clone.querySelectorAll('[role="banner"]').forEach(el => el.remove());
        return clone.innerText;
      });
    } catch (_) {
      return await page.locator('body').innerText();
    }
  }
  await page.goto('{対象URL}');
  await waitSfReady(page);
  // DOM を確認してロケータを確定する（参照のみ）
  return await getPageText(page);
}
```

この後 `mcp__playwright__browser_snapshot` でのスナップショット確認、または上記コードブロックの返却テキストからロケータを確定し、本番操作コードブロックに組み込む。

---

## フォールバック手順（コードブロックが失敗した場合）

コードブロックがロケータ不一致・タイムアウトで失敗した場合:

1. まず `mcp__playwright__browser_run_code_unsafe` で軽量スキャン（下記コードブロック）を実行し、操作対象になりうる要素（button/a/input/select/textarea/role属性/aria-label属性を持つ要素）の tag・role・aria-label・テキストを一覧取得する。`page.locator()` は Shadow DOM を自動貫通するため LWC/Aura コンポーネント内部の要素も収集できる（`page.locator('.slds-spinner, lightning-spinner')` と同じ仕組み。「高速待機」セクション参照）。`mcp__playwright__browser_snapshot` のページ全体アクセシビリティツリー取得よりコストが小さい。

   ```javascript
   // フォールバック軽量スキャン（証跡保存なし・返却のみ）
   async (page) => {
     const selector = 'button, a, input, select, textarea, [role], [aria-label]';
     const handles = await page.locator(selector).all();
     const results = [];
     for (const el of handles.slice(0, 150)) {
       if (!(await el.isVisible().catch(() => false))) continue;
       results.push({
         tag: await el.evaluate(node => node.tagName.toLowerCase()),
         role: await el.getAttribute('role'),
         ariaLabel: await el.getAttribute('aria-label'),
         text: (await el.innerText().catch(() => '')).trim().slice(0, 40),
       });
     }
     return JSON.stringify(results);
   }
   ```

2. 軽量スキャンの結果から対象要素が特定できれば、コードブロックのロケータ・waitFor 条件を修正して `mcp__playwright__browser_run_code_unsafe` を再実行する
3. 軽量スキャンで対象要素が特定できない場合のみ `mcp__playwright__browser_snapshot` で現在の DOM 全体（アクセシビリティツリー）を取得し、実際の aria-label・テキスト・ロール等を確認する
4. 2 回目も失敗した場合は、個別の `mcp__playwright__browser_click` / `mcp__playwright__browser_type` 等を使って対話的に操作する

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
  async function getPageText(page) {
    // グローバルヘッダー（role="banner"）ノイズを除去して取得する（「DOM 本文取得」節参照）
    try {
      return await page.evaluate(() => {
        const clone = document.body.cloneNode(true);
        clone.querySelectorAll('[role="banner"]').forEach(el => el.remove());
        return clone.innerText;
      });
    } catch (_) {
      return await page.locator('body').innerText();
    }
  }
  await page.goto('/lightning/setup/LoginAccessPolicies/home');
  await waitSfReady(page);
  // アンカー要素（設定ページ固有テキスト）の出現で遷移完了を確認
  await page.waitForSelector('text=ログインアクセスポリシー', { timeout: 15000 }).catch(() => {});
  const text = await getPageText(page);
  return text;
}
```

返却テキストに「管理者が任意のユーザーとしてログイン」が確認できれば有効。
文言がない場合は Login As 不可として記録し、当該ユーザが必要な手順を「要手動（Login As 不可）」として記録する。

### 実ユーザ名の解決

プロファイル名から SOQL で実ユーザ名を取得する（`Id` は Login As 高速パス〈servlet.su 直接遷移〉の `suorgadminid` に使うため必ず取得する）:

```bash
sf data query --target-org "$SF_ALIAS" \
  -q "SELECT Id, Username, Name, Profile.Name FROM User WHERE Profile.Name = '{プロファイル名}' AND IsActive = true"
```

複数該当時は Name が対象と一致するものを選ぶ。組織クエリで特定できない場合のみユーザに 1 回質問する（パスワード不要）。

**組織 ID の解決**（Login As 高速パスの `oid` に使用。TC/手順全体で 1 回だけ取得しキャッシュする）:

```bash
sf data query --target-org "$SF_ALIAS" -q "SELECT Id FROM Organization LIMIT 1"
```

### Login As 操作（ユーザ単位バッチ — 1 Login As → 全 TC → 1 logout）

**バッチ化の原則**: 同じユーザが対象の TC を全てまとめて 1 コードブロックで実行する。TC ごとに Login As/logout を往復しない。

**高速パス優先の原則**: `servlet.su` への直接 URL 遷移（1 遷移）を第一候補にし、遷移後に成功を検証する。`servlet.su` は Salesforce の非公式・内部エンドポイント（公式ドキュメント記載なし）のため、委任管理者の Login As 権限設定・IP 制限・My Domain 設定等の組織固有事情で失敗しうる前提で扱い、**検証に失敗した場合のみ** ManageUsers 経由の GUI 操作（4 遷移）に自動フォールバックする。フォールバックが起きても結果は従来どおり成功する＝退行なし。

```javascript
async (page) => {
  page.setDefaultTimeout(15000);
  async function waitSfReady(page) {
    await page.waitForLoadState('domcontentloaded');
    await page.locator('.slds-spinner, lightning-spinner')
      .first().waitFor({ state: 'hidden', timeout: 15000 }).catch(() => {});
  }
  const ERROR_SIGNATURES = ['問題が発生しました', '問題が発生しているようです', 'is malformed',
    '関連リストはレイアウトにありません', '権限が不十分です', 'Insufficient Privileges',
    'このページには到達できません', 'URL No Longer Exists', '予期しないエラーが発生しました', 'Unexpected Error'];
  async function saveText(p, text, path) {
    // DOM 全文を LLM 経由で書き戻さず直接保存する（「DOM テキストの直接保存」節参照）
    try {
      const downloadPromise = p.waitForEvent('download', { timeout: 8000 }).catch(() => null);
      await p.evaluate(({ text, filename }) => {
        const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.download = filename;
        a.href = url;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
      }, { text, filename: path.split(/[\\/]/).pop() });
      const download = await downloadPromise;
      if (!download) return false;
      await download.saveAs(path);
      return true;
    } catch (_) {
      return false;
    }
  }
  function looksLikeLoginAsFailure(text, url) {
    const failMarkers = ['このページを表示する権限がありません', 'insufficient privileges', 'Invalid Session', 'ページが見つかりません', 'INVALID_SESSION_ID'];
    if (failMarkers.some(m => text.includes(m))) return true;
    if (/\/login\.jsp/.test(url)) return true; // ログイン画面に戻された＝失敗
    return false;
  }
  async function getPageText(page) {
    // グローバルヘッダー（role="banner"）ノイズを除去して取得する（「DOM 本文取得」節参照）
    try {
      return await page.evaluate(() => {
        const clone = document.body.cloneNode(true);
        clone.querySelectorAll('[role="banner"]').forEach(el => el.remove());
        return clone.innerText;
      });
    } catch (_) {
      return await page.locator('body').innerText();
    }
  }

  // ─── Login As 高速パス（servlet.su 直接遷移。上記で解決済みの OrgId/UserId を使う）───
  let loginAsOk = false;
  try {
    await page.goto('/servlet/servlet.su?oid={OrgId}&suorgadminid={UserId}&targetURL=%2Fhome%2Fhome.jsp');
    await waitSfReady(page);
    const checkText = await getPageText(page);
    loginAsOk = !looksLikeLoginAsFailure(checkText, page.url());
  } catch (e) {
    loginAsOk = false;
  }

  // ─── フォールバック: ManageUsers 経由の GUI 操作（高速パス失敗時のみ実行）───
  if (!loginAsOk) {
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
  }

  // ─── 当該ユーザの TC を連続撮影（TC が増えてもここに追加するだけ）───
  const results = [];
  // TC-XXX: {観点}
  await page.goto('{対象画面URL_1}');
  await waitSfReady(page);
  // before 撮影（fullPage: true）+ before DOM 取得（**書き込み動詞ありの TC のみ**。表示・参照のみは before を採取しない）
  await page.screenshot({path: '/絶対パス/{No}_xxx_before.png', fullPage: true, animations: 'disabled', scale: 'css'});
  const beforeText1 = await getPageText(page);
  const beforeSaved1 = await saveText(page, beforeText1, '/絶対パス/{No}_xxx_before.txt');
  // （操作があれば）
  await page.getByText('{ラベル}').click();
  await waitSfReady(page);
  // after 撮影（fullPage: true）
  await page.screenshot({path: '/絶対パス/{No}_xxx.png', fullPage: true, animations: 'disabled', scale: 'css'});
  const text1 = await getPageText(page);
  const afterSaved1 = await saveText(page, text1, '/絶対パス/{No}_xxx.txt');
  results.push({
    no: '{No}', ok: true, url: page.url(),
    textLen: text1.length, thinDom: text1.length < 200,
    errorSignature: ERROR_SIGNATURES.find(s => text1.includes(s)) || null,
    ...(beforeSaved1 ? {} : { beforeText: beforeText1 }),
    ...(afterSaved1 ? {} : { text: text1 }),
  });

  // TC-YYY: {観点} — 同ユーザの次 TC はそのまま続ける（再ログイン不要）
  await page.goto('{対象画面URL_2}');
  await waitSfReady(page);
  await page.screenshot({path: '/絶対パス/{No2}_yyy.png', fullPage: true, animations: 'disabled', scale: 'css'});
  const text2 = await getPageText(page);
  const afterSaved2 = await saveText(page, text2, '/絶対パス/{No2}_yyy.txt');
  results.push({
    no: '{No2}', ok: true, url: page.url(),
    textLen: text2.length, thinDom: text2.length < 200,
    errorSignature: ERROR_SIGNATURES.find(s => text2.includes(s)) || null,
    ...(afterSaved2 ? {} : { text: text2 }),
  });

  // ─── プロキシ解除（このユーザの全 TC 完了後に 1 回だけ実行）───
  await page.goto('/secur/logout.jsp');
  await waitSfReady(page);

  // saveText が true を返した分は保存済み。エージェントは beforeText/text が存在する要素（フォールバック）のみ Write する
  return JSON.stringify(results);
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
  const ERROR_SIGNATURES = ['問題が発生しました', '問題が発生しているようです', 'is malformed',
    '関連リストはレイアウトにありません', '権限が不十分です', 'Insufficient Privileges',
    'このページには到達できません', 'URL No Longer Exists', '予期しないエラーが発生しました', 'Unexpected Error'];
  async function saveText(p, text, path) {
    // DOM 全文を LLM 経由で書き戻さず直接保存する（「DOM テキストの直接保存」節参照）
    try {
      const downloadPromise = p.waitForEvent('download', { timeout: 8000 }).catch(() => null);
      await p.evaluate(({ text, filename }) => {
        const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.download = filename;
        a.href = url;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
      }, { text, filename: path.split(/[\\/]/).pop() });
      const download = await downloadPromise;
      if (!download) return false;
      await download.saveAs(path);
      return true;
    } catch (_) {
      return false;
    }
  }
  async function getPageText(page) {
    // グローバルヘッダー（role="banner"）ノイズを除去して取得する（「DOM 本文取得」節参照）
    try {
      return await page.evaluate(() => {
        const clone = document.body.cloneNode(true);
        clone.querySelectorAll('[role="banner"]').forEach(el => el.remove());
        return clone.innerText;
      });
    } catch (_) {
      return await page.locator('body').innerText();
    }
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
  await page.screenshot({path: '/絶対パス/evidence/before/{No}_before.png', fullPage: true, animations: 'disabled', scale: 'css'});
  const beforeText = await getPageText(page);
  const beforeSaved = await saveText(page, beforeText, '/絶対パス/evidence/before/{No}_before.txt');
  // （フロー操作）
  await page.screenshot({path: '/絶対パス/evidence/after/screen/{No}_xxx.png', fullPage: true, animations: 'disabled', scale: 'css'});
  const afterText = await getPageText(page);
  const afterSaved = await saveText(page, afterText, '/絶対パス/evidence/after/screen/{No}_xxx.txt');
  const afterUrl = page.url(); // 管理者復帰（ステップ4）前に確定させる（コミュニティ画面のURLを記録するため）

  // ─── ステップ4: コミュニティセッション終了 → 管理者に戻る ───
  // コミュニティ上で管理者に戻るには以下のいずれかを使う
  // 方法A: SF 管理者 URL に直接移動（セッションが管理者に戻る）
  await page.goto('/lightning/setup/home');
  await waitSfReady(page);
  // 方法B: コミュニティヘッダーに「管理者に戻る」リンクがある場合はクリック
  // await page.getByText('管理者として戻る').or(page.getByText('Return to Admin')).click().catch(() => {});

  // saveText が true を返した分は保存済み。エージェントは beforeText/text が存在する要素（フォールバック）のみ Write する
  return JSON.stringify({
    no: '{No}', ok: true, url: afterUrl,
    textLen: afterText.length, thinDom: afterText.length < 200,
    errorSignature: ERROR_SIGNATURES.find(s => afterText.includes(s)) || null,
    ...(beforeSaved ? {} : { beforeText }),
    ...(afterSaved ? {} : { text: afterText }),
  });
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
│  → 通常 Login As（servlet.su 直接遷移 → 失敗時のみ ManageUsers → ユーザに代わってログイン）
│
└─ 外部プロファイル（Customer Community / Partner / コミュニティ / Portal 系）
   → コミュニティ Login As（Contact ページ → ユーザーとしてログイン）
```

---

## 並列 UI 証跡（複数コンテキスト）

**読み取り専用かつユーザ切替なし**の TC のみが対象。データ作成/更新を伴うケースと Login As ケースは逐次を維持する。

### 仕組み

`page.context().browser().newContext()` で TC ごとに独立したブラウザコンテキストを作成する。frontdoor 認証は最初に1回だけ行い、その `storageState`（Cookie 等の認証状態）を全コンテキストの生成時（`newContext({storageState})`）に渡して使い回すことで、TC ごとの frontdoor 再ログインを回避する（各コンテキストは対象 URL へ直接遷移）。`max_workers_ui`（デフォルト3）件ずつ `Promise.all` でチャンク処理する。

### 骨格コード

```javascript
async (page) => {
  const MAX_WORKERS = 3; // max_workers_ui を展開
  const FRONTDOOR = 'FRONTDOOR_URL_HERE'; // 変数展開で埋め込む（accessToken は直書き禁止）
  const ERROR_SIGNATURES = ['問題が発生しました', '問題が発生しているようです', 'is malformed',
    '関連リストはレイアウトにありません', '権限が不十分です', 'Insufficient Privileges',
    'このページには到達できません', 'URL No Longer Exists', '予期しないエラーが発生しました', 'Unexpected Error'];

  async function waitSfReady(p) {
    await p.waitForLoadState('domcontentloaded');
    await p.locator('.slds-spinner, lightning-spinner')
      .first().waitFor({ state: 'hidden', timeout: 15000 }).catch(() => {});
  }

  async function saveText(p, text, path) {
    // DOM全文をLLM経由で書き戻さず Blob download 経由で直接保存する
    // （browser_run_code_unsafe の実行環境には fs/require が無く、コードブロック内から直接ファイル書き込みはできないため）
    try {
      const downloadPromise = p.waitForEvent('download', { timeout: 8000 }).catch(() => null);
      await p.evaluate(({ text, filename }) => {
        const blob = new Blob([text], { type: 'text/plain;charset=utf-8' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.download = filename;
        a.href = url;
        document.body.appendChild(a);
        a.click();
        a.remove();
        URL.revokeObjectURL(url);
      }, { text, filename: path.split(/[\\/]/).pop() });
      const download = await downloadPromise;
      if (!download) return false; // 発火しなかった → 呼び出し側で text をフォールバック返却
      await download.saveAs(path);
      return true;
    } catch (_) {
      return false;
    }
  }

  async function getPageText(p) {
    // グローバルヘッダー（role="banner"）ノイズを除去して取得する（「DOM 本文取得」節参照）
    try {
      return await p.evaluate(() => {
        const clone = document.body.cloneNode(true);
        clone.querySelectorAll('[role="banner"]').forEach(el => el.remove());
        return clone.innerText;
      });
    } catch (_) {
      return await p.locator('body').innerText();
    }
  }

  // 並列可 TC のリスト（エージェントが TC 分だけ定義する）
  // 【before 採取の設計方針】並列可＝グループ①（読み取り専用）は before≒after（同じ画面）となり
  // 「修正前も同じ内容だった」と誤読させる証跡になるため before は採取しない（after のみ）
  const tasks = [
    { no: 'TC-001', url: '{対象URL_1}', afterPath: '/絶対パス/TC-001_xxx.png', txtPath: '/絶対パス/TC-001_xxx.txt' },
    { no: 'TC-003', url: '{対象URL_2}', afterPath: '/絶対パス/TC-003_yyy.png', txtPath: '/絶対パス/TC-003_yyy.txt' },
    // ... TC 数だけ追加
  ];

  // 0. frontdoor 認証を1回だけ確立し storageState（Cookie 等）を取得（以降の全コンテキストで使い回す）
  const bootCtx = await page.context().browser().newContext();
  const bootPage = await bootCtx.newPage();
  bootPage.setDefaultTimeout(15000);
  await bootPage.goto(FRONTDOOR);
  await waitSfReady(bootPage);
  const authState = await bootCtx.storageState();
  await bootCtx.close();

  const results = [];
  // MAX_WORKERS 件ずつチャンク処理
  for (let i = 0; i < tasks.length; i += MAX_WORKERS) {
    const chunk = tasks.slice(i, i + MAX_WORKERS);
    const chunkResults = await Promise.all(chunk.map(async (t) => {
      let ctx;
      try {
        ctx = await page.context().browser().newContext({ storageState: authState }); // frontdoor 再ログイン不要（Cookie 引き継ぎ）
        const p = await ctx.newPage();
        p.setDefaultTimeout(15000);
        await p.goto(t.url);
        await waitSfReady(p);
        if (/\/(secur\/login|login)/i.test(p.url())) {
          // storageState のセッションが無効だった場合のみ frontdoor で個別ログイン（フォールバック）
          await p.goto(FRONTDOOR);
          await waitSfReady(p);
          await p.goto(t.url);
          await waitSfReady(p);
        }
        // ケース固有操作があればここに挿入
        // after 撮影（fullPage: true）+ after DOM 取得（グループ①は before を採取しない）
        await p.screenshot({ path: t.afterPath, fullPage: true, animations: 'disabled', scale: 'css' });
        const text = await getPageText(p);
        const afterSaved = await saveText(p, text, t.txtPath);
        return {
          no: t.no, ok: true, url: p.url(),
          textLen: text.length, thinDom: text.length < 200,
          errorSignature: ERROR_SIGNATURES.find(s => text.includes(s)) || null,
          ...(afterSaved ? {} : { text }),
        };
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

`saveText` が `true` を返した TC は保存済みのため、呼び出し元エージェントは `text` フィールドが存在する要素（download 不発火時のフォールバック）のみ Write すればよい。

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
- **Salesforce のログイン画面へ Playwright でユーザー名・パスワードを直接入力する方式は使わない**。認証は必ず sf CLI 認証済みセッション経由の frontdoor（上記）のみを正規経路とする。別ユーザーでの確認が必要な場合は「Login As」（パスワード不要）を使う。対象ユーザーが sf CLI 未認証で Login As も使えない場合は、パスワードを聞き出さず `sandbox-alias-check.md` の「未認証時の対処」（ユーザー本人による `sf org login web`）に従う
