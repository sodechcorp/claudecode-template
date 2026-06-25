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

## 未認証時の対処

```bash
sf auth web login --alias <alias> --instance-url https://<instance>.salesforce.com
```

## 参照元エージェントでの使い方

Sandbox 操作（sf apex run test / sf project deploy / SOQL 等）の直前に本テンプレートを参照してチェックを実施する。チェックが失敗した場合は操作を中断してユーザーに確認を取る。

> このテンプレートを参照するエージェント: `backlog-tester.md` / `backlog-releaser.md` / `backlog-validator.md`（SOQL dryrun 時）/ `backlog-repro-runner.md`（バグ再現・仮説検証）/ `auto-evidence-runner.md`（テスト証跡採取）
