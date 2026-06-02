# Salesforce 標準仕様 集約知識

このファイルはどのプロジェクトでも参照される共通の Salesforce 標準仕様。
**プロジェクト固有の挙動はここに書かない**（docs/overview/ または docs/catalog/ へ）。

最終照合日: 2026-05-26（次回 `option-sf-docs-verification` 実行時に更新すること）

---

## §ガバナ制限（数値一覧）

| 制限項目 | 同期トランザクション | 非同期トランザクション |
|---|---|---|
| SOQL クエリ実行回数 | 100 | 200 |
| DML 文の回数 | 150 | 150 |
| SOQL で取得できる合計レコード数 | 50,000 | 50,000 |
| SOQL クエリ結果のサイズ | 制限なし（行数制限のみ） | — |
| ヒープサイズ | 6 MB | 12 MB |
| CPU タイム | 10,000 ms | 60,000 ms |
| コールアウト回数 | 100 | 100 |
| コールアウトタイムアウト合計 | 120,000 ms | 120,000 ms |
| メール送信先アドレス数（1トランザクション） | 10 | 10 |
| Future メソッドの最大キュー数（1トランザクション） | 50 | — |
| Queueable ジョブのネスト | 1 | — |
| 一括処理（Batchable）一度に処理可能なレコード数 | — | 50,000,000 |

### 注意ポイント
- DML / SOQL は**ループ外**に配置（バルク処理必須）
- `Database.insert(list, false)` で部分コミット可能（一括 allOrNone: false）
- バッチ処理の `execute()` は scope サイズ 200 が一般的な推奨値

---

## §トリガ実行順序

1. システム入力規則（System Validation Rules）
2. **Before triggers**（before insert / before update / before delete）
3. カスタム入力規則（Custom Validation Rules）
4. 重複チェックルール
5. レコードを保存（未コミット）
6. **After triggers**（after insert / after update / after delete / after undelete）
7. 割り当てルール（Lead / Case Assignment Rules）
8. 自動応答ルール（Auto-response Rules）
9. ワークフロールール（非推奨。処理後に before/after が再実行される場合あり）
10. エスカレーションルール
11. フロー自動化（Record-Triggered Flow）
12. プロセスビルダー（非推奨）
13. ロールアップ集計項目の再計算
14. 共有ルールの再評価

### 注意ポイント
- 1回の DML 操作でトリガが複数回実行される場合がある（`Trigger.isExecuting` の確認は必須）
- 再帰トリガを防ぐためのフラグ（`Set<Id>` や `static Boolean`）を使う
- Record-Triggered Flow と Apex トリガが**同一オブジェクトに存在する場合**は実行順序を設計書に明記する
- `before update` でのフィールド変更は DML 不要（`Trigger.new` の項目を直接変更）

---

## §sharing 評価順序

Salesforce のレコードアクセス判定は以下の順序で「最も広い権限」を OR で評価:

1. **OWD（Organization-Wide Defaults）** — オブジェクトのデフォルトアクセス設定（Private/Read Only/Read Write/Controlled by Parent）
2. **ロール階層** — OWD が Public でない場合、上位ロールのユーザーは下位のレコードを参照可
3. **共有ルール（Sharing Rules）** — 条件や役割グループに基づいて追加付与
4. **手動共有（Manual Sharing）** — レコードオーナーまたは上位者が個別付与
5. **Apex 共有（Apex Managed Sharing）** — コードで `Share` オブジェクトに手動挿入
6. **with sharing キーワード（Apex コード内）** — 評価された最終的な共有設定をコードに適用

### 注意ポイント
- `with sharing` — ランタイムの共有設定を強制適用（推奨・デフォルト）
- `without sharing` — 共有設定をスキップ（FLS も適用されない）
- `inherited sharing` — 呼び出し元のコンテキストを継承（default: without sharing と同等）
- OWD が `Private` でもロール階層が有効な場合は上位者が閲覧可能（意図せぬ参照漏れに注意）

---

## §Profile vs PermissionSet 優先順位

### 権限の評価ルール
- オブジェクト・FLS 権限は **Profile + PermissionSet の OR 評価**（Permission Set が権限を「広げる」だけで「狭める」はできない）
- Profile で No → PermissionSet で Yes → **ユーザーはアクセス可能**
- Profile で Yes → PermissionSet で No → **ユーザーはアクセス可能**（狭めることはできない）

