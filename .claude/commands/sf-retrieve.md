---
description: "Salesforce組織からメタデータを取得する。package.xml の生成と取得対象をクリック選択で指定できる。"
---

Salesforce組織からメタデータを取得してください。

> **前提**: sf CLI **2.133.0+** が必要です。`standard` / `all` モードはスクリプトが自動チェックします。
> 旧版の場合: `npm install --global @salesforce/cli@latest` で更新してください。

## ユーザー入力

$ARGUMENTS

---

## Step 1: 取得対象の選択

引数がある場合はそれを「指定する」として解釈し、Step 2 の「指定する」の処理へ進む。

引数がない場合、AskUserQuestion ツールを以下の内容で呼び出す。

**質問**: 「メタデータの取得対象を選択してください。」

**選択肢**:
- `standard` — 標準セット（Apex・フロー・オブジェクト・LWC等、開発でよく使うもの）
- `all` — 全メタデータ（時間がかかる）
- `select` — 取得するメタデータ名を個別に指定する

---

## Step 2: 実行

### 「standard」の場合

```bash
bash scripts/sf-retrieve.sh standard
```

### 「all」の場合

```bash
bash scripts/sf-retrieve.sh all
```

### 「select」の場合

取得したいメタデータ名（クラス名・フロー名・オブジェクト名等）をチャットで確認する（カンマ区切りで複数指定可。例:「MyClass, MyFlow, Account」）。
取得前に `git status force-app/` で未コミットの変更を確認し、変更がある場合は AskUserQuestion で以下を表示する:

**質問**: 「force-app/ に未コミットの変更があります。取得を続行しますか？」

**選択肢**:
- `続行する` — 変更を上書きして取得する
- `中断する` — キャンセルする

`中断する` を選択した場合は処理を終了する。

指定された名前からメタデータタイプを判定し `manifest/package.xml` を生成して取得する。

**package.xml 生成ルール**:
- ユーザー指定のコンポーネント名ごとに下記の対応表でメタデータタイプ（`<name>`）を判定する
- `<members>` には対応表の例（`MyClass` 等）を使わず、**ユーザー指定値**をそのまま入れる
- 対応表にないタイプは Salesforce Metadata API 名をそのまま `<name>` に指定する
- 指定されたタイプが不明な場合は AskUserQuestion でユーザーに確認する

```bash
# 例: Apex クラス MyClass・フロー MyFlow・オブジェクト Account を指定した場合
[ -f sfdx-project.json ] || { echo "sfdx-project.json が見つかりません。SFDXプロジェクトのルートで実行してください"; exit 1; }
API_VER=$(python3 -c "import json; d=json.load(open('sfdx-project.json')); print(d.get('sourceApiVersion', '62.0'))" 2>/dev/null || echo "62.0")
TARGET_ORG=$(sf config get target-org --json 2>/dev/null | python3 -c "import sys,json; r=json.load(sys.stdin).get('result',[]); print(r[0]['value'] if r else '')" 2>/dev/null || echo "")
if [ -z "$TARGET_ORG" ]; then
    echo "target-org が設定されていません。sf config set target-org <alias> で設定してから再実行してください。"
    exit 1
fi
mkdir -p manifest
cat > manifest/package.xml << XMLEOF
<?xml version="1.0" encoding="UTF-8"?>
<Package xmlns="http://soap.sforce.com/2006/04/metadata">
    <types>
        <members>MyClass</members>
        <name>ApexClass</name>
    </types>
    <types>
        <members>MyFlow</members>
        <name>Flow</name>
    </types>
    <types>
        <members>Account</members>
        <name>CustomObject</name>
    </types>
    <version>${API_VER}</version>
</Package>
XMLEOF

sf project retrieve start --manifest manifest/package.xml --target-org "$TARGET_ORG"
```

メタデータタイプの対応表（主要なもの）:

| 指定内容 | `<name>` タグ |
|---|---|
| Apex クラス | `ApexClass` |
| Apex トリガー | `ApexTrigger` |
| Visualforce ページ | `ApexPage` |
| フロー | `Flow` |
| LWC コンポーネント | `LightningComponentBundle` |
| オブジェクト・項目 | `CustomObject` |
| カスタム表示ラベル | `CustomLabel` |
| カスタムメタデータ型 | `CustomMetadata` |
| カスタム設定 | `CustomSetting` |
| カスタムタブ | `CustomTab` |
| 権限セット | `PermissionSet` |
| 権限セットグループ | `PermissionSetGroup` |
| 入力規則 | `ValidationRule` |
| レイアウト | `Layout` |
| Lightning ページ | `FlexiPage` |
| 静的リソース | `StaticResource` |
| メールテンプレート | `EmailTemplate` | ⚠ フォルダ型 |
| レポートタイプ | `ReportType` | |
| レポート | `Report` | ⚠ フォルダ型 |
| ダッシュボード | `Dashboard` | ⚠ フォルダ型 |
| 名前付き資格情報 | `NamedCredential` |
| リモートサイト設定 | `RemoteSiteSetting` |
| プロファイル | `Profile` |

