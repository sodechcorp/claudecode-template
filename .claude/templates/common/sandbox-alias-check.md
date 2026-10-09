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

## メール到達安全確認（お客様に届く可能性があるときだけ対処・自動回避を優先）

**実績インシデント（2026-08-03）**: Sandbox 検証中に承認プロセスのメールアラートが実際の顧客メールアドレスへ送信された（Sandbox ユーザーの Email から `.invalid` が外れていた）。

**原則**: 毎回人に確認しない。①そもそもメールを送る処理を動かすか、②送信先がお客様か、を機械的に判定し、③お客様に届く場合は**テストの質を落とさずに自動で回避する**。人に確認するのは、回避するとテストの前提が変わってしまう（または回避しようがない）場合だけ。

**実施タイミング**: 実データへの DML・匿名Apex 実行・UI 上での登録/更新/削除/承認操作の直前。SOQL の SELECT・dry-run デプロイ等、レコードを変更しない操作では不要。

### Step 1: メール送信処理の有無

今回実行する操作が起動する処理（test-spec の実行アクション、`investigation.md`「## スコープ」のスコープ内処理＝実行経路・保存時に連動するトリガー/フロー、変更対象ファイル）について、以下を `force-app/` から Grep する（大文字小文字を区別しない）:

| 種類 | 検出パターン |
|---|---|
| Apex | `Messaging.sendEmail` / `Messaging.SingleEmailMessage` / `Messaging.MassEmailMessage` |
| フロー | `*.flow-meta.xml` の `<actionType>emailSimple</actionType>` / `<actionType>emailAlert</actionType>` |
| ワークフロー・メールアラート | `*.workflow-meta.xml` の `<alerts>`（起動条件が今回の操作に該当するもの） |
| 承認プロセス | `*.approvalProcess-meta.xml`（申請・承認・却下で通知が飛ぶ） |
| 自動レスポンス | `*.autoResponseRules-meta.xml`（ケース・リードの作成時） |

- **該当なし** → 「メール送信処理なし」と記録し、確認なしで進む
- 保存時に連動するフロー・承認プロセスが force-app に取得されていない可能性がある場合（`investigation.md`「## スコープ」で組織側に存在を確認済みのものが force-app に無い等）は、「該当あり」として Step 2 に進む（安全側）

### Step 2: 送信先の判定

送信処理がある場合、今回のテストで送信先になりうるアドレスを洗い出す:

- テストで使うレコードのメール項目（取引先責任者・リード・Email 型のカスタム項目）
- 通知先ユーザー（承認者・レコード所有者・キュー／公開グループのメンバー・メールアラートの受信者設定）
- メールアラート・Apex に直接書かれたアドレス

各アドレスを **許可ドメイン** と照合する:
- 既定: `sodech.com`、および末尾が `.invalid`（Sandbox 作成時に付与される無効化サフィックス）
- 追加: プロジェクトの `CLAUDE.md` に「テスト用許可メールドメイン: xxx.co.jp」の形で書かれたドメイン

**全て許可ドメイン** → 「送信先は全て許可ドメイン」と記録し、確認なしで進む。

### Step 3: 自動回避（許可ドメイン外の送信先がある場合）

テストの条件を変えずに、次の順で回避する。回避した内容は `{log_dir}/.email-safety.json` と test-report に記録する:

1. **テストデータのメール項目をテスト用アドレスにする**: テストで作るレコードは最初から `test+{issueID}@sodech.com` 等の許可ドメインのアドレスで作る。既存レコードを使う TC は、同じ条件のテスト用レコードを作ってそちらを使う
2. **通知先ユーザーをテスト用ユーザーにする**: 承認者・所有者に、同じプロファイル・権限セットで、許可ドメインのメールを持つユーザーを指定する（テストの条件＝権限・分岐は変えない）
3. **既存ユーザーの Email は書き換えない**（メールアドレス変更の確認メールが送信されるため）

回避できたら、確認なしで進む。

### Step 4: 回避できない場合のみ確認する