### FLS（Field-Level Security）の優先順位
- Profile で Read Only → PermissionSet で Edit → **Edit が有効**（広い方が勝つ）
- Profile で Hidden → PermissionSet で Read Only → **Read Only が有効**

### Permission Set Group
- 複数の PermissionSet をグループ化して一括付与可能
- Muting Permission Set でグループ内の特定権限を打ち消せる（唯一「狭める」手段）

### 注意ポイント
- Custom Profile の DML 権限を確認しないと「Profile では Read Only なのに PermissionSet でも Edit が当たって更新できてしまう」設計漏れが起きる
- テストクラスでは `System.runAs(user)` で共有設定・FLS を有効にしてテストすること

---

## §FLS 評価のタイミング

| 操作 | FLS 評価 |
|---|---|
| 標準 UI（Lightning/Classic） | **自動評価（非表示 or エラー）** |
| Apex `with sharing` | **評価されない**（明示的な確認が必要） |
| Apex `without sharing` | **評価されない** |
| `SOQL WITH SECURITY_ENFORCED` | FLS 対象外の項目があれば **例外スロー** |
| `SOQL WITH USER_MODE` (API v56+) | FLS・sharing 両方を強制評価（推奨） |
| `Schema.SObjectField.getDescribe().isAccessible()` | 手動で FLS チェック可能 |
| LWC `@AuraEnabled` | **自動評価されない**（Apex 側で明示確認） |
| `Database.query()` + Security.stripInaccessible() | 非アクセス項目を Apex 側でフィルタ |

### 推奨パターン（FLS チェック）
```apex
// SOQL 単体の場合（v56+）
List<Account> accounts = [SELECT Id, Name FROM Account WITH USER_MODE];

// Apex コード内での明示チェック
if (!Schema.sObjectType.Account.fields.Name.isAccessible()) {
    throw new System.NoAccessException();
}

// stripInaccessible パターン（CRUD+FLS 両対応）
SObjectAccessDecision decision = Security.stripInaccessible(
    AccessType.READABLE, accounts
);
List<Account> filteredAccounts = decision.getRecords();
```

---

## §LWC ⇔ Apex データ往復ルール

### @AuraEnabled の cacheable 属性
| 属性 | 読み取り | 書き込み | キャッシュ |
|---|---|---|---|
| `@AuraEnabled(cacheable=true)` | 可 | **不可**（DML 等は例外スロー） | あり（ブラウザキャッシュ） |
| `@AuraEnabled(cacheable=false)` | 可 | 可 | なし |

### データ型の制限
- 戻り値は **JSON シリアライズ可能な型のみ**（`SObject` / `List` / `Map<String, Object>` / プリミティブ）
- `Map<Id, List<SObject>>` は可。`Map<Schema.SObjectType, ...>` は不可
- `AuraHandledException` を使うとユーザー向けメッセージとして表示される

### リアクティブプロパティ・Wire
```javascript
// Wire でキャッシュ付き取得（cacheable=true が必要）
@wire(getRelatedData, { recordId: '$recordId' })
wiredData({ error, data }) { ... }

// Imperative call（ボタン押下時など。cacheable 不問）
const result = await getRelatedData({ recordId: this.recordId });
```

### 注意ポイント
- `cacheable=true` の Apex は **トランザクション単位のガバナ制限には含まれない**（Wire は別コンテキスト）
- LWC から LWC へデータを渡す場合は `@api` プロパティ / `CustomEvent` / `pubsub` / `@wire(MessageContext)` のいずれかを選ぶ
- `@track` は廃止（現在は全プロパティがリアクティブ）

---

## §よくある落とし穴（標準仕様起因・全プロジェクト共通）

