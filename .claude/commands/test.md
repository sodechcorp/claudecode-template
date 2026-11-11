---
description: "Salesforce 保守課題の実装後テストを全自動実行し、証跡採取・OK/NG判定・エビデンスExcel出力・共有フォルダ保存まで行う。/backlog Phase 6（Sandboxデプロイ）後に /test [課題ID] で実行。"
argument-hint: "[課題ID] [--full] [--force] [--serial]"
---

# /test [課題ID]

Salesforce 保守課題の実装後テストを全自動実行し、エビデンスを証跡採取・Excel 出力する。

`/backlog` Phase 6（Sandbox デプロイ）完了後に実行する網羅的テスト工程。デプロイ済み Sandbox を前提として証跡を自動採取し Excel 出力する（通常フローではデプロイしない。例外: Phase F-2 の NG 自動修正ループが発動した場合のみ、修正後の軽量再デプロイを実施する）。

---

## 前提条件

| 前提 | 確認方法 |
|---|---|
| `/backlog` Phase 6（Sandbox デプロイ）完了後であること（デプロイ済み Sandbox 前提） | Phase A でデプロイの記録 `{log_dir}/.sandbox-deployed`（backlog-releaser がデプロイの成功時に書く）の有無と、その後に force-app が変わっていないかを確かめる（外れたら `[WARN]`。止めないが Phase F-2 の自動修正はしない） |
| Sandbox org に認証済みであること | `sf auth list` でログイン状態を確認 |
| `docs/logs/{issueID}/test-spec.md` が存在すること | Phase B で自動生成（不在は許容・`--force` で再生成）。事前の手動用意は不要 |
| Pillow インストール | Phase A で自動インストール実行。失敗時は手動貼付にフォールバック |

---

## compact 跨ぎの復元

Phase A は `/test` 起動時に一度だけ実行し、確定した変数を `{log_dir}/.test-context.json` に書き出す（Phase A 手順8・自己防衛のため書き込み失敗は無視）。長時間セッションで `/compact` が発生した後に Phase B 以降から会話を再開する場合は、このファイルが存在すれば `project_dir` / `xlsx_folder` / `evidence_dir` / `spec_path` / `judgment_path` / `alias` / `instance_url` を読み込んで復元し、Phase A を再実行しない（Sandbox 判定は re-run しても結果が変わらないため）。ファイルが存在しない場合は Phase A から実行する。どちらの場合も Step 0 の Read はやり直す。

---

## フェーズ構成

> **Phase B（test-spec-builder）・Phase C（auto-evidence-runner）が完了報告を返さず中断した場合**は、test-spec.md・証跡が途中まで保存されていても完了とみなさず、次の Phase に進まずにその報告を提示して止まる。

### Step 0: 共通 CRITICAL ルールの読込（必須・コマンド起動直後）

以下を **Read で全文読み込む**（CLAUDE.md には要旨のみ・詳細は外出し先）:

1. Read `.claude/templates/common/verify-implementation-spec.md` — 実装裏付けルール。追加ルール記入欄まで読む
2. Read `.claude/templates/common/verify-source-attribution-spec.md` — 出典確認ルール。追加ルール記入欄まで読む
3. Read `.claude/templates/common/answer-scope-spec.md` — 回答時のスコープ管理ルール（派生事項の分離・無断リファクタ禁止）
4. Read `.claude/templates/common/uncertainty-marker-spec.md` — 確証なし時のマーカー規約（[推定]/[要確認]/[出典不明]の使い分け）

**理由**: main thread が Phase D-2（AI 判定）・Phase F-1（Backlog の課題本文・コメントの解釈）・NG の差し戻し案内を行い、ユーザーの質問にも直接応答する。Phase F-2 で起動する backlog-* agent の Step 0c と同じ spec を読み、main thread と agent の知識を揃える（`backlog.md` Step 0 と同一パターン）。Phase B・C の委譲先（test-spec-builder・auto-evidence-runner）は Backlog に接続せず（課題原文は investigation.md から読む）、ユーザーの質問にも答えないため Step 0c を持たない。

### Phase A: 前提検証・接続確認

> **[ハーネス直接実行]**

```bash
# 1. 課題ID の解決
ISSUE_ID="{issueID}"
if [ -z "$ISSUE_ID" ]; then
  echo "[FATAL] 課題IDを指定してください: /test GF-350"
  exit 1
fi

# オプション（/test {issueID} [--full] [--force] [--serial]）— アシスタントが起動引数から置換
#   --force 指定時 → FORCE_SPEC=true / 未指定 → false
#   --serial 指定時 → FORCE_SERIAL=true / 未指定 → false（低速組織・API 制限時の全逐次フォールバック。Phase C の serial パラメータに渡す）
#   --full は Phase C 冒頭の差分対象の算出で使う（--force で test-spec.md を作り直した回も全量実行）
FORCE_SPEC="{force_spec}"
FORCE_SERIAL="{force_serial}"

# 2. プロジェクトルート・ログディレクトリの確定
PROJECT_DIR="$(pwd -W)"
LOG_DIR="${PROJECT_DIR}/docs/logs/${ISSUE_ID}"

# 2.5. プロジェクトルート判定（SFDX プロジェクト外での誤実行を早期検知。sf-setup.md と同一パターン）
if [ ! -f "${PROJECT_DIR}/sfdx-project.json" ]; then
  echo "[FATAL] sfdx-project.json が見つかりません（${PROJECT_DIR}）。SFDX プロジェクトのルートで実行してください。"
  exit 1
fi

# 3. 必須ファイルの存在確認
if [ ! -f "${LOG_DIR}/implementation-plan.md" ]; then
  echo "[FATAL] implementation-plan.md が見つかりません。/backlog Phase 3 を先に実行してください（管理画面操作で対応する課題〔investigation.md の deploy_route: manual-operation〕は /test の対象外）。"
  exit 1
fi
if [ ! -f "${LOG_DIR}/investigation.md" ]; then
  echo "[WARN] investigation.md が見つかりません。テスト仕様の展開精度が下がる可能性があります。"
fi

# 3.5. Sandbox へのデプロイの記録（backlog-releaser が /backlog Phase 6・F-2 の再デプロイの成功時に書く）
if [ ! -f "${LOG_DIR}/.sandbox-deployed" ]; then
  echo "[WARN] Sandbox へのデプロイの記録（.sandbox-deployed）がありません。/backlog Phase 6 を終えていなければ、今の force-app を反映していない Sandbox をテストします。"
elif [ -n "$(find force-app -type f -newer "${LOG_DIR}/.sandbox-deployed" 2>/dev/null | head -1)" ]; then
  echo "[WARN] Sandbox へのデプロイ（$(cat "${LOG_DIR}/.sandbox-deployed")）の後に force-app が変わっています。再デプロイしていなければ、今の force-app を反映していない Sandbox をテストします。"
fi

# 4. sandbox-alias-check（本番保護。共通手順 .claude/templates/common/sandbox-alias-check.md の
# 「エイリアス取得」「Sandbox 判定」を、Phase A 全体が単一 bash フェンスのハーネス直接実行で
# 変数（SF_ALIAS 等）を後続ステップと共有する制約上、意図的にインライン複製している。
# 共通テンプレート改修時は本ブロックとの整合を確認すること（test.md は同テンプレートの
# 「参照元エージェント」一覧にも記載済み）。
# 判定条件の isSandbox OR instanceUrl は test.md 固有の拡張（共通テンプレートは isSandbox のみ）。
# 2026-06-23 導入時から意図的に付与されており、削除の要否は根拠不明のため現状維持。
SF_ALIAS=$(sf config get target-org --json | python -c "import sys,json; print(json.load(sys.stdin)['result'][0]['value'])" 2>/dev/null || echo "")
SF_ORG_JSON=$(sf org display --target-org "$SF_ALIAS" --json 2>/dev/null)
IS_SANDBOX=$(echo "$SF_ORG_JSON" | python -c "import sys,json; d=json.load(sys.stdin)['result']; print(d.get('isSandbox')==True or 'sandbox.my.salesforce.com' in d.get('instanceUrl',''))" 2>/dev/null || echo "false")
if [ "$IS_SANDBOX" != "True" ]; then
  echo "[FATAL] 接続先が Sandbox ではありません ($SF_ALIAS). 本番への操作は禁止されています。"
  exit 1
fi
echo "OK: Sandbox 接続確認済み ($SF_ALIAS)"

# 4.5. instanceUrl の取得（目視ハンドオフのレコードURL組み立て用。accessToken を含まないため出力可）
INSTANCE_URL=$(echo "$SF_ORG_JSON" | python -c "import sys,json; print(json.load(sys.stdin)['result'].get('instanceUrl',''))" 2>/dev/null || echo "")

# 4.6. Sandbox判定キャッシュへの書き込み（本ステップの確認結果を後続の auto-evidence-runner Step0 /
# soql_evidence.py / anon_apex_runner.py が再利用できるようにする。実測11～20秒重複の一部を解消。
# 書き込み失敗は無視。accessTokenはキャッシュしない。詳細: auto-evidence-runner.md Step0）
mkdir -p "${PROJECT_DIR}/.sf" && python -c "import json,time; json.dump({'alias':'$SF_ALIAS','is_sandbox':True,'instance_url':'$INSTANCE_URL','checked_at':time.time()}, open(r'${PROJECT_DIR}/.sf/sandbox_check_cache.json','w',encoding='utf-8'))" 2>/dev/null || true
echo "INSTANCE_URL=$INSTANCE_URL"

# 5. xlsx_folder / evidence_dir の確定（対応記録.xlsx 廃止に伴い LOG_DIR 配下に固定。2026-09-18）
XLSX_FOLDER="${LOG_DIR}"
EVIDENCE_DIR="${LOG_DIR}/evidence"

INVEST_FILE="${LOG_DIR}/investigation.md"
SPEC_PATH="${LOG_DIR}/test-spec.md"
JUDGMENT_PATH="${LOG_DIR}/judgment-result.json"
echo "PROJECT_DIR=$PROJECT_DIR"
echo "LOG_DIR=$LOG_DIR"
echo "XLSX_FOLDER=$XLSX_FOLDER"
echo "EVIDENCE_DIR=$EVIDENCE_DIR"
echo "SPEC_PATH=$SPEC_PATH"
echo "JUDGMENT_PATH=$JUDGMENT_PATH"

# 5.5. 証跡のコピー先（共有フォルダ）の確認。表示のみで書き込まない（コピーは Phase G）
python "$(pwd -W)/scripts/python/backlog-xlsx/share_evidence.py" --project-dir "$PROJECT_DIR" --issue-id "$ISSUE_ID" resolve | grep -E "^(SHARE_STATUS|REPORT_DIR|SHARE_FILE)=" || true

# 6. test-spec.md の存在確認（なければ Phase B へ）
if [ ! -f "$SPEC_PATH" ]; then
  echo "[INFO] test-spec.md が見つかりません。Phase B でテスト仕様を展開します。"
fi

# 7. 再開確認
if [ -d "${EVIDENCE_DIR}/after" ]; then
  echo "[INFO] ${EVIDENCE_DIR}/after が既に存在します。差分再実行モードでは非対象 TC の既存証跡を維持します。"
fi

# 8. compact 跨ぎ復元用コンテキストの保存（本 Phase A 確定値のスナップショット。
# Phase B 以降で /compact が発生した場合、本ファイルがあれば Phase A を再実行せず変数を復元できる。
# 書き込み失敗は無視・後続処理をブロックしない）
python -c "import json; json.dump({'issue_id':'$ISSUE_ID','project_dir':r'$PROJECT_DIR','log_dir':r'$LOG_DIR','xlsx_folder':r'$XLSX_FOLDER','evidence_dir':r'$EVIDENCE_DIR','spec_path':r'$SPEC_PATH','judgment_path':r'$JUDGMENT_PATH','alias':'$SF_ALIAS','instance_url':'$INSTANCE_URL'}, open(r'${LOG_DIR}/.test-context.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=2)" 2>/dev/null || true
```

