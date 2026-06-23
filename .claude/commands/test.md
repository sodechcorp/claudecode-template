# /test [課題ID]

Salesforce 保守課題の実装後テストを全自動実行し、エビデンスを証跡採取・Excel 出力する。

`/backlog` Phase 4（実装完了）後に実行すること。Phase 5（合同 UI 確認）の代替。

---

## 前提条件

| 前提 | 確認方法 |
|---|---|
| `/backlog` Phase 4（実装）が完了済みであること | `docs/logs/{issueID}/implementation-plan.md` が存在する |
| Sandbox org に認証済みであること | `sf auth list` でログイン状態を確認 |
| `docs/logs/{issueID}/test-spec.md` が存在すること | Phase B で生成。なければ Phase B を先に実行 |
| Pillow インストール | Phase A で自動インストール実行。失敗時は手動貼付にフォールバック |

---

## フェーズ構成

### Phase A: 前提検証・接続確認

> **[ハーネス直接実行]**

```bash
# 1. 課題ID の解決
ISSUE_ID="${1:-}"
if [ -z "$ISSUE_ID" ]; then
  echo "[FATAL] 課題IDを指定してください: /test GF-350"
  exit 1
fi

# 2. プロジェクトルート・ログディレクトリの確定
PROJECT_DIR="$(pwd)"
LOG_DIR="${PROJECT_DIR}/docs/logs/${ISSUE_ID}"

# 3. 必須ファイルの存在確認
if [ ! -f "${LOG_DIR}/implementation-plan.md" ]; then
  echo "[FATAL] implementation-plan.md が見つかりません。/backlog Phase 3 を先に実行してください。"
  exit 1
fi
if [ ! -f "${LOG_DIR}/investigation.md" ]; then
  echo "[WARN] investigation.md が見つかりません。テスト仕様の展開精度が下がる可能性があります。"
fi

# 4. sandbox-alias-check（本番保護）
SF_ALIAS=$(sf config get target-org --json | python -c "import sys,json; print(json.load(sys.stdin)['result'][0]['value'])" 2>/dev/null || echo "")
IS_SANDBOX=$(sf org display --target-org "$SF_ALIAS" --json | python -c "
import sys,json
d=json.load(sys.stdin)['result']
print(d.get('isSandbox')==True or 'sandbox.my.salesforce.com' in d.get('instanceUrl',''))
" 2>/dev/null || echo "false")
if [ "$IS_SANDBOX" != "True" ]; then
  echo "[FATAL] 接続先が Sandbox ではありません ($SF_ALIAS). 本番への操作は禁止されています。"
  exit 1
fi
echo "OK: Sandbox 接続確認済み ($SF_ALIAS)"

# 5. xlsx_folder の確定（優先: investigation.md フロントマター → .backlog_config.yml → LOG_DIR）
XLSX_FOLDER=""
EVIDENCE_DIR=""

# ① investigation.md フロントマターから読む（/backlog と同じ一次ソース）
INVEST_FILE="${LOG_DIR}/investigation.md"
if [ -f "$INVEST_FILE" ]; then
  XLSX_FOLDER=$(python -c "
import sys, re
text = open(r'${INVEST_FILE}', encoding='utf-8').read()
m = re.search(r'^xlsx_folder:\s*(.+)$', text, re.MULTILINE)
print(m.group(1).strip().strip('\"').strip(\"'\")) if m else print('')
" 2>/dev/null || echo "")
  EVIDENCE_DIR=$(python -c "
import sys, re
text = open(r'${INVEST_FILE}', encoding='utf-8').read()
m = re.search(r'^evidence_dir:\s*(.+)$', text, re.MULTILINE)
print(m.group(1).strip().strip('\"').strip(\"'\")) if m else print('')
" 2>/dev/null || echo "")
fi

# ② .backlog_config.yml から読む（後方互換）
if [ -z "$XLSX_FOLDER" ]; then
  CONFIG_FILE="${PROJECT_DIR}/docs/.backlog_config.yml"
  if [ -f "$CONFIG_FILE" ]; then
    XLSX_FOLDER=$(python -c "
import yaml, sys
with open(r'${CONFIG_FILE}', encoding='utf-8') as f:
    d = yaml.safe_load(f) or {}
issues = d.get('issues', {})
print(issues.get('${ISSUE_ID}', {}).get('xlsx_folder', ''))
" 2>/dev/null || echo "")
  fi
fi

# ③ フォールバック: LOG_DIR
if [ -z "$XLSX_FOLDER" ]; then
  XLSX_FOLDER="$LOG_DIR"
  echo "[INFO] xlsx_folder 未設定。${LOG_DIR} に保存します。"
fi
if [ -z "$EVIDENCE_DIR" ]; then
  EVIDENCE_DIR="${XLSX_FOLDER}/evidence"
fi
SPEC_PATH="${LOG_DIR}/test-spec.md"
JUDGMENT_PATH="${LOG_DIR}/judgment-result.json"

# 6. test-spec.md の存在確認（なければ Phase B へ）
if [ ! -f "$SPEC_PATH" ]; then
  echo "[INFO] test-spec.md が見つかりません。Phase B でテスト仕様を展開します。"
fi

# 7. 差分デプロイ（Sandbox へ。本番 alias は上で物理ブロック済み）
echo "=== force-app 差分を Sandbox にデプロイ ==="
sf project deploy start --target-org "$SF_ALIAS" --ignore-conflicts --concise || {
  echo "[FATAL] デプロイ失敗。実装コードを確認してください。"
  exit 1
}
echo "OK: Sandbox デプロイ完了"

# 8. Pillow の存在確認・自動インストール（PNG 自動貼付に必要）
python -c "import PIL" 2>/dev/null || {
  echo "[INFO] Pillow が未インストールです。自動インストールを実行します..."
  pip install Pillow
  if python -c "import PIL" 2>/dev/null; then
    echo "OK: Pillow インストール完了"
  else
    echo "[WARN] Pillow のインストールに失敗しました。PNG 自動貼付を手動貼付にフォールバックします。"
  fi
}

# 9. 差分再実行モードの判定
TARGET_TC_LIST=""
if [ -f "$JUDGMENT_PATH" ] && [ "${FORCE_FULL:-}" != "1" ]; then
  echo "[INFO] 前回の判定結果を検出。差分再実行モードを使用します（前回 OK の TC は再実行しません）。"
  echo "[INFO] 全量再実行する場合は --full オプションを指定してください。"
  TARGET_TC_LIST=$(python -c "
import json, sys
with open(r'$JUDGMENT_PATH') as f: d = json.load(f)
ng = [r['no'] for r in d.get('results', []) if r.get('status') == 'NG']
print(','.join(ng))
" 2>/dev/null || echo "")
  if [ -z "$TARGET_TC_LIST" ]; then
    echo "[INFO] 前回 NG なし。差分対象なし（全件スキップ）。"
  else
    echo "[INFO] 差分対象: $TARGET_TC_LIST"
  fi
else
  echo "[INFO] 全量実行モード（初回または --full 指定）"
fi

# 10. 再開確認
if [ -d "${EVIDENCE_DIR}/after" ]; then
  echo "[INFO] ${EVIDENCE_DIR}/after が既に存在します。差分再実行モードでは非対象 TC の既存証跡を維持します。"
fi
```

