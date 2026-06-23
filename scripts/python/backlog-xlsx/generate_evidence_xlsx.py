# -*- coding: utf-8 -*-
"""backlog-xlsx / generate_evidence_xlsx.py
機械実行用エビデンス.xlsx を生成する（テスト仕様 → 実行結果の自動記入版）。

旧 create_evidence.py（人手貼付前提）の後継。
test-spec.md（9列スキーマ）を読み、コンパクト表＋証跡別シートの 2 シート構成で生成する。

Sheet 1「テスト結果」  : 1 行 = 1 ケース。実際の結果・判定（OK/NG 色分け）を自動記入。
Sheet 2「証跡」        : 各ケースの証跡（スクショ PNG / SOQL テキスト）を縦に配置し、
                          「テスト結果」シートからハイパーリンクで紐付け。
「要手動」ケースのみ旧来の「貼付枠＋指示文」を証跡シートに残す（ハイブリッド）。

Usage:
    python generate_evidence_xlsx.py \\
      --folder /path/to/xlsx_folder \\
      --issue-id GF-350 \\
      --spec /path/to/docs/logs/GF-350/test-spec.md \\
      --evidence-dir /path/to/evidence/after \\
      --judgment /path/to/judgment-result.json
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

from _common import validate_folder, _stripe_fill

try:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill, Border, Side, GradientFill
    from openpyxl.styles.differential import DifferentialStyle
    from openpyxl.formatting.rule import Rule
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.hyperlink import Hyperlink
except ImportError:
    print("[ERROR] openpyxl がインストールされていません。`pip install openpyxl` を実行してください。")
    sys.exit(1)

# Pillow は add_image に必要（PNG 読み込み）
try:
    from openpyxl.drawing.image import Image as XLImage
    _PIL_OK = True
    try:
        from PIL import Image as PILImage
    except ImportError:
        _PIL_OK = False
except ImportError:
    _PIL_OK = False

# ── スタイル定数 ─────────────────────────────────────────────────────────────
WRAP = Alignment(wrap_text=True, vertical="top")
HDR_FILL = PatternFill("solid", fgColor="1F3864")   # 濃紺ヘッダー
HDR_FONT = Font(bold=True, color="FFFFFF", name="游ゴシック", size=10)
OK_FILL  = PatternFill("solid", fgColor="C6EFCE")   # 緑
NG_FILL  = PatternFill("solid", fgColor="FFC7CE")   # 赤
MANUAL_FILL = PatternFill("solid", fgColor="FFEB9C") # 黄（要手動）
EVIDENCE_BG = PatternFill("solid", fgColor="FFF3CD") # エビデンス枠
LIGHT_BLUE  = PatternFill("solid", fgColor="D6E4F7") # サブヘッダー
WHITE  = PatternFill("solid", fgColor="FFFFFF")

THIN = Side(style="thin", color="AAAAAA")
THIN_BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)

COL_WIDTHS_RESULT = [8, 30, 12, 20, 20, 10, 20]  # No/観点/種別/期待/実際/判定/証跡リンク
COL_WIDTHS_EVIDENCE = [8, 60]


# ── パーサ ───────────────────────────────────────────────────────────────────

def parse_test_spec(spec_path: str) -> list:
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


def load_judgment(judgment_path: str) -> dict:
    """judge_results.py の出力 JSON を読む。なければ空辞書。"""
    if not judgment_path or not os.path.exists(judgment_path):
        return {}
    data = json.loads(Path(judgment_path).read_text(encoding="utf-8"))
    return {r["no"]: r for r in data.get("results", [])}


# ── 証跡ファイル探索 ─────────────────────────────────────────────────────────

def find_evidence_file(evidence_dir: str, tc_no: str, shubetsu: str) -> str:
    """後方互換: 最初の1ファイルのみ返す。"""
    files = find_evidence_files(evidence_dir, tc_no, shubetsu)
    return files[0] if files else ""


def find_evidence_files(evidence_dir: str, tc_no: str, shubetsu: str) -> list:
    """証跡ディレクトリから TC-001 に対応する全ファイルを返す（複数証跡・分岐ラベル対応）。"""
    subdir_map = {"SOQL": "soql", "ApexTest": "apex", "AnonApex": "apex",
                  "UI": "screen", "メタ確認": "meta", "ファイル確認": "meta"}
    subdir = subdir_map.get(shubetsu, "")
    search_dirs = []
    if subdir:
        search_dirs.append(os.path.join(evidence_dir, subdir))
    search_dirs.append(evidence_dir)
    found = []
    seen = set()
    for d in search_dirs:
        if not os.path.isdir(d):
            continue
        for fname in sorted(os.listdir(d)):
            # before ファイルは除外
            if "_before." in fname:
                continue
            if fname.startswith(tc_no) or fname.startswith(tc_no.replace("TC-", "tc-")):
                fpath = os.path.join(d, fname)
                if fpath not in seen:
                    seen.add(fpath)
                    found.append(fpath)
    return found


# ── テキスト証跡ヘルパー ─────────────────────────────────────────────────────

def _read_text_safe(path: str) -> str:
    """UTF-16 LE 自動検出＋制御文字除去してテキストを返す（打ち切りなし）。"""
    try:
        raw = Path(path).read_bytes()
        if raw[:2] in (b'\xff\xfe', b'\xfe\xff'):
            text = raw.decode("utf-16", errors="replace")
        elif len(raw) > 1 and raw[1] == 0x00:
            text = raw.decode("utf-16-le", errors="replace")
        else:
            text = raw.decode("utf-8", errors="replace")
    except Exception:
        text = ""
    return re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f]', '', text)


def _append_text_block(ws, path: str, start_row: int) -> int:
    """テキストファイルを ws の start_row から全行展開し、書いた行数を返す（打ち切りなし）。"""
    text = _read_text_safe(path)
    lines = text.splitlines()
    for i, line in enumerate(lines):
        c = ws.cell(row=start_row + i, column=2, value=line)
        c.font = Font(name="Courier New", size=9)
    return len(lines)


def _count_lines(path: str) -> int:
    return len(_read_text_safe(path).splitlines())


# ── Sheet 1: テスト結果 ───────────────────────────────────────────────────────

def build_result_sheet(ws, test_cases: list, judgment: dict, evidence_dir: str) -> dict:
    """テスト結果シートを構築し {tc_no: sheet2_anchor} を返す（証跡シートへのリンク用）。"""
    headers = ["No", "確認観点", "種別", "期待結果", "実際の結果", "判定", "証跡"]
    ws.title = "テスト結果"

    # ヘッダー行
    for j, h in enumerate(headers, start=1):
        c = ws.cell(row=1, column=j, value=h)
        c.fill = HDR_FILL
        c.font = HDR_FONT
        c.alignment = WRAP
        c.border = THIN_BORDER
    ws.row_dimensions[1].height = 22

    # 列幅
    for j, w in enumerate(COL_WIDTHS_RESULT, start=1):
        ws.column_dimensions[get_column_letter(j)].width = w

    tc_to_row = {}
    for i, tc in enumerate(test_cases):
        row = i + 2
        no = tc.get("No", "")
        shubetsu = tc.get("種別", "")
        kiki = tc.get("期待結果", "")
        auto = tc.get("自動化可否", "自動").strip()
        is_manual = "要手動" in auto

        # 判定結果から実際の結果・ステータスを取得
        j_result = judgment.get(no, {})
        actual = j_result.get("actual", "")
        status = j_result.get("status", "SKIP" if is_manual else "")

        # 判定セルの表示と色
        if status == "OK":
            judge_text = "✅ OK"
            row_fill = OK_FILL
        elif status == "NG":
            judge_text = "❌ NG"
            row_fill = NG_FILL
        else:
            judge_text = "⬜ 要手動"
            row_fill = MANUAL_FILL

        fill = _stripe_fill(i) if status == "OK" else row_fill

        vals = [no, tc.get("観点", ""), shubetsu, kiki, actual, judge_text, "→証跡"]
        for j_col, val in enumerate(vals, start=1):
            c = ws.cell(row=row, column=j_col, value=val)
            c.alignment = WRAP
            c.border = THIN_BORDER
            if j_col == 6:  # 判定列は個別の色
                c.fill = row_fill
                c.font = Font(bold=True, name="游ゴシック", size=10)
            else:
                c.fill = fill

        ws.row_dimensions[row].height = 40
        tc_to_row[no] = row

    return tc_to_row


# ── Sheet 2: 証跡 ────────────────────────────────────────────────────────────

def build_evidence_sheet(ws, test_cases: list, judgment: dict, evidence_dir: str, tc_to_row: dict) -> None:
    """証跡シートを構築し、テスト結果シートの証跡列にハイパーリンクを設定する。"""
    ws.title = "証跡"

    headers = ["No", "証跡内容"]
    for j, h in enumerate(headers, start=1):
        c = ws.cell(row=1, column=j, value=h)
        c.fill = HDR_FILL
        c.font = HDR_FONT
        c.alignment = WRAP
        c.border = THIN_BORDER
    for j, w in enumerate(COL_WIDTHS_EVIDENCE, start=1):
        ws.column_dimensions[get_column_letter(j)].width = w

    row_ptr = 2
    result_ws_name = "テスト結果"

    for tc in test_cases:
        no = tc.get("No", "")
        shubetsu = tc.get("種別", "")
        auto = tc.get("自動化可否", "自動").strip()
        is_manual = "要手動" in auto

        # 複数証跡ファイルを全件取得
        all_evidence = find_evidence_files(evidence_dir, no, shubetsu)

        # TC セクションヘッダー
        ws.merge_cells(start_row=row_ptr, start_column=1, end_row=row_ptr, end_column=2)
        hdr = ws.cell(row=row_ptr, column=1,
                      value=f"■ {no}: {tc.get('観点', '')} （{shubetsu}）")
        hdr.fill = LIGHT_BLUE
        hdr.font = Font(bold=True, name="游ゴシック", size=10)
        hdr.alignment = WRAP
        anchor_cell_addr = f"A{row_ptr}"
        row_ptr += 1

        if is_manual:
            # 要手動: 貼付枠を残す
            ws.merge_cells(start_row=row_ptr, start_column=1, end_row=row_ptr, end_column=2)
            c = ws.cell(row=row_ptr, column=1,
                        value="⬜ 要手動確認 — ユーザーがここにスクリーンショットを貼り付けてください")
            c.fill = EVIDENCE_BG
            c.alignment = WRAP
            row_ptr += 1
            paste_top = row_ptr
            paste_bottom = paste_top + 9
            for r in range(paste_top, paste_bottom + 1):
                for col in range(1, 3):
                    ws.cell(r, col).fill = WHITE
            ws.merge_cells(start_row=paste_top, start_column=1, end_row=paste_bottom, end_column=2)
            ws.cell(paste_top, 1, "（スクリーンショット貼付エリア）").alignment = WRAP
            row_ptr = paste_bottom + 2

        elif not all_evidence:
            ws.cell(row_ptr, 2, "（証跡ファイルなし）").alignment = WRAP
            row_ptr += 2

        else:
            # 証跡ファイルを1ファイル1ブロックで展開（PNG は before 除く / txt は DOM 含む）
            # PNG + 同名 txt のペアは PNG -> txt の順で同一ブロックに入れる
            processed = set()
            for ep in all_evidence:
                if ep in processed:
                    continue
                processed.add(ep)
                fname = os.path.basename(ep)

                # ブロック小見出し（複数ある場合のみ）
                if len(all_evidence) > 1:
                    ws.merge_cells(start_row=row_ptr, start_column=1, end_row=row_ptr, end_column=2)
                    sub_hdr = ws.cell(row=row_ptr, column=1, value=f"  └ {fname}")
                    sub_hdr.font = Font(italic=True, name="游ゴシック", size=9)
                    sub_hdr.alignment = WRAP
                    row_ptr += 1

                if ep.lower().endswith(".png") and _PIL_OK:
                    # PNG: 自動貼付
                    try:
                        pil_img = PILImage.open(ep)
                        max_w = 800
                        w, h = pil_img.size
                        if w > max_w:
                            ratio = max_w / w
                            pil_img = pil_img.resize((int(w * ratio), int(h * ratio)), PILImage.LANCZOS)
                            resized_path = ep.replace(".png", "_resized.png")
                            pil_img.save(resized_path)
                            ep_use = resized_path
                        else:
                            ep_use = ep
                        xl_img = XLImage(ep_use)
                        xl_img.anchor = f"B{row_ptr}"
                        ws.add_image(xl_img)
                        img_rows = max(10, int(pil_img.size[1] / 18) + 2)
                        # 行高は変更しない（デフォルト高さ行を img_rows 分送るだけで画像は上に浮く）
                        row_ptr += img_rows + 1
                    except Exception as e:
                        ws.cell(row_ptr, 2, f"[WARN] 画像読込失敗: {e}").alignment = WRAP
                        row_ptr += 2

                    # 同名 DOM スナップショット (.txt) を連続して展開
                    snap_path = re.sub(r'\.png$', '.txt', ep, flags=re.IGNORECASE)
                    if os.path.exists(snap_path) and snap_path not in processed:
                        processed.add(snap_path)
                        _append_text_block(ws, snap_path, row_ptr)
                        row_ptr += _count_lines(snap_path) + 1

                elif ep.lower().endswith(".png") and not _PIL_OK:
                    ws.cell(row_ptr, 2, f"[PNG] {fname} — Pillow 未インストールのため未貼付").alignment = WRAP
                    row_ptr += 2

                else:
                    # テキスト証跡: 全行展開（打ち切りなし）
                    n = _append_text_block(ws, ep, row_ptr)
                    row_ptr += n + 1

        # 証跡シート先頭アドレスをメモ（後でリンク設定）
        tc_to_row[no + "_ev"] = anchor_cell_addr


# ── ハイパーリンク設定 ────────────────────────────────────────────────────────

def set_hyperlinks(result_ws, evidence_ws_name: str, tc_to_row: dict, test_cases: list) -> None:
    """テスト結果シートの「証跡」列から証跡シートへの内部ハイパーリンクを設定。"""
    for tc in test_cases:
        no = tc.get("No", "")
        result_row = tc_to_row.get(no)
        ev_addr = tc_to_row.get(no + "_ev", "A2")
        if not result_row:
            continue
        cell = result_ws.cell(row=result_row, column=7)
        cell.hyperlink = f"#{evidence_ws_name}!{ev_addr}"
        cell.font = Font(color="0563C1", underline="single", name="游ゴシック", size=10)
        cell.value = "→ 証跡を見る"


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="機械記入用エビデンス.xlsx を生成する")
    parser.add_argument("--folder",       required=True, help="xlsx 出力フォルダ")
    parser.add_argument("--issue-id",     required=True, dest="issue_id")
    parser.add_argument("--spec",         required=True, help="test-spec.md のパス")
    parser.add_argument("--evidence-dir", required=True, dest="evidence_dir",
                        help="証跡ファイルの after/ ディレクトリ")
    parser.add_argument("--judgment",     default="",    help="judge_results.py 出力 JSON のパス")
    args = parser.parse_args()

    args.folder = validate_folder(args.folder)
    if not _PIL_OK:
        print("[WARN] Pillow がインストールされていません。PNG の自動貼付をスキップします。")
        print("       `pip install Pillow` でインストールするとスクショが自動貼付されます。")

    test_cases = parse_test_spec(args.spec)
    if not test_cases:
        print("[WARN] test-spec.md にテストケースが見つかりませんでした。空のエビデンスファイルを生成します。")

    judgment = load_judgment(args.judgment)

    wb = Workbook()
    result_ws   = wb.active
    evidence_ws = wb.create_sheet("証跡")

    tc_to_row = build_result_sheet(result_ws, test_cases, judgment, args.evidence_dir)
    build_evidence_sheet(evidence_ws, test_cases, judgment, args.evidence_dir, tc_to_row)
    set_hyperlinks(result_ws, "証跡", tc_to_row, test_cases)

    # ウィンドウ固定（ヘッダー行）
    result_ws.freeze_panes = "A2"
    evidence_ws.freeze_panes = "A2"

    out_path = os.path.join(args.folder, f"{args.issue_id}_エビデンス.xlsx")
    os.makedirs(args.folder, exist_ok=True)
    try:
        wb.save(out_path)
    except PermissionError as e:
        print(f"[ERROR] xlsx の保存失敗（ファイルが開かれている可能性）: {out_path}\n{e}")
        sys.exit(1)

    ok_count = sum(1 for r in judgment.values() if r.get("status") == "OK")
    ng_count = sum(1 for r in judgment.values() if r.get("status") == "NG")
    skip_count = sum(1 for r in judgment.values() if r.get("status") == "SKIP")

    print(f"生成完了: {out_path}")
    print(f"  テストケース: {len(test_cases)} 件 (OK={ok_count} / NG={ng_count} / 要手動={skip_count})")
    if not _PIL_OK:
        print("  ※ Pillow 未インストールのため PNG 自動貼付はスキップ。手動で貼り付けてください。")


if __name__ == "__main__":
    main()