次のいずれかに当たる場合だけ、操作を止めて担当者に確認する:
- 送信先が処理に直接書かれていて、テストデータ・ユーザーの差し替えで変えられない
- 特定の実在ユーザー・実在レコードでないと再現できない（差し替えるとテストの前提が変わる）

確認では「どの処理が・どのアドレスに・なぜ回避できないか」と推奨（例: その TC だけ送信処理の手前までで確認する／配信性（Email Deliverability）を「システムメールのみ」に変更する〔組織設定の変更は Claude が行わず担当者が実施〕）を示す。担当者の判断は `{log_dir}/.email-safety.json` に記録し（サブエージェントは確認内容と「確認内容と判断を `{log_dir}/.email-safety.json` に書いてから再実行する」ことを返して止まり、呼び出し元が書く）、同じ課題で送信処理・送信先が変わらない再実行では再確認しない。

> このチェックを実施するエージェント: `auto-evidence-runner.md`（Step 1.5）/ `backlog-repro-runner.md`（Step 4.5・Step 5 の Sandbox 検証直前）/ `backlog-investigator.md`（調査原則「Sandbox のデータは変えずに確かめる」）

## 外部システム呼び出しの確認（本番と同じ接続先へ送るときだけ止める）

Sandbox の接続先（URL・認証情報）は本番からコピーされたまま残っていることがあり（コードに書かれた URL・認証情報は Sandbox でも本番と同じ先へ送る）、送ったデータは rollback でも取り消せない。

**実施タイミング**: 実データへの DML・匿名Apex 実行・UI 上での登録/更新/削除/承認・ボタン操作の直前。メール到達安全確認と続けて行う。SOQL の SELECT・dry-run デプロイ等では不要。

### Step 1: 呼び出しの有無

メール到達安全確認の Step 1 と同じ処理について、以下を `force-app/` から Grep する（大文字小文字を区別しない）:

| 種類 | 検出パターン |
|---|---|
| Apex | `HttpRequest` / `WebServiceCallout` / `ExternalService.`（非同期処理の中も含む） |
| フロー | `*.flow-meta.xml` の `<actionType>externalService</actionType>`（HTTP コールアウト・外部サービス） |

送信メッセージ（ワークフロー・フローから送るもの。管理パッケージのものを含む）は force-app ではなく Sandbox に問い合わせる: Tooling API の `SELECT Id, Name, EntityDefinitionId FROM WorkflowOutboundMessage` のうち、今回の操作で作成・更新されるオブジェクトのもの（EntityDefinitionId が Id なら `SELECT QualifiedApiName FROM EntityDefinition WHERE DurableId = '{Id}'` で名前にする）を該当とする。起動条件（その送信メッセージを使うワークフロールールとフロー）が今回の操作に該当しないと force-app で確かめられたものは除く。

- **該当なし** → 「外部システム呼び出しなし」と記録し、確認なしで進む
- force-app に取得されていない処理の扱いはメール到達安全確認の Step 1 と同じ（該当ありとして Step 2 に進む）

### Step 2: 接続先が本番と同じか

呼び出しごとに接続先を特定し、Sandbox と本番の接続先のホストを比べる（本番はプロジェクトの `CLAUDE.md` にある本番エイリアス〔[prod-readonly-check.md](prod-readonly-check.md)「本番エイリアスの特定」〕で読むだけ。記載が無い・読めない・本番に同じ名前の設定やレコードが無ければ「特定できない」）:

| 接続先の決まり方 | 比べる値 |
|---|---|
| 指定ログイン情報（`callout:{名前}`） | `SELECT DeveloperName, Endpoint FROM NamedCredential WHERE DeveloperName = '{名前}'` |
| フローの外部サービス | Tooling API の `SELECT DeveloperName, NamedCredential FROM ExternalServiceRegistration` で指定ログイン情報を引き、上と同じ |
| コードに書かれた URL | 本番と同じとする（環境で切り替えるコードは、それぞれの環境で選ばれる URL） |
| カスタム設定・カスタムメタデータから読む URL | その値を SOQL で |
| 送信メッセージ | Sandbox は Step 1 の Id、本番は同じオブジェクト・同じ Name のものの Id で、Tooling API の `SELECT Metadata FROM WorkflowOutboundMessage WHERE Id = '{Id}'`（1件ずつ）の `endpointUrl` |
| 応答で返る URL（リダイレクト先等） | その応答を返した呼び出しと同じ扱い |

