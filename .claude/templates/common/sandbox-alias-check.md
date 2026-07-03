# Sandbox alias 検証共通手順

Sandbox に接続していることを確認してから操作する。本番組織への誤操作を防ぐための必須チェック。

## エイリアス取得

```bash
SF_ALIAS=$(sf config get target-org --json | python -c "import sys,json; print(json.load(sys.stdin)['result'][0]['value'])" 2>/dev/null || echo "")
if [ -z "$SF_ALIAS" ]; then
  echo "WARN: target-org が設定されていません。sf config set target-org <alias> で設定してください。"
fi
```

## Sandbox 判定

```bash
IS_SANDBOX=$(sf org display --target-org "$SF_ALIAS" --json | python -c "import sys,json; print(json.load(sys.stdin)['result'].get('isSandbox', False))" 2>/dev/null || echo "false")
if [ "$IS_SANDBOX" != "True" ]; then
  echo "FATAL: 接続先が Sandbox ではありません ($SF_ALIAS). 本番への操作は禁止されています。"
  exit 1
fi
echo "OK: Sandbox 接続確認済み ($SF_ALIAS)"
```

## 認証状態の確認（frontdoor 認証の前提）

Playwright の frontdoor 認証（`sf org open --url-only`）は対象エイリアスが sf CLI に**有効な状態で**認証済みであることが前提。実行前に確認する:

```bash
sf org list --json
```

`result.nonScratchOrgs` / `result.scratchOrgs` から対象エイリアス・ユーザー名のエントリを探し `connectedStatus` を確認する:
- `"Connected"` → 認証済み・有効。frontdoor 認証に進んでよい
- 一覧に存在しない / `connectedStatus` が `"Connected"` 以外（`"RefreshTokenAuthError"` など）→ **未認証または認証切れ**。下記「未認証時の対処」に従う（frontdoor 取得を試みても失敗するため、ここで止める）

## 未認証時の対処（必須: ユーザー判断・ユーザー実行）

```bash
sf org login web --alias <alias> --instance-url https://<instance>.salesforce.com
```

**Claude はこのコマンドを無断で代行しない**。ブラウザでの認証操作が発生するため、実行と認証完了は必ずユーザー本人に委ねる:

1. 上記コマンドの実行をユーザーに依頼する（Bash で実行するとブラウザが開くので、その場でユーザーがログインを完了する）
2. 認証完了後、`sf org list --json` で対象エイリアスの `connectedStatus` が `"Connected"` になったことを再確認してから frontdoor 認証に進む

**禁止事項（例外なし・"ログインできませんでした"の再発防止）**:
- ユーザーにパスワードをチャットへ貼らせて Playwright のログインフォームへ直接入力させる方式は使わない。パスワード期限切れ・MFA で失敗しやすく、パスワードが会話ログに残る
- 対象ユーザーが sf CLI 未認証・管理者の Login As も使えない場合でも、パスワードを聞き出して代替しない。必ず `sf org login web`（ユーザー実施）→ frontdoor の順で解決する
- 認証済みエイリアスが「別ユーザー」の場合（例: 必要なのは A さんだが認証済みなのは B さん）は、まず playwright-sf-screen-ops.md の「Login As」（パスワード不要）が使えないか検討する。Login As 不可の場合のみ本人の `sf org login web` に進む

## 参照元エージェントでの使い方

Sandbox 操作（sf apex run test / sf project deploy / SOQL 等）の直前に本テンプレートを参照してチェックを実施する。チェックが失敗した場合は操作を中断してユーザーに確認を取る。

> このテンプレートを参照するエージェント: `backlog-tester.md` / `backlog-releaser.md` / `backlog-validator.md`（SOQL dryrun 時）/ `backlog-repro-runner.md`（バグ再現・仮説検証）/ `auto-evidence-runner.md`（テスト証跡採取）
