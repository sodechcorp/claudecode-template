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
from collections import Counter
from pathlib import Path

from _common import (
    validate_folder, _stripe_fill,
    _font, _align, _thin_border, _thin_side,
    _set_row_height, _set_col_width, _freeze,
    _auto_col_width, _row_height_by_lines,
)

try:
    from openpyxl import Workbook
    from openpyxl.styles import PatternFill, Font, Border, Side
    from openpyxl.utils import get_column_letter
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
HDR_FILL    = PatternFill("solid", fgColor="1F3864")   # 濃紺ヘッダー
HDR_FONT    = _font(fg="FFFFFF", bold=True, size=10)
OK_FILL     = PatternFill("solid", fgColor="C6EFCE")   # 緑
NG_FILL     = PatternFill("solid", fgColor="FFC7CE")   # 赤
MANUAL_FILL = PatternFill("solid", fgColor="FFEB9C")   # 黄（要手動）
EVIDENCE_BG = PatternFill("solid", fgColor="FFF3CD")   # エビデンス枠
LIGHT_BLUE  = PatternFill("solid", fgColor="D6E4F7")   # サブヘッダー
WHITE       = PatternFill("solid", fgColor="FFFFFF")

THIN_BORDER = _thin_border("AAAAAA")
WRAP        = _align("left", "top", wrap=True)
CENTER_MID  = _align("center", "center", wrap=False)

# 列幅初期値（auto-fit の下限として機能）
_MIN_COL_WIDTHS_RESULT   = [8, 8, 18, 12, 18, 18, 10, 24, 14]   # No/対応要求/観点/種別/期待/実際/判定/NG原因/証跡リンク
_MIN_COL_WIDTHS_EVIDENCE = [8, 58]

# 印刷設定
_PAPER_SIZE   = 9   # A4
_ORIENTATION  = "landscape"
_MARGIN_CM    = 0.8  # 上下左右余白 cm（openpyxl は inch 単位）
_CM_PER_INCH  = 2.54


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

def _tc_normalize(tc_str: str) -> int:
    """TC番号文字列から数値部を抽出（桁差を吸収: TC-004 / TC-04 / TC-4 → 4）。"""
    m = re.match(r'(?:[Tt][Cc])-0*(\d+)', tc_str.strip())
    return int(m.group(1)) if m else -1


def find_evidence_file(evidence_dir: str, tc_no: str, shubetsu: str, judgment: dict = None) -> str:
    """後方互換: 最初の1ファイルのみ返す。"""
    files = find_evidence_files(evidence_dir, tc_no, shubetsu, judgment)
    return files[0] if files else ""


def find_evidence_files(evidence_dir: str, tc_no: str, shubetsu: str, judgment: dict = None) -> list:
    """証跡ディレクトリから TC 番号に対応する全ファイルを返す。
    優先順:
      ① judgment-result.json の evidence パス（検証済み正本・絶対パスで直参照）
      ② os.walk 再帰探索（複合種別・before/after サブディレクトリ・桁差 TC-04 vs TC-004 対応）
    before ファイル（"_before." を含む）は除外。
    """
    found = []
    seen = set()

    # ① judgment の evidence パスを最優先（正本が既にある場合は即採用）
    if judgment is not None:
        ev_path = judgment.get(tc_no, {}).get("evidence", "")
        if ev_path and os.path.isfile(ev_path) and ev_path not in seen:
            seen.add(ev_path)
            found.append(ev_path)

    # ② os.walk 再帰探索（TC番号正規化で桁差・複合種別・サブディレクトリを吸収）
    tc_num = _tc_normalize(tc_no)
    if tc_num >= 0 and os.path.isdir(evidence_dir):
        for dirpath, _dirs, filenames in os.walk(evidence_dir):
            for fname in sorted(filenames):
                # before / リサイズ済みサムネイルは対象外
                if "_before." in fname or "_resized." in fname:
                    continue
                fpath = os.path.join(dirpath, fname)
                if fpath in seen:
                    continue
                # ファイル名先頭の "TC-NNN" 部分を抽出して TC番号と比較
                fname_prefix = fname.split("_")[0]  # "TC-001" / "TC-04" / "tc-4"
                if _tc_normalize(fname_prefix) == tc_num:
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
        # "=" 始まりの行は openpyxl が数式セルとして書き出し Excel 修復ダイアログが出る
        safe = (" " + line) if line.startswith("=") else line
        c = ws.cell(row=start_row + i, column=2, value=safe)
        c.font = Font(name="Courier New", size=9)
        c.border = THIN_BORDER
        c.alignment = _align("left", "top", wrap=True)
    return len(lines)