- **本番と違う** → 「Sandbox 用の接続先」と記録し、確認なしで進む
- **本番と同じ・特定できない** → 接続先のホストがプロジェクトの `CLAUDE.md` に「Sandbox から呼んでよい接続先: xxx.com」の形で書かれていれば、その旨を記録し、確認なしで進む。書かれていなければ、その操作を止めて担当者に確認する

確認では「どの処理が・どの接続先へ・何を送るか」と推奨（例: その TC だけ呼び出しの手前までで確認する／Sandbox の接続先を試験用に付け替える〔組織設定の変更は Claude が行わず担当者が実施〕／いつも呼んでよい接続先ならプロジェクトの `CLAUDE.md` に書く）を示す。担当者の判断はメール到達安全確認の Step 4 と同じく `{log_dir}/.email-safety.json` に記録し（書く主体も同じ）、同じ課題で呼び出し・接続先が変わらない再実行では再確認しない。

> このチェックを実施するエージェント: メール到達安全確認の一覧と同じ。ただし `backlog-investigator.md` は Step 1 だけ行う（該当したものの扱いは同ファイルの調査原則「Sandbox のデータは変えずに確かめる」）

---

## 認証状態の確認（frontdoor 認証の前提）

Playwright の frontdoor 認証（`sf org open --url-only`）は対象エイリアスが sf CLI に**有効な状態で**認証済みであることが前提。実行前に確認する:

```bash
sf org list --json
```

`result.nonScratchOrgs` / `result.scratchOrgs` から対象エイリアス・ユーザー名のエントリを探し `connectedStatus` を確認する:
- `"Connected"` → CLI の認証は有効。frontdoor 認証に進んでよい（パスワードの期限切れ等で画面にログインできないことはここでは分からない。`playwright-sf-screen-ops.md`「frontdoor 認証」の着地の確認で見る）
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

> このテンプレートを参照するエージェント: `backlog-tester.md` / `backlog-releaser.md` / `backlog-validator.md`（SOQL dryrun 時）/ `backlog-repro-runner.md`（バグ再現・仮説検証）/ `auto-evidence-runner.md`（テスト証跡採取）/ `backlog-investigator.md`（Phase 1 の匿名 Apex。メール到達安全確認と「外部システム呼び出しの確認」の Step 1 のみ。回避できない・該当したものの扱いは同ファイルの調査原則「Sandbox のデータは変えずに確かめる」）
>
> 上記のうち実データへの DML・匿名Apex 実行・UI 上での書き込み操作を行うエージェントは、当該操作の直前に「メール到達安全確認」「外部システム呼び出しの確認」も実施する（実施するエージェントは各セクション末尾の一覧）。
>
> **例外（インライン複製）**: `test.md` の Phase A は「エイリアス取得」「Sandbox 判定」のロジックを Read 参照ではなく意図的にインライン複製している（Phase A 全体が単一 bash フェンスのハーネス直接実行で、後続ステップと `SF_ALIAS` 等の変数を共有する構成のため）。判定条件に `instanceUrl` による OR 条件を独自に追加している点も含め、本テンプレートを改修する際は `test.md` 側との整合を確認すること。

**`INSTANCE_URL` の再利用**: ユーザーへの目視確認ハンドオフ（レコードURL・画面URLの提示）が必要なエージェントは、ここで取得済みの `INSTANCE_URL` をそのまま使う（再取得しない）。組み立て方・出力フォーマットは [visual-confirmation-handoff.md](visual-confirmation-handoff.md) を参照。
