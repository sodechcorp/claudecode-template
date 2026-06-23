# -*- coding: utf-8 -*-
"""backlog-xlsx / soql_evidence.py
SOQL を Sandbox で実行し、結果を証跡テキストファイルとして保存する。

Usage:
    python soql_evidence.py \\
      --alias <sandbox-alias> \\
      --query "SELECT Id, Name FROM Account LIMIT 10" \\
      --out /path/to/evidence/after/soql/TC-001_account.txt \\
      --no TC-001 --label "取引先件数確認"

    # 複数クエリを一括実行する場合（--queries-file）
    python soql_evidence.py \\
      --alias <sandbox-alias> \\
      --queries-file /path/to/test-spec.md \\
      --out-dir /path/to/evidence/after/soql/
"""

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
from pathlib import Path


# ── sandbox 判定 ─────────────────────────────────────────────────────────────

def assert_sandbox(alias: str) -> str:
    """alias が Sandbox であることを確認する。本番なら SystemExit。接続済み alias を返す。"""
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
        raise SystemExit(f"[FATAL] org display 失敗 ({alias}). Sandbox 接続確認ができません。")

    if not is_sandbox:
        raise SystemExit(
            f"[FATAL] 接続先が Sandbox ではありません ({alias})。\n"
            "        本番組織への SOQL 実行は禁止されています。"
        )
    return alias


# ── SOQL 実行 ────────────────────────────────────────────────────────────────

def run_soql(alias: str, query: str) -> dict:
    """sf data query を実行して JSON 結果を返す。エラー時は SystemExit。"""
    result = subprocess.run(
        ["sf", "data", "query", "--target-org", alias, "--query", query,
         "--result-format", "json"],
        capture_output=True, text=True
    )
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        raise SystemExit(
            f"[FATAL] SOQL レスポンスの JSON パース失敗:\n{result.stdout[:500]}\n{result.stderr[:300]}"
        )
    if data.get("status") != 0 and "result" not in data:
        msg = data.get("message") or result.stderr or "不明なエラー"
        raise SystemExit(f"[FATAL] SOQL 実行失敗: {msg}")
    return data


# ── 証跡テキスト生成 ─────────────────────────────────────────────────────────

def to_text_evidence(data: dict, out_path: str, query: str, label: str = "", no: str = "") -> int:
    """SOQL 結果を人間可読テキストとして保存し、件数を返す。"""
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    result = data.get("result", {})
    records = result.get("records", [])
    total = result.get("totalSize", len(records))

    lines = []
    lines.append("=" * 60)
    lines.append(f"SOQL 証跡")
    lines.append(f"No      : {no}" if no else "")
    lines.append(f"観点    : {label}" if label else "")
    lines.append(f"実行日時: {ts}")
    lines.append(f"クエリ  : {query}")
    lines.append(f"件数    : {total} 件")
    lines.append("=" * 60)

    if records:
        # ヘッダー行
        keys = [k for k in records[0].keys() if k != "attributes"]
        col_widths = {k: max(len(k), max((len(str(r.get(k, ""))) for r in records), default=0)) for k in keys}
        header = " | ".join(k.ljust(col_widths[k]) for k in keys)
        sep = "-+-".join("-" * col_widths[k] for k in keys)
        lines.append(header)
        lines.append(sep)
        for rec in records:
            row = " | ".join(str(rec.get(k, "")).ljust(col_widths[k]) for k in keys)
            lines.append(row)
    else:
        lines.append("（レコードなし）")

    lines.append("")
    text = "\n".join(l for l in lines if l is not None)

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    Path(out_path).write_text(text, encoding="utf-8")
    print(f"[OK] SOQL 証跡を保存: {out_path} ({total} 件)")
    return total


# ── queries-file パーサ（test-spec.md の SOQL 行を抽出） ─────────────────────

def parse_queries_from_spec(spec_path: str) -> list:
    """test-spec.md の Markdown テーブルから 種別=SOQL の行を抽出する。
    返り値: [{"no": "TC-001", "label": "...", "query": "SELECT ..."}]
    """
    text = Path(spec_path).read_text(encoding="utf-8")
    headers = []
    rows = []
    in_table = False

    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            if in_table:
                break
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if all(re.match(r"^[-: ]+$", c) for c in cells):
            in_table = True
            continue
        if not headers:
            headers = cells
            in_table = True
        else:
            row = dict(zip(headers, cells))
            rows.append(row)

    queries = []
    for row in rows:
        # 種別列の表記ゆれに対応
        shubetsu = row.get("種別", row.get("実行種別", "")).strip()
        if shubetsu.upper() != "SOQL":
            continue
        action = row.get("実行アクション", row.get("確認手順", "")).strip()
        # SELECT から始まる SOQL を抽出
        m = re.search(r"(SELECT\s.+)", action, re.IGNORECASE)
        query = m.group(1) if m else action
        queries.append({
            "no": row.get("No", "").strip(),
            "label": row.get("観点", row.get("確認観点", "")).strip(),
            "query": query,
            "auto": row.get("自動化可否", "自動").strip(),
        })
    return queries


# ── 並列実行ヘルパー ──────────────────────────────────────────────────────────

