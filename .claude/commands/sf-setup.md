---
description: "Salesforce組織の認証を行う。org alias・CLAUDE.md記録・default-org設定を自動実施。setup.sh でプロジェクト作成後に実行する。"
---

## 事前チェック

**チェック 1**: SF CLI

```bash
sf --version
```

失敗した場合: Salesforce CLI が未インストール。インストール手順を案内して終了。

**チェック 2**: SFDX プロジェクトルート

```bash
test -f sfdx-project.json && echo "OK"
```

失敗した場合: SFDX プロジェクトのルートで実行されていない。「sfdx-project.json があるフォルダで実行してください」と伝えて終了。

## Step 1: 組織種別の選択

AskUserQuestion ツールを使い、以下をクリック選択式で提示する:

- `本番` — login.salesforce.com
- `Sandbox` — test.salesforce.com
- `skip` — 後で設定する

## Step 2: エイリアス名の入力

`skip` 以外の場合、まずプロジェクトフォルダ名を取得する:

```bash
basename "$(pwd)"  # Git Bash 環境での実行を想定
```

出力値を **`detected_alias`** として控える。`detected_alias` が空の場合はチャットで直接入力してもらう（以下の AskUserQuestion をスキップ）。

AskUserQuestion で確認（明示2択。ランタイムが Other（自由入力）を自動付与）:
- label: `{detected_alias}`、description: "プロジェクトフォルダ名をそのまま使用"
- label: "別名を入力する"、description: "チャットでエイリアス名を入力する"

「別名を入力する」または Other が選ばれた場合はチャットで入力してもらう。確定した値を `alias` として保持する。

## Step 3: 認証

```bash
bash scripts/setup-sf-project.sh "$alias"            # 本番の場合（login.salesforce.com）
bash scripts/setup-sf-project.sh "$alias" sandbox    # Sandboxの場合（test.salesforce.com）
```

> **Sandbox の `--instance-url` について**: `sandbox` 引数を渡すと `https://test.salesforce.com` が自動で使われる。

スクリプト内でブラウザが開く。ログイン後に自動で認証確認まで完了する。
スクリプトの「メタデータを取得しますか？」には自動的に N が選択されます（/sf-retrieve が後続ステップで担当するため）。

#### Step 3-1: MyDomain・カスタムURL の場合（任意）

MyDomain（`https://xxx.sandbox.my.salesforce.com` など）を使う組織に接続する場合は、上記スクリプト実行後に以下で URL を上書きする:

```bash
sf org login web --alias "$alias" --instance-url <URL>
```

カスタムURL を使わない場合はこのステップをスキップする。

## Step 4: 完了案内

### 4-1: 接続組織の種別を確認

Step 1 で選択した組織種別と実際の認証先が一致しているかを `sf org display` で二重チェックする（MyDomain 等で意図と異なる組織に接続している可能性を検知するための安全装置）:

```bash
sf org display --target-org "$alias" --json
```

`isSandbox` フィールドが Step 1 の選択（本番/Sandbox）と矛盾していた場合は、その旨をユーザーに警告してから先に進む。

> **注意**: 接続先をルート `CLAUDE.md` に静的テキストで記録しない。接続先は `sf org display` のライブ確認で判定するため、スナップショットを焼き込むと切り替え後に誤判定を起こす。

CLAUDE.md への記録完了後、以下をユーザーに提示する:

```
✅ 認証完了
  alias: {alias}
  種別: Sandbox / 本番
  default-org に設定済み（/backlog で使用される組織です）

別の組織も登録したい場合は再度 /sf-setup を実行してください。
default-org を切り替えるには: sf config set target-org <別alias>
```

### 4-2: 次のアクション分岐

`force-app/` 配下にファイルが存在するか確認する:

```bash
find force-app -mindepth 1 -maxdepth 3 -type f 2>/dev/null | head -1
```

**force-app/ にファイルがある場合（メタデータ取得済み）**:

```
次のアクション:
- /setup-mcp  — Backlog・Notion・GitHub 等の外部連携を設定する（連携を使う場合は必須）
- /sf-memory  — 組織情報を収集・記録する（/setup-mcp の後に実行推奨）
```

**force-app/ が空の場合（メタデータ未取得）**:

AskUserQuestion ツールで以下を表示する:

**質問**: 「認証が完了しました。続けてメタデータの取得を行いますか？」

**選択肢**:
- `取得する` — そのまま /sf-retrieve を実行する
- `あとで` — 手順を案内して終了する

`取得する` の場合は Skill ツールを使って /sf-retrieve を実行する。

`あとで` の場合は以下を案内して終了する:

```
初期セットアップの次のステップ:
1. /sf-retrieve  — メタデータを取得する（force-app/ に展開）
2. CLAUDE.md     — プロジェクト固有情報を記入する
3. /setup-mcp    — 外部ツール連携を設定する（Backlog・Notion・GitHub 連携を使う場合は必須）
4. /sf-memory    — 組織情報を収集・記録する（docs/ を生成） ★本番接続中に実施
5. /sf-doc       — 設計書・定義書を生成する

⚠️ 本番接続中（Step 4）は読み取り操作のみです。
   データの変更・デプロイ・force-app への書き込みは行いません。
```
