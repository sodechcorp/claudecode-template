# -*- coding: utf-8 -*-
"""backlog-xlsx / anon_apex_runner.py
匿名 Apex を Sandbox で実行し、debug ログから結果を抽出する。
テストデータの作成・Flow 起動・後始末（削除）にも使用する。

Usage（実行）:
    python anon_apex_runner.py run \\
      --alias <sandbox-alias> \\
      --apex-file /path/to/anon.apex \\
      --out /path/to/evidence/after/apex/TC-002_apex.txt \\
      --no TC-002 --label "Flow 起動確認"

Usage（テストデータ削除・後始末）:
    python anon_apex_runner.py cleanup \\
      --alias <sandbox-alias> \\
      --sobject Account \\
      --external-id-prefix "AUTOTEST_GF-350_"
"""

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path


# ── sandbox 判定（soql_evidence.py と同一ロジック） ────────────────────────

def assert_sandbox(alias: str) -> str:
    """alias が Sandbox であることを確認する。本番なら SystemExit。確定した alias を返す。"""
    if not alias:
        result = subprocess.run(
            ["sf", "config", "get", "target-org", "--json"],
            capture_output=True, text=True
        )
        try:
            alias = json.loads(result.stdout)["result"][0]["value"]
        except (json.JSONDecodeError, KeyError, IndexError):
            raise SystemExit("[FATAL] target-org が設定されていません。--alias を指定してください。")

    result = subprocess.run(
        ["sf", "org", "display", "--target-org", alias, "--json"],
        capture_output=True, text=True
    )
    try:
        org_info = json.loads(result.stdout)["result"]
        is_sandbox = org_info.get("isSandbox", False)
    except (json.JSONDecodeError, KeyError):
        raise SystemExit(f"[FATAL] org display 失敗 ({alias}). Sandbox 確認ができません。")

    if not is_sandbox:
        raise SystemExit(
            f"[FATAL] 接続先が Sandbox ではありません ({alias})。\n"
            "        本番組織への匿名 Apex 実行は禁止されています。"
        )
    return alias


# ── 匿名 Apex 実行 ───────────────────────────────────────────────────────────

def run_anonymous(alias: str, apex_file: str) -> dict:
    """sf apex run --file を実行し JSON 結果を返す。失敗時は SystemExit。"""
    result = subprocess.run(
        ["sf", "apex", "run", "--target-org", alias, "--file", apex_file, "--json"],
        capture_output=True, text=True
    )
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        raise SystemExit(
            f"[FATAL] Apex run レスポンスの JSON パース失敗:\n{result.stdout[:500]}"
        )

    # status 非 0 またはコンパイルエラー
    apex_result = data.get("result", {})
    if apex_result.get("compiled") is False:
        errs = apex_result.get("compileProblem", "（コンパイルエラー詳細なし）")
        raise SystemExit(f"[FATAL] Apex コンパイルエラー:\n{errs}")
    if apex_result.get("success") is False:
        exc = apex_result.get("exceptionMessage", "") or apex_result.get("exceptionStackTrace", "")
        raise SystemExit(f"[FATAL] Apex 実行時例外:\n{exc}")
    return data


def extract_debug_output(apex_result: dict) -> list:
    """debug ログから System.debug 出力を抽出して行リストを返す。"""
    log = apex_result.get("result", {}).get("logs", "") or ""
    lines = []
    for line in log.splitlines():
        # ログ形式: timestamp|USER_DEBUG|[1]|DEBUG|...
        m = re.search(r"\|USER_DEBUG\|\[\d+\]\|DEBUG\|(.+)$", line)
        if m:
            lines.append(m.group(1).strip())
    return lines


def to_text_evidence(apex_result: dict, out_path: str, label: str = "", no: str = "", apex_code: str = "") -> None:
    """Apex 実行結果を証跡テキストとして保存する。"""
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    result = apex_result.get("result", {})
    debug_lines = extract_debug_output(apex_result)

    lines = []
    lines.append("=" * 60)
    lines.append("匿名 Apex 実行証跡")
    if no:
        lines.append(f"No      : {no}")
    if label:
        lines.append(f"観点    : {label}")
    lines.append(f"実行日時: {ts}")
    lines.append(f"成功    : {result.get('success', '?')}")
    lines.append("=" * 60)

    if apex_code:
        lines.append("--- 実行コード ---")
        lines.append(apex_code[:2000])  # 長すぎる場合は先頭 2000 文字
        lines.append("")

    lines.append("--- System.debug 出力 ---")
    if debug_lines:
        lines.extend(debug_lines)
    else:
        lines.append("（debug 出力なし）")
    lines.append("")

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    Path(out_path).write_text("\n".join(lines), encoding="utf-8")
    print(f"[OK] Apex 証跡を保存: {out_path}")


# ── テストデータ後始末 ────────────────────────────────────────────────────────

