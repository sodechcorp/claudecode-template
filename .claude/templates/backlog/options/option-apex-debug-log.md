# option-apex-debug-log

## 何をするか

Apex デバッグログを取得・解析し、バグの発生箇所・例外内容・実行時の変数値を特定する。「コードを読んだだけでは分岐到達を確認できない」「エラー/例外が出ているが発生箇所が不明」「処理が走っているかどうか不明」なケースで実行時挙動を直接確認する。

## 実行手順

### Step 1: 前提確認

1. Sandbox 接続を確認する:
   ```bash
   sf org display --target-org <sandbox-alias> --json
   ```
   - `isSandbox: true` であること。本番（false）ではこのオプションを実行しない
   - alias が不明な場合: `sf config list --json` で `target-org` を確認する
   
2. 既存ログの確認（直近ログがあれば再現前に取得を試みる）:
   ```bash
   sf apex log list --target-org <sandbox-alias> --json
   ```
   - 課題の発生時刻に近いログがあれば `sf apex log get` で取得 → Step 4 へ
   - 関係するログがなければ Step 2 へ

### Step 2: TraceFlag 設定（ログ有効化）

課題で報告された操作ユーザーに合わせて TraceFlag を設定する:

```bash
# 操作ユーザーのIDを取得
sf data query --query "SELECT Id, Name, Username FROM User WHERE Username = '<username>' LIMIT 1" \
  --target-org <sandbox-alias> --json

# TraceFlag を設定（30分）
sf data create record --sobject DebugLevel \
  --values "DeveloperName=BugInvestigation MasterLabel=BugInvestigation ApexCode=FINEST ApexProfiling=INFO Callout=INFO Database=FINEST System=DEBUG Validation=INFO Visualforce=INFO Workflow=INFO" \
  --target-org <sandbox-alias> --json

sf data create record --sobject TraceFlag \
  --values "LogType=USER_DEBUG TracedEntityId=<UserId> DebugLevelId=<DebugLevelId> StartDate=$(date -u +%Y-%m-%dT%H:%M:%SZ) ExpirationDate=$(date -u -d '+30 minutes' +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || date -u -v+30M +%Y-%m-%dT%H:%M:%SZ)" \
  --target-org <sandbox-alias> --json
```

> 設定が困難な場合は `ApexCode=DEBUG` に下げて再試行。`date` コマンドは OS によって異なる（Mac/Linux 共用の場合は代替手順を検討）。

### Step 3: 症状を再現する

investigation.md の「再現条件」セクション（Step A.5 で作成済み）に従い、Sandbox で操作を再現する:
- Playwright MCP で UI 操作を行う（`mcp__playwright__browser_*`）
- または「再現コマンドを実行する形式」であれば Anonymous Apex を使用する:
  ```bash
  sf apex run --file /tmp/reproduce_bug.apex --target-org <sandbox-alias> --json
  ```

再現後、すぐに Step 4 へ進む（TraceFlag の有効期限内に取得）。

### Step 4: ログ取得・解析

```bash
# ログ一覧を確認（最新のものが対象）
sf apex log list --target-org <sandbox-alias> --json

# ログを取得（最新のログIDを指定）
sf apex log get --log-id <logId> --target-org <sandbox-alias> > /tmp/apex_debug.log

# 重要箇所を抽出
grep -E "(FATAL_ERROR|EXCEPTION_THROWN|SOQL_EXECUTE_BEGIN|CODE_UNIT_STARTED|USER_DEBUG|DML_BEGIN|VALIDATION_FAIL)" /tmp/apex_debug.log | head -100
```

解析の着眼点:
| ログイベント | 着眼点 |
|---|---|
| `EXCEPTION_THROWN` | 例外クラス・メッセージ・スタックトレース → 発生箇所の特定 |
| `FATAL_ERROR` | ガバナ制限超過・未ハンドル例外 → 根本原因 |
| `CODE_UNIT_STARTED` | Trigger/Flow/Apex の実行開始 → 呼び出し順序の確認 |
| `SOQL_EXECUTE_BEGIN` | 実行された SOQL・件数 → 0件返却・ガバナ消費の確認 |
| `USER_DEBUG` | 開発者が仕込んだデバッグ出力 → 変数値・条件分岐の状態 |
| `VALIDATION_FAIL` | Validation Rule 名 → UI エラーの発生源 |
| `DML_BEGIN` | INSERT/UPDATE 件数 → DML が実行されたか |

### Step 5: TraceFlag の後片付け

```bash
# TraceFlag を削除（期限が来れば自動削除されるが明示的に消す）
sf data delete record --sobject TraceFlag --record-id <TraceFlagId> --target-org <sandbox-alias> --json
```

## 出力

investigation.md「根本原因」セクションに追記:

```markdown
## Apex デバッグログ解析結果

- ログ取得日時: {YYYY-MM-DD HH:MM}
- 再現操作: {何を行ったか}
- 対象ユーザー: {Username / Profile}

### 重要ログ抜粋

```
{EXCEPTION_THROWN / FATAL_ERROR / CODE_UNIT_STARTED の該当行}
```

### 発見事項

| 項目 | 内容 |
|---|---|
| 例外発生箇所 | {クラス名:行番号} |
| 例外メッセージ | {メッセージ} |
| 実行されなかった処理 | {CODE_UNIT が現れなかった箇所} |
| SOQL で 0 件返却 | {クエリ内容 + 0件の理由仮説} |

### 仮説への影響

- H{N}（{仮説名}）: {ログが支持する / 反証する} → 尤度を {高/中/低} に更新
```

## 禁止事項

- **本番組織での TraceFlag 設定・ログ取得は原則禁止**。本番ログが不可欠な場合は `option-prod-select-reference` 準拠でユーザー明示許可を得てから実行する
- 本番に対する INSERT / UPDATE / DELETE / UPSERT / DML 実行は絶対禁止
- context 肥大を防ぐため、ログ全文を investigation.md に貼り付けない。抽出した重要行のみを記録する

## context 肥大への対処

ログが大きい（数千行超）場合は Agent ツールで使い捨て subagent に委譲してサマリーのみ持ち帰る:

```
Agent:
ログファイル /tmp/apex_debug.log を読み、以下の情報を抽出して返してください:
1. EXCEPTION_THROWN / FATAL_ERROR の行（前後3行含む）
2. CODE_UNIT_STARTED の一覧（クラス名のみ）
3. SOQL_EXECUTE_BEGIN で 0 行返却のクエリ
4. USER_DEBUG の全出力
```
