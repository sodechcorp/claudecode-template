---
description: "sf code-analyzer（PMD/CPD/regex 実エンジン）でSalesforceプロジェクトを静的解析し、Critical/Warning/Info形式で報告する。org接続不要・デプロイ操作なし。"
argument-hint: "[対象パス（省略時: force-app 全体）]"
---

Salesforce プロジェクトに対して `sf code-analyzer`（PMD/CPD/regex の実解析エンジン）による静的解析を実行してください。

> **位置づけ**: reviewer.md の LLM 目視レビュー（FLS/CRUD 権限設計の妥当性・設計意図の確認等）を **代替しない**。governor limit 違反・CRUD 違反・共有モデル未宣言等の機械的に検出できる違反を実エンジンで補完する。両方を併用するのが前提。

## ユーザー入力

$ARGUMENTS

---

## Step 1: 実行

sfdx-project.json のあるプロジェクトルートで実行する。`$ARGUMENTS` に対象パス（ファイル・ディレクトリ・globパターン）が指定されていればそれをスクリプトの第1引数として渡す。省略時は引数なしで実行する（スクリプト側で `force-app` 全体がデフォルト適用される）。

```bash
# 引数あり（例: 対象パスが force-app/main/default/classes/MyClass.cls の場合）
bash scripts/sf-code-analyze.sh force-app/main/default/classes/MyClass.cls

# 引数省略（force-app 全体が対象）
bash scripts/sf-code-analyze.sh
```

> **前提**: sf CLI が必要（`sf --version` で確認可）。`code-analyzer` プラグインは初回実行時に自動インストールされるため、初回のみ数十秒程度かかる場合がある。org 接続は不要（ローカルのソースコードのみを解析。デプロイ・データ操作は一切行わない）。

## Step 2: 結果の提示

スクリプトの出力（Critical/Warning/Info の3段組 Markdown、`file:line` 根拠付き）を **そのままチャットに表示する**。要約・省略はしない。

## Step 3: 対応確認

Critical が1件以上ある場合、AskUserQuestion で対応要否を確認する。

**質問**: 「Critical な指摘が{件数}件あります。対応しますか？」

**選択肢**:
- `対応する` — 指摘内容を1件ずつ確認し、Edit で修正する（誤検知の可能性があるため、修正前に該当コードを Read して妥当性を確認すること）
- `今回は見送る` — 指摘内容のみ記録し、修正はしない

Warning/Info のみの場合は確認不要。結果を提示して終了する。

---

## 注意事項

- 実エンジンによる自動検出のため誤検知があり得る。指摘を鵜呑みにせず、該当コードを確認してから対応する
- FLS/CRUD の権限設定の妥当性・設計意図との整合性など、機械的に検出できない観点は reviewer.md 側のチェックリストで別途確認する