def collect_created_ids(alias: str, sobject: str, external_id_prefix: str) -> list:
    """ExternalId__c または Name に external_id_prefix を持つレコードの Id を取得。"""
    # 汎用的に Name 列で一致確認（ExternalId__c がないオブジェクトでも動く）
    query = (
        f"SELECT Id FROM {sobject} WHERE Name LIKE '{external_id_prefix}%' LIMIT 200"
    )
    result = subprocess.run(
        ["sf", "data", "query", "--target-org", alias, "--query", query,
         "--result-format", "json"],
        capture_output=True, text=True
    )
    try:
        data = json.loads(result.stdout)
        records = data.get("result", {}).get("records", [])
        return [r["Id"] for r in records]
    except (json.JSONDecodeError, KeyError):
        return []


def cleanup_records(alias: str, sobject: str, ids: list) -> dict:
    """指定 Id リストのレコードを削除する。件数が少なければ逐次、多ければ bulk。"""
    if not ids:
        return {"deleted": 0, "failed": []}

    failed = []
    deleted = 0

    if len(ids) <= 10:
        for record_id in ids:
            result = subprocess.run(
                ["sf", "data", "delete", "record",
                 "--target-org", alias,
                 "--sobject-type", sobject,
                 "--record-id", record_id,
                 "--json"],
                capture_output=True, text=True
            )
            try:
                data = json.loads(result.stdout)
                if data.get("status") == 0:
                    deleted += 1
                else:
                    failed.append(record_id)
            except json.JSONDecodeError:
                failed.append(record_id)
    else:
        # bulk delete: CSV 一時ファイル経由
        with tempfile.NamedTemporaryFile(mode="w", suffix=".csv",
                                         delete=False, encoding="utf-8") as f:
            f.write("Id\n")
            for record_id in ids:
                f.write(f"{record_id}\n")
            csv_path = f.name
        try:
            result = subprocess.run(
                ["sf", "data", "bulk", "delete",
                 "--target-org", alias,
                 "--sobject-type", sobject,
                 "--file", csv_path,
                 "--wait", "5",
                 "--json"],
                capture_output=True, text=True
            )
            data = json.loads(result.stdout)
            if data.get("status") == 0:
                deleted = len(ids)
            else:
                failed = ids
        except (json.JSONDecodeError, FileNotFoundError):
            failed = ids
        finally:
            os.unlink(csv_path)

    return {"deleted": deleted, "failed": failed}


# ── 一括並列実行（run-batch サブコマンド） ───────────────────────────────────

def run_one_anon_case(alias: str, case: dict) -> dict:
    """1 AnonApex ケースを実行し証跡保存する。ThreadPoolExecutor から呼ぶ純関数。
    case = {"no": str, "label": str, "apex_file": str, "out": str}
    返り値: {"no","label","ok":bool,"out":str,"error":str}
    """
    try:
        apex_code = Path(case["apex_file"]).read_text(encoding="utf-8")
        data = run_anonymous(alias, case["apex_file"])
        to_text_evidence(data, case["out"], case["label"], case["no"], apex_code)
        r = data.get("result", {})
        return {"no": case["no"], "label": case["label"], "ok": True,
                "out": case["out"], "error": "",
                "compiled": r.get("compiled"), "success": r.get("success")}
    except SystemExit as e:
        return {"no": case["no"], "label": case["label"], "ok": False,
                "out": case["out"], "error": str(e),
                "compiled": None, "success": None}


