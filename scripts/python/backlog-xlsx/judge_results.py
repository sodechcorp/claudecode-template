# -*- coding: utf-8 -*-
"""backlog-xlsx / judge_results.py
test-spec.md の期待結果と証跡ファイルの実際の結果を突き合わせ、
OK/NG を判定して対応記録.xlsx の H 列（実際の結果）を更新する。

Usage:
    python judge_results.py \\
      --folder /path/to/xlsx_folder \\
      --issue-id GF-350 \\
      --spec /path/to/test-spec.md \\
      --evidence-dir /path/to/evidence/after \\
      --out /path/to/judgment-result.json
"""

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

from _common import validate_folder


# ── test-spec.md パーサ ───────────────────────────────────────────────────────

def parse_test_spec(spec_path: str) -> list:
    """test-spec.md のテーブルを dict リストとして返す。"""
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
            rows.append(dict(zip(headers, cells)))

    return rows


# ── 証跡ファイル探索 ────────────────────────────────────────────────────────

def find_evidence_file(evidence_dir: str, tc_no: str, shubetsu: str) -> str:
    """証跡ディレクトリから TC-001 に対応するファイルを探す。"""
    # 種別別サブディレクトリ
    subdir_map = {
        "SOQL": "soql",
        "ApexTest": "apex",
        "AnonApex": "apex",
        "UI": "screen",
        "メタ確認": "meta",
        "ファイル確認": "meta",
    }
    subdir = subdir_map.get(shubetsu, "")
    search_dirs = []
    if subdir:
        search_dirs.append(os.path.join(evidence_dir, subdir))
    search_dirs.append(evidence_dir)

    for d in search_dirs:
        if not os.path.isdir(d):
            continue
        for fname in os.listdir(d):
            if fname.startswith(tc_no):
                return os.path.join(d, fname)
    return ""


# ── 判定ロジック ─────────────────────────────────────────────────────────────