対応表に記載のないメタデータタイプは、Salesforce Metadata API 名（例: `WorkflowRule`、`Queue`）をそのまま `<name>` に指定する。指定されたタイプが不明な場合は AskUserQuestion でユーザーに確認する。

> **⚠ フォルダ型の注意**: Dashboard / Report / EmailTemplate / Document を `select` で個別指定する場合、`<members>*</members>` は使えない。以下のいずれかを使うこと:
> - フォルダ名のみ: `<members>FolderName</members>` → そのフォルダ内の全アイテム取得
> - 個別指定: `<members>FolderName/ItemName</members>` → 特定のアイテムのみ
> - フォルダ型と同時指定: `DashboardFolder` / `ReportFolder` の `<types>` ブロックも含める

---

## Step 3a: 完了報告（初回）

以下の bash で `docs/overview/org-profile.md` の存在を確認する:

```bash
[ -f docs/overview/org-profile.md ] && echo "exists" || echo "not-found"
```

**「not-found」の場合（初回）**:

AskUserQuestion で以下を表示する:

**質問**: 「メタデータの取得が完了しました。次のステップを選択してください。」

**選択肢**:
- `外部ツール連携を設定する（/setup-mcp）` — 外部連携（Backlog・GitHub 等）を使う場合は必須（/sf-memory の前に実行）
- `組織情報を収集する（/sf-memory）` — Backlog MCP 不要の場合はそのまま実行可

`外部ツール連携を設定する` を選択した場合: /setup-mcp を実行する（完了後に /sf-memory の実行を案内する）
`組織情報を収集する` を選択した場合: /sf-memory を実行する

---

## Step 3b: 完了報告（2回目以降）

**「exists」の場合（2回目以降）**:

取得後に git diff で変更内容を確認し、変更の種別に応じて以下を通知する:

```bash
git diff --name-only force-app/
```

変更ファイルを種別ごとに分類する。以下のパスプレフィックスで判定する:

| パス | 種別 |
|---|---|
| `force-app/main/default/classes/` | Apex |
| `force-app/main/default/triggers/` | Trigger |
| `force-app/main/default/flows/` | Flow |
| `force-app/main/default/lwc/` | LWC |
| `force-app/main/default/aura/` | Aura |
| `force-app/main/default/pages/` | Visualforce |
| `force-app/main/default/objects/` | オブジェクト / 項目 / レイアウト / レコードタイプ |
| それ以外 | その他メタデータ |

該当する項目のみ通知する:

```
メタデータ取得完了。force-app/ に差分があります。

【変更検出】
- Apex / Flow / LWC / Trigger: {変更ファイル名一覧}
- オブジェクト / 項目 / レイアウト / レコードタイプ: {変更ファイル名一覧}
- その他メタデータ: {変更ファイル名一覧}

【ドキュメント更新推奨】

■ /sf-memory（記憶の更新）
  □ cat1: requirements.md / usecases.md
    → 仕様変更・新機能追加・業務フロー変更を伴う場合
  □ cat2: オブジェクト/項目定義
    → オブジェクト項目・レイアウト・レコードタイプ・入力規則変更時
    対象: {オブジェクト名}
  □ cat3: マスタデータ/自動化設定
    → フロー外の自動化・メールテンプレート・マスタデータ変更時
  □ cat4: コンポーネント設計書
    → Apex / Trigger / Flow / LWC / Aura / Visualforce / Batch / Integration 全コンポーネント変更時
    対象: {コンポーネント名}
  □ cat5: 機能グループ（FG）再定義
    → コンポーネント追加・削除時、またはcat4でコンポーネントの主目的・主要呼出関係が変更された場合
    対象: {コンポーネント名}

■ /sf-design / /sf-doc（成果物の再生成）
  □ 機能一覧.xlsx        — 新規コンポーネント追加・削除時（cat4完了後）
  □ オブジェクト定義書.xlsx — オブジェクト/項目変更時（cat2完了後）  対象: {オブジェクト名}
  □ 詳細設計.xlsx        — コード・オブジェクト・仕様いずれかの変更時（cat4完了後）  対象FG: {FG名}
  □ プログラム設計書.xlsx  — コード変更時（cat4完了後）  対象: {コンポーネント名}
```

変更がない場合は「メタデータ取得完了。差分はありません。」とだけ伝える。