手順3.5 の `[WARN]` が出たら控えて、完了報告の「未確認事項」に写す。

`{log_dir}/test-report.md` に `## テスト結果:` 見出しがあれば、その見出しより後の最初の `### 総合判定` の次の行を `再テスト待ち — テストの完了で確定します` に Edit で書き換える（今回の /test が途中で止まったとき、前回の判定が完了扱いされないようにするため。test-report.md は Phase F で作り直される）。

**実行内容の提示**（提示のみ・停止しない。ユーザーは `/test {issueID}` を明示入力済みで課題ID・Sandbox は確定済みのため。実データへの書き込みを伴う操作の承認は auto-evidence-runner.md Step 1.5（メール到達安全確認・外部システム呼び出しの確認）に集約する）:

```
=== /test 実行内容 ===
課題ID    : {issueID}
Sandbox   : {alias}
証跡保存先: {evidence_dir}
Excel出力 : {xlsx_folder}/{issueID}_エビデンス.xlsx
共有フォルダ: {SHARE_STATUS=ok なら SHARE_FILE / unset なら「未設定（テスト完了後に保存先を伺います）」/ missing なら「設定済みの保存先 {REPORT_DIR} が見つかりません（テスト完了後に伺います）」}

実行内容:
  Phase A: 前提検証・接続確認（Sandbox 判定）
  Phase B: テスト仕様の展開（test-spec.md 生成・網羅性チェック）
  Phase C: SOQL / 匿名 Apex / Playwright UI の自動実行（分岐網羅・before/after）
  Phase D: OK/NG 判定（機械判定できない TC は Phase D-2 で AI が証跡を読んで判定）
  Phase E: エビデンス.xlsx 生成（スクショはエビデンスと NG の TC だけ貼付。ほかは画面の文字・SOQL の結果を載せる）
  Phase F: test-report.md 生成・一時ファイル後始末（テストデータは削除せず Sandbox に保持）
  Phase G: 証跡（エビデンス.xlsx・evidence/before/）を共有フォルダへコピー
```
上記を表示したうえで確認を待たずそのまま Phase A-2（環境準備）に進む。

> **[ハーネス直接実行（A-2: 環境準備）]**

Sandbox 判定は直前の A-1 で確認済み（本番だった場合は A-1 の時点で `[FATAL]` により停止しているため、本ステップは Pillow 確認のみ行う。再確認しない）。

```bash
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

**B-0: 組織の地図で回帰の候補を出す（main thread。地図の部品があるときだけ。`test-spec.md` が既にあり再生成しないときは省く）**: `{impl_plan_path}`（無ければ investigation.md）の変更対象のうち、項目・クラス・LWC・フローを地図の書き方（`Obj__c.Field__c`・クラス名・`LWC:名前`・フロー名）にして引き、`{log_dir}/lineage-regression.md` に保存する。test-spec-builder は Bash を持たないので、ここで引いて渡す（引き方・読み方の決まりは [option-lineage-map.md](../templates/backlog/options/option-lineage-map.md)）。
```bash
if [ -f scripts/python/sf-lineage/lineage.py ]; then
  { python scripts/python/sf-lineage/lineage.py who {変更した部品・項目…} --depth 2
    python scripts/python/sf-lineage/lineage.py save {変更したオブジェクト…} --depth 1; } > "{log_dir}/lineage-regression.md" 2>&1 \
    || echo "[WARN] 地図を引けませんでした（軸2・軸3は従来どおり）"
fi
```
引けなかった・部品が無いときは `lineage_path` を渡さない（軸2・軸3は従来どおり）。

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
- `evidence_dir`: `{evidence_dir}`（`/backlog` Phase 3.5 の Before 証跡 `before/` の有無確認に使う）
- `lineage_path`: `{log_dir}/lineage-regression.md`（B-0 で作れたときだけ。軸2の回帰 TC・軸3の消費者リストの候補。省略可）

`test-spec-builder` が `test-spec.md` を生成し、網羅性セルフチェックを完了させる。返却に `[WARN]` 行（investigation.md 不在による軸1・軸3スキップ、軸3 消費者リスト source 不在等）が含まれる場合は内容を保持し、完了報告の「未確認事項」欄に転記する。

`target=` 必須ルールのバックストップ自己チェック（test-spec-builder Step 3 軸0 の抜け漏れ検知）:
```bash
MISSING_TARGET=$(python "$(pwd -W)/scripts/python/backlog-xlsx/check_target_required.py" --spec "{spec_path}")
if [ $? -eq 2 ]; then
  echo "[FATAL] test-spec.md からテストケースを読めません（上の理由）。Phase C に進まない"
elif [ -n "$MISSING_TARGET" ]; then
  echo "[WARN] target= 未付記のエビデンスの UI TC があります: $MISSING_TARGET（test-spec-builder Step 3 軸0 で追記されているはずです。test-spec.md を確認してください）"
fi
```
`[FATAL]` が出たら Phase C に進まず、test-spec.md の表を直す（または `/test {issueID} --force` で作り直す）。`[WARN]` が出た場合は内容を保持し、完了報告の「未確認事項」欄に転記する。

> **仕様スキーマ（参考）**: 11 列 — No / 観点 / 種別 / 前提・データ準備 / 実行アクション / テスト手順 / 期待結果 / 判定方法 / 証跡取得 / 自動化可否 / 確認ポイント（着眼点）。`テスト手順` と `確認ポイント（着眼点）` は任意列（詳細は `test-spec-builder.md` §Step 2 参照）。  
> 詳細な展開ルール・種別選択肢・自動化可否判断基準・網羅性チェック手順は `test-spec-builder.md` に定義されている。  
> **「観点」列はエビデンス Excel・判定ログに verbatim 転記される**: 自然文1文・ラベル（日本語表示名）優先・接頭ラベル（要求充足=①②…、回帰=`回帰`、共有コンポーネント consumer fan-out=`横展開`）必須。詳細と良い例・悪い例は `test-spec-builder.md` §「観点」列の記述ルールを参照。  
> **網羅性は三軸**（軸1 要求充足／軸2 変更点回帰／軸3 共有コンポーネント consumer fan-out）。軸3は共有データ取得メソッド／共通ユーティリティを変更した場合、その全呼び出し元（入口／画面／フロー）で報告症状が再発しないかを各入口 1 TC で検証する。起動ゲートは `test-spec-builder.md` §軸3 を参照。

既に `test-spec.md` が存在する場合は生成をスキップする（`--force` 指定時は再生成）。スキップ時も軸0（判定方法のフォーマット検証）のみ再実施される（詳細は `test-spec-builder.md` §Step 0 参照）。

---

### Phase C: 自動テスト実行＋証跡採取

> **[ハーネス直接実行（差分対象の算出）]**

```bash
# Phase B の後で算出する（Phase B で test-spec.md を作った回は全量実行にするため）
FORCE_FULL="{force_full}"   # --full 指定時、または Phase B で test-spec.md を作った（--force・既存なしからの生成）とき → 1 / それ以外 → 空（アシスタントが置換。作り直した TC を全て撮り直す）
EVIDENCE_DIR="{evidence_dir}"
SPEC_PATH="{spec_path}"
JUDGMENT_PATH="{judgment_path}"