def run_one_soql_case(alias: str, q: dict, out_dir: str) -> dict:
    """1 SOQL ケースを実行し証跡保存する。ThreadPoolExecutor から呼ぶ純関数。
    返り値: {"no","label","ok":bool,"count":int|None,"out":str,"error":str}
    """
    fname = f"{q['no']}_{re.sub(r'[^\w]', '_', q['label'])[:30]}.txt"
    out_path = os.path.join(out_dir, fname)
    try:
        data = run_soql(alias, q["query"])
        total = to_text_evidence(data, out_path, q["query"], q["label"], q["no"])
        return {"no": q["no"], "label": q["label"], "ok": True,
                "count": total, "out": out_path, "error": ""}
    except SystemExit as e:
        return {"no": q["no"], "label": q["label"], "ok": False,
                "count": None, "out": out_path, "error": str(e)}


def run_queries_parallel(alias: str, queries: list, out_dir: str,
                         max_workers: int = 4,
                         target_tc: set = None) -> list:
    """SOQL ケース群を並列実行する。
    - target_tc が指定された場合、含まれない TC はスキップ（差分再実行）。
    - 要手動ケースはスキップ。
    - max_workers <= 1 で完全逐次（後方互換・--serial フォールバック）。
    - API 制限エラー（REQUEST_LIMIT_EXCEEDED / 429）を検出して警告する。
    - assert_sandbox は呼び出し元（main）で1回だけ実施済みの前提。
    返り値: ケースごとの結果 dict リスト（No 昇順）。
    """
    from concurrent.futures import ThreadPoolExecutor, as_completed

    targets = []
    for q in queries:
        if "要手動" in q.get("auto", ""):
            print(f"[SKIP] {q['no']}: 要手動のためスキップ")
            continue
        if target_tc is not None and q["no"] not in target_tc:
            print(f"[SKIP] {q['no']}: 差分対象外（前回 OK）")
            continue
        targets.append(q)

    if not targets:
        return []

    results = []
    limit_errors = []

    if max_workers <= 1:
        for q in targets:
            r = run_one_soql_case(alias, q, out_dir)
            results.append(r)
            if not r["ok"] and ("REQUEST_LIMIT" in r["error"] or "429" in r["error"]):
                limit_errors.append(r["no"])
    else:
        with ThreadPoolExecutor(max_workers=max_workers) as ex:
            futs = {ex.submit(run_one_soql_case, alias, q, out_dir): q for q in targets}
            for fut in as_completed(futs):
                r = fut.result()
                results.append(r)
                if not r["ok"] and ("REQUEST_LIMIT" in r["error"] or "429" in r["error"]):
                    limit_errors.append(r["no"])

    if limit_errors:
        print(f"[WARN] API 制限エラーが発生しました（{limit_errors}）。"
              " --serial オプションで逐次実行に切り替えてください。")

    return sorted(results, key=lambda r: r["no"])


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="SOQL を Sandbox で実行し証跡 txt を保存する")
    parser.add_argument("--alias", default="", help="Sandbox org alias（省略時は target-org を使用）")
    parser.add_argument("--query", default="", help="実行する SOQL 文（単発実行）")
    parser.add_argument("--out", default="", help="証跡ファイルの出力パス（単発実行）")
    parser.add_argument("--no", default="", dest="tc_no", help="テストケース番号（TC-001 等）")
    parser.add_argument("--label", default="", help="テスト観点ラベル")
    parser.add_argument("--queries-file", default="", dest="queries_file",
                        help="test-spec.md のパス（SOQL 行を一括実行）")
    parser.add_argument("--out-dir", default="", dest="out_dir",
                        help="--queries-file 使用時の証跡ファイル出力ディレクトリ")
    parser.add_argument("--max-workers", type=int, default=4, dest="max_workers",
                        help="--queries-file 一括実行時の並列 worker 数（デフォルト 4）")
    parser.add_argument("--serial", action="store_true",
                        help="--queries-file 一括実行を強制的に逐次で実行（--max-workers を 1 に上書き）")
    parser.add_argument("--target-tc", default="", dest="target_tc",
                        help="差分再実行対象の TC 番号カンマ区切り（例: TC-003,TC-011）。省略時は全件")
    args = parser.parse_args()

    alias = assert_sandbox(args.alias)  # Sandbox 確認はループ前に1回だけ実施

    if args.queries_file:
        # 一括実行（並列 or 逐次）
        if not args.out_dir:
            print("[ERROR] --queries-file 使用時は --out-dir が必須です。")
            sys.exit(1)
        queries = parse_queries_from_spec(args.queries_file)
        if not queries:
            print("[WARN] test-spec.md に SOQL 種別のテストケースが見つかりませんでした。")
            return
        max_workers = 1 if args.serial else args.max_workers
        target_tc = (set(t.strip() for t in args.target_tc.split(",") if t.strip())
                     if args.target_tc else None)
        mode = "逐次" if max_workers <= 1 else f"並列 (max_workers={max_workers})"
        print(f"[INFO] {len(queries)} 件の SOQL テストケースを{mode}で実行します。")
        results = run_queries_parallel(alias, queries, args.out_dir,
                                       max_workers=max_workers, target_tc=target_tc)
        ng_count = sum(1 for r in results if not r["ok"])
        if ng_count:
            print(f"[WARN] {ng_count} 件の SOQL ケースでエラーが発生しました。")
            for r in results:
                if not r["ok"]:
                    print(f"  [NG] {r['no']} ({r['label']}): {r['error']}")
    else:
        # 単発実行
        if not args.query:
            print("[ERROR] --query または --queries-file が必要です。")
            sys.exit(1)
        if not args.out:
            print("[ERROR] --out が必要です。")
            sys.exit(1)
        data = run_soql(alias, args.query)
        to_text_evidence(data, args.out, args.query, args.label, args.tc_no)


if __name__ == "__main__":
    main()