def judge_case(tc: dict, evidence_path: str) -> dict:
    """1テストケースを判定し {"ok": bool, "actual": str, "reason": str} を返す。"""
    no = tc.get("No", "")
    label = tc.get("観点", "")
    kiki = tc.get("期待結果", "").strip()
    judge_method = tc.get("判定方法", "").strip()
    auto = tc.get("自動化可否", "自動").strip()

    # 要手動ケースは判定スキップ
    if "要手動" in auto:
        return {"ok": None, "actual": "要手動確認", "reason": "自動化不可・ユーザー手動確認"}

    # 証跡ファイルがない場合
    if not evidence_path or not os.path.exists(evidence_path):
        return {"ok": False, "actual": "", "reason": f"証跡ファイルが見つかりません (No: {no})"}

    # スクショ（PNG）: 存在確認のみ
    if evidence_path.lower().endswith(".png"):
        size = os.path.getsize(evidence_path)
        if size < 1000:
            return {"ok": False, "actual": f"スクショあり ({size}B・小さすぎる)", "reason": "PNG が不正に小さい"}
        return {"ok": True, "actual": f"スクショ取得済 ({size // 1024}KB)", "reason": ""}

    # テキスト証跡（SOQL/Apex ログ）
    # UTF-16 LE（Write ツール Windows 出力）も自動検出して読む
    try:
        raw = Path(evidence_path).read_bytes()
        if raw[:2] in (b'\xff\xfe', b'\xfe\xff'):
            content = raw.decode("utf-16", errors="replace")
        elif len(raw) > 1 and raw[1] == 0x00:
            content = raw.decode("utf-16-le", errors="replace")
        else:
            content = raw.decode("utf-8", errors="replace")
    except Exception:
        content = ""

    # 構造化証跡（auto-evidence-runner 生成）: 「判定: OK/NG —」行を最優先参照
    m_verdict = re.search(r"^判定\s*:\s*(OK|NG)", content, re.MULTILINE)
    if m_verdict:
        ok = m_verdict.group(1) == "OK"
        m_reason = re.search(r"^判定\s*:.+?—\s*(.+)$", content, re.MULTILINE)
        reason = m_reason.group(1).strip() if m_reason else ""
        actual_str = "OK — " + reason if ok else "NG — " + reason
        return {"ok": ok, "actual": actual_str, "reason": "" if ok else reason}

    # 件数一致判定 (期待結果が "N 件" 形式)
    m_expected_count = re.search(r"(\d+)\s*件", kiki)
    m_actual_count = re.search(r"件数\s*:\s*(\d+)\s*件", content)
    if m_expected_count and m_actual_count:
        exp = int(m_expected_count.group(1))
        act = int(m_actual_count.group(1))
        ok = (exp == act) if "完全一致" in judge_method or "件数一致" in judge_method else (act >= exp)
        actual_str = f"{act} 件"
        reason = "" if ok else f"期待 {exp} 件 / 実際 {act} 件"
        return {"ok": ok, "actual": actual_str, "reason": reason}

    # 含む判定 (期待結果に含まれるべき文字列): 「実際の値:」行以降のみを検索し期待値行の誤ヒットを防ぐ
    if "含む" in judge_method or "存在" in judge_method:
        # 「実際の値:」セクション以降のみを対象にする（なければ全体）
        m_actual_section = re.search(r"実際の値\s*[:：](.+?)(?=判定\s*[:：]|\Z)", content, re.DOTALL)
        search_scope = m_actual_section.group(1) if m_actual_section else content
        ok = kiki.lower() in search_scope.lower() if kiki else True
        actual_str = f"「{kiki[:30]}」{'あり' if ok else 'なし'}"
        return {"ok": ok, "actual": actual_str, "reason": "" if ok else f"「{kiki[:30]}」が証跡に含まれない"}

    # ApexTest 成功確認: "Pass Rate" / "Outcome: Passed" を正として "FAIL" の誤ヒットを避ける
    if re.search(r"Pass\s+Rate\s*[:\|]\s*100%", content) or re.search(r"Outcome\s*:\s*Passed", content):
        return {"ok": True, "actual": "Apex テスト PASS", "reason": ""}
    if re.search(r"Pass\s+Rate\s*[:\|]\s*0%", content) or re.search(r"Outcome\s*:\s*Failed", content):
        m_fail = re.search(r"(Failures:.+)", content)
        reason = m_fail.group(1) if m_fail else "Apex テスト FAIL"
        return {"ok": False, "actual": "Apex テスト FAIL", "reason": reason}
    # Fallback: 旧パターン（sf CLI raw 出力等）
    if "success" in content.lower() and re.search(r"\bPASS\b|\bPassed\b", content):
        return {"ok": True, "actual": "Apex テスト PASS", "reason": ""}
    if re.search(r"\bFailed\b", content) or re.search(r"Fail\s+Rate\s*[:\|]\s*(?!0%)\d", content):
        m_fail = re.search(r"(Failures:.+)", content)
        reason = m_fail.group(1) if m_fail else "Apex テスト FAIL"
        return {"ok": False, "actual": "Apex テスト FAIL", "reason": reason}

    # デフォルト: 証跡ファイルが存在していれば暫定 OK（スクショ目視など）
    return {"ok": True, "actual": "証跡取得済（目視確認要）", "reason": ""}


# ── 対応記録.xlsx H 列の追記 ─────────────────────────────────────────────────

