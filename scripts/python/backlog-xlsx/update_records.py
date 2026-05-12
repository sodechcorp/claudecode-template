# -*- coding: utf-8 -*-
"""
backlog-xlsx / update_records.py
対応記録.xlsx を更新するスクリプト

Usage (タイムライン行を追加):
    python update_records.py --folder FOLDER --issue-id ID timeline \
      --phase "調査" --source "Claude" --content "〇〇を調査: 原因は△△"

Usage (セルを直接更新):
    python update_records.py --folder FOLDER --issue-id ID cell \
      --sheet "対応方針" --row 10 --col 1 --value "採用理由の説明"
"""

import argparse
import datetime
import os
import re
import sys

try:
    import openpyxl
    from openpyxl.styles import Alignment, PatternFill
except ImportError:
    print("[ERROR] openpyxl がインストールされていません。`pip install openpyxl` を実行してください。")
    sys.exit(1)

WRAP = Alignment(wrap_text=True, vertical="top")
_STRIPE_A_RGB = "FFFFFF"  # 奇数行
_STRIPE_B_RGB = "F2F7FB"  # 偶数行（薄青）


def _stripe_fill(no):
    """1-indexed の行番号 no に対応する stripe PatternFill を毎回 fresh に生成して返す。
    openpyxl の style index aliasing バグ（singleton を使うと白代入が青セルで silent no-op になる）を回避する。
    """
    rgb = _STRIPE_A_RGB if no % 2 == 1 else _STRIPE_B_RGB
    return PatternFill("solid", fgColor=rgb)


def find_next_empty_row(ws, col=1, start_row=1):
    """指定列で最初の空行を返す（start_row から下方向に検索）"""
    r = start_row
    while ws.cell(row=r, column=col).value is not None:
        r += 1
    return r


def cmd_timeline(args, wb):
    """サマリー・経緯シートのタイムラインに1行追加する"""
    sheet_name = "サマリー・経緯"
    if sheet_name not in wb.sheetnames:
        print(f"[ERROR] シート '{sheet_name}' が見つかりません。")
        sys.exit(1)
    ws = wb[sheet_name]

    # タイムラインヘッダー行を探す（"No" がある行）
    timeline_header_row = None
    for row in ws.iter_rows():
        for cell in row:
            if cell.value == "No":
                timeline_header_row = cell.row
                break
        if timeline_header_row:
            break

    if not timeline_header_row:
        print("[ERROR] タイムラインのヘッダー行（'No' セル）が見つかりません。")
        sys.exit(1)

    data_start = timeline_header_row + 1
    next_row = find_next_empty_row(ws, col=1, start_row=data_start)

    # No 列は現在の行数から算出
    no = next_row - data_start + 1
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    fill = _stripe_fill(no)

    for col, value in enumerate([no, now, args.source, args.phase, args.content, args.reason or ""], start=1):
        cell = ws.cell(row=next_row, column=col, value=value)
        cell.alignment = WRAP
        cell.fill = fill

    print(f"タイムライン追加: 行{next_row} / {now} / {args.phase} / {args.content[:30]}...")


def cmd_cell(args, wb):
    """指定したシート・行・列のセルを更新する"""
    if args.sheet not in wb.sheetnames:
        print(f"[ERROR] シート '{args.sheet}' が見つかりません。利用可能: {wb.sheetnames}")
        sys.exit(1)
    ws = wb[args.sheet]
    ws.cell(row=args.row, column=args.col, value=args.value).alignment = WRAP
    print(f"セル更新: {args.sheet}!({args.row},{args.col}) = {args.value[:40]}...")


def _extract_validation_summary(text):
    """validation-report.md から実装前検証の概要サマリー文字列を抽出する。"""
    # Step 2 の判定行を探す
    step2_match = re.search(
        r"## Step 2[：:][^\n]*\n(.*?)(?=\n## |\Z)", text, re.DOTALL
    )
    if step2_match:
        step2_body = step2_match.group(1)
        # PASS 率・カバレッジ行を探す
        pass_lines = []
        for ln in step2_body.splitlines():
            ln = ln.strip()
            if re.search(r"Pass Rate|PASS|カバレッジ|Coverage|判定", ln, re.IGNORECASE):
                clean = re.sub(r"\*+", "", ln).strip()
                if clean and not clean.startswith("|"):
                    pass_lines.append(clean[:80])
        if pass_lines:
            return "実装前確認済み（" + " / ".join(pass_lines[:2]) + "）"

    # 総合判定を探す
    verdict_match = re.search(r"## 総合判定\n+\*+([^\n*]+)\*+", text)
    if verdict_match:
        return f"実装前確認済み: {verdict_match.group(1).strip()}"

    return "実装前確認済み（validation-report.md 参照）"


