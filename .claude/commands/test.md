---
description: "Salesforce 保守課題の実装後テストを全自動実行し、証跡採取・OK/NG判定・エビデンスExcel出力まで行う。/backlog Phase 6（Sandboxデプロイ）後に /test [課題ID] で実行。"
---

# /test [課題ID]

Salesforce 保守課題の実装後テストを全自動実行し、エビデンスを証跡採取・Excel 出力する。

`/backlog` Phase 6（Sandbox デプロイ）完了後に実行する網羅的テスト工程。デプロイ済み Sandbox を前提として証跡を自動採取し Excel 出力する（本コマンドはデプロイしない）。

---

## 前提条件

| 前提 | 確認方法 |
|---|---|
| `/backlog` Phase 6（Sandbox デプロイ）完了後であること（デプロイ済み Sandbox 前提） | `implementation-plan.md` の存在を確認（※これは Phase 3 成果物。デプロイ完了自体は自動検査されない前提条件） |
| Sandbox org に認証済みであること | `sf auth list` でログイン状態を確認 |
| `docs/logs/{issueID}/test-spec.md` が存在すること | Phase B で自動生成（不在は許容・`--force` で再生成）。事前の手動用意は不要 |
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
SF_ORG_JSON=$(sf org display --target-org "$SF_ALIAS" --json 2>/dev/null)
IS_SANDBOX=$(echo "$SF_ORG_JSON" | python -c "
import sys,json
d=json.load(sys.stdin)['result']
print(d.get('isSandbox')==True or 'sandbox.my.salesforce.com' in d.get('instanceUrl',''))
" 2>/dev/null || echo "false")
if [ "$IS_SANDBOX" != "True" ]; then
  echo "[FATAL] 接続先が Sandbox ではありません ($SF_ALIAS). 本番への操作は禁止されています。"
  exit 1
fi
echo "OK: Sandbox 接続確認済み ($SF_ALIAS)"

# 4.5. instanceUrl の取得（目視ハンドオフのレコードURL組み立て用。accessToken を含まないため出力可）
INSTANCE_URL=$(echo "$SF_ORG_JSON" | python -c "import sys,json; print(json.load(sys.stdin)['result'].get('instanceUrl',''))" 2>/dev/null || echo "")
echo "INSTANCE_URL=$INSTANCE_URL"

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

# ③ xlsx_folder 未設定 — 自動フォールバック禁止。ユーザー確認待ちマーカーを出力する
if [ -z "$XLSX_FOLDER" ]; then
  echo "[XLSX_FOLDER_UNRESOLVED] investigation.md の xlsx_folder 欄が空で、.backlog_config.yml にも記録がありません。"
  echo "  【診断】原因の可能性: /backlog の Phase 1.5（xlsx_folder 確定ステップ）が未実行、または compact 再開時に investigation.md のフロントマターへ xlsx_folder が書き戻されていない可能性があります。"
  echo "  → investigation.md の frontmatter に 'xlsx_folder:' 行があり値が入っているか確認してください。空なら /backlog を再開してフォルダを確定させると解消します。"
  echo "  対応記録フォルダを特定できません。このまま続行するか、正しいパスを指定してください。"
fi
if [ -n "$XLSX_FOLDER" ] && [ -z "$EVIDENCE_DIR" ]; then
  EVIDENCE_DIR="${XLSX_FOLDER}/evidence"
fi
SPEC_PATH="${LOG_DIR}/test-spec.md"
JUDGMENT_PATH="${LOG_DIR}/judgment-result.json"
echo "XLSX_FOLDER=$XLSX_FOLDER"
echo "EVIDENCE_DIR=$EVIDENCE_DIR"
echo "SPEC_PATH=$SPEC_PATH"
echo "JUDGMENT_PATH=$JUDGMENT_PATH"

# 6. test-spec.md の存在確認（なければ Phase B へ）
if [ ! -f "$SPEC_PATH" ]; then
  echo "[INFO] test-spec.md が見つかりません。Phase B でテスト仕様を展開します。"
fi

# 7. 回次退避 + 差分再実行モードの判定
TARGET_TC_LIST=""
if [ -f "$JUDGMENT_PATH" ] && [ "${FORCE_FULL:-}" != "1" ]; then
  echo "[INFO] 前回の判定結果を検出。差分再実行モードを使用します（前回 OK の TC は再実行しません）。"
  echo "[INFO] 全量再実行する場合は --full オプションを指定してください。"

  # ── 回次退避（今回の実行前に前回データをアーカイブする）──────────────────
  # 退避済み R{N}.json の本数 + 1 が今回の回次番号
  PREV_ROUND=$(python -c "
import glob, re, os
base = r'$JUDGMENT_PATH'.replace('.json','')
files = glob.glob(base + '.R*.json')
nums = [int(m.group(1)) for f in files for m in [re.search(r'\.R(\d+)\.json$', f)] if m]
print(max(nums) if nums else 0)
" 2>/dev/null || echo "0")
  ARCHIVE_N=$((PREV_ROUND + 1))
  ARCHIVED_J="${JUDGMENT_PATH%.json}.R${ARCHIVE_N}.json"
  ARCHIVED_EV="${EVIDENCE_DIR}/after_R${ARCHIVE_N}"
  cp "$JUDGMENT_PATH" "$ARCHIVED_J" 2>/dev/null && echo "[INFO] 回次退避: $ARCHIVED_J"
  if [ -d "${EVIDENCE_DIR}/after" ]; then
    cp -r "${EVIDENCE_DIR}/after" "$ARCHIVED_EV" 2>/dev/null && echo "[INFO] 証跡退避: $ARCHIVED_EV"
  fi
  # ─────────────────────────────────────────────────────────────────────────

  TARGET_TC_LIST=$(python -c "
import json, sys
with open(r'$JUDGMENT_PATH') as f: d = json.load(f)
ng = [r['no'] for r in d.get('results', []) if r.get('status') == 'NG']
print(','.join(ng))
" 2>/dev/null || echo "")
  if [ -z "$TARGET_TC_LIST" ]; then
    echo "[INFO] 前回 NG なし。差分対象なし（全件スキップ）。"
  else
    echo "[INFO] 差分対象（前回 NG）: $TARGET_TC_LIST"
    echo "[INFO] 影響範囲の TC も再テスト対象に含めるか、auto-evidence-runner が確認します。"
  fi
else
  echo "[INFO] 全量実行モード（初回または --full 指定）"
fi

# 8. 再開確認
if [ -d "${EVIDENCE_DIR}/after" ]; then
  echo "[INFO] ${EVIDENCE_DIR}/after が既に存在します。差分再実行モードでは非対象 TC の既存証跡を維持します。"
fi
```

> **⚠️ `[XLSX_FOLDER_UNRESOLVED]` が出力された場合（xlsx_folder 未設定）**:  
> 自動でフォールバックせず、以下をユーザーに確認してから続行する:  
> 「対応記録フォルダが特定できませんでした（investigation.md の `xlsx_folder:` 欄が空）。  
> `docs/logs/{issueID}/` に出力しますか？ または正しいパスを指定しますか？」  
> - **「docs/logs/ に出力する」**: `XLSX_FOLDER = docs/logs/{issueID}/`、`EVIDENCE_DIR = docs/logs/{issueID}/evidence` として続行する  
> - **パス入力**: そのパスを `XLSX_FOLDER`・`EVIDENCE_DIR = {パス}/evidence` として設定してから続行する

**ユーザー確認プロトコル**（実行前に必ず提示する）:

```
=== /test 実行前確認 ===
課題ID    : {issueID}
Sandbox   : {alias}
証跡保存先: {evidence_dir}
Excel出力 : {xlsx_folder}/{issueID}_エビデンス.xlsx

実行内容:
  Phase A: 前提検証・接続確認（Sandbox 判定）
  Phase B: テスト仕様の展開（test-spec.md 生成・網羅性チェック）
  Phase C: SOQL / 匿名 Apex / Playwright UI の自動実行（分岐網羅・before/after）
  Phase D: OK/NG 判定・対応記録.xlsx 更新
  Phase E: エビデンス.xlsx 生成（スクショ・DOM・SOQL 証跡を自動貼付）
  Phase F: test-report.md 生成・一時ファイル後始末（テストデータは削除せず Sandbox に保持）

続行しますか？（テスト実行・データ操作が発生します）
```

> **[ハーネス直接実行（A-2: 環境準備）]**

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

# 9. Pillow の存在確認・自動インストール（PNG 自動貼付に必要）
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
- `project_dir`: `{project_dir}`
- `log_dir`: `{log_dir}`
- `impl_plan_path`: `{log_dir}/implementation-plan.md`
- `investigation_path`: `{log_dir}/investigation.md`
- `spec_path`: `{spec_path}`（出力先）
- `pattern_map_path`: `.claude/templates/backlog/test-pattern-map.md`
- `force`: `${FORCE_SPEC:-false}`（`--force` 指定時は true）
- `validation_report_path`: `{log_dir}/validation-report.md`（Phase 3.5 regression-guard の逆参照結果。軸3消費者リスト source・省略可）

`test-spec-builder` が `test-spec.md` を生成し、網羅性セルフチェックを完了させる。

> **仕様スキーマ（参考）**: 9 列 — No / 観点 / 種別 / 前提・データ準備 / 実行アクション / 期待結果 / 判定方法 / 証跡取得 / 自動化可否。  
> 詳細な展開ルール・種別選択肢・自動化可否判断基準・網羅性チェック手順は `test-spec-builder.md` に定義されている。  
> **「観点」列はエビデンス Excel・判定ログ・対応記録に verbatim 転記される**: 自然文1文・ラベル（日本語表示名）優先・接頭ラベル（要求充足=①②…、回帰=`回帰`、共有コンポーネント consumer fan-out=`横展開`）必須。詳細と良い例・悪い例は `test-spec-builder.md` §「観点」列の記述ルールを参照。  
> **網羅性は三軸**（軸1 要求充足／軸2 変更点回帰／軸3 共有コンポーネント consumer fan-out）。軸3は共有データ取得メソッド／共通ユーティリティを変更した場合、その全呼び出し元（入口／画面／フロー）で報告症状が再発しないかを各入口 1 TC で検証する。起動ゲートは `test-spec-builder.md` §軸3 を参照。

既に `test-spec.md` が存在する場合はスキップ（`--force` 指定時は再生成）。

---

### Phase C: 自動テスト実行＋証跡採取

> **[auto-evidence-runner（オーケストレータ）へ委譲]**

`auto-evidence-runner` への委譲パラメータ:
- `issueID`: `{issueID}`
- `alias`: `{alias}`
- `instance_url`: `{INSTANCE_URL}`（Phase A で取得済み。目視ハンドオフのレコードURL組み立て用）
- `project_dir`: `{project_dir}`
- `log_dir`: `{log_dir}`
- `evidence_dir`: `{evidence_dir}`
- `xlsx_folder`: `{xlsx_folder}`
- `spec_path`: `{spec_path}`
- `target_tc_list`: `{target_tc_list}`（空=全件）
- `max_workers_soql`: 4（低速組織や API 制限が疑われる場合は 1 で逐次 / `--serial` を渡す）
- `max_workers_anon`: 3（同上）
- `max_workers_ui`: 3（UI 並列コンテキスト数。`--serial` 指定時は 1 で逐次フォールバック）
- `serial`: false（`--serial` 指定時は true で全逐次フォールバック）
- ※ `judgment_path` は **渡さない**（= 証跡採取モードで起動。後始末・test-report.md 生成は Phase F が担当）

**実行の流れ**（`auto-evidence-runner` 内部・証跡採取モード）:
1. 種別仕分け＋差分対象 TC の絞り込み
2. SOQL → `soql_evidence.py --queries-file --max-workers 4`（内部並列）
3. AnonApex → コード生成（LLM）→ `anon_apex_runner.py run-batch --max-workers 3`（内部並列）
4. UI → `ui-evidence-runner` に委譲（種別=UI が 0 件なら起動しない）。読み取り専用ケースは複数コンテキスト並列（max_workers_ui=3）、データ更新/Login As ケースは逐次
5. 証跡存在確認（後始末・test-report.md 生成は Phase F が担当）

実行後に証跡ファイルの存在確認:
```bash
echo "=== 証跡ファイル一覧 ==="
ls -lhR "{evidence_dir}/after/" 2>/dev/null | grep -E "\.(txt|png)$"
```

---

### Phase D: OK/NG 判定・結果記入

> **[ハーネス直接実行]**

```bash
# 差分再実行時は前回判定を --prev で渡して前回 OK をマージする（.prev は毎回最新 judgment へ更新）
PREV_ARG=""
if [ -f "{judgment_path}" ]; then
  cp "{judgment_path}" "{judgment_path}.prev"
fi
if [ -f "{judgment_path}.prev" ]; then
  PREV_ARG="--prev {judgment_path}.prev"
fi

python "$(pwd)/scripts/python/backlog-xlsx/judge_results.py" \
  --folder "{xlsx_folder}" \
  --issue-id "{issueID}" \
  --spec "{spec_path}" \
  --evidence-dir "{evidence_dir}/after" \
  --out "{judgment_path}" \
  $PREV_ARG

# judge_results.py は exit 1 で NG を報告する。同一ブロック内で終了コードを確認（別ブロックだと Bash の新シェル起動により $? が無効化される）
RC=$?
echo "判定結果 exit code: $RC"
cat "{judgment_path}" | python -c "import sys,json; d=json.load(sys.stdin); print(f'OK={d[\"ok\"]} NG={d[\"ng\"]} 要手動={d[\"skip\"]}')"
```

---

### Phase E: エビデンス Excel 生成・証跡自動貼付

> **[ハーネス直接実行]**

```bash
python "$(pwd)/scripts/python/backlog-xlsx/generate_evidence_xlsx.py" \
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

### Phase F: test-report.md 生成・後始末

> **[auto-evidence-runner（レポート・後始末モード）へ委譲]**

`auto-evidence-runner` への委譲パラメータ:
- `issueID`: `{issueID}`
- `alias`: `{alias}`
- `instance_url`: `{INSTANCE_URL}`（Phase A で取得済み。test-report.md の目視ハンドオフブロック生成に使う）
- `project_dir`: `{project_dir}`
- `log_dir`: `{log_dir}`
- `evidence_dir`: `{evidence_dir}`
- `xlsx_folder`: `{xlsx_folder}`
- `spec_path`: `{spec_path}`
- `judgment_path`: `{judgment_path}`（**必須**・Phase D の `judge_results.py` が生成した JSON）
- ※ `target_tc_list` / `max_workers_*` / `serial` は不要（証跡採取を再実行しないため）

`{judgment_path}` が指定されているため auto-evidence-runner は**レポート・後始末モード**で起動する:
1. `{judgment_path}` JSON を読み、test-report.md を `{log_dir}` に生成する（Step 6）
2. 一時ファイル（`{log_dir}/tmp/`）を削除する（Step 5）

匿名 Apex で作成したテストデータ（`AUTOTEST_{issueID}_` プレフィックス）は削除しない。Sandbox に蓄積させ、目視確認にも使う方針。

---

### Phase F-2: NG 自動修正ループ（実装バグ限定）

> **[ハーネス直接実行]**

`judgment-result.json` の `ng_list` から、`ng_type` が空（実装バグ）の TC とそれ以外（要確認・未実行）の TC を分類する:

```bash
# 実装バグ TC（ng_type が空文字 = 証跡あり・実装が期待値と不一致）
AUTO_FIX_TCS=$(python -c "
import json
d=json.load(open(r'{judgment_path}', encoding='utf-8'))
print(','.join(r['no'] for r in d.get('ng_list',[]) if (r.get('ng_type','') or '')==''))
" 2>/dev/null || echo "")

# その他のNG（要確認/未実行）— 後続の手動案内で対応
OTHER_NG=$(python -c "
import json
d=json.load(open(r'{judgment_path}', encoding='utf-8'))
print(','.join(r['no'] for r in d.get('ng_list',[]) if (r.get('ng_type','') or '') in ('要確認','未実行')))
" 2>/dev/null || echo "")

echo "実装バグ（自動修正候補）: ${AUTO_FIX_TCS:-なし}"
echo "その他のNG（要確認/未実行）: ${OTHER_NG:-なし}"
```

**`AUTO_FIX_TCS` が空の場合**: このフェーズをスキップし、後続「NG があった場合の差し戻し」セクションで手動案内を実施する。

**`AUTO_FIX_TCS` が非空の場合**: 以下のガードを確認する。

```bash
# ループ上限チェック（退避済み R{N}.json 本数で通算カウント。退避自体は次回 /test Phase A が実施・ここでは読むだけ）
PREV_ROUND_F2=$(python -c "
import glob, re
base = r'{judgment_path}'.replace('.json','')
files = glob.glob(base + '.R*.json')
nums = [int(m.group(1)) for f in files for m in [re.search(r'\.R(\d+)\.json$', f)] if m]
print(max(nums) if nums else 0)
" 2>/dev/null || echo "0")
echo "これまでの NG 修正回数（退避済み R{N} 本数）: ${PREV_ROUND_F2} 回"

# 前提ファイルの存在確認（backlog-implementer が必須とするファイル）
PLAN_EXISTS=$([ -f "{log_dir}/implementation-plan.md" ] && echo "true" || echo "false")
INVEST_EXISTS=$([ -f "{log_dir}/investigation.md" ] && echo "true" || echo "false")
echo "implementation-plan.md: ${PLAN_EXISTS} / investigation.md: ${INVEST_EXISTS}"
```

**ガード①: ループ上限到達（`PREV_ROUND_F2 >= 3`）**:
→ 自動修正をスキップ。後続「NG があった場合の差し戻し」セクションで「繰り返し NG が続いています。業務担当者との打合せを推奨します。」を提示して停止する。

**ガード②: 前提ファイル欠落**（`PLAN_EXISTS` または `INVEST_EXISTS` が false）:
→ 自動修正不可。「`implementation-plan.md` / `investigation.md` が見つかりません。`/backlog` Phase 1〜3 を先に完了させてください。」を提示し、後続の手動案内に移行する。

**ガードを全て通過した場合**: 以下の順で agent を直列 Task 起動して自動修正・再デプロイを実施する。

#### F-2 Step 1: backlog-implementer（実装修正）

Task tool で `backlog-implementer` を起動する:

```
task_description: 「/test 自動修正起動: {issueID} の実装バグ NG（{auto_fix_tcs}）を修正する。
  NG の詳細は {judgment_path} の ng_list と {log_dir}/test-report.md を参照。
  実装方針（implementation-plan.md）の変更は禁止。investigation.md は不変。
  期待値ドリフト禁止（test.md「NG があった場合の差し戻し」節の原則）。」
パラメータ:
  issueID: {issueID}
  project_dir: {project_dir}
  log_dir: {log_dir}
  xlsx_folder: {xlsx_folder}
  auto_fix_mode: true
  auto_fix_tcs: {auto_fix_tcs}
  ng_source: {judgment_path}
```

**backlog-implementer が経路2/3（実装方針の問題・検証漏れ）を報告した場合**: 自動修正ループを中断し、後続「NG があった場合の差し戻し」セクションで手動案内に移行する（実装バグのつもりが方針問題 → 人間判断に委ねる）。

#### F-2 Step 2: backlog-tester（dry-run 検証）

Task tool で `backlog-tester` を起動する:

```
task_description: 「/test 自動修正起動: {issueID} の修正後 dry-run 検証（PASS/FAIL を返す）」
パラメータ:
  issueID: {issueID}
  project_dir: {project_dir}
  log_dir: {log_dir}
  xlsx_folder: {xlsx_folder}
  auto_fix_mode: true
```

- **PASS** → F-2 Step 3 へ進む。
- **条件付きPASS（NoTestRun フォールバック発生）** → 自動再デプロイしない（FAIL と同様に扱う）。対応テストクラス未整備でカバレッジ未検証である旨を提示し、後続「NG があった場合の差し戻し」セクションで手動案内に移行する。
- **FAIL** → 自動再デプロイしない。dry-run のエラー内容を提示し、後続「NG があった場合の差し戻し」セクションで手動案内に移行する。

#### F-2 Step 3: backlog-releaser（軽量再デプロイ・確認なし）

Task tool で `backlog-releaser` を起動する:

```
task_description: 「/test 自動修正起動: {issueID} の修正後 Sandbox 軽量再デプロイ（確認なし・dry-run PASS 済み）。
  直前の F-2 Step 2（backlog-tester）で現在の force-app に対し dry-run PASS 済み・以降 force-app は無変更。
  再 dry-run は不要のため、スキップ判定（backlog-releaser.md L110-128）に従い省略して本デプロイのみ実行する。」
パラメータ:
  issueID: {issueID}
  project_dir: {project_dir}
  log_dir: {log_dir}
  xlsx_folder: {xlsx_folder}
  auto_fix_mode: true
  redeploy_no_confirm: true
```

`test-report.md` は Phase F で生成済みのため、releaser のモード判定（test-report.md 存在 → 軽量再デプロイ）が自動適用される（お客様確認・知見還流をスキップ）。

#### F-2 完了報告

```
=== 自動修正・再デプロイ完了 ===
修正した NG : {auto_fix_tcs}
再デプロイ  : Sandbox ({alias}) に再デプロイ完了

次のステップ（別セッションで実施）:
  /test {issueID} を再実行してください（差分モード）。
  次回 /test 起動時に今回の judgment-result.json と証跡が自動的に R{N+1} として退避されます。
```

`OTHER_NG` が空でない場合は、続けて後続「NG があった場合の差し戻し」セクションで `OTHER_NG` の手動案内も実施する。

---

#### NG があった場合の差し戻し（期待値ドリフト防止）

> **設計原則**: `investigation.md`（課題原文・真因）は不変。修正は「実装方針の変更」であり「課題認識の変更」ではない。`test-spec.md` の期待結果は NG 理由なく書き換えない。

1. `judgment-result.json` の `ng_type` で NG の種類を区別し、戻り先を確定する:

   | `ng_type` | NG の意味 | 次のアクション |
   |---|---|---|
   | `"未実行"` | 証跡が採取されていない（環境起因・実行漏れ・デプロイ後キャッシュ遅延） | **再テスト**: 差分再実行（`/test {issueID}` のみ・実装修正不要） |
   | `"要確認"` | 証跡はあるが判定パターンが機械照合できない | **test-spec.md の判定方法を修正**後に再実行 |
   | `"画面エラー"` | Salesforce の標準エラー画面が撮影された（「問題が発生しました」「Record ID is malformed」「関連リストはレイアウトにありません」等） | **要調査**: 実装/設定の不備（レイアウトへの関連リスト未追加等）か、テスト手順・前提データの誤り（不正な ID 参照・前提レコード未作成等）かを確認し、該当する方に差し戻す |
   | `""` (空) | 証跡あり・実装が期待値と一致しない（実装バグ） | **実装差し戻し**: 実装修正→ `/test {issueID}` 再実行 |

   NG 種類が混在している場合は、実装バグ（ng_type 空）を最優先で修正してから再テストする。

2. `test-report.md` の「NG 一覧」と `.claude/templates/backlog/test-fail-routing.md` で戻り先 Phase を確定する
3. **NGの原因と修正方針を `implementation-plan.md` の改版履歴に追記する**（修正に着手する前に必ず実施）:
   ```
   | {YYYY-MM-DD} | /test NG差し戻し | {NGのTC番号・観点} | {NGの原因（実際の結果）} | {修正方針（何をどう変えるか）} | investigation.md §{対応する要求} |
   ```
   これにより「何をなぜ変えたか」が記録に残り、NG 修正ループで実装の方向が課題の真因から静かにずれるのを防ぐ。
4. **対応記録.xlsx の NG対応履歴に記録する**（xlsx が存在する場合のみ）:
   ```bash
   python "$(pwd)/scripts/python/backlog-xlsx/update_records.py" \
     --folder "{xlsx_folder}" --issue-id "{issueID}" ng-history \
     --round "R{N}" --tc "{TC番号}" --reason "{NG原因}" --fix "{修正方針}"
   ```
   複数 NG TC がある場合は TC ごとに1回ずつ呼ぶ。

5. ユーザーに戻り先 Phase・NG 原因・修正方針（上記で記録した内容）を提示する

6. 修正後の手順をユーザーに案内する:
   ```
   修正手順（この順番で実施してください）:
     1. /backlog {issueID} 再開 → Phase 4 修正 → Phase 5（dry-run 確認）
     2. Phase 6 で Sandbox に再デプロイ（/backlog Phase 6 で実施。/test はデプロイしません）
     3. /test {issueID} を再実行（差分モード: 前回OK分は証跡を流用・取り直しなし）
        次回 /test 起動時に judgment-result.json と証跡が自動的に R{N} として退避されます
   ```

#### xlsx 対応記録の更新（タイムライン）

```bash
python "$(pwd)/scripts/python/backlog-xlsx/update_records.py" \
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

{実装バグ NG が Phase F-2 で自動修正・再デプロイされた場合}
自動修正: 完了（Phase F-2）
  修正 TC: {auto_fix_tcs}
  次のステップ: 別セッションで /test {issueID} を再実行してください（差分モード）。
               次回 /test 起動時に今回の証跡が自動的に R{N} として退避されます。

{手動対応が必要な NG がある場合（要確認/未実行 / 自動修正のガードで止まった場合 / dry-run FAIL の場合）}
NG 一覧:
  - TC-00X: {観点} — {理由}（ng_type: {値}）

修正手順（この順番で実施してください）:
  1. implementation-plan.md の改版履歴にNG原因と修正方針を追記
     （何をなぜ変えるかを記録してから手を動かす。investigation.md は変更しない）
  2. 対応記録.xlsx の「NG対応履歴」に回次・TC・原因・修正内容を記録
  3. /backlog {issueID} 再開 → Phase 4 修正 → Phase 5（dry-run）
  4. Phase 6 で Sandbox に再デプロイ（/backlog Phase 6 で実施。/test はデプロイしません）
  5. /test {issueID} を再実行（差分モード: 前回OK分は証跡を流用・前回結果は自動退避）

{要手動がある場合}
要手動確認:
  - TC-00X: {観点} — エビデンス.xlsx「証跡」シートに手動でスクショを貼り付けてください。
    確認対象: {ラベル（日本語表示名）} / URL: {instance_url}/lightning/r/{SObject}/{Id}/view または {画面URL（クエリ除去済み）} / 操作手順: {test-spec.mdの「テスト手順」列 or 要約}
    ※ 対象レコード・URLが特定できない TC は URL 行を省略する（[visual-confirmation-handoff.md](../templates/common/visual-confirmation-handoff.md) 準拠）
```

test-report.md の「🔎 目視確認のご案内」に全対象の一覧（レコードURL・操作手順つき）がまとまっている。要手動・NG（画面エラー含む）ともにここから直接開いて確認できる。

---

## 注意事項

- **本番組織への操作は Phase A で物理ブロック**。Sandbox alias でのみ実行可。
- accessToken は一切ファイルに保存しない（`sf org open --url-only` のワンタイム URL のみ使用）。
- テストデータ（`AUTOTEST_{issueID}_` プレフィックス）は削除しない。Sandbox に蓄積させ、ユーザーが目視で確認できるようにする。
- `/backlog` Phase 6（Sandbox デプロイ）完了後の後続工程。デプロイ済み Sandbox を前提として網羅的テストを実施する（本コマンドはデプロイしない）。
- **`/test` は共有コンポーネント修正漏れの二次防御（バックストップ）**: 同一根本原因が複数入口に fan-out するケースは、修正が共有メソッド自体に入った場合のみ軸3（consumer fan-out）で検出できる。修正が呼び出し元側だけに入った場合は /test では検出できない。一次防御は `/backlog` 調査段階（backlog-investigator の根本原因特定＋ option-reverse-grep / regression-guard の逆参照で全消費者を修正スコープに含める判断。Step C-2 参照）である。