def _count_lines(path: str) -> int:
    return len(_read_text_safe(path).splitlines())


# ── 結果シートヘルパー ────────────────────────────────────────────────────────

def _extract_req_label(kanpoin: str) -> str:
    """観点テキストから要求ラベル（①②③ / 回帰）を抽出する。"""
    m = re.match(r'^([①②③④⑤⑥⑦⑧⑨⑩]+)', kanpoin.strip())
    if m:
        return m.group(1)
    if "回帰" in kanpoin:
        return "回帰"
    return ""


def _build_ng_action(j_result: dict) -> str:
    """NG判定結果からユーザー向けのアクション文を生成する（NG原因/次アクション列）。"""
    reason = j_result.get("reason", "")
    ng_type = j_result.get("ng_type", "")
    if ng_type == "未実行":
        return "再テスト要" + (f": {reason}" if reason else "（証跡なし）")
    if ng_type == "要確認":
        return "判定方法修正要" + (f": {reason}" if reason else "")
    return reason or "要確認"


# ── Sheet 1: テスト結果 ───────────────────────────────────────────────────────

def build_result_sheet(ws, test_cases: list, judgment: dict, evidence_dir: str) -> dict:
    """テスト結果シートを構築し {tc_no: sheet2_anchor} を返す（証跡シートへのリンク用）。"""
    headers = ["No", "対応要求", "確認観点", "種別", "期待結果", "実際の結果", "判定", "NG原因/次アクション", "証跡"]
    ws.title = "テスト結果"

    # ヘッダー行
    for j, h in enumerate(headers, start=1):
        c = ws.cell(row=1, column=j, value=h)
        c.fill = HDR_FILL
        c.font = HDR_FONT
        c.alignment = CENTER_MID
        c.border = THIN_BORDER
    _set_row_height(ws, 1, 22)

    # 列幅初期値を設定（auto-fit の下限）
    for j, w in enumerate(_MIN_COL_WIDTHS_RESULT, start=1):
        _set_col_width(ws, j, w)

    tc_to_row = {}
    for i, tc in enumerate(test_cases):
        row = i + 2
        no = tc.get("No", "")
        shubetsu = tc.get("種別", "")
        kanpoin = tc.get("観点", "")
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

        req_label = _extract_req_label(kanpoin)
        ng_action = _build_ng_action(j_result) if status == "NG" else ""
        vals = [no, req_label, kanpoin, shubetsu, kiki, actual, judge_text, ng_action, "→証跡"]
        for j_col, val in enumerate(vals, start=1):
            c = ws.cell(row=row, column=j_col, value=val)
            c.border = THIN_BORDER
            if j_col == 1:
                # No 列: 中央揃え・游ゴシック
                c.alignment = CENTER_MID
                c.font = _font(bold=True)
                c.fill = fill
            elif j_col == 2:
                # 対応要求列: 中央揃え・小さめフォント
                c.alignment = CENTER_MID
                c.font = _font(bold=True, size=9)
                c.fill = fill
            elif j_col == 7:
                # 判定列: 中央揃え・太字
                c.alignment = CENTER_MID
                c.fill = row_fill
                c.font = _font(bold=True)
            elif j_col == 8:
                # NG原因/次アクション列: NG のみ赤背景
                c.alignment = WRAP
                c.font = _font(size=9)
                c.fill = row_fill if status == "NG" else fill
            else:
                c.alignment = WRAP
                c.font = _font()
                c.fill = fill

        # 行高: 実際の結果が長い場合に折り返し分を確保（下限 30pt）
        h = max(30.0, _row_height_by_lines(actual, col_width=18))
        _set_row_height(ws, row, h)
        tc_to_row[no] = row

    # 観点・期待結果・実際の結果列は内容に応じて幅を自動調整（列番号が1シフト）
    for col_idx in [3, 5, 6]:  # 確認観点, 期待結果, 実際の結果
        _auto_col_width(ws, col_idx, min_w=_MIN_COL_WIDTHS_RESULT[col_idx - 1], max_w=40)

    # ── 要件カバレッジ・サマリー（末尾に追記）──────────────────────────────
    req_count: Counter = Counter()
    req_ok: Counter = Counter()
    req_ng: Counter = Counter()
    for tc in test_cases:
        lbl = _extract_req_label(tc.get("観点", "")) or "その他"
        j_r = judgment.get(tc.get("No", ""), {})
        st = j_r.get("status", "")
        req_count[lbl] += 1
        if st == "OK":
            req_ok[lbl] += 1
        elif st == "NG":
            req_ng[lbl] += 1
    summary_parts = []
    for lbl in sorted(req_count.keys()):
        n = req_count[lbl]
        ok_ = req_ok.get(lbl, 0)
        ng_ = req_ng.get(lbl, 0)
        summary_parts.append(f"{lbl}: {n}TC (OK={ok_}/NG={ng_})")
    summary_row = len(test_cases) + 3  # ヘッダー行 + データ行数 + 空白行1
    ncols = len(headers)
    ws.merge_cells(start_row=summary_row, start_column=1, end_row=summary_row, end_column=ncols)
    sc = ws.cell(row=summary_row, column=1,
                 value="■ 要件カバレッジ: " + " | ".join(summary_parts))
    sc.fill = LIGHT_BLUE
    sc.font = _font(bold=True, size=9)
    sc.alignment = _align("left", "center")
    sc.border = THIN_BORDER
    _set_row_height(ws, summary_row, 20)

    _freeze(ws, 2)

    # 印刷設定
    ws.page_setup.paperSize = _PAPER_SIZE
    ws.page_setup.orientation = _ORIENTATION
    ws.page_setup.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    margin_inch = _MARGIN_CM / _CM_PER_INCH
    ws.page_margins.top    = margin_inch
    ws.page_margins.bottom = margin_inch
    ws.page_margins.left   = margin_inch
    ws.page_margins.right  = margin_inch
    ws.print_title_rows = "1:1"  # ヘッダー行を全ページに繰り返し

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
        c.alignment = CENTER_MID
        c.border = THIN_BORDER
    for j, w in enumerate(_MIN_COL_WIDTHS_EVIDENCE, start=1):
        _set_col_width(ws, j, w)
    _set_row_height(ws, 1, 22)

    row_ptr = 2
    result_ws_name = "テスト結果"

    for tc in test_cases:
        no = tc.get("No", "")
        shubetsu = tc.get("種別", "")
        auto = tc.get("自動化可否", "自動").strip()
        is_manual = "要手動" in auto

        # 複数証跡ファイルを全件取得（judgment 正本→再帰探索の二段構え）
        all_evidence = find_evidence_files(evidence_dir, no, shubetsu, judgment)

        # TC セクションヘッダー
        ws.merge_cells(start_row=row_ptr, start_column=1, end_row=row_ptr, end_column=2)
        hdr = ws.cell(row=row_ptr, column=1,
                      value=f"■ {no}: {tc.get('観点', '')} （{shubetsu}）")
        hdr.fill = LIGHT_BLUE
        hdr.font = _font(bold=True, size=10)
        hdr.alignment = WRAP
        hdr.border = THIN_BORDER
        anchor_cell_addr = f"A{row_ptr}"
        _set_row_height(ws, row_ptr, 20)
        row_ptr += 1

        if is_manual:
            # 要手動: 貼付枠を残す
            ws.merge_cells(start_row=row_ptr, start_column=1, end_row=row_ptr, end_column=2)
            c = ws.cell(row=row_ptr, column=1,
                        value="⬜ 要手動確認 — ユーザーがここにスクリーンショットを貼り付けてください")
            c.fill = EVIDENCE_BG
            c.font = _font()
            c.alignment = WRAP
            c.border = THIN_BORDER
            row_ptr += 1
            paste_top = row_ptr
            paste_bottom = paste_top + 9
            for r in range(paste_top, paste_bottom + 1):
                for col in range(1, 3):
                    cell = ws.cell(r, col)
                    cell.fill = WHITE
                    cell.border = THIN_BORDER
            ws.merge_cells(start_row=paste_top, start_column=1, end_row=paste_bottom, end_column=2)
            inst = ws.cell(paste_top, 1, "（スクリーンショット貼付エリア）")
            inst.alignment = _align("center", "center", wrap=False)
            inst.font = _font(fg="888888", italic=True)
            row_ptr = paste_bottom + 2

        elif not all_evidence:
            c = ws.cell(row_ptr, 2, "（証跡ファイルなし）")
            c.alignment = WRAP
            c.font = _font(fg="888888", italic=True)
            c.border = THIN_BORDER
            c1 = ws.cell(row_ptr, 1)
            c1.border = THIN_BORDER
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
                    sub_hdr.font = _font(italic=True, size=9, fg="444444")
                    sub_hdr.alignment = WRAP
                    sub_hdr.border = THIN_BORDER
                    _set_row_height(ws, row_ptr, 16)
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
                        disp_w, disp_h = pil_img.size  # 実際に貼り付ける表示サイズ（px）
                        xl_img = XLImage(ep_use)
                        xl_img.width  = disp_w          # DPIメタデータを無視し表示サイズを固定
                        xl_img.height = disp_h
                        xl_img.anchor = f"B{row_ptr}"
                        ws.add_image(xl_img)
                        # 行高を 15pt (≒20px@96dpi) に固定し、画像が占める行数を決定論的に算出
                        ROW_PX = 20
                        img_rows = max(10, (disp_h + ROW_PX - 1) // ROW_PX + 2)  # ceil + 余白2行
                        for r in range(row_ptr, row_ptr + img_rows):
                            _set_row_height(ws, r, 15)  # 15pt = 20px 固定
                            ws.cell(r, 1).border = THIN_BORDER
                            ws.cell(r, 2).border = THIN_BORDER
                        row_ptr += img_rows + 1
                    except Exception as e:
                        c = ws.cell(row_ptr, 2, f"[WARN] 画像読込失敗: {e}")
                        c.alignment = WRAP
                        c.font = _font(fg="CC0000")
                        c.border = THIN_BORDER
                        ws.cell(row_ptr, 1).border = THIN_BORDER
                        row_ptr += 2

                    # 同名 DOM スナップショット (.txt) を連続して展開
                    snap_path = re.sub(r'\.png$', '.txt', ep, flags=re.IGNORECASE)
                    if os.path.exists(snap_path) and snap_path not in processed:
                        processed.add(snap_path)
                        _append_text_block(ws, snap_path, row_ptr)
                        row_ptr += _count_lines(snap_path) + 1

                elif ep.lower().endswith(".png") and not _PIL_OK:
                    c = ws.cell(row_ptr, 2, f"[PNG] {fname} — Pillow 未インストールのため未貼付")
                    c.alignment = WRAP
                    c.font = _font(fg="888888")
                    c.border = THIN_BORDER
                    ws.cell(row_ptr, 1).border = THIN_BORDER
                    row_ptr += 2

                else:
                    # テキスト証跡: 全行展開（打ち切りなし）
                    n = _append_text_block(ws, ep, row_ptr)
                    ws.cell(row_ptr, 1).border = THIN_BORDER
                    row_ptr += n + 1

        # 証跡シート先頭アドレスをメモ（後でリンク設定）
        tc_to_row[no + "_ev"] = anchor_cell_addr

    _freeze(ws, 2)

    # 印刷設定
    ws.page_setup.paperSize = _PAPER_SIZE
    ws.page_setup.orientation = _ORIENTATION
    ws.page_setup.fitToPage = True
    ws.page_setup.fitToWidth = 1
    ws.page_setup.fitToHeight = 0
    margin_inch = _MARGIN_CM / _CM_PER_INCH
    ws.page_margins.top    = margin_inch
    ws.page_margins.bottom = margin_inch
    ws.page_margins.left   = margin_inch
    ws.page_margins.right  = margin_inch
    ws.print_title_rows = "1:1"  # ヘッダー行を全ページに繰り返し


# ── ハイパーリンク設定 ────────────────────────────────────────────────────────

def set_hyperlinks(result_ws, evidence_ws_name: str, tc_to_row: dict, test_cases: list) -> None:
    """テスト結果シートの「証跡」列から証跡シートへの内部ハイパーリンクを設定。"""
    for tc in test_cases:
        no = tc.get("No", "")
        result_row = tc_to_row.get(no)
        ev_addr = tc_to_row.get(no + "_ev", "A2")
        if not result_row:
            continue
        cell = result_ws.cell(row=result_row, column=9)  # 証跡列（列追加後は9列目）
        cell.hyperlink = f"#{evidence_ws_name}!{ev_addr}"
        cell.font = _font(color="0563C1", underline="single")
        cell.value = "→ 証跡を見る"
        cell.alignment = CENTER_MID


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

    out_path = os.path.join(args.folder, f"{args.issue_id}_エビデンス.xlsx")
    os.makedirs(args.folder, exist_ok=True)
    try:
        wb.save(out_path)
    except PermissionError as e:
        print(f"[ERROR] xlsx の保存失敗（ファイルが開かれている可能性）: {out_path}\n{e}")
        sys.exit(1)

    ok_count   = sum(1 for r in judgment.values() if r.get("status") == "OK")
    ng_count   = sum(1 for r in judgment.values() if r.get("status") == "NG")
    skip_count = sum(1 for r in judgment.values() if r.get("status") == "SKIP")

    print(f"生成完了: {out_path}")
    print(f"  テストケース: {len(test_cases)} 件 (OK={ok_count} / NG={ng_count} / 要手動={skip_count})")
    if not _PIL_OK:
        print("  ※ Pillow 未インストールのため PNG 自動貼付はスキップ。手動で貼り付けてください。")


if __name__ == "__main__":
    main()
