# 指示パターン別の動き方 詳細手順

> 各パターン開始前に `docs/overview/org-profile.md`（用語集）を確認すること。全パターン共通。

## 「項目を作って」「項目追加して」

1. `docs/catalog/` で対象オブジェクトの既存構成を確認
2. `docs/overview/org-profile.md` の用語集で命名を統一
3. プロジェクトルート `CLAUDE.md` の命名規則に従う
4. `force-app/` が存在するか確認 → なければ「`/sf-retrieve` または `sf project retrieve` を実行して force-app/ を生成してください」と案内してから続行
5. メタデータファイルを作成（force-app 配下）
6. **権限・基本設定を設定する**: [new-metadata-permissions-checklist.md](new-metadata-permissions-checklist.md) の「カスタム項目」セクションに従い、FLS（権限セット）・ページレイアウト配置を必ず実施。チェック漏れを黙殺しない
7. `docs/catalog/` の該当定義書を更新（項目追加を反映）

## 「オブジェクトを作って」「カスタムオブジェクト追加して」

1. `docs/catalog/` で既存オブジェクト構成・命名規則を確認
2. `docs/overview/org-profile.md` の用語集で命名を統一
3. プロジェクトルート `CLAUDE.md` の命名規則に従う
4. メタデータファイルを作成（`force-app/main/default/objects/` 配下）
5. **権限・基本設定を設定する**: [new-metadata-permissions-checklist.md](new-metadata-permissions-checklist.md) の「カスタムオブジェクト」セクションに従い、CRUD権限・タブ・ページレイアウト・アプリ追加を必ず実施
6. `docs/catalog/` に新オブジェクトの定義書を作成

## 「レコードタイプを作って」

1. 対象オブジェクトの既存レコードタイプ構成（`force-app/` の `recordType-meta.xml`）を確認
2. 要件（ピックリスト制限・レイアウト分岐・対象ユーザー）を確認
3. メタデータファイルを作成
4. **権限・基本設定を設定する**: [new-metadata-permissions-checklist.md](new-metadata-permissions-checklist.md) の「レコードタイプ」セクションに従い、権限セット割当・レイアウト割当・ピックリスト値割当を必ず実施

## 「タブを作って」

1. 対象オブジェクト・Webタブ・VFページ等の種別を確認
2. メタデータファイルを作成（`force-app/main/default/tabs/` 配下）
3. **権限・基本設定を設定する**: [new-metadata-permissions-checklist.md](new-metadata-permissions-checklist.md) の「タブ」セクションに従い、権限セットのタブ表示設定・アプリへの追加を必ず実施

## 「Apex 作って」「トリガー書いて」

1. `docs/design/apex/` に該当設計書があるか確認 → あれば設計に従う
2. `docs/catalog/` で対象オブジェクトの項目・リレーションを確認
3. `docs/requirements/requirements.md` で関連するビジネスルール（BR-XXX）を確認
4. Quality Standards に従って実装（バルク対応・テストクラス付き）
5. **権限・基本設定を確認する**: [new-metadata-permissions-checklist.md](new-metadata-permissions-checklist.md) の「Apex クラス」セクションに従い、対象権限セットへの `classAccesses` 付与を確認
6. 設計書がない場合は「設計書がありませんが実装しますか？先に `sf-architect` に設計書作成を依頼することも可能です」と提案

## 「フロー作って」

1. `docs/design/flow/` に該当設計書があるか確認 → あれば設計に従う
2. `docs/catalog/` で対象オブジェクトの入力規則・既存自動化を確認（競合リスク）
3. 実装してメタデータファイルを作成
4. **権限・基本設定を確認する**: [new-metadata-permissions-checklist.md](new-metadata-permissions-checklist.md) の「フロー」セクションに従い、画面フローの場合は実行権限を確認
5. 設計書がない場合は「設計書がありませんが実装しますか？先に `sf-architect` に設計書作成を依頼することも可能です」と提案

## 「バグ直して」「エラー出る」

1. エラー内容を確認
2. `docs/catalog/` で関連オブジェクト・項目を把握
3. `docs/design/` で該当機能の設計意図を確認
4. `docs/requirements/requirements.md` で関連ビジネスルールを確認（仕様なのかバグなのか判断）→ ファイルがない場合はスキップして次へ
5. 修正実施

## 「デプロイして」

1. `docs/logs/changelog.md` で最近の変更を確認
2. 対象のメタデータを確認
3. デプロイコマンドを提示してユーザー確認待ち（**本番組織は絶対に実行しない** → Security セクション参照）
4. ユーザーが「実行して」と指示した場合: Sandbox/開発環境ならコマンドを実行。本番ならユーザー自身での実行を促して終了する

## スコープ外の依頼（`docs/requirements/requirements.md` のスコープ定義と合致しない場合）

1. 作業を始める前に「この依頼は現在のスコープ定義に含まれていない可能性があります」と伝える
2. 該当するスコープ定義を引用して提示する
3. 以下の選択肢を提示する:
   ```
   a. スコープに追加して進める（要件定義書を更新します）
   b. スコープ外として対応しない
   c. スコープを確認してから判断する
   ```
4. ユーザーの判断を待ってから動く。勝手に進めない

requirements.md にスコープ定義がない場合はこのチェックをスキップして作業する。

## docs が存在しない場合

セットアップ直後や docs が空の場合でも開発は可能。ただし:
- 「用語集がないため、命名は一般的なSalesforce慣例に従います」と伝える
- 「設計書が見つかりません。要件を教えてください」と聞く
- 作業後に「`/sf-memory` で定義書を更新することを推奨します」と提案