# 1. 証跡PNG削除マーカーの検出（cleanup_evidence.py 実行済みなら差分再実行モードを使わない）
# 前回に SKIP（要手動）がある等で差分モードに入ると、PNG 削除済みの前回 OK の TC が
# 証跡ファイル不在の偽 NG になるため、マーカーがあれば全量実行へ倒す。
# マーカーは全量採取の完了後（下の証跡ファイルの存在確認）で消す（Phase C が途中で止まっても次回も全量実行になるように）。
if [ -f "${EVIDENCE_DIR}/.png-cleaned" ]; then
  echo "[INFO] 証跡PNGが削除済み（cleanup_evidence.py 実行済み）を検出。差分再実行モードは使わず今回は全量実行します。"
  FORCE_FULL=1
fi

# 2. 差分再実行モードの判定
# 回次退避（前回データのアーカイブ）はここでは行わない。/test を最初（Phase A）から実行した
# 場合にしかここを通らないため、会話の流れで証跡採取・判定だけを直接再実行する
# ショートカットを踏むと退避が効かず履歴が失われる（2026-07-06 DFA-198 で確認された実害）。
# 退避の実体は実際にデータを上書きする箇所に移設済み:
#   - 証跡（evidence/after）: auto-evidence-runner.md Step 0.5（証跡採取モードのみ・自己防衛）
#   - 判定（judgment-result.json）: judge_results.py の _archive_previous_round（--out 書込み直前）
# どちらも「まだ退避されていなければ」実行する冪等な自己防衛のため、経路によらず必ず履歴が残る。
TARGET_TC_LIST=""
if [ -f "$JUDGMENT_PATH" ] && [ "${FORCE_FULL:-}" != "1" ]; then
  echo "[INFO] 前回の判定結果を検出。差分再実行モードを使用します（期待結果・判定方法を書き換えていない前回 OK の TC は再実行しません）。"
  echo "[INFO] 全量再実行する場合は --full オプションを指定してください。"

  # 差分対象 = 前回 NG ∪ 前回 SKIP ∪ 前回結果に存在しない TC（test-spec.md に後から追加した TC）
  #   ∪ 前回の判定後に期待結果・判定方法・種別を書き換えた TC（証跡が書き換え前の期待結果で撮られているため。匿名 Apex の自己検証は期待結果から作る。
  #     書き換えを確かめられない旧版の判定結果〔spec_sig なし〕は全 TC）。
  # 前回「AI判定」のまま残った TC（Phase D-2 が中断された等）は書き換えていなければ証跡を撮り直さず、Phase D・D-2 で判定だけやり直す
  # （撮り直す TC がほかに無ければ Phase D-2 から続ける。前回の判定の後に証跡採取を始めていた〔after_R{判定の回次} がある〕ときは証跡が消えている場合があり、
  #   force-app を変えていた〔再実装〕ときは証跡が古いので、全件で撮り直す）。
  # 書き換えていない前回 OK・AI判定・対象外のみ除外する（SKIP を除外すると--full まで解消されず残留し、新規 TC を除外すると
  # 証跡未採取のまま judge_results.py で「証跡ファイルが見つかりません」の偽 NG になるため）。
  TARGET_TC_LIST=$(python "$(pwd -W)/scripts/python/backlog-xlsx/resolve_target_tcs.py" --judgment "$JUDGMENT_PATH" --spec "$SPEC_PATH" 2>/dev/null || echo "")
  PREV_AI=$(python -c "import json; print(json.load(open(r'$JUDGMENT_PATH', encoding='utf-8')).get('ai_pending', 0))" 2>/dev/null || echo "0")
  JUDGED_ROUND=$(python -c "import glob, re; base = r'$JUDGMENT_PATH'.replace('.json',''); nums = [int(m.group(1)) for f in glob.glob(base + '.R*.json') for m in [re.search(r'\.R(\d+)\.json$', f)] if m]; print(max(nums + [0]) + 1)" 2>/dev/null || echo "1")
  FA_CHANGED=$(find force-app -type f -newer "$JUDGMENT_PATH" 2>/dev/null | head -1)
  if [ -z "$TARGET_TC_LIST" ] && [ "$PREV_AI" -gt 0 ] && [ ! -d "${EVIDENCE_DIR}/after_R${JUDGED_ROUND}" ] && [ -z "$FA_CHANGED" ]; then
    echo "[INFO] 撮り直す TC は無く、前回の判定に AI判定待ちが ${PREV_AI} 件あります。証跡採取（auto-evidence-runner）と Phase D を行わず、前回の判定・証跡のまま Phase D-2 から続けます（前回の判定の後で管理画面の設定を変えた・force-app を変えずに再デプロイした場合は --full で実行し直してください）。"
  elif [ -z "$TARGET_TC_LIST" ]; then
    echo "[INFO] 前回 NG・SKIP・新規 TC と、期待結果・判定方法を書き換えた TC なし。TARGET_TC_LIST が空のため、実装上の制約により今回は全 TC を再実行します（「空リスト＝対象なし」と「未指定＝全件」を区別する仕組みが未実装。本当にスキップしたい場合は --full を使わず本セッションを終了してください）。"
  else
    echo "[INFO] 差分対象（前回 NG・SKIP・新規 TC と、期待結果・判定方法を書き換えた TC）: $TARGET_TC_LIST"
    echo "[INFO] 影響範囲の TC は今回の実行対象には含まれません（Phase F で NG があった場合のみ、次回再テストの判断材料として提示されます）。"
  fi
else
  echo "[INFO] 全量実行モード（初回・--full 指定・test-spec.md を作った回のいずれか）"
fi
echo "TARGET_TC_LIST=$TARGET_TC_LIST"
```

`Phase D-2 から続けます` が出たら、auto-evidence-runner を起動せず（下の証跡ファイルの確認も行わない）、Phase D も行わずに Phase D-2 へ進む。

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
- `serial`: `${FORCE_SERIAL:-false}`（`--serial` 指定時は true で全逐次フォールバック）
- ※ `judgment_path` は **渡さない**（= 証跡採取モードで起動。後始末・test-report.md 生成は Phase F が担当）

**実行の流れ**（`auto-evidence-runner` 内部・証跡採取モード）:
1. 種別仕分け＋差分対象 TC の絞り込み
2. AnonApex（UI・SOQL の TC の前提の匿名 Apex を含む）→ コード生成（LLM）→ `anon_apex_runner.py run-batch --max-workers 3`（内部並列。2回に分ける TC・前提の匿名 Apex の後を確かめる SOQL の TC を含む逐次の TC は1件ずつ2回目・SOQL まで済ませて次へ。UI の操作の後を確かめる・使う TC は 3 の後）
3. UI → `ui-evidence-runner` に委譲（種別=UI が 0 件なら起動しない）。読み取り専用ケースは複数コンテキスト並列（max_workers_ui=3）、データ更新/Login As ケースは逐次
4. SOQL → `soql_evidence.py --queries-file --max-workers 4`（内部並列。匿名 Apex・UI の操作の後に取る。保存で動く非同期処理の結果は完了を待って取る。後の TC がデータを変える前に取るものは 2・3 の前か途中で取る）
5. 証跡存在確認（後始末・test-report.md 生成は Phase F が担当）

auto-evidence-runner の完了報告に「戻し・後片付けに失敗:」の行があれば控えて、/test の完了報告の「要対応」に写す。完了報告を返したら、証跡ファイルの存在を確認する（0件ゲート・早期検知）:
```bash
echo "=== 証跡ファイル一覧 ==="
ls -lhR "{evidence_dir}/after/" 2>/dev/null | grep -E "\.(txt|png)$"
EVIDENCE_COUNT=$(find "{evidence_dir}/after" -type f \( -name "*.txt" -o -name "*.png" \) 2>/dev/null | wc -l)
if [ "$EVIDENCE_COUNT" -eq 0 ]; then
  echo "[WARN] 証跡ファイルが1件も見つかりません。auto-evidence-runner が正常に完了したか確認してください（このまま Phase D に進むと全 TC が「証跡ファイルが見つかりません」で NG になります）。"
fi
# 全量で採取し終えた回（差分対象なし）だけ、証跡PNG削除マーカーを消す（Phase C 冒頭参照）
if [ -z "{target_tc_list}" ] && [ "$EVIDENCE_COUNT" -gt 0 ]; then rm -f "{evidence_dir}/.png-cleaned"; fi
```

---

### Phase D: OK/NG 判定・結果記入

> **[ハーネス直接実行]**

```bash
# 差分再実行時は前回判定を --prev で渡して前回 OK をマージする（--prev は --out の書き込み前に読まれるため同じパスでよい。無ければ無視される）
python "$(pwd -W)/scripts/python/backlog-xlsx/judge_results.py" \
  --issue-id "{issueID}" \
  --spec "{spec_path}" \
  --evidence-dir "{evidence_dir}/after" \
  --out "{judgment_path}" \
  --prev "{judgment_path}"

# judge_results.py は exit 1 で NG を報告する。同一ブロック内で終了コードを確認（別ブロックだと Bash の新シェル起動により $? が無効化される）
RC=$?
echo "判定結果 exit code: $RC"
if [ "$RC" -le 1 ]; then
  cat "{judgment_path}" | python -c "import sys,json; d=json.load(sys.stdin); print(f'OK={d[\"ok\"]} NG={d[\"ng\"]} AI判定待ち={d.get(\"ai_pending\",0)} 要手動={d[\"skip\"]}')"