**ユーザー確認プロトコル**（実行前に必ず提示する）:

```
=== /test 実行前確認 ===
課題ID    : {issueID}
Sandbox   : {alias}
証跡保存先: {evidence_dir}
Excel出力 : {xlsx_folder}/{issueID}_エビデンス.xlsx

実行内容:
  Phase A: force-app 差分を Sandbox にデプロイ
  Phase B: テスト仕様の展開（test-spec.md 生成・網羅性チェック）
  Phase C: SOQL / Apex テスト / 匿名 Apex / Playwright UI の自動実行（分岐網羅・before/after）
  Phase D: エビデンス.xlsx 生成（スクショ・DOM・SOQL 証跡を自動貼付）
  Phase E: OK/NG 判定・対応記録.xlsx 更新
  Phase F: test-report.md 生成・テストデータ後始末

続行しますか？（テスト実行・データ操作が発生します）
```

---

### Phase B: テスト仕様の展開

> **[auto-evidence-runner へ委譲]**

> **テストの主眼**: Apex / Flow / LWC を実際に動かし「データ準備 → 処理起動 → 結果確認（SOQL ＋ UI）」で実処理の挙動を確認すること。カバレッジはおまけ。AnonApex / UI を最優先実行、ApexTest は回帰・カバレッジ補助。

