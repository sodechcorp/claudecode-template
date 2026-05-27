# 開発時の振る舞いルール

**日本語の指示に対して、docs/ のコンテキストを活用して精度の高い作業を行う。**

## 作業前に必ず参照するもの

どんな開発タスクでも、着手前に以下を確認する:

| 状況 | 参照先 | 理由 |
|---|---|---|
| **常に** | `docs/overview/org-profile.md` | 用語集でオブジェクト名・項目名の正しい対応を確認 |
| 項目・オブジェクト操作 | `docs/catalog/{対象}.md` | 既存の項目構成・リレーション・入力規則を把握 |
| 機能実装 | `docs/design/{種別}/` | 該当機能の設計書があれば設計に従う |
| 要件確認 | `docs/requirements/requirements.md` | 要件番号・ビジネスルール・受入基準を確認 |
| マスタ参照 | `docs/data/master-data.md` | ピックリスト値・商品名等の正確な値を使う |
| メール関連 | `docs/data/email-templates.md` | 既存テンプレートのトーン・差し込み項目を把握 |
| 自動化・承認関連 | `docs/data/automation-config.md` | 既存のキュー・承認プロセスを把握 |

## 指示パターン別の動き方

詳細手順: `.claude/templates/common/dev-task-patterns.md` 参照

| パターン | 概要 |
|---|---|
| 「項目を作って」 | catalog 確認 → force-app 確認 → 作成 → catalog 更新 |
| 「Apex 作って」 | docs/design/apex 確認 → バルク実装 → 設計書なければ提案 |
| 「フロー作って」 | docs/design/flow 確認 → 競合チェック → 実装 |
| 「バグ直して」 | エラー確認 → catalog/design → requirements 確認 → 修正 |
| 「デプロイして」 | changelog 確認 → メタデータ確認 → 提示してユーザー確認待ち |
| スコープ外の依頼 | スコープ確認 → 3択提示 → ユーザー判断待ち |

## docs が存在しない場合

docs がない場合: 「命名は一般的なSalesforce慣例に従います」と伝え、作業後に `/sf-memory` 実行を提案する。

## 実装後のドキュメント更新（全エージェント共通）

実装完了時にドキュメントも更新する。提案ではなく実行する。対象ファイルが存在しない場合のみ作成を提案。`docs/logs/changelog.md` に変更サマリを1行追記する。

更新対象マッピング: `.claude/templates/common/post-implementation-doc-update.md` 参照

## 判断記録の自動追記

保守課題や設計判断で「なぜこの方針にしたか」を決定した場合、`docs/decisions.md` に記録を追記する。

**記録するタイミング**: `/backlog` で方針確定・実装完了したとき / 複数案から1つを選択したとき / 既存実装の背景・制約が判明したとき

**記録しないもの**: 自明な対応（typo修正等）/ 一般的なSalesforceベストプラクティスに従っただけの判断

**形式**: 最上部に追記（降順）。テンプレートのコメントに従う。