fi
```

exit 2 は判定していない（test-spec.md からテストケースを読めない等。`{judgment_path}` は書き換えていない）。Phase D-2 以降に進まず、`[FATAL]` の理由を見て test-spec.md の表を直して（または `--force` で作り直して）から `/test {issueID}` をやり直す。

---

### Phase D-2: AI 判定（`ai_pending` が 1 件以上の場合のみ）

> **[メインスレッドが実施]** 機械判定できなかった TC（期待件数の無い件数一致・検証出力の無い匿名 Apex・DOM の無いスクショ・空白に近い証跡・判定パターン未一致など）を、**人間の目視に回さず** AI が判定する。`ai_pending` が 0 なら本 Phase はスキップする。

1. `{judgment_path}` の `ai_list` を読む（各要素に `no`・`label`・`expected`・`judge_method`・`shubetsu`・`evidence_files`・`reason` がある）
2. TC ごとに、`{spec_path}` の該当行（観点・前提・実行アクション・期待結果・判定方法）と、`evidence_files` の全ファイルを **Read する**（`.txt` は本文、`.png` は画像として中身を見る）
3. 次の基準で **OK / NG を必ず決める**（保留・要目視にしない）:
   - **OK**: 観点と期待結果が求めていることが、証跡上で**具体的に確認できる**（どの値・どの表示を見て判断したかを書ける）
   - **NG（ng_type 空＝実装が期待と不一致）**: 処理は実行され結果も採れているが、期待と違う
   - **NG（ng_type `未実行`＝証跡が不十分で再採取が必要）**: 画面が空白・ログイン画面・前提データ未作成・処理が起動していない等で、期待の成否を証跡から判断できない
   - **NG（ng_type `画面エラー`）**: Salesforce のエラー画面が写っている。または匿名 Apex の debug 出力に期待しないエラー文言があり、原因が実装かテスト側（前提データ・テストコード・実行ユーザー）かを証跡から決められない
   - 証跡から確認できないことを推測で OK にしない（「たぶん表示されている」は NG `未実行`）
4. 判定結果を `{log_dir}/tmp/ai-decisions.json` に JSON 配列で Write する。`basis` には**証跡のどこを見て判断したか**を具体的に書く（例: 「SOQL 結果の Status__c 列が全2行とも『完了』」「スクショ右上のトーストに『保存しました』」）:
   ```json
   [{"no": "TC-004", "status": "OK", "basis": "..."}, {"no": "TC-007", "status": "NG", "basis": "...", "ng_type": ""}]
   ```
5. 反映する:
   ```bash
   python "$(pwd -W)/scripts/python/backlog-xlsx/apply_ai_judgment.py" \
     --judgment "{judgment_path}" \
     --decisions "{log_dir}/tmp/ai-decisions.json"
   echo "反映 exit code: $?"
   ```
   exit 2（反映エラー）の場合は stderr の理由を直して再実行する（`{judgment_path}` が読めないときは手で直さず、`mv "{judgment_path}" "{judgment_path}.broken"` で退けてから Phase D からやり直す）。判定サマリーの `AI判定待ち=` が 0 でなければ、残りの TC を判定して反映し直してから Phase E に進む（AI判定待ちを残したまま Phase E に進まない。前に反映した TC を decisions に残したまま再実行してよい）
6. **期待結果・判定方法の書き方が原因で AI 判定に回った TC**（期待件数なし・`項目=値` なし・判定方法の書き漏れ等）は、次回の機械判定のために `{spec_path}` の該当行を機械判定できる形（`test-pattern-map.md`「判定方法の選択肢」参照）に Edit しておく。期待値の意味は変えない（期待値ドリフト禁止）

---

### Phase E: エビデンス Excel 生成・証跡自動貼付

> **[ハーネス直接実行]**

```bash
python "$(pwd -W)/scripts/python/backlog-xlsx/generate_evidence_xlsx.py" \
  --folder "{xlsx_folder}" \
  --issue-id "{issueID}" \
  --spec "{spec_path}" \
  --evidence-dir "{evidence_dir}/after" \
  --judgment "{judgment_path}"
```

スクリプトの stdout（`生成完了: {出力パス}` / `テストケース: {N}件 (OK=.. / NG=.. / 要手動=.. / 対象外=..)` / `回次: {N}回`）をそのまま完了根拠とする。シート生成に失敗した場合（`PermissionError` 等）はスクリプトが exit 1 で終了するため、正常終了＝シート存在が保証される（目視確認は不要）。

証跡シートにスクショを貼るのは、エビデンスの TC（観点の末尾が「（エビデンス）」。test-spec-builder 軸4 の1〜2件）と NG の TC だけ。ほかの画面テストは画面の文字の一致行（機械照合の結果）だけを載せ、画像は `{evidence_dir}/after/` に残す（テストは全件行い、人が見る証跡は最小にする。完了報告で案内する証跡クリーンアップを実行すると消える）。AI がスクショを読んで判定した TC と、画面の文字が無い・空のスクショがある TC は、スクショが判定の根拠なので貼る。エビデンスの印が1件も無い test-spec.md は従来どおり全部貼る。

---

### Phase F: test-report.md 生成・後始末

> **[ハーネス直接実行（レポート生成）＋ auto-evidence-runner（知見還流モード）へ委譲]**

**手順1（レポート生成）**: test-report.md 生成・tmp/ 削除（決定論的変換のためスクリプト直接実行、サブエージェント不要）:

```bash
python "$(pwd -W)/scripts/python/backlog-xlsx/generate_test_report.py" \
  --issue-id "{issueID}" \
  --judgment "{judgment_path}" \
  --spec "{spec_path}" \
  --log-dir "{log_dir}" \
  --alias "{alias}" \
  --instance-url "{INSTANCE_URL}"
```

スクリプトの stdout（`生成完了: {出力パス}` / `テストケース: {N}件 (OK=.. / NG=.. / 要手動=.. / 対象外=..)` / `回次: {N}回`）をそのまま完了根拠とする。`judgment-result.json` が見つからない等の異常時はスクリプトが exit 1 で終了するため、正常終了＝test-report.md 生成済みが保証される。

**手順2（知見還流）**: write-after、判断を要するため auto-evidence-runner へ委譲する（※ 直後の「Phase F-1」は本コマンドの独立した次フェーズであり、この手順2とは無関係）:

`auto-evidence-runner` への委譲パラメータ:
- `issueID`: `{issueID}`
- `project_dir`: `{project_dir}`
- `log_dir`: `{log_dir}`
- `evidence_dir`: `{evidence_dir}`
- `spec_path`: `{spec_path}`
- `judgment_path`: `{judgment_path}`（**必須**・Phase D の `judge_results.py` が生成した JSON。§ 2 レシピ還流の実行条件判定に使う）
- ※ `alias` / `instance_url` / `xlsx_folder` / `target_tc_list` / `max_workers_*` / `serial` は不要（test-report.md 本体は本 Phase の手順1で生成済み・証跡採取も再実行しないため）

`{judgment_path}` が指定されているため auto-evidence-runner は**知見還流モード**（Step 7 のみ）で起動する。手順1が生成した `{log_dir}/test-report.md` の「### テストデータ」セクションに、還流結果（または還流スキップの理由）を追記する。

匿名 Apex で作成したテストデータ（`AUTOTEST_{issueID}_` プレフィックス）は削除しない。Sandbox に蓄積させ、目視確認にも使う方針。

---

### Phase F-1: 受入基準再確認

> **[ハーネス直接実行]**

After エビデンスが確定した時点での完了確認。`.claude/templates/backlog/options/option-acceptance-criteria-recheck.md` の実行手順に従う:

1. **軽量フェッチ（キャッシュ判定用）**: `mcp__backlog__get_issue`（課題本文。`updated` フィールドを含む）・`mcp__backlog__get_issue_comments`（`order: desc`, `count: 1` で最新コメント1件のみ）で `{issueID}` の `updated` タイムスタンプと最終コメントIDを取得する（この時点では全コメント本文は取得しない）
2. **キャッシュ判定**: 取得した `issue_updated` と `last_comment_id` を、`{log_dir}/.acceptance-recheck.json` の前回値と比較する:
   - キャッシュが存在し、`issue_updated` と `last_comment_id` が両方とも前回値と完全一致し、かつ前回 `verdict` が「リリース可」で `section` がある場合: 全コメント取得・後付け要件確認（手順3〜4）を実行せず、キャッシュの `section`（前回追記したセクション本文）を `{log_dir}/test-report.md` に追記する（末尾に「（コメント・課題本文に増分なしのため前回結果を再掲）」を付記）
   - キャッシュ不在、値が不一致、前回 `verdict` が「追加実装要」、または `section` が無い場合: `mcp__backlog__get_issue_comments`（引数なし＝全コメント）で全件を改めて取得し、手順3〜4を実行する
3. 後付け要件・受入基準充足・スコープ縮小を確認する（`{log_dir}/approach-plan.md`「### 今回対象外とする要求・入口」に書かれたものは漏れにしない。詳細は option の「スコープの確認」）
4. `{log_dir}/test-report.md` に「## 受入基準再確認」セクションを option-acceptance-criteria-recheck.md の出力フォーマットに従って追記する。完了後、`{log_dir}/.acceptance-recheck.json` に `{"issue_updated": "{updated値}", "last_comment_id": "{最終コメントID}", "verdict": "{最終判定}", "section": "{追記したセクション本文（「## 受入基準再確認」と、書いた場合は「## 派生事項（質問外）」）}"}` を Write する

未対応の後付け要件を発見した場合: 対応内容を `implementation-plan.md` に追記し、業務判断を伴うため自動実装はせず「最終判定: 追加実装要」としてユーザーに提示する。

#### 総合判定への反映

```bash
NG_COUNT=$(python -c "import json; print(json.load(open(r'{judgment_path}', encoding='utf-8')).get('ng', 0))" 2>/dev/null || echo "1")
AI_PENDING=$(python -c "import json; print(json.load(open(r'{judgment_path}', encoding='utf-8')).get('ai_pending', 0))" 2>/dev/null || echo "1")
echo "NG件数: ${NG_COUNT} / AI判定待ち: ${AI_PENDING}"
```

`{log_dir}/test-report.md` の「### 総合判定」欄を以下で判定する:

| `NG_COUNT` | 受入基準再確認の最終判定 | 総合判定欄 |
|---|---|---|
| ≠ 0 | （不問） | 変更しない（Phase F が書き込んだ「FAIL」を維持） |
| = 0 で `AI_PENDING` ≠ 0 | （不問） | 変更しない（Phase F が書き込んだ「AI判定待ちあり」を維持。PASS にしない） |
| = 0 で `AI_PENDING` = 0 | 追加実装要 | 「条件付きPASS」に書き換え |
| = 0 で `AI_PENDING` = 0 | リリース可 | `PASS` に書き換え |

「条件付きPASS」への書き換え内容:
```
条件付きPASS（要確認: 受入基準再確認で指摘あり。詳細は「## 受入基準再確認」を参照）
```
「変更しない」の場合も、「追加実装要」の判定自体は「## 受入基準再確認」セクションへの記録として残る（総合判定欄には反映しないだけ）。

---

### Phase F-2: NG 自動修正ループ（実装バグ限定）

> **[ハーネス直接実行]**

`judgment-result.json` の `ng_list` から、`ng_type` が空（実装バグ）の TC とそれ以外（未実行・画面エラー等）の TC を分類する:

```bash
# 実装バグ TC（ng_type が空文字 = 証跡あり・実装が期待値と不一致）
AUTO_FIX_TCS=$(python -c "import json; d=json.load(open(r'{judgment_path}', encoding='utf-8')); print(','.join(r['no'] for r in d.get('ng_list',[]) if (r.get('ng_type','') or '')==''))" 2>/dev/null || echo "")