`implementation-plan.md` の「テスト観点（軽量列挙）」と `investigation.md` のテストシナリオを読み込み、機械実行可能な 9 列スキーマの `test-spec.md` を生成する。

`docs/logs/{issueID}/test-spec.md` に保存する。既に存在する場合はスキップ（`--force` 指定時は再生成）。

**9 列スキーマ**:

| No | 観点 | 種別 | 前提・データ準備 | 実行アクション | 期待結果 | 判定方法 | 証跡取得 | 自動化可否 |

種別の選択肢:
- `SOQL` — sf data query で確認
- `ApexTest` — sf apex run test でテストクラス実行（権限差分テストは System.runAs で）
- `AnonApex` — 匿名 Apex でデータ作成・ロジック起動・Flow 起動（AnonApex を最優先）
- `UI` — Playwright ヘッドレスで画面操作・スクショ（ユーザ別表示差分は Login As で切替）
- `メタ確認` — XML/JSON ファイルを Read/Grep で照合
- `ファイル確認` — force-app/ 配下のファイル内容確認

自動化可否: 以下の3類型のみ `要手動（理由）`。**それ以外は必ず `自動`**。判断に迷う場合は `自動` にする。
  - 実外部サービスへの実通信が必須
  - 本番限定データ・権限セットが物理的前提
  - スケジュール実時刻起動が必須なバッチ
  ※ UI確認・条件分岐・ユーザ別表示はすべて `自動`（Playwright で取得する）

**展開の注意**:
- No は `implementation-plan.md` の TC番号を引き継ぐ（再採番しない。新規観点のみ続き番号で追加）
- 証跡ファイル名は `{No}_{観点サニタイズ}.{txt|png}` 形式とする（before=`before/{No}_{観点}_before.png`、after=`after/{種別}/{No}_{観点}.{txt|png}`）
- 期待結果は「3 件」「true」「エラーなし」等、機械比較可能な値にする
- 判定方法は「件数一致」「含む」「存在確認」「完全一致」等を明示する
- 証跡取得は「SOQL結果txt」「スクショPNG」「Apexデバッグログ」等を明示する
- AnonApex は「前提・データ準備」列に作成するデータとその値（Name プレフィックス等）を具体的に記載する
- 課題種別ごとの必須観点は `.claude/templates/backlog/test-pattern-map.md` に従う。機械不可は `自動化可否=要手動（理由）` で skip 可（無理強いしない）
- 条件分岐がある場合（ビザ種別・入力値・権限等）は**分岐ごとに別の TC 行** or 「証跡取得」列に `{No}_{観点}_{分岐ラベル}.png` / `.txt` を列挙する
- 「期待結果」列は分岐ごとに記述可（例: `I797あり→質問表示 / I797なし→非表示`）

**網羅性セルフチェック**（test-spec.md 生成直後・Phase C 前に必ず実施）:
1. `investigation.md` の「課題原文」各要求 → 対応 TC のマッピングを照合する
2. 未カバーの要求があれば TC を追加してから Phase C に進む
3. 全カバーできたことを確認してから委譲する

---

### Phase C: 自動テスト実行＋証跡採取

> **[auto-evidence-runner へ委譲]**

`test-spec.md` の各ケースを種別に応じて実行し、証跡を `{evidence_dir}` に保存する。

auto-evidence-runner への委譲パラメータ:
- `{target_tc_list}` — Phase A で確定した差分再実行対象の TC番号リスト（空=全件）
- `{evidence_dir}` — `{xlsx_folder}/evidence`

詳細手順は `auto-evidence-runner.md` の Step 2〜6 を参照。

実行後に証跡ファイルの存在確認:
```bash
echo "=== 証跡ファイル一覧 ==="
ls -lhR "{evidence_dir}/after/" 2>/dev/null | grep -E "\.(txt|png)$"
```

---

### Phase D: エビデンス Excel 生成・証跡自動貼付

> **[ハーネス直接実行]**

```bash
python scripts/python/backlog-xlsx/generate_evidence_xlsx.py \
  --folder "{xlsx_folder}" \
  --issue-id "{issueID}" \
  --spec "{spec_path}" \
  --evidence-dir "{evidence_dir}/after" \
  --judgment "{judgment_path}"
```

