# 本番 read-only 確認共通手順

本番組織に対して **read-only 操作のみ**を行う前に接続先を確認する。`sandbox-alias-check.md` は Sandbox 強制（`isSandbox:false` で `exit 1`）のため本番を読むこと自体ができない。本テンプレートはその逆で「本番であることを確認した上で read-only のみ許可する」ガード。

## 前提

**このガードを通過しても許可されるのは以下のみ**:
- `sf org display`
- `sf org list metadata` / `sf org list metadata-types`
- `sf sobject describe`（項目一覧の取得）
- `sf project retrieve start`（`force-app/` 以外への取得。一時ディレクトリ、および `/release` のバックアップ・リリース資材の控え用の `docs/logs/{issueID}/` 配下。`force-app/` への直接取得は禁止）
- `sf data query`（SELECT のみ）
- Playwright による画面の閲覧（frontdoor 認証・Login As を含む。下記「本番 UI 確認」の範囲のみ）

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

1. プロジェクト CLAUDE.md（ルート）§Salesforce組織情報 に本番組織のエイリアス記載があれば参照する
2. 記録がない・不明な場合はユーザーに確認する: 「本番組織のエイリアスを確認します。`sf org list` の出力から本番組織のエイリアスを教えてください」

**`PROD_ALIAS` はプレースホルダ**: 上記で特定した実際のエイリアス文字列を指す。`{tmp_dir}` / `{issueID}` と同様、Claude が値を保持し、以下および他ファイル（`option-org-drift-check.md` 等）のコード例を実行する際にその都度リテラル値へ置き換える。シェル変数として `export` する・前段の Bash 呼び出しでの代入が後続の別 Bash 呼び出しに引き継がれることを前提にしない（Bash ツールは呼び出しごとに独立したシェルを起動し、環境変数を永続化しないため）。

## 本番判定

> **※単一行限定**: 以下の `python -c` は改行・インデントを含まない単一物理行。多行ロジックへ拡張しない（詳細: [inline-script-hygiene.md](inline-script-hygiene.md)）。

```bash
PROD_ALIAS="<上記で特定した本番組織のエイリアス>"
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

## 本番 UI 確認（read-only）

本番の画面表示・レイアウト・権限による見え方の違いを、ユーザーの許可を待たず自動で確認してよい。ただし**データ・設定を変えない閲覧に限る**（Sandbox と違い、実顧客のデータが画面に出る）。手順の実体は `playwright-sf-screen-ops.md`。

**許可**:
- frontdoor 認証（`sf org open --target-org "$PROD_ALIAS" --url-only`。セキュリティ規約は `playwright-sf-screen-ops.md`「frontdoor 認証」）
- Lightning／Setup／Experience Cloud 画面の閲覧（一覧・レコード詳細・タブ・アプリ切替）、DOM テキスト取得、スクリーンショット
- Login As（他ユーザーとして閲覧）: 権限・項目レベルセキュリティ・レイアウトの見え方の差分確認。手順は `playwright-sf-screen-ops.md`「Login As」。確認後は必ず `/secur/logout.jsp` でプロキシ解除してから終了する（Login As のまま放置しない）
**禁止（状態を変えるもの。ユーザー指示があっても実行しない）**:
- 保存・作成・更新・削除・承認／却下・送信（メール・Chatter 投稿を含む）・ファイルアップロードの操作
- パスワード変更・セキュリティトークンのリセット・Setup の設定変更
- 副作用の有無を確認できていない Setup URL への直接遷移（`playwright-sf-screen-ops.md`「未検証 URL への navigate 前チェック」を厳守。「Confirm」に見える URL でも遷移時点で実行される実績がある）
- 画面フロー・Apex を起動するボタン等の実行（存在と表示の確認までにとどめる）
- 新規・編集フォームを開く確認（ボタンの上書き・クイックアクション・画面フローで、開いただけで処理が走る場合を機械的に見分けられないため、担当者の確認に回す。レコードタイプの選択肢の確認等）
- `browser_run_code_unsafe` で、上記の許可以外のコードを書くこと（`.fill` / `.type` / `.press` / `selectOption` / `setInputFiles`、保存・削除・承認・送信系のクリック、`fetch` による API 呼び出し）。唯一の例外は Login As フォールバックの ManageUsers 検索欄。なお Playwright の操作を機械的にブロックする hook は無く、この禁止は指示による制約である

**証跡の扱い**: 本番画面には実顧客の個人情報・機密が写る。スクリーンショット・DOM テキストは `docs/logs/{issueID}/` 配下に保存し、個人情報が写っていないことを確認するまでチャット・Backlog・共有ドライブ・git コミットへ載せない（写っている場合はマスクするか、個人情報のない画面・レコードに選び直す）。**Playwright MCP が自動保存するファイル（プロジェクト直下の `.playwright-mcp/` のページスナップショット・コンソールログ・ダウンロードの複製）も同じく個人情報を含む**ため、本番の画面確認の終了時に開始時刻以降のファイルを削除する（`prod-ui-verifier` Step 4）。git コミットする文書（`decisions.md` 等）には、レコードの値・氏名を書かず、V 番号・画面名・差の種類だけを書く。

> Claude Code の自動モード（分類器）が本番の読み取り・画面確認をブロックする場合は、メンバー個人設定（`~/.claude/settings.json` の `autoMode`）が必要。プロジェクト共有の settings.json では効かない。手順: [security-and-permissions.md](../../spec/security-and-permissions.md)「自動モードの分類器設定」。

## 実行前セルフチェック（必須）

コマンドを実行する直前に、そのコマンドが上記「許可される操作」のみで構成されているかを目視確認する。`--dry-run` を含むデプロイ系コマンドは「read-only」に見えても対象外（hook が deny を返す設計だが、そもそも実行を試みないこと）。迷った場合は実行せずユーザーに確認する。