# その他のNG（ng_type あり: 未実行・画面エラー等）— 後続の手動案内で対応
OTHER_NG=$(python -c "import json; d=json.load(open(r'{judgment_path}', encoding='utf-8')); print(','.join(r['no'] for r in d.get('ng_list',[]) if (r.get('ng_type','') or '')!=''))" 2>/dev/null || echo "")

echo "実装バグ（自動修正候補）: ${AUTO_FIX_TCS:-なし}"
echo "その他のNG（未実行・画面エラー等）: ${OTHER_NG:-なし}"
```

**`AUTO_FIX_TCS` が空の場合**: このフェーズをスキップし、後続「NG があった場合の差し戻し」セクションで手動案内を実施する。

**`AUTO_FIX_TCS` が非空の場合**: 以下のガードを確認する。

```bash
# ループ上限チェック（退避済み R{N}.json の最大回次番号 N で通算カウント。欠番があっても
# 本数（ファイル数）ではなく最大値を基準にする＝過少カウントで上限判定が緩まないようにする。
# 退避自体は次回 /test 実行時に judge_results.py の _archive_previous_round（判定）/
# auto-evidence-runner Step 0.5（証跡）が実施する。Phase A では行わない・ここでは読むだけ）
PREV_ROUND_F2=$(python -c "import glob, re; base = r'{judgment_path}'.replace('.json',''); files = glob.glob(base + '.R*.json'); nums = [int(m.group(1)) for f in files for m in [re.search(r'\.R(\d+)\.json$', f)] if m]; print(max(nums) if nums else 0)" 2>/dev/null || echo "0")
echo "これまでの NG 修正回数（退避済み R{N}.json の最大回次番号）: ${PREV_ROUND_F2} 回"

# 前提ファイルの存在確認（backlog-implementer が必須とするファイル）
PLAN_EXISTS=$([ -f "{log_dir}/implementation-plan.md" ] && echo "true" || echo "false")
INVEST_EXISTS=$([ -f "{log_dir}/investigation.md" ] && echo "true" || echo "false")
echo "implementation-plan.md: ${PLAN_EXISTS} / investigation.md: ${INVEST_EXISTS}"

# Sandbox が今の force-app を反映しているか（Phase A 手順3.5 と同じ確かめ方）
DEPLOYED=$([ -f "{log_dir}/.sandbox-deployed" ] && [ -z "$(find force-app -type f -newer "{log_dir}/.sandbox-deployed" 2>/dev/null | head -1)" ] && echo "true" || echo "false")
echo "Sandbox へのデプロイの記録（その後 force-app の変更なし）: ${DEPLOYED}"
```

**ガード①: ループ上限到達（`PREV_ROUND_F2 >= 3`）**:
→ 自動修正をスキップ。後続「NG があった場合の差し戻し」セクションで「繰り返し NG が続いています。業務担当者との打合せを推奨します。」を提示し、ユーザーに継続・中止の判断を求める（`test-fail-routing.md` §「ループ上限」と同一の扱い）。

**ガード②: 前提ファイル欠落**（`PLAN_EXISTS` または `INVEST_EXISTS` が false）:
→ 自動修正不可。「`implementation-plan.md` / `investigation.md` が見つかりません。`/backlog` Phase 1〜3 を先に完了させてください。」を提示し、後続の手動案内に移行する（implementation-plan.md は Phase A で確かめ済みなので、欠けているのは investigation.md。差し戻しの戻り先は Phase 1）。

**ガード③: デプロイの記録が無い・その後に force-app が変わった（`DEPLOYED` が false）**:
→ 自動修正しない（NG が Sandbox に反映されていない変更のせいかもしれないため）。後続「NG があった場合の差し戻し」に移るが、`AUTO_FIX_TCS` は手順1・3・5・7の対象にせず（戻り先を決めない・validation-report.md・discussion-log.md・implementation-plan.md を書き換えない）、手順6・7で `OTHER_NG` の案内に添えて「{AUTO_FIX_TCS} は Sandbox が今の force-app を反映していない可能性があります（デプロイの記録なし／その後に force-app を変更）。デプロイしていなければ /backlog {issueID} 再開 → Phase 6（再デプロイだけ）から → /test {issueID} を再実行してください（再デプロイ後も NG なら、その /test が自動修正します。implementation-plan.md の改版履歴の最新の「/test NG差し戻し」の行に自動修正の途中の変更が残っていると書かれていれば、Phase 6 ではなく validation-report.md の総合判定が示す戻り先〔無ければ Phase 4〕から）」と案内する（デプロイ済みだと担当者が答えたら、手順1からの通常の扱いに戻す）。

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
  auto_fix_mode: true
  auto_fix_tcs: {auto_fix_tcs}
  ng_source: {judgment_path}
```

**backlog-implementer が中断を報告した場合（経路2/3〈実装方針の問題・検証漏れ〉、非対話停止点〈API名不一致・describe・FieldDefinition の失敗〉、テスト仕様の誤りの疑い〈期待結果が実装計画と食い違う〉、または承認ガード例外の条件不成立のいずれか）**: 自動修正ループを中断し、後続「NG があった場合の差し戻し」セクションで手動案内に移行する（実装バグのつもりが方針・テスト仕様の問題や前提未確認 → 人間判断に委ねる）。

**backlog-implementer 完了後（上記いずれの中断も発生していない場合）**: F-2 Step 2 へ進む。完了の返却（変更ファイル数・主な変更点）を返さずに終わった場合は中断と同じに扱う（変えたファイルは「不明」として差し戻しに書く）。

#### F-2 Step 2: backlog-tester（dry-run 検証）

Task tool で `backlog-tester` を起動する:

```
task_description: 「/test 自動修正起動: {issueID} の修正後 dry-run 検証（総合判定 PASS / 条件付きPASS / FAIL を返す）」
パラメータ:
  issueID: {issueID}
  project_dir: {project_dir}
  log_dir: {log_dir}
  auto_fix_mode: true
```

- **PASS** → F-2 Step 3 へ進む。
- **条件付きPASS（NoTestRun フォールバック発生）** → 自動再デプロイしない（FAIL と同様に扱う）。対応テストクラス未整備でカバレッジ未検証である旨を提示し、後続「NG があった場合の差し戻し」セクションで手動案内に移行する。
- **FAIL**（総合判定を返さなかった場合も同じ） → 自動再デプロイしない。backlog-tester が返した NG 原因（dry-run のエラー内容等）を提示し、後続「NG があった場合の差し戻し」セクションで手動案内に移行する。

#### F-2 Step 3: backlog-releaser（軽量再デプロイ・確認なし）

Task tool で `backlog-releaser` を起動する:

```
task_description: 「/test 自動修正起動: {issueID} の修正後 Sandbox 軽量再デプロイ（確認なし・dry-run PASS 済み）。
  直前の F-2 Step 2（backlog-tester）で現在の force-app に対し dry-run PASS 済み・以降 force-app は無変更。
  再 dry-run は不要のため、backlog-releaser.md の『スキップ判定』セクション（auto_fix_mode+redeploy_no_confirm 例外を含む）に従い省略して本デプロイのみ実行する。」
パラメータ:
  issueID: {issueID}
  project_dir: {project_dir}
  log_dir: {log_dir}
  auto_fix_mode: true
  redeploy_no_confirm: true
```

上記で渡した `auto_fix_mode: true` により、releaser のモード判定（`auto_fix_mode: true` → 軽量再デプロイ）が自動適用される（お客様確認・知見還流・目視確認のご案内・完了報告以降を省き、デプロイの成否と alias を返す）。

**releaser が失敗（接続先確認・dry-run・デプロイ）を返した場合**: F-2 完了報告を出さない。エラー内容と「修正は force-app にあるが Sandbox には未反映（デプロイが時間切れで返った場合は反映を未確認）」を伝え、後続「NG があった場合の差し戻し」セクションで手動案内に移行する。