def cmd_test_precheck(args, wb):
    """validation-report.md の確認結果をテスト・検証記録シートの「実装前」行に反映する。"""
    sheet_name = "テスト・検証記録"
    if sheet_name not in wb.sheetnames:
        print(f"[ERROR] シート '{sheet_name}' が見つかりません。")
        sys.exit(1)

    if not os.path.exists(args.report):
        print(f"[ERROR] validation-report.md が見つかりません: {args.report}")
        sys.exit(1)

    with open(args.report, encoding="utf-8") as f:
        validation_text = f.read()

    summary = _extract_validation_summary(validation_text)
    ws = wb[sheet_name]

    # ヘッダー行（No / タイミング 列が並ぶ行）を探す
    header_row = None
    for row in ws.iter_rows(min_row=1, max_row=30):
        for cell in row:
            if cell.value == "No":
                next_cell = ws.cell(cell.row, cell.column + 1)
                if next_cell.value in ("タイミング", "区分", "確認観点"):
                    header_row = cell.row
                    break
        if header_row:
            break

    if not header_row:
        print("[WARN] テスト・検証記録シートのヘッダー行が見つかりませんでした。")
        return

    updated = 0
    for r in range(header_row + 1, header_row + 100):
        no_val = ws.cell(r, 1).value
        timing_val = ws.cell(r, 2).value
        if no_val is None and timing_val is None:
            break  # データ終端
        if str(timing_val or "").strip() == "実装前":
            result_cell = ws.cell(r, 6)
            verdict_cell = ws.cell(r, 7)
            if not result_cell.value:  # 既入力の場合は上書きしない
                result_cell.value = summary
                result_cell.alignment = WRAP
                fill = _stripe_fill(updated + 1)
                result_cell.fill = fill
            if not verdict_cell.value:
                verdict_cell.value = "OK"
                verdict_cell.alignment = WRAP
            updated += 1

    print(f"[OK] 実装前テスト行 {updated} 件に validation-report.md の結果を反映しました")


def main():
    parser = argparse.ArgumentParser(description="対応記録.xlsx を更新する")
    parser.add_argument("--folder",   required=True, help="保存先フォルダパス")
    parser.add_argument("--issue-id", required=True, dest="issue_id", help="課題ID (例: GF-327)")

    sub = parser.add_subparsers(dest="command", required=True)

    # タイムライン追加サブコマンド
    p_tl = sub.add_parser("timeline", help="タイムラインに行を追加する")
    p_tl.add_argument("--phase",   required=True, help="フェーズ名 (例: 調査, 実装, テスト)")
    p_tl.add_argument("--source",  default="Claude", help="発生元 (例: Claude, ユーザ)")
    p_tl.add_argument("--content", required=True, help="内容・決定事項")
    p_tl.add_argument("--reason",  default="", help="変更・判断の理由（任意）")

    # セル直接更新サブコマンド
    p_cell = sub.add_parser("cell", help="特定セルを直接更新する")
    p_cell.add_argument("--sheet", required=True, help="シート名")
    p_cell.add_argument("--row",   required=True, type=int, help="行番号")
    p_cell.add_argument("--col",   required=True, type=int, help="列番号")
    p_cell.add_argument("--value", required=True, help="書き込む値")

    # テスト実装前結果反映サブコマンド
    p_precheck = sub.add_parser("test-precheck", help="validation-report.md の実装前確認結果をテスト行に反映する")
    p_precheck.add_argument("--report", required=True, help="validation-report.md のパス")

    args = parser.parse_args()

    xlsx_path = os.path.join(args.folder, f"{args.issue_id}_対応記録.xlsx")
    if not os.path.exists(xlsx_path):
        print(f"[ERROR] ファイルが見つかりません: {xlsx_path}")
        sys.exit(1)

    try:
        wb = openpyxl.load_workbook(xlsx_path)
    except Exception as e:
        print(f"[ERROR] xlsx の読み込みに失敗しました: {xlsx_path}\n{e}")
        sys.exit(1)

    if args.command == "timeline":
        cmd_timeline(args, wb)
    elif args.command == "cell":
        cmd_cell(args, wb)
    elif args.command == "test-precheck":
        cmd_test_precheck(args, wb)

    try:
        wb.save(xlsx_path)
    except PermissionError as e:
        print(f"[ERROR] xlsx の保存に失敗しました（ファイルが開かれている可能性があります）: {xlsx_path}\n{e}")
        sys.exit(1)
    print(f"保存完了: {xlsx_path}")


if __name__ == "__main__":
    main()
