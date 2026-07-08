# 本番 read-only 確認共通手順

本番組織に対して **read-only 操作のみ**を行う前に接続先を確認する。`sandbox-alias-check.md` は Sandbox 強制（`isSandbox:false` で `exit 1`）のため本番を読むこと自体ができない。本テンプレートはその逆で「本番であることを確認した上で read-only のみ許可する」ガード。

> 参照元エージェント: `release-preparer.md`（Phase 4 環境状態確認・ドリフト検知）のみ。他エージェントは `sandbox-alias-check.md`（Sandbox 強制）を使うこと。

## 前提

**このガードを通過しても許可されるのは以下のみ**:
- `sf org display`
- `sf org list metadata` / `sf org list metadata-types`
- `sf project retrieve start`（一時ディレクトリへの取得。`force-app/` への直接取得は禁止）
- `sf data query`（SELECT のみ）

**このガードを通過しても以下は絶対に行わない**（hook / settings.json のハードブロック対象と同一。ガード通過を理由に実行を試みないこと）:
- `sf project deploy`（`--dry-run` 含む）
- `sf data upsert / delete / update / create / import / bulk / resume`
- `sf apex run`
- `sf package install / uninstall`
- `sf org delete / assign / enable / disable`
- `force-app/` への書き込み・DML 全般

## 接続先確認

```bash
sf config get target-org --json
```

```bash
sf org display --json
```

`isSandbox` / `alias` / `Username` を読み取る。

## 本番エイリアスの特定

1. プロジェクト CLAUDE.md（ルート）に本番組織のエイリアス記録があれば参照する（`/sf-setup` で記録済みの場合が多い）
2. 記録がない・不明な場合はユーザーに確認する: 「本番組織のエイリアスを確認します。`sf org list` の出力から本番組織のエイリアスを教えてください」

## 本番判定

> **※単一行限定**: 以下の `python -c` は改行・インデントを含まない単一物理行。多行ロジックへ拡張しない（詳細: [inline-script-hygiene.md](inline-script-hygiene.md)）。

```bash
IS_SANDBOX=$(sf org display --target-org "$PROD_ALIAS" --json | python -c "import sys,json; print(json.load(sys.stdin)['result'].get('isSandbox', False))" 2>/dev/null || echo "unknown")
if [ "$IS_SANDBOX" = "unknown" ]; then
  echo "WARN: 接続確認に失敗しました。認証切れの可能性があります。sf org login web で再認証してください。"
elif [ "$IS_SANDBOX" = "True" ]; then
  echo "NOTE: 指定エイリアスは Sandbox です。本番ドリフト確認の対象外（Sandbox 側は git diff で確認済みのはず）。"
else
  echo "OK: 本番組織を確認しました ($PROD_ALIAS)。read-only 操作のみ許可。"
fi
```

## 未認証時の対処

```bash
sf org login web --alias <alias> --instance-url https://<instance>.salesforce.com
```

認証は user 判断で行う（Claude が無断で `sf org login web` を実行しない。ブラウザ操作が発生するため必ずユーザーに実行を委ねる）。詳細は `sandbox-alias-check.md` の「認証状態の確認」「未認証時の対処」を参照（禁止事項含む）。

## 実行前セルフチェック（必須）

コマンドを実行する直前に、そのコマンドが上記「許可される操作」のみで構成されているかを目視確認する。`--dry-run` を含むデプロイ系コマンドは「read-only」に見えても対象外（hook が deny を返す設計だが、そもそも実行を試みないこと）。迷った場合は実行せずユーザーに確認する。