#### F-2 完了報告

報告の前に、backlog-implementer の完了の返却（主な変更点）で今回直した部品について、下の「NG があった場合の差し戻し」手順4 と同じく影響範囲の候補 TC を出す（`AUTO_FIX_TCS` は除く。組織の地図が無ければ行ごと省略）。

```
=== 自動修正・再デプロイ完了 ===
修正した NG : {auto_fix_tcs}
再デプロイ  : Sandbox ({alias}) に再デプロイ完了
影響範囲の候補 TC : {上で出した TC。無ければ行ごと省略}
派生事項    : {backlog-implementer が返した派生事項。無ければ行ごと省略}

次のステップ（別セッションで実施）:
  /test {issueID} を再実行してください（差分モード: 前回 NG・SKIP・新規 TC と、期待結果・判定方法を書き換えた TC を再テスト）。
  次回 /test 起動時に今回の judgment-result.json と証跡が自動的に次の回次として退避されます。
  ⚠ 差分モードは今回の修正が前回 OK だった他 TC に影響していないか（回帰）までは検出しません。
    修正がバグ再現 TC 以外のコンポーネントにも及ぶ場合は --full での全件再テストを検討してください。
```

`OTHER_NG` が空でない場合は、続けて後続「NG があった場合の差し戻し」セクションで `OTHER_NG` の手動案内も実施する（修正・再デプロイした `AUTO_FIX_TCS` は差し戻しの手順1・5・7の対象にしない。/test の再実行で確かめる）。

---

#### NG があった場合の差し戻し（期待値ドリフト防止）

> **設計原則**: `investigation.md`（課題原文・真因）は不変。修正は「実装方針の変更」であり「課題認識の変更」ではない。`test-spec.md` の期待結果は NG 理由なく書き換えない。

1. `judgment-result.json` の `ng_type` で NG の種類を区別し、戻り先を確定する:

   | `ng_type` | NG の意味 | 次のアクション |
   |---|---|---|
   | `"未実行"` | 証跡が採取されていない・結果を確かめられなかった（環境起因・実行漏れ・デプロイ後キャッシュ遅延・テスト側のクエリ／匿名 Apex を実行できなかった） | **再テスト**: 差分再実行（`/test {issueID}` のみ・実装修正不要。テスト側のクエリの誤りは理由のエラーを見て test-spec.md を直してから。理由に「他の証跡の NG」があり、未確認の理由が再テストで変わらないもの〔完了を確かめる手段が無い等。Login As の相手が書かれていないものは書いてから再テスト〕は、その NG が未確認の証跡の結果に依るかを人が見て、依らなければ実装差し戻し。理由が「前提の TC-xxx が実行できなかったか…」なら TC-xxx の NG を先に片付ける。TC-xxx の未確認が再テストで変わらないものなら、依る TC も証跡を人が見て判定する） |
   | `"証跡不正"`・`"命名不一致"` | 証跡の PNG が画像として開けない・証跡のファイル名の `TC-` の有無が No 列と違う（証跡採取側の不備） | **再テスト**: 差分再実行（`/test {issueID}` のみ・実装修正不要） |
   | `"画面エラー"` | Salesforce の標準エラー画面が撮影された（「問題が発生しました」「Record ID is malformed」「関連リストはレイアウトにありません」等。Phase D-2 で原因を決められなかった匿名 Apex の debug 出力のエラー文言を含む） | **要調査**: 実装/設定の不備（レイアウトへの関連リスト未追加等）か、テスト手順・前提データの誤り（不正な ID 参照・前提レコード未作成等）かを確認し、該当する方に差し戻す |
   | `""` (空) | 証跡あり・実装が期待値と一致しない（実装バグ） | **実装差し戻し**: 実装修正→ `/test {issueID}` 再実行 |

   NG 種類が混在している場合は、実装バグ（ng_type 空）を最優先で修正してから再テストする。

   Phase F-2 の Step 2（条件付きPASS・FAIL）・Step 3（再デプロイの失敗）で止まった場合は、`AUTO_FIX_TCS` をこの表の `""` として扱い、手順5の NG の原因に dry-run の NG 原因（条件付きPASS はテストクラス未整備）・再デプロイのエラーを、修正方針の先頭に「自動修正で force-app に反映済み・Sandbox 未反映（時間切れで返ったときは未確認）」を書く（Phase 4 で同じ修正をやり直さないため）。Step 1 の backlog-implementer の中断で止まった場合は、`AUTO_FIX_TCS` の戻り先を手順3で中断の理由から決め（実装方針の問題は Phase 3、検証漏れは Phase 3.5 で、この2つは `""` でも Phase 4 にしない。テスト仕様の誤りの疑いは、implementer が挙げた TC を test-fail-routing.md の「テスト仕様・期待値・シナリオ自体の誤り」の行で、その条件を満たさなければ「判断できない・複合原因」の行で決め、残りの TC は `""` として扱う。API名不一致・describe・FieldDefinition の失敗は Phase 4〔名前を決めてから・接続を直してから〕。承認ガード例外の条件不成立は validation-report.md の総合判定と理由で決める。完了の返却が無いまま終わったものは Phase 4）、implementer が返した force-app の変更ファイルがあれば（返却が無ければ「不明」として）修正方針の先頭に「自動修正の途中の変更が force-app に残っている（{ファイル}）・Sandbox 未反映」を書く（戻すかは方針を見直すときに決める）。

2. **ループ回次を確認する**（`judgment-result.R{N}.json` の最大回次番号 N = これまでの NG 修正回数。欠番があってもファイル数ではなく最大値を基準にする＝ Phase F-2 ガード①の `PREV_ROUND_F2` と同一の算出方法。`test-fail-routing.md` §「ループ上限」のセッション跨ぎ通算カウント基準と同一）:
   ```bash
   PREV_ROUND=$(python -c "import glob, re; base = r'{log_dir}/judgment-result'; files = glob.glob(base + '.R*.json'); nums = [int(m.group(1)) for f in files for m in [re.search(r'\.R(\d+)\.json$', f)] if m]; print(max(nums) if nums else 0)")
   echo "PREV_ROUND=$PREV_ROUND"
   ```
   3 回以上の場合（Phase F-2 ガード①の `PREV_ROUND_F2 >= 3` と同じ基準）は 7 のユーザー提示に「繰り返し NG が続いています。業務担当者との打ち合わせを推奨します」を含め、継続・中止の判断を求める（`test-fail-routing.md` §「ループ上限」と同一の扱い）。

3. `test-report.md` の「NG 一覧」と `.claude/templates/backlog/test-fail-routing.md` で戻り先 Phase を確定する。戻り先が Phase 3・2・3.5・1（ガード②）のときは、`validation-report.md` があればその「## 総合判定」で始まる見出し（回ごとに複数あれば全て）の判定の行を、Phase 3 は `**Phase 3（実装方針）に戻る**`、Phase 2・1 は `**Phase 2 に戻る（決定方針に問題）**`、Phase 3.5 は `**再検証待ち**` に「（/test の NG: {TC}）」（Phase 1 は「（/test: investigation.md なし。Phase 1 から）」）を添えて書き換え、Phase 3・2 は discussion-log.md の改版履歴に `Phase3-戻り`／`Phase2-戻り` の行（discussion-log-spec.md の書式。発生Phase は `/test`、理由は NG の TC・原因と、force-app に途中の変更が残っていればそのファイル）と、本文の末尾に同じ内容の `[test] 変更:` の1行を書く（/backlog の再開がその Phase を出し、Phase 4 の着手ガードが古い判定で通らないように。planner と /backlog Phase 2 は discussion-log.md から戻り理由を読み、Phase 3 戻りの通算にも入る）。判定が既に「（/test の NG」付きの同じ値なら改版履歴の行は足さない。手順6で担当者が戻り先を変えたら変えた先で書き直し、Phase 4・テスト仕様の修正に変えたときは判定の行を元の値に戻して、本文の末尾に `[test] 変更: 担当者の判断で戻り先を {変えた先} に変更` を書く（今回改版履歴の行を足していれば「（直前の {Phase3-戻り／Phase2-戻り} は取り消し）」を添える。Phase 3 と Phase 2 の間で変えたときも同じ）（元の値が「Phase 4（実装）へ進んでよい」・続行の記録がある「技術確認待ち」以外なら、手順7 の A の1. は「Phase 3.5（今の計画のまま再判定）から Phase 4 まで」にする）

4. **影響範囲の TC を提示候補として洗い出す**（修正コンポーネントが変わった場合の回帰漏れ防止）:
   `implementation-plan.md` の改版履歴（最新行）から変更コンポーネント・オブジェクトを読み取り、`test-spec.md` の TC（観点・期待結果）と突き合わせて再テスト候補 TC を列挙する。組織の地図があれば、先に `python scripts/python/sf-lineage/lineage.py who <修正する部品・項目> --depth 2` を引き、出た部品・項目（「処理」「画面・帳票」区分）が観点・前提・期待結果に出てくる TC も候補に入れる（差分モードは書き換えていない前回 OK の TC を撮り直さないため。[option-lineage-map.md](../templates/backlog/options/option-lineage-map.md)。地図はクラス単位なので、メソッドで絞るときはファイルで確かめる）。