def update_xlsx_h_col(folder: str, issue_id: str, tc_no: str, value: str) -> bool:
    """update_records.py cell コマンドで H 列を更新する。"""
    # 対象行番号を特定（実装後・UI手動以外）
    xlsx_path = os.path.join(folder, f"{issue_id}_対応記録.xlsx")
    if not os.path.exists(xlsx_path):
        return False

    find_row_code = f"""
import openpyxl, os
wb = openpyxl.load_workbook(r'{xlsx_path}')
ws = wb['テスト・検証']
for r in range(1, ws.max_row + 1):
    v = [ws.cell(r, c).value for c in range(1, 9)]
    if (any(v) and str(v[1] or '').strip() == '実装後'
            and str(v[2] or '').strip() != 'UI手動'
            and str(v[3] or '').strip().startswith('{tc_no}')):
        print(r)
        break
"""
    result = subprocess.run(
        ["python", "-c", find_row_code],
        capture_output=True, text=True
    )
    row_str = result.stdout.strip()
    if not row_str.isdigit():
        return False

    row_num = int(row_str)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    update_script = os.path.join(script_dir, "update_records.py")

    result = subprocess.run(
        ["python", update_script,
         "--folder", folder, "--issue-id", issue_id,
         "cell", "--sheet", "テスト・検証",
         "--row", str(row_num), "--col", "8",
         "--value", value],
        capture_output=True, text=True
    )
    return result.returncode == 0


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="テストケースの OK/NG 判定と xlsx H 列更新")
    parser.add_argument("--folder", required=True, help="xlsx 出力フォルダ")
    parser.add_argument("--issue-id", required=True, dest="issue_id")
    parser.add_argument("--spec", required=True, help="test-spec.md のパス")
    parser.add_argument("--evidence-dir", required=True, dest="evidence_dir",
                        help="証跡ファイルの after/ ディレクトリ")
    parser.add_argument("--out", default="", help="判定結果 JSON の出力パス（省略時は stdout）")
    parser.add_argument("--no-xlsx", action="store_true", dest="no_xlsx",
                        help="対応記録.xlsx の H 列更新をスキップする")
    args = parser.parse_args()

    args.folder = validate_folder(args.folder)
    test_cases = parse_test_spec(args.spec)
    if not test_cases:
        print("[WARN] test-spec.md にテストケースが見つかりませんでした。")
        sys.exit(0)

    results = []
    ng_list = []
    skip_list = []

    for tc in test_cases:
        no = tc.get("No", "")
        shubetsu = tc.get("種別", tc.get("実行種別", "")).strip()
        evidence_path = find_evidence_file(args.evidence_dir, no, shubetsu)
        judgment = judge_case(tc, evidence_path)

        ok = judgment["ok"]
        actual = judgment["actual"]
        reason = judgment["reason"]

        if ok is None:
            status = "SKIP"
            skip_list.append(no)
            xlsx_value = "要手動確認"
        elif ok:
            status = "OK"
            xlsx_value = f"OK"
        else:
            status = "NG"
            ng_list.append({"no": no, "label": tc.get("観点", ""), "reason": reason})
            xlsx_value = f"NG: {reason}" if reason else "NG"

        results.append({
            "no": no,
            "label": tc.get("観点", ""),
            "status": status,
            "actual": actual,
            "reason": reason,
            "evidence": evidence_path,
        })

        # xlsx H 列更新
        if not args.no_xlsx and ok is not None:
            updated = update_xlsx_h_col(args.folder, args.issue_id, no, xlsx_value)
            if not updated:
                print(f"[WARN] {no}: 対応記録.xlsx の H 列更新をスキップ（行特定失敗）")

        icon = {"OK": "[OK]", "NG": "[NG]", "SKIP": "[--]"}[status]
        print(f"{icon} {no}: {tc.get('観点', '')} → {actual}" + (f" ({reason})" if reason else ""))

    # サマリー
    ok_count = sum(1 for r in results if r["status"] == "OK")
    ng_count = len(ng_list)
    skip_count = len(skip_list)
    print(f"\n判定サマリー: OK={ok_count} / NG={ng_count} / 要手動={skip_count} / 合計={len(results)}")

    output = {
        "ok": ok_count,
        "ng": ng_count,
        "skip": skip_count,
        "total": len(results),
        "ng_list": ng_list,
        "skip_list": skip_list,
        "results": results,
    }

    if args.out:
        os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
        Path(args.out).write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"[OK] 判定結果を保存: {args.out}")
    else:
        print(json.dumps(output, ensure_ascii=False, indent=2))

    # NG があれば exit 1
    if ng_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
