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

    args = parser.parse_args()
    alias = assert_sandbox(args.alias)

    if args.subcommand == "run":
        apex_code = Path(args.apex_file).read_text(encoding="utf-8")
        data = run_anonymous(alias, args.apex_file)
        to_text_evidence(data, args.out, args.label, args.tc_no, apex_code)

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
