# /test [課題ID]

Salesforce 保守課題の実装後テストを全自動実行し、エビデンスを証跡採取・Excel 出力する。

`/backlog` Phase 5（スモーク確認）PASS 後に実行する網羅的テスト工程。証跡を自動採取し Excel 出力する。

---

## 前提条件

| 前提 | 確認方法 |
|---|---|
| `/backlog` Phase 4（実装）完了 + Phase 5（スモーク確認）PASS 後であること | `implementation-plan.md` の存在を確認（※これは Phase 3 成果物。実装・スモーク完了自体は自動検査されない前提条件） |
| Sandbox org に認証済みであること | `sf auth list` でログイン状態を確認 |
| `docs/logs/{issueID}/test-spec.md` が存在すること | Phase B で生成。なければ Phase B を先に実行 |
| Pillow インストール | Phase A で自動インストール実行。失敗時は手動貼付にフォールバック |

---

## フェーズ構成

### Phase A: 前提検証・接続確認

> **[ハーネス直接実行]**

```bash
# 1. 課題ID の解決
ISSUE_ID="{issueID}"
if [ -z "$ISSUE_ID" ]; then
  echo "[FATAL] 課題IDを指定してください: /test GF-350"
  exit 1
fi

# オプション（/test {issueID} [--full] [--force]）— アシスタントが起動引数から置換
#   --full 指定時 → FORCE_FULL=1 / 未指定 → 空
#   --force 指定時 → FORCE_SPEC=true / 未指定 → false
FORCE_FULL="{force_full}"
FORCE_SPEC="{force_spec}"

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

> **[ハーネス直接実行（A-2: デプロイ・環境準備）]**

```bash
# SF_ALIAS の再導出（Bash ツールは毎回新シェル。A-1 の変数を引き継げないため再取得）
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
```

---

### Phase B: テスト仕様の展開

> **[test-spec-builder へ委譲]**

`test-spec-builder` への委譲パラメータ:
- `issueID`: `{issueID}`
- `project_dir`: `{PROJECT_DIR}`
- `log_dir`: `{LOG_DIR}`
- `impl_plan_path`: `{LOG_DIR}/implementation-plan.md`
- `investigation_path`: `{LOG_DIR}/investigation.md`
- `spec_path`: `{SPEC_PATH}`（出力先）
- `pattern_map_path`: `.claude/templates/backlog/test-pattern-map.md`
- `force`: `${FORCE_SPEC:-false}`（`--force` 指定時は true）

`test-spec-builder` が `test-spec.md` を生成し、網羅性セルフチェックを完了させる。

> **仕様スキーマ（参考）**: 9 列 — No / 観点 / 種別 / 前提・データ準備 / 実行アクション / 期待結果 / 判定方法 / 証跡取得 / 自動化可否。  
> 詳細な展開ルール・種別選択肢・自動化可否判断基準・網羅性チェック手順は `test-spec-builder.md` に定義されている。

既に `test-spec.md` が存在する場合はスキップ（`--force` 指定時は再生成）。

---

### Phase C: 自動テスト実行＋証跡採取

> **[auto-evidence-runner（オーケストレータ）へ委譲]**

`auto-evidence-runner` への委譲パラメータ:
- `issueID`: `{issueID}`
- `alias`: `{SF_ALIAS}`
- `project_dir`: `{PROJECT_DIR}`
- `log_dir`: `{LOG_DIR}`
- `evidence_dir`: `{EVIDENCE_DIR}`
- `xlsx_folder`: `{XLSX_FOLDER}`
- `spec_path`: `{SPEC_PATH}`
- `target_tc_list`: `{TARGET_TC_LIST}`（空=全件）
- `max_workers_soql`: 4（低速組織や API 制限が疑われる場合は 1 で逐次 / `--serial` を渡す）
- `max_workers_anon`: 3（同上）
- `serial`: false（`--serial` 指定時は true で全逐次フォールバック）

**実行の流れ**（`auto-evidence-runner` 内部）:
1. 種別仕分け＋差分対象 TC の絞り込み
2. SOQL → `soql_evidence.py --queries-file --max-workers 4`（内部並列）
3. AnonApex → コード生成（LLM）→ `anon_apex_runner.py run-batch --max-workers 3`（内部並列）
4. ApexTest → 直列実行
5. UI → `ui-evidence-runner` に委譲（種別=UI が 0 件なら起動しない）
6. 証跡存在確認 → cleanup（逐次）→ test-report.md 生成

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
if [ ! -f "{judgment_path}.prev" ] && [ -f "{judgment_path}" ]; then
  cp "{judgment_path}" "{judgment_path}.prev"
fi
if [ -f "{judgment_path}.prev" ]; then
  PREV_ARG="--prev {judgment_path}.prev"
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

#### NG があった場合の差し戻し（期待値ドリフト防止）

> **設計原則**: `investigation.md`（課題原文・真因）は不変。修正は「実装方針の変更」であり「課題認識の変更」ではない。`test-spec.md` の期待結果は NG 理由なく書き換えない。

1. `test-report.md` の「NG 一覧」と `test-fail-routing.md` で戻り先 Phase を確定する
2. **NGの原因と修正方針を `implementation-plan.md` の改版履歴に追記する**（修正に着手する前に必ず実施）:
   ```
   | {YYYY-MM-DD} | /test NG差し戻し | {NGのTC番号・観点} | {NGの原因（実際の結果）} | {修正方針（何をどう変えるか）} | investigation.md §{対応する要求} |
   ```
   これにより「何をなぜ変えたか」が記録に残り、NG 修正ループで実装の方向が課題の真因から静かにずれるのを防ぐ。
3. ユーザーに戻り先 Phase・NG 原因・修正方針（上記で記録した内容）を提示する
4. 修正後に再度 `/test {issueID}` を実行するよう案内する（差分再実行モードで前回 OK の TC は証跡を流用・取り直しなし）

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

修正手順（この順番で実施してください）:
  1. implementation-plan.md の改版履歴にNG原因と修正方針を追記
     （何をなぜ変えるかを記録してから手を動かす。investigation.md は変更しない）
  2. /backlog Phase {N} で修正を実施
  3. /test {issueID} を再実行（差分モード: 前回OK分は証跡を流用）

{要手動がある場合}
要手動確認:
  - TC-00X: {観点} — エビデンス.xlsx「証跡」シートに手動でスクショを貼り付けてください。
```

---

## 注意事項

- **本番組織への操作は Phase A で物理ブロック**。Sandbox alias でのみ実行可。
- accessToken は一切ファイルに保存しない（`sf org open --url-only` のワンタイム URL のみ使用）。
- テストデータは必ず後始末する。削除失敗件数は test-report.md に明記してユーザーに手動対応を依頼。
- `/backlog` Phase 5（スモーク確認）PASS 後の後続工程。スモークが通ってから本コマンドで網羅的テストを実施する。
