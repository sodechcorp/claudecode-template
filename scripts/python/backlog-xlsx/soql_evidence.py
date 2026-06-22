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
    args = parser.parse_args()

    alias = assert_sandbox(args.alias)

    if args.queries_file:
        # 一括実行
        if not args.out_dir:
            print("[ERROR] --queries-file 使用時は --out-dir が必須です。")
            sys.exit(1)
        queries = parse_queries_from_spec(args.queries_file)
        if not queries:
            print("[WARN] test-spec.md に SOQL 種別のテストケースが見つかりませんでした。")
            return
        print(f"[INFO] {len(queries)} 件の SOQL テストケースを実行します。")
        for q in queries:
            if "要手動" in q.get("auto", ""):
                print(f"[SKIP] {q['no']}: 要手動のためスキップ")
                continue
            fname = f"{q['no']}_{re.sub(r'[^\\w]', '_', q['label'])[:30]}.txt"
            out_path = os.path.join(args.out_dir, fname)
            try:
                data = run_soql(alias, q["query"])
                to_text_evidence(data, out_path, q["query"], q["label"], q["no"])
            except SystemExit as e:
                print(f"[NG] {q['no']}: {e}")
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