| # | 落とし穴 | 影響 | 対処 |
|---|---|---|---|
| 1 | Boolean 数式項目で `BlankAsZero` 未設定時の `null` 比較 | 条件分岐が意図通りに動かない | 数式項目作成時は `BlankAsZero = true` を設定 |
| 2 | SOQL / DML をループ内に記述 | ガバナ制限超過（100/150回） | ループ外でリスト取得→ループ内で処理 |
| 3 | `Trigger.new` を `before update` で直接 DML | 「DML prohibited in before trigger」例外 | before では `Trigger.new` の値を直接変更するだけでよい |
| 4 | `String.valueOf(null).contains(...)` | NullPointerException | null チェック後に操作 |
| 5 | Test クラスで `Test.startTest()` / `stopTest()` なし | 非同期処理（Future / Queueable）がテスト内で実行されない | `Test.startTest()` 〜 `Test.stopTest()` で囲む |
| 6 | `@wire` と `@AuraEnabled(cacheable=false)` の組み合わせ | ランタイムエラー（Wire は cacheable=true 必須） | Wire 用の Apex には `cacheable=true` を付ける |
| 7 | FLS チェックなしの Apex で SOQL → UI に表示 | 非表示フィールドのデータが Apex から返却される | `WITH USER_MODE` / `Security.stripInaccessible` / 明示 `isAccessible()` を使う |
| 8 | Record-Triggered Flow と Apex トリガの二重実行 | 同一処理が2回走りデータ整合性が崩れる | 設計書に実行順序を明記し、どちらか一方に集約 |
| 9 | `SOQL WHERE Id IN :idSet`（`idSet` が空） | `SOQL WHERE Id IN :()` → 構文エラー | `if (!idSet.isEmpty())` のガードを忘れない |
| 10 | Contact 名変更時に User.Name と非同期で乖離 | 関連表示名が一致しない（ユーザー報告の誤認につながる） | Contact→User の同期は `Trigger.afterUpdate` で User 更新または運用周知 |
| 11 | Contact Trigger で User を更新する際に Mixed DML エラーを警戒して不要な @future を追加 | 過剰実装・工数増大 | 下記 §User の Mixed DML 例外ルール を参照 |
| 12 | `with sharing` Apex でも FLS は自動評価されない | 非表示フィールドが返る | FLS は必ず明示確認（§FLS 評価のタイミング 参照） |
| 13 | `Database.insert(records)` で null レコードが混入 | NullPointerException | リスト生成前に `addAll` や `add(null)` が混入していないか確認 |

---

## §User の Mixed DML 例外ルール

**出典**: [Apex 開発者ガイド — 非 sObject との DML 操作の混在（日本語版）](https://developer.salesforce.com/docs/atlas.ja-jp.apexcode.meta/apexcode/apex_dml_non_mix_sobjects.htm)

### 原則

Salesforce では「セットアップオブジェクト（User / UserRole 等）」と「非セットアップオブジェクト（Account / Contact 等）」を同一 Apex トランザクションで DML すると `MIXED_DML_OPERATION` エラーになる。

### 例外（User のみ適用）

API バージョン **15.0 以降**で保存された Apex の場合、以下の**両方を満たす場合は** Contact 等と同一トランザクションで `update user` が可能:

1. そのユーザーが Lightning Sync 設定（有効・無効問わず）に**含まれていない**
2. 以下のフィールドを**更新しない**:
   - `UserRoleId`
   - `IsActive`
   - `ForecastEnabled`
   - `IsPortalEnabled`
   - `Username`
   - `ProfileId`

→ **`FirstName` / `LastName` の更新は上記フィールドに該当しないため、Apex Trigger の after update から直接 `update user` できる（@future 不要）**

### Flow での挙動

宣言的 Record-Triggered Flow からの User 更新は Apex の Mixed DML 制約を受けない。Contact トリガーフローで User.FirstName / LastName を直接更新しても `MIXED_DML_OPERATION` は発生しない（実証済み）。

### 設計上の判断指針

| ケース | 推奨実装 |
|---|---|
| Contact → User の名前同期（FirstName/LastName のみ） | **Flow（最もシンプル）** または Apex Trigger 直接 update（@future 不要） |
| UserRoleId / IsActive / ProfileId 等の変更を伴う場合 | Apex @future または Queueable 必須 |
| Apex Trigger 内で上記例外に該当するか不明な場合 | `[要確認: Lightning Sync 設定 + 更新フィールド確認]` とマークして実装者に判断させる |

---

## 参考: 公式ドキュメント

- ガバナ制限一覧: https://developer.salesforce.com/docs/atlas.en-us.apexcode.meta/apexcode/apex_gov_limits.htm
- トリガ実行順序: https://help.salesforce.com/s/articleView?id=sf.trigger_order_of_execution.htm
- FLS チェック方法: https://developer.salesforce.com/docs/atlas.en-us.apexcode.meta/apexcode/apex_classes_enforce_usermode.htm
- LWC と Apex の連携: https://developer.salesforce.com/docs/component-library/documentation/en/lwc/apex
