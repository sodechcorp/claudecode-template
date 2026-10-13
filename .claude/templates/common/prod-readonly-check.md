# 本番 read-only 確認共通手順

本番組織に対して **read-only 操作のみ**を行う前に接続先を確認する。`sandbox-alias-check.md` は Sandbox 強制（`isSandbox:false` で `exit 1`）のため本番を読むこと自体ができない。本テンプレートはその逆で「本番であることを確認した上で read-only のみ許可する」ガード。

## 前提

**このガードを通過しても許可されるのは以下のみ**:
- `sf org display`
- `sf org list metadata` / `sf org list metadata-types`
- `sf sobject describe`（項目一覧の取得）
- `sf project retrieve start`（`force-app/` 以外への取得。一時ディレクトリ、および `docs/logs/{issueID}/` 配下〔`/release` のバックアップ・リリース資材の控え等〕。取得先のパスにはドットで始まるフォルダを含めない〔`docs/logs/{issueID}/.tmp` の下を含め、Succeeded のまま1ファイルも書かれない〕。`force-app/` への直接取得は禁止）
- `sf data query`（SELECT のみ）
- Playwright による画面の閲覧と、新規・編集画面での入力（保存しない）（frontdoor 認証・Login As を含む。下記「本番 UI 確認」の範囲のみ）

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

本番の画面を、ユーザーの許可を待たず自動で確認してよい。**境界は確定操作（保存・送信・実行）を押すかどうか**で、その手前までは行ってよい。新規・編集画面を開いて項目の値を書き換えるのは可、そのあと保存ボタンを押すのは不可（データ・設定は変えない。Sandbox と違い、実顧客のデータが画面に出る）。手順の実体は `playwright-sf-screen-ops.md`。

**許可**:
- frontdoor 認証（`sf org open --target-org "$PROD_ALIAS" --url-only`。セキュリティ規約は `playwright-sf-screen-ops.md`「frontdoor 認証」）
- Lightning／Setup／Experience Cloud 画面の閲覧（一覧・レコード詳細・タブ・アプリ切替）、DOM テキスト取得、スクリーンショット
- Login As（他ユーザーとして閲覧）: 権限・項目レベルセキュリティ・レイアウトの見え方の差分確認。手順は `playwright-sf-screen-ops.md`「Login As」。確認後は必ず `/secur/logout.jsp` でプロキシ解除してから終了する（Login As のまま放置しない）
- **新規・編集画面を開いて値を入力する（保存しない）**: 標準の新規・編集画面（レコードタイプの選択を含む）・インライン編集・標準のクイックアクション（レコードの作成・更新・活動の記録など、項目を入れて保存するだけのもの）を開き、入力・選択リストの選択・参照項目の検索をして、編集できるか・必須か・選択肢・初期値・連動する選択リスト・項目の表示の切り替わりを確かめる。済んだら**キャンセル**で閉じる（「変更を破棄」の確認が出たら破棄を選ぶ。キャンセルは保存ボタンと隣り合うため、押す前に snapshot でラベルを確かめる）。Login As 中も同じ
- **上書き画面・カスタム画面は、開く・入力する時点で走る処理をソースで確かめてから**: 新規・編集ボタンの上書き（`objects/{Object}/{Object}.object-meta.xml` の `actionOverrides` で `New`／`Edit` が `Default` 以外）、Visualforce・LWC・Aura のクイックアクション、画面フローは、開いただけ・入力しただけで処理が走りうる。force-app で、開いた時点（Visualforce の `<apex:page action>`、LWC の `connectedCallback`・Aura の `init`、画面フローの最初の画面より前の要素）と入力した時点（`actionSupport`・`actionFunction`、入力のハンドラから呼ぶ Apex）の処理に、DML・メール送信・外部呼び出し・非同期ジョブの起動が無いと確かめた場合だけ開く／入力する。確かめられなければ開かない（担当者の確認に回す）

**禁止（状態を変えるもの。ユーザー指示があっても実行しない）**:
- **確定操作のボタン**: 保存・保存＆新規・インライン編集の保存・作成・削除・送信（メール・Chatter 投稿を含む）・承認申請／承認／却下、画面フローの「次へ」「完了」「一時停止」（画面の間の要素〔レコードの作成・更新等〕は次へ進むときに実行される。一時停止は中断した状態を保存する）、押した時点で処理が走るカスタムボタン・アクション（ヘッドレスのクイックアクション・Apex を呼ぶボタン等。上の「許可」で開いた時点の処理を確かめたもの以外）
- **フォームの外で押した時点で保存される部品**: ToDo の完了チェック、かんばんのドラッグ、パスの「完了としてマーク」、フォロー・いいね・お気に入り、リストビューの保存。入力してよいのは新規・編集画面（保存ボタンのあるフォーム）の中の入力欄だけ
- **入力欄での Enter キー**（フォームが送信〔保存〕されうる）: 値は Enter を押さずに入れる（`fill`。`browser_type` は `submit` を付けない）。唯一の例外は Login As フォールバックの ManageUsers 検索欄
- ファイルの選択（Lightning のファイルアップロードは、選んだ時点でアップロードされる）
- パスワード変更・セキュリティトークンのリセット・Setup の設定の保存
- 副作用の有無を確認できていない Setup URL への直接遷移（`playwright-sf-screen-ops.md`「未検証 URL への navigate 前チェック」を厳守。「Confirm」に見える URL でも遷移時点で実行される実績がある）
- `browser_run_code_unsafe` で、上記の許可以外のコードを書くこと。書いてよいのは閲覧・スクリーンショット・DOM 取得・Login As と、新規・編集画面の中の入力（`.fill`・`.selectOption`・`.check`）、新規・編集・キャンセルのクリック。書かないもの: 確定操作のボタンの `click`、`.press('Enter')`、`setInputFiles`、`fetch` 等による API 呼び出し。なお Playwright の操作を機械的にブロックする hook は無く、この禁止は指示による制約である

**証跡の扱い**: 本番画面には実顧客の個人情報・機密が写る。スクリーンショット・DOM テキストは `docs/logs/{issueID}/` 配下に保存し、個人情報が写っていないことを確認するまでチャット・Backlog・共有ドライブ・git コミットへ載せない（写っている場合はマスクするか、個人情報のない画面・レコードに選び直す）。**Playwright MCP が自動保存するファイル（プロジェクト直下の `.playwright-mcp/` のページスナップショット・コンソールログ・ダウンロードの複製）も同じく個人情報を含む**ため、本番の画面確認の終了時に開始時刻以降のファイルを削除する（`prod-ui-verifier` Step 4）。git コミットする文書（`decisions.md` 等）には、レコードの値・氏名を書かず、V 番号・画面名・差の種類だけを書く。

> Claude Code の自動モード（分類器）が本番の読み取り・画面確認をブロックする場合は、メンバー個人設定（`~/.claude/settings.json` の `autoMode`）が必要。プロジェクト共有の settings.json では効かない。手順: [security-and-permissions.md](../../spec/security-and-permissions.md)「自動モードの分類器設定」。

## 実行前セルフチェック（必須）

コマンドを実行する直前に、そのコマンドが上記「許可される操作」のみで構成されているかを目視確認する。`--dry-run` を含むデプロイ系コマンドは「read-only」に見えても対象外（hook が deny を返す設計だが、そもそも実行を試みないこと）。迷った場合は実行せずユーザーに確認する。
