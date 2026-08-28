# Sandbox alias 検証共通手順

Sandbox に接続していることを確認してから操作する。本番組織への誤操作を防ぐための必須チェック。

## エイリアス取得

```bash
SF_ALIAS=$(sf config get target-org --json | python -c "import sys,json; print(json.load(sys.stdin)['result'][0]['value'])" 2>/dev/null || echo "")
if [ -z "$SF_ALIAS" ]; then
  echo "WARN: target-org が設定されていません。sf config set target-org <alias> で設定してください。"
fi
```

**`SF_ALIAS` はプレースホルダ**: 上記コマンドで一度取得した値を、Claude が `{tmp_dir}` / `{issueID}` と同様に保持し、以降のコード例（本ファイル内の別ブロック、および `option-org-drift-check.md`・`backlog-releaser.md` 等の参照先）を実行する際にその都度リテラル値へ置き換える。Bash ツールは呼び出しごとに独立したシェルを起動し環境変数を永続化しないため、上記ブロックでの代入は後続の別 Bash 呼び出しには引き継がれない。値を再確認したい場合のみ上記コマンドを再実行する。

## Sandbox 判定

```bash
SF_ORG_JSON=$(sf org display --target-org "$SF_ALIAS" --json 2>/dev/null)
IS_SANDBOX=$(echo "$SF_ORG_JSON" | python -c "import sys,json; print(json.load(sys.stdin)['result'].get('isSandbox', False))" 2>/dev/null || echo "false")
if [ "$IS_SANDBOX" != "True" ]; then
  echo "FATAL: 接続先が Sandbox ではありません ($SF_ALIAS). 本番への操作は禁止されています。"
  exit 1
fi
echo "OK: Sandbox 接続確認済み ($SF_ALIAS)"

# instanceUrl（accessToken を含まない組織ベースURL）も同じ JSON から取得しておく。
# 目視確認ハンドオフ（レコードURL組み立て）に使う。詳細: visual-confirmation-handoff.md
INSTANCE_URL=$(echo "$SF_ORG_JSON" | python -c "import sys,json; print(json.load(sys.stdin)['result'].get('instanceUrl',''))" 2>/dev/null || echo "")
echo "INSTANCE_URL=$INSTANCE_URL"
```

## メール到達安全確認（DML・匿名Apex 実行・UI 上での登録/更新/削除/承認操作の直前に必須）

**実績インシデント（2026-08-03）**: Sandbox 検証中に承認プロセスのメールアラートが実際の顧客メールアドレスへ送信された。原因は Sandbox ユーザーの Email から `.invalid` サフィックスが外れていたこと（通常は Sandbox 作成時に自動付与されるが、手動編集等で個別ユーザーだけ外れることがある。ユーザーの Email ドメインが実在するかどうかは事前に見分けが付かない）。

承認プロセス（Approval Process）・ワークフロー/Process Builder のメールアラート・Flow の「メールを送信」アクションを起動しうる操作（**実データへの DML・匿名Apex 実行・UI 上での登録/更新/削除/承認操作**）の直前に必ず実施する。SOQL の SELECT・dry-run デプロイ等、レコードを変更しない操作では不要。

```bash
sf data query --target-org "$SF_ALIAS" \
  -q "SELECT Username, Email FROM User WHERE IsActive = true AND Email != null AND NOT Email LIKE '%.invalid'" -r csv
```

**再確認スキップ判定（キャッシュ）**: クエリ結果が0件（該当ユーザーなし）の場合は確認不要でそのまま続行する。1件以上ある場合、Username・Email の組み合わせ（ソート済み）を安定した文字列にして SHA256 でハッシュ化し、キャッシュファイル（`{log_dir}/.email-safety-ack.json`。呼び出し元が `{log_dir}` を持たない場合は `docs/logs/{issueID}/.email-safety-ack.json`）と比較する:
- キャッシュが存在し `hash` が一致する場合: 「前回確認済みの対象ユーザーリストと同一のため再確認をスキップします（前回確認: {キャッシュの `confirmed_at`}）」と表示して続行する（下記のユーザー確認は行わない）
- キャッシュが不在、または `hash` が不一致（対象ユーザーが増減・変化した）の場合: 下記のとおり通常どおりユーザーに確認を取る。ユーザーが承認したら `{"hash": "{ハッシュ}", "confirmed_at": "{ISO日時}", "usernames": [{該当ユーザー一覧}]}` をキャッシュファイルに Write する

- **1件でも該当（`.invalid` が付いていない実アクティブユーザー）があれば、キャッシュ一致でない限り操作を中断してユーザーに確認を取る。無断で続行しない**
- 該当ユーザーの Username・Email を一覧化した上で「これらのユーザーが承認者・関連ユーザーになっている操作を行うと、実アドレスへメールが送信される可能性があります。続行しますか？」と確認する
- ユーザーが続行を明示的に承認した場合のみ操作を続行する
- より確実な対策として、Setup → メール管理 → 配信性（Email Deliverability）を「システムメールのみ」に変更することを提案してよい。ただし組織設定変更は Claude が無断で行わず、必ずユーザー判断・ユーザー実施とする

> このチェックを実施するエージェント: `auto-evidence-runner.md`（Step 1.5・AnonApex/UI ケースがある場合）/ `backlog-repro-runner.md`（Step 4.5・Step 5 の Sandbox 検証直前）

---

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
>
> 上記のうち実データへの DML・匿名Apex 実行・UI 上での書き込み操作を行う `backlog-repro-runner.md` と `auto-evidence-runner.md` は、当該操作の直前に「メール到達安全確認」も追加で実施する（上記セクション参照）。

**`INSTANCE_URL` の再利用**: ユーザーへの目視確認ハンドオフ（レコードURL・画面URLの提示）が必要なエージェントは、ここで取得済みの `INSTANCE_URL` をそのまま使う（再取得しない）。組み立て方・出力フォーマットは [visual-confirmation-handoff.md](visual-confirmation-handoff.md) を参照。