5. **NGの原因と修正方針を `implementation-plan.md` の改版履歴に追記する**（実装・設定・方針を直す NG、または test-spec.md の期待結果・シナリオ・前提を直す NG があるときだけ。修正に着手する前に必ず実施。撮り直すだけで済む NG だけなら書かない。test-spec.md を直すものは修正方針に「test-spec.md の {TC} の {期待結果/前提} を〜に直す（理由）」と書く）:
   ```
   | {YYYY-MM-DD} | /test NG差し戻し | {NGのTC番号・観点} | {NGの原因（実際の結果）} | {修正方針（何をどう変えるか）} | investigation.md §{対応する要求} |
   ```
   これにより「何をなぜ変えたか」が記録に残り、NG 修正ループで実装の方向が課題の真因から静かにずれるのを防ぐ。
6. ユーザーに戻り先 Phase・NG 原因・修正方針（手順5で implementation-plan.md に記録した場合はその内容）・（該当時）ループ回次警告・影響範囲 TC 候補を提示する

7. 修正後の手順を案内する。A か B かは手順1・3で決めた行き先で選び、実装・設定・方針を直す NG が1件でもあれば A、再テストだけで済む NG（手順1の表で再テストになったもの〔未実行のうち表の扱いで実装差し戻しになったものを除く〕・画面エラーでテスト側の誤りと分かったもの・手順3でテスト仕様の誤りとしたもの）だけなら B:
   ```
   A. 修正手順（この順番で実施してください）:
     1. /backlog {issueID} 再開 → {手順3の戻り先: 「Phase 4 修正」/「Phase 3（実装方針の見直し）から Phase 4 まで」/「Phase 2（対応方針の見直し）から Phase 4 まで」/「Phase 3.5（実装前検証のやり直し・今の計画のまま再判定）から Phase 4 まで」/「Phase 1（調査）から Phase 4 まで」（ガード②）} → Phase 5（dry-run 確認）
     2. Phase 6 で Sandbox に再デプロイ（/backlog Phase 6 で実施。/test はデプロイしません）
     3. {test-spec.md を直す TC があれば「test-spec.md の {TC} を直してから」}/test {issueID} を再実行（差分モード: 期待結果・判定方法を書き換えていない前回OK分は証跡を流用・取り直しなし）
        次回 /test 起動時に judgment-result.json と証跡が自動的に次の回次として退避されます
   B. 再テスト手順: {test-spec.md を直す TC があれば「test-spec.md の {TC} を直してから」}/test {issueID} を再実行してください（実装の修正・再デプロイは不要。前回 NG の TC を撮り直します）
   ```

---

### Phase G: 証跡を共有フォルダへ保存

> **[ハーネス直接実行]**

`docs/logs/` は git 管理外で本人の PC にしか残らないため、チームが見る証跡を共有フォルダへコピーする（対応記録.xlsx の廃止〔2026-09-18〕で証跡の置き場を `docs/logs/` に移したとき、共有フォルダへの保存も一緒に無くなっていたため戻した。2026-10-06）。コピーするのは次の2つ:

- `{xlsx_folder}/{issueID}_エビデンス.xlsx`（after の証跡と過去回次は埋め込み済み）
- `{evidence_dir}/before/` の中身（実装前・操作前の画面と DOM・データ。`generate_evidence_xlsx.py` は before を xlsx に入れない）→ 課題フォルダの `evidence/before/`

`{evidence_dir}` のそれ以外（after/・after_R*・before_R*）はローカルに残す（回次の退避・`cleanup_evidence.py` の削除はローカルで行う）。共有フォルダへは上書きのみで、共有フォルダにしか無いファイルは消さない。共有フォルダのエビデンス.xlsx に手が加わっている可能性があるとき（前回この PC から保存した後の変更・手を加えた版の保存・記録が無い）は、上書き前のものを課題フォルダの `BK/` に日時付きで残す。ローカルが前回保存した版のまま（F-1・Phase G だけのやり直し等）で共有フォルダだけが変わっていれば、共有フォルダの版を残して上書きしない。/test の再実行だけでは `BK/` を増やさない（判定は `share_evidence.py` の先頭コメントを参照）。共有ドライブ・ネットワークフォルダへの書き込みも確認は取らない（[shared-folder-protection.md](../templates/common/shared-folder-protection.md)）。総合判定（PASS / FAIL）に関わらず、Phase F-2 と NG の差し戻し案内の後に毎回実行する。共有フォルダと内容が同じなら書き込まないため、何度やり直してもよい。

保存先は `docs/.backlog_config.yml` の `report_dir`（課題フォルダの親。対応記録.xlsx のころと同じキー）配下の `{issueID}_` で始まる既存フォルダ、無ければ `{issueID}_{件名}`（件名は investigation.md の「件名」行）。決め方の詳細は `share_evidence.py` の先頭コメントを参照。

```bash
python "$(pwd -W)/scripts/python/backlog-xlsx/share_evidence.py" --project-dir "{project_dir}" --issue-id "{issueID}" resolve
```

| resolve の出力 | 対応 |
|---|---|
| exit 1（設定ファイルが読めない等）または `SOURCE_EXISTS=false` | コピーしない。完了報告の共有フォルダ行に理由を書く |
| `SHARE_STATUS=ok` かつ `SOURCE_EXISTS=true` | 確認せずに下記の copy を実行してから完了報告を出す（共有フォルダと同じ内容なら copy は書き込まずに `保存済み:` を出す） |
| `SHARE_STATUS=unset`（`report_dir` 未設定）/ `missing`（`report_dir` のフォルダが無い。共有ドライブの再編等） | 完了報告の後に下記の文で保存先をチャットで聞く |

保存先を聞く文（`missing` の場合は先頭に「設定されていた保存先 `{REPORT_DIR}` が見つかりませんでした。」を付ける）:

```
証跡（エビデンス.xlsx と実装前の画面）を保存する共有フォルダ（課題フォルダの親。例: G:/共有ドライブ/…/04_保守課題）を入力してください。その下の {SHARE_FOLDER_NAME} フォルダ（同じ課題IDで始まるフォルダが既にあればそちら）に保存します。保存しない場合は「保存しない」と返してください。
```

- フォルダが入力された場合: バックスラッシュはスラッシュに直して以下で `report_dir` に保存し、resolve からやり直す（`ok` になれば確認せずに copy を実行し、結果を下記の copy の説明のとおり1行で伝える）。exit 1 の場合は出力の理由（課題フォルダそのものを指定した等）を伝えて聞き直す
  ```bash
  python "$(pwd -W)/scripts/python/backlog-xlsx/share_evidence.py" --project-dir "{project_dir}" --issue-id "{issueID}" set-report-dir --path "{入力されたフォルダ}"
  ```
- 「保存しない」と返された場合: コピーしない（`docs/logs/{issueID}/` にだけ残る）

copy:

```bash
python "$(pwd -W)/scripts/python/backlog-xlsx/share_evidence.py" --project-dir "{project_dir}" --issue-id "{issueID}" copy
```

- 完了根拠: stdout の `保存完了: {パス}（…）` または `保存済み: {パス}（…）`（書き込んだファイルごとにローカルと内容が一致することまでスクリプトが確かめる）
- `上書き前のエビデンス.xlsx を退避: {パス}` も出た場合（失敗した回にも出る）: 退避先と「手で貼ったスクショはそこから貼り直してください」を添える
- 括弧内に「エビデンス.xlsx は共有フォルダの版を残しました」が出た場合: 共有フォルダのエビデンス.xlsx は上書きしていない（手で貼ったスクショ・別の PC から保存した版等を残した）ことと、「ローカルの版を共有したい場合は /test を再実行してください（共有フォルダの版は BK/ に残ります）」を添える
- 伝える場所: 完了報告の前の copy は完了報告の共有フォルダ行に、完了報告の後の copy（保存先を聞いた後・失敗後のやり直し）は保存先のパスと上の2点を1行で伝える
- exit 1 の場合: 出力の理由（共有フォルダのエビデンス.xlsx を Excel で開いている等）を伝え、同じ会話で「閉じた」等の返答があれば copy だけを実行し直す

保存しないまま会話を終えた場合（入力待ち・保存失敗）は、後から本 Phase G だけを実行すれば保存できる（/test 全体の再実行は不要。別セッションでは「{issueID} の /test Phase G だけ実施して」等で依頼する）。

---

## 完了後の確認事項

| 確認項目 | 確認コマンド |
|---|---|
| エビデンス.xlsx の存在 | `ls -lh "{xlsx_folder}/{issueID}_エビデンス.xlsx"` |
| 共有フォルダへの保存 | Phase G の copy の stdout `保存完了:` / `保存済み:`（「保存しない」を選んだ場合は対象外） |
| test-report.md の存在 | `ls -lh "{log_dir}/test-report.md"` |
| 証跡ファイルの件数 | `find "{evidence_dir}/after" -type f \| wc -l` |
| tmp/ 削除済み | `ls "{log_dir}/tmp/" 2>/dev/null \| wc -l` が 0 |

---

## 完了報告フォーマット

[completion-report-spec.md](../templates/common/completion-report-spec.md) の適用対象。