生成された `{xlsx_folder}/{issueID}_エビデンス.xlsx` を確認:
- 「テスト結果」シートが存在するか
- 「証跡」シートが存在するか
- ケース数が test-spec.md と一致するか

---

### Phase E: OK/NG 判定・結果記入

> **[ハーネス直接実行]**

```bash
# 差分再実行時は前回判定を --prev で渡して前回 OK をマージする
PREV_ARG=""
if [ -f "{judgment_path}.prev" ]; then
  PREV_ARG="--prev {judgment_path}.prev"
elif [ -f "{judgment_path}" ]; then
  cp "{judgment_path}" "{judgment_path}.prev"
fi

python scripts/python/backlog-xlsx/judge_results.py \
  --folder "{xlsx_folder}" \
  --issue-id "{issueID}" \
  --spec "{spec_path}" \
  --evidence-dir "{evidence_dir}/after" \
  --out "{judgment_path}" \
  $PREV_ARG
```

`judge_results.py` は exit 1 で NG を報告する。終了コードを確認:
```bash
echo "判定結果 exit code: $?"
cat "{judgment_path}" | python -c "import sys,json; d=json.load(sys.stdin); print(f'OK={d[\"ok\"]} NG={d[\"ng\"]} 要手動={d[\"skip\"]}')"
```

---

### Phase F: test-report.md 生成・後始末

> **[auto-evidence-runner へ委譲]**

1. `{judgment_path}` を読み、test-report.md を `{log_dir}` に生成する
2. 匿名 Apex で作成したテストデータを削除する（cleanup）
3. 一時ファイル（`{log_dir}/tmp/`）を削除する

#### NG があった場合の差し戻し

1. test-report.md の「NG 一覧」と `test-fail-routing.md` で戻り先 Phase を確定する
2. ユーザーに戻り先 Phase と修正すべき点を提示する
3. 修正後に再度 `/test {issueID}` を実行するよう案内する

#### xlsx 対応記録の更新（タイムライン）

```bash
python scripts/python/backlog-xlsx/update_records.py \
  --folder "{xlsx_folder}" --issue-id "{issueID}" \
  timeline --phase "テスト" --source "Claude" \
  --content "Phase C-F 完了: 全{total}件 {NG=0なら'全件PASS' / NG>0なら 'NG={ng}件'}"
```

---

## 完了後の確認事項

| 確認項目 | 確認コマンド |
|---|---|
| エビデンス.xlsx の存在 | `ls -lh "{xlsx_folder}/{issueID}_エビデンス.xlsx"` |
| test-report.md の存在 | `ls -lh "{log_dir}/test-report.md"` |
| 証跡ファイルの件数 | `find "{evidence_dir}/after" -type f \| wc -l` |
| テストデータ後始末 | anon_apex_runner.py cleanup の結果を確認 |
| tmp/ 削除済み | `ls "{log_dir}/tmp/" 2>/dev/null \| wc -l` が 0 |

---

## 完了報告フォーマット

```
=== /test {issueID} 完了 ===

テスト結果: {OK=N / NG=N / 要手動=N}
総合判定: PASS ✅ / FAIL ❌ （NG が {N} 件）

成果物:
  エビデンス.xlsx : {xlsx_folder}/{issueID}_エビデンス.xlsx
  test-report.md  : {log_dir}/test-report.md
  証跡ファイル    : {evidence_dir}/ 配下 {N} ファイル

{NG がある場合}
NG 一覧:
  - TC-00X: {観点} — {理由}
  → /backlog Phase {N} に差し戻して修正後、再度 /test {issueID} を実行してください。

{要手動がある場合}
要手動確認:
  - TC-00X: {観点} — エビデンス.xlsx「証跡」シートに手動でスクショを貼り付けてください。
```

---

## 注意事項

- **本番組織への操作は Phase A で物理ブロック**。Sandbox alias でのみ実行可。
- accessToken は一切ファイルに保存しない（`sf org open --url-only` のワンタイム URL のみ使用）。
- テストデータは必ず後始末する。削除失敗件数は test-report.md に明記してユーザーに手動対応を依頼。
- `/backlog` Phase 5（合同 UI 確認）とは排他。どちらか一方を使う。