def run_batch_parallel(alias: str, cases: list, max_workers: int = 3,
                       serial_nos: set = None) -> list:
    """AnonApex ケース群を並列実行する。
    - serial_nos に含まれる TC（データ競合懸念）は並列対象外にし、
      並列バッチ完了後に逐次実行する。
    - max_workers <= 1 で全逐次（--serial フォールバック）。
    - rollbackケース（Savepoint/rollback）はトランザクションローカルなので並列安全。
    - 永続化ケースは AUTOTEST_{issueID}_{TC_No}_ プレフィックスで論理分離される前提。
    - 同一既存レコードを複数 TC が触る場合は serial_nos に列挙して逐次化すること。
    - ガバナ制限エラー（ConcurrentPerOrgLongTxn / REQUEST_LIMIT）を検出して警告する。
    - assert_sandbox は呼び出し元で1回だけ実施済みの前提。
    返り値: ケースごとの結果 dict リスト（No 昇順）。
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    serial_nos = serial_nos or set()
    parallel_cases = [c for c in cases if c["no"] not in serial_nos]
    serial_cases = [c for c in cases if c["no"] in serial_nos]

    results = []
    limit_errors = []

    if max_workers <= 1:
        for c in cases:
            r = run_one_anon_case(alias, c)
            results.append(r)
            if not r["ok"] and ("ConcurrentPerOrgLongTxn" in r["error"] or
                                "REQUEST_LIMIT" in r["error"]):
                limit_errors.append(r["no"])
    else:
        # 並列バッチ（競合懸念のない TC）
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futs = {ex.submit(run_one_anon_case, alias, c): c for c in parallel_cases}
            for fut in as_completed(futs):
                r = fut.result()
                results.append(r)
                if not r["ok"] and ("ConcurrentPerOrgLongTxn" in r["error"] or
                                    "REQUEST_LIMIT" in r["error"]):
                    limit_errors.append(r["no"])
        # 競合懸念 TC を並列バッチ完了後に逐次実行
        for c in serial_cases:
            r = run_one_anon_case(alias, c)
            results.append(r)
            if not r["ok"] and ("ConcurrentPerOrgLongTxn" in r["error"] or
                                "REQUEST_LIMIT" in r["error"]):
                limit_errors.append(r["no"])

    if limit_errors:
        print(f"[WARN] ガバナ制限エラーが発生しました（{limit_errors}）。"
              " --serial オプションで逐次実行に切り替えてください。")

    return sorted(results, key=lambda r: r["no"])


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="匿名 Apex の実行と後始末")
    sub = parser.add_subparsers(dest="subcommand", required=True)

    # run サブコマンド
    p_run = sub.add_parser("run", help="匿名 Apex を実行し証跡を保存する")
    p_run.add_argument("--alias", default="", help="Sandbox org alias")
    p_run.add_argument("--apex-file", required=True, dest="apex_file",
                       help="実行する .apex ファイルのパス")
    p_run.add_argument("--out", required=True, help="証跡ファイルの出力パス")
    p_run.add_argument("--no", default="", dest="tc_no", help="テストケース番号（TC-001 等）")
    p_run.add_argument("--label", default="", help="テスト観点ラベル")

    # cleanup サブコマンド
    p_clean = sub.add_parser("cleanup", help="テストデータ（Name プレフィックス一致）を削除する")
    p_clean.add_argument("--alias", default="", help="Sandbox org alias")
    p_clean.add_argument("--sobject", required=True, help="削除対象の SObject API 名")
    p_clean.add_argument("--external-id-prefix", required=True, dest="prefix",
                         help="Name 列で一致する AUTOTEST_{issueID}_ 等のプレフィックス")
    p_clean.add_argument("--dry-run", action="store_true", dest="dry_run",
                         help="実際には削除せず件数のみ確認する")

    # run-batch サブコマンド（並列一括実行）
    p_batch = sub.add_parser("run-batch", help="複数の匿名 Apex を一括実行する（並列対応）")
    p_batch.add_argument("--alias", default="", help="Sandbox org alias")
    p_batch.add_argument("--cases-file", required=True, dest="cases_file",
                         help='実行ケース定義 JSON ファイル（[{"no","label","apex_file","out"},...] 形式）')
    p_batch.add_argument("--max-workers", type=int, default=3, dest="max_workers",
                         help="並列 worker 数（デフォルト 3）")
    p_batch.add_argument("--serial", action="store_true",
                         help="強制的に逐次実行（ガバナ競合時のフォールバック用）")
    p_batch.add_argument("--serial-nos", default="", dest="serial_nos",
                         help="逐次実行に寄せる TC 番号カンマ区切り（同一既存レコード競合懸念 TC）")

    args = parser.parse_args()
    alias = assert_sandbox(args.alias)  # Sandbox 確認はループ前に1回だけ実施

    if args.subcommand == "run":
        apex_code = Path(args.apex_file).read_text(encoding="utf-8")
        data = run_anonymous(alias, args.apex_file)
        to_text_evidence(data, args.out, args.label, args.tc_no, apex_code)

    elif args.subcommand == "run-batch":
        cases = json.loads(Path(args.cases_file).read_text(encoding="utf-8"))
        serial_nos = (set(t.strip() for t in args.serial_nos.split(",") if t.strip())
                      if args.serial_nos else set())
        max_workers = 1 if args.serial else args.max_workers
        mode = "逐次" if max_workers <= 1 else f"並列 (max_workers={max_workers})"
        print(f"[INFO] {len(cases)} 件の AnonApex ケースを{mode}で実行します。")
        results = run_batch_parallel(alias, cases, max_workers=max_workers,
                                     serial_nos=serial_nos)
        ng_count = sum(1 for r in results if not r["ok"])
        print(f"[INFO] run-batch 完了: {len(results)} 件実行 / NG {ng_count} 件")
        if ng_count:
            for r in results:
                if not r["ok"]:
                    print(f"  [NG] {r['no']} ({r['label']}): {r['error']}")
            sys.exit(1)

    elif args.subcommand == "cleanup":
        ids = collect_created_ids(alias, args.sobject, args.prefix)
        if not ids:
            print(f"[INFO] 削除対象レコードなし (SObject: {args.sobject}, prefix: {args.prefix})")
            return
        print(f"[INFO] 削除対象: {len(ids)} 件 (SObject: {args.sobject})")
        if args.dry_run:
            print("[DRY-RUN] 削除をスキップします。")
            for rid in ids:
                print(f"  - {rid}")
            return
        result = cleanup_records(alias, args.sobject, ids)
        print(f"[OK] 削除完了: {result['deleted']} 件")
        if result["failed"]:
            print(f"[NG] 削除失敗: {len(result['failed'])} 件 — 手動削除してください:")
            for rid in result["failed"]:
                print(f"  - {rid}")
            sys.exit(1)


if __name__ == "__main__":
    main()