```
=== /test {issueID} 完了（{alias} Sandbox・本番未反映） ===

確認環境: Sandbox（{alias}）
本番反映状況: 未 ⚠️（Sandbox 検証までの完了。本番反映は別セッションで /release {issueID} を実施）
テスト結果: {OK=N / NG=N / 要手動=N。AI判定待ちがあれば / AI判定待ち=N}（うち AI 判定 {judgment-result.json の ai_judged_count。キーの無い古い判定結果は results の ai_judged が true の件数} 件）
総合判定: {実際の判定結果に応じて次の1つを選んで記載: PASS ✅ / 条件付きPASS ⚠️（要確認: 受入基準再確認で指摘あり） / FAIL ❌ （NG が {N} 件） / AI判定待ちあり ⏸（Phase D-2 未完了） / 受入基準再確認待ち ⏸（Phase F-1 未完了）}

成果物:
  エビデンス.xlsx : {xlsx_folder}/{issueID}_エビデンス.xlsx
  共有フォルダ    : {Phase G の結果: 保存済み（{SHARE_FILE}・evidence/before/ {N} 件。退避した場合は「上書き前のものは {退避先} に退避。手で貼ったスクショはそこから貼り直してください」） / 保存済み（変更なし） / 保存済み（evidence/before/ {N} 件。エビデンス.xlsx は共有フォルダで変更があったため上書きせず残した） / 保存先の入力待ち / 保存しない（{理由}） / 保存失敗（{理由}。退避した場合は退避先も）。入力待ち・保存失敗のときは「後から /test の Phase G だけを実行すれば保存できます」を添える}
  test-report.md  : {log_dir}/test-report.md
  証跡ファイル    : {evidence_dir}/ 配下 {N} ファイル

{auto-evidence-runner が「戻し・後片付けに失敗:」を返した場合}
要対応: 戻し・後片付けに失敗した TC があり、Sandbox のデータが戻っていません（{No}・{要旨}）。手で戻してください

{総合判定が PASS または 条件付きPASS（要確認）の場合}
本番リリースを準備する場合は、別セッション（クリーンな会話）で以下を起動してください（/release が独立して本番リリース準備を担当します。/test 自身は本番へのデプロイ・準備を行いません）:
  /release {issueID}

{総合判定が PASS または 条件付きPASS（要確認）の場合 かつ docs/logs/{issueID}/pending-signoff.md が存在する場合（2026-09-15追加）}
お客様確認: pending-signoff.md を Read し、記録済みの「要否」に応じて以下のいずれかをリマインドする（テストが確定した今が適切なタイミング。Sandbox デプロイ直後〔/backlog Phase 6〕ではリマインドしていない。詳細: [customer-signoff.md §リマインドを出すタイミング](../templates/backlog/customer-signoff.md)）:
  - 要否=必須: 「お客様確認サインを取得してください（Backlog コメント返信 / メール等、手段はユーザー判断）。確認対象は pending-signoff.md 記載の目視確認のご案内を参照してください。取得後に『サイン取得済み』と教えてください」
  - 要否=UAT実施予定がある場合のみ: 「UAT 実施予定があれば、お客様確認サインを取得してください（確認対象は pending-signoff.md 参照）。任意の手段で OK です」
  - 要否=任意: リマインド省略可
  取得報告を待たずに完了報告は確定させる（ブロッキングしない）。ユーザーが本セッション内で「サイン取得済み」等を報告した場合は `pending-signoff.md` を削除する（次に `/backlog` を開いたときに二重リマインドされないようにするため）。

{総合判定が PASS または 条件付きPASS（要確認）の場合 かつ `{log_dir}/approach-plan.md`「### 今回対象外とする要求・入口」が「なし」以外の場合}
お客様への連絡: 「お客様に連絡するときに、要望から外した点と理由もあわせて伝えてください: {要求・入口} — {理由}」を添える（1件1行。[CLAUDE.md §要望への対応範囲の取捨選択](../CLAUDE.md#要望への対応範囲の取捨選択全エージェント共通) 5.）。お客様確認サインの要否や取得済みかどうかによらず出す

{総合判定が PASS（完全・要確認なし）の場合のみ}
証跡クリーンアップ: 証跡スクショ（PNG）のうちxlsxに実際に格納済みのものはエビデンス.xlsxに残っています（before/等xlsx対象外のファイル・DOM テキスト・investigation.md 等は削除されません。埋め込み実数を検証してから削除する安全設計です）。エビデンス以外の画面テストの PNG（xlsx に貼らない機械照合用）も一緒に消えます（画面の文字の .txt は残ります）。本番リリース準備が完了し、この課題でもう /test を再実行しない見込みなら、以下でディスク容量を削減できます:
  python "{project_dir}/scripts/python/backlog-xlsx/cleanup_evidence.py" --folder "{xlsx_folder}" --issue-id "{issueID}" --evidence-dir "{evidence_dir}" --judgment "{judgment_path}" --spec "{spec_path}"
※ 削除後に /test を再実行する場合は自動的に全量再実行になります（差分再実行モードは使われません）。

{実装バグ NG が Phase F-2 で自動修正・再デプロイされた場合}
自動修正: 完了（Phase F-2）
  修正 TC: {auto_fix_tcs}
  次のステップ: 別セッションで /test {issueID} を再実行してください（差分モード: 前回 NG・SKIP・新規 TC と、期待結果・判定方法を書き換えた TC を再テスト）。
               次回 /test 起動時に今回の証跡が自動的に次の回次として退避されます。
               ⚠ 差分モードは今回の修正が前回 OK だった他 TC に影響していないか（回帰）までは検出しません。
                 修正がバグ再現 TC 以外のコンポーネントにも及ぶ場合は --full での全件再テストを検討してください。

{総合判定が条件付きPASS（要確認）の場合（Phase F-1）}
要確認: 受入基準再確認で指摘があります。
  詳細: test-report.md の「## 受入基準再確認」を参照してください。
  対応: 業務判断が必要なため自動修正はしていません。指摘内容を確認し、必要なら implementation-plan.md に追記してから /backlog Phase 4 で再実装してください。

{総合判定が AI判定待ちありの場合（Phase D-2 未完了）}
要対応: AI 判定していない TC が残っています（{judgment-result.json の ai_list の No}）。Phase D-2 で判定してから Phase E からやり直してください（別セッションでは /backlog {issueID} の再開で Phase D-2 から Phase G までだけを実施できます。/test 全体の再実行は不要）。

{総合判定が受入基準再確認待ちの場合（Phase F-1 未完了）}
要対応: 受入基準再確認（Phase F-1）が完了していません。Backlog に接続できる状態で Phase F-1 と Phase G だけをやり直し、この完了報告を出し直してください（別セッションでは /backlog {issueID} の再開で F-1 と Phase G だけを実施できます。/test 全体の再実行は不要）。

{手動対応が必要な NG がある場合（ng_type あり〔OTHER_NG〕/ 自動修正のガードで止まった場合 / implementer の中断・dry-run の条件付きPASS・FAIL・再デプロイの失敗で止まった場合）}
NG 一覧:
  - TC-00X: {観点} — {理由}（種別: `ng_type` の値。空欄の場合は「実装バグ」と表示する）
{Phase F-2 の Step 2・3 で止まった場合}自動修正: force-app に反映済み・Sandbox 未反映（{止まった段と理由。時間切れで返ったときは「反映は未確認」}）
{Phase F-2 の Step 1 の中断で止まった場合}自動修正: 中断（{理由}）{force-app に変更があれば（不明を含む）「。途中の変更が force-app に残っている・Sandbox 未反映（{ファイル}）」}

{「NG があった場合の差し戻し」手順7で案内した A（修正手順。NG 原因・修正方針は手順5で implementation-plan.md に記録済み）または B（再テスト手順）と、Phase F-2 のガード③で止まった場合はその再デプロイの案内をそのまま書く}

{要手動がある場合}
要手動確認:
  - TC-00X: {観点} — エビデンス.xlsx（Phase G で共有フォルダに保存した場合はそちら）の「証跡」シートに手動でスクショを貼り付けてください（/test を再実行すると上書きされるため、最後の /test の後に貼る。共有フォルダで貼ったものは、上書きの前に課題フォルダの BK/ へ残る）。
    確認対象: {ラベル（日本語表示名）} / URL: {instance_url}/lightning/r/{SObject}/{Id}/view または {画面URL（クエリ除去済み）} / 操作手順: {test-spec.mdの「テスト手順」列 or 要約}
    ※ 対象レコード・URLが特定できない TC は URL 行を省略する（[visual-confirmation-handoff.md](../templates/common/visual-confirmation-handoff.md) 準拠）

確認方法: 担当者がエビデンス.xlsx の「テスト結果」シートの判定と、証跡シートのエビデンスの TC・NG の TC（test-report.md に「🔎 目視確認のご案内」があればそのレコード URL・操作手順）を開き、期待結果どおりなら OK
未確認事項: {Phase A 手順3.5・Phase B（test-spec-builder）返却の [WARN] 行があれば列挙 ＋ 要手動確認 TC があれば「上記「要手動確認」参照」を追記 / いずれもなければ「未確認事項なし」}
```

test-report.md の「🔎 目視確認のご案内」に Claude が操作した対象の一覧（レコードURL・操作手順つき）がまとまっている。NG（画面エラー含む）はここから直接開いて確認できる（要手動は通常含まれない）。

---

## 注意事項

- **本番組織への操作は Phase A で物理ブロック**。Sandbox alias でのみ実行可。
- accessToken は一切ファイルに保存しない（`sf org open --url-only` のワンタイム URL のみ使用）。
- テストデータ（`AUTOTEST_{issueID}_` プレフィックス）は削除しない。Sandbox に蓄積させ、ユーザーが目視で確認できるようにする。
- `/backlog` Phase 6（Sandbox デプロイ）完了後の後続工程。デプロイ済み Sandbox を前提として網羅的テストを実施する（通常フローではデプロイしない。例外: Phase F-2 の NG 自動修正ループが発動した場合のみ、修正後の軽量再デプロイを実施する）。
- **`/test` は共有コンポーネント修正漏れの二次防御（バックストップ）**: 同一根本原因が複数入口に fan-out するケースは、修正が共有メソッド自体に入った場合のみ軸3（consumer fan-out）で検出できる。修正が呼び出し元側だけに入った場合は /test では検出できない。一次防御は `/backlog` 調査段階（backlog-investigator の根本原因特定＋ option-reverse-grep / regression-guard の逆参照で全消費者を修正スコープに含める判断。Step C-2 参照）である。
