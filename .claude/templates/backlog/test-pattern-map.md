# 課題種別 → テストパターンマッピング

`/test` Phase B のテスト仕様展開（test-spec.md 生成）で参照する対応表。
`test-spec-builder`（Phase B）・`auto-evidence-runner`（オーケストレータ）・`backlog-planner` のテスト観点列挙でも参照する。

---

## 目的

**テストの主眼**: Apex / Flow / LWC を実際に動かし「データ準備 → 処理起動 → 結果確認（SOQL ＋ UI）」で実処理の挙動を確認すること。カバレッジはおまけ。AnonApex / UI を最優先実行、ApexTest は回帰・カバレッジ補助。

---

## 種別一覧（実行手段）

| 種別 | 実行手段 | 主な用途 |
|---|---|---|
| `SOQL` | `sf data query` | データ件数・フィールド値の確認 |
| `ApexTest` | `sf apex run test` | 既存テストクラスの回帰確認・権限ロジック（System.runAs） |
| `AnonApex` | `sf apex run --file`（匿名Apex） | データ作成・Flow起動・ビジネスロジック直接実行・結果確認 |
| `UI` | Playwright ヘッドレス | 画面表示・ボタン・遷移・ユーザ別見え方確認 |
| `メタ確認` | Read / Grep | メタデータ XML / JSON の設定値照合 |
| `ファイル確認` | Read / Grep | force-app/ 配下コードの内容確認 |

---

## 課題種別 → 必ず当てる観点

| 課題種別 | 必ず当てる観点（種別） | skip 可な例 |
|---|---|---|
| バグ修正 | 再現解消（AnonApex / UI）＋ 回帰（SOQL / ApexTest） | 本番データ依存の再現 |
| バリデーションルール | 違反データで弾く＋ 正常データが通過（AnonApex） | — |
| トリガ | before / after 各経路 ＋ バルク 200 件 ＋ 再帰防止（AnonApex / ApexTest） | — |
| バッチ | `executeBatch` 起動 → 結果確認（AnonApex）＋ スコープ件数（SOQL） | スケジュール実時刻起動 |
| Flow | Flow 起動 or レコード操作（AnonApex / UI）＋ 結果（SOQL） | 外部呼出経路 |
| LWC | 画面表示・操作・エラー表示（UI: Playwright）＋ コントローラ（ApexTest） | デザイン微調整の目視 |
| 権限・FLS | `System.runAs` での権限差分（ApexTest）＋ 該当ユーザの UI 表示（UI: Login As） | 本番限定権限セット |
| 数式・ロールアップ | 子操作 → 親再計算 ＋ 境界値（AnonApex / SOQL） | — |
| 連携（外部） | `HttpCalloutMock` でモックテスト（ApexTest）＋ Named Credential 設定確認（メタ確認） | 実外部疎通（要手動） |

---

## 権限・ユーザ切り替えテストのアーキテクチャ（runAs＋Login As）

### FLS / CRUD / 共有ロジック → Apex System.runAs（追加認証不要・全自動）

```apex
@IsTest
static void testAsTargetUser() {
    User u = [SELECT Id FROM User WHERE Profile.Name = 'BPM' LIMIT 1];
    System.runAs(u) {
        // 対象処理を実行
        // Assert.isTrue(...) で権限差分を検証
    }
}
```

- 追加認証不要（管理者 alias 1つで動く）
- FLS / CRUD / sharing rules の自動評価に有効（`WITH USER_MODE` も活用可）
- 匿名 Apex では runAs 不可（@IsTest 専用）。権限差分テストは必ず ApexTest に寄せる

### UI 表示差分（権限別画面） → Playwright + Login As（管理者1認証のまま）

1. 管理者 frontdoor URL でログイン
2. 設定 → ユーザの管理 → 対象ユーザのページを開く
3. 「ユーザに代わってログイン（Login As）」をクリック
4. 対象画面でスクショ取得
5. 「{ユーザに代わってログアウト}」で管理者に戻る
6. 次のユーザへ

**前提チェック**: 組織設定「管理者によるユーザログインを許可」が有効であること（Sandbox では一般的に有効）。無効の場合は `要手動（Login As 不可）` に降格して auto-evidence-runner に記録する。

**対象ユーザ名**: test-spec 「前提・データ準備」列に対象プロファイル/ユーザを記載 → 実ユーザ名は org-profile.md から解決（不明時のみユーザー確認）。

---

## 判定方法の選択肢

| 判定方法 | 使いどころ |
|---|---|
| `件数一致` | SOQL 結果件数が期待値と一致 |
| `含む` | SOQL 結果・Apex ログに特定文字列が存在 |
| `完全一致` | フィールド値・メタ設定値が完全一致 |
| `存在確認` | ファイル・レコード・設定の存在 |
| `Apex PASS` | `sf apex run test` が全テスト PASS |
| `PNG 存在` | スクショ PNG が 1KB 以上存在 |
| `スクショ＋DOM照合` | 画面表示の確認（PNG＋ `browser_snapshot` のペアで自動判定。期待テキストが DOM に含まれるか機械照合） |

> **廃止**: `スクショ目視（要手動に格下げ推奨）` — これは使わない。画面確認は常にスクショ＋DOM照合で自動実行する。

---

## skip 可の判断基準

**原則: 判断に迷うケースは `自動` にする。要手動は以下の3類型のみ許容する**:

1. **実外部サービスへの実通信が必須**（Webhook・外部 API への実疎通が避けられない）
2. **本番限定データ・権限セットが物理的前提**（Sandbox に再現不可能な本番固有設定が必要）
3. **Salesforce のスケジュール実時刻起動が必須**なバッチ（cronトリガーの発火待ちが前提）

**要手動にしてはいけないケース（= 全て自動）**:
- 画面表示・ボタン・フォーム・エラーメッセージの確認 → `UI`（Playwright）
- 複数ユーザの表示差分 → `UI: Login As`（管理者1認証で切替）
- 条件分岐ごとの挙動確認 → `AnonApex` or `UI`（分岐ごとに実行）
- Login As: 組織設定の有効/無効は**実行時に検知して初めて降格**（事前に要手動にしない）
