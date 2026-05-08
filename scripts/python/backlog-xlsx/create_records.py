# -*- coding: utf-8 -*-
"""backlog-xlsx / create_records.py
対応記録.xlsx を生成する（Phase 3 完了直後に MD3点を読んで全シート埋め）

Usage:
    python create_records.py \\
      --folder FOLDER --issue-id ID \\
      --investigation PATH \\
      --approach-plan PATH \\
      --implementation-plan PATH
"""

import argparse
import copy
import datetime
import os
import re
import sys
from pathlib import Path

try:
    from openpyxl import load_workbook
    from openpyxl.styles import Alignment, PatternFill
    from openpyxl.utils import get_column_letter
except ImportError:
    print("[ERROR] openpyxl がインストールされていません。`pip install openpyxl` を実行してください。")
    sys.exit(1)

TEMPLATE = Path(__file__).parent / "対応記録テンプレート.xlsx"
WRAP = Alignment(wrap_text=True, vertical="top")
_STRIPE_A_RGB = "FFFFFF"  # 白 (偶数行 i=0,2,4,...)
_STRIPE_B_RGB = "F2F7FB"  # 薄青 (奇数行 i=1,3,5,...)


def _stripe_fill(i):
    """i 行目用の縞模様 PatternFill を毎回 fresh に生成して返す。

    openpyxl の style index aliasing バグ（singleton を使うと白代入が
    青セルで silent no-op になる）を回避するため、呼び出し毎に新規生成する。
    """
    rgb = _STRIPE_A_RGB if i % 2 == 0 else _STRIPE_B_RGB
    return PatternFill("solid", fgColor=rgb)


# ── MD パースユーティリティ ─────────────────────────────────────────────────

def read_md(path):
    if path and Path(path).exists():
        try:
            return Path(path).read_text(encoding="utf-8")
        except UnicodeDecodeError as e:
            print(f"[ERROR] ファイルのエンコーディングが UTF-8 ではありません: {path}\n{e}")
            sys.exit(1)
    return ""


def extract_section(md, *headings):
    """指定見出し（## または ###）のセクション本文を返す。
    複数見出しは先にマッチしたものを使用。本文が空のセクションはスキップ。
    末尾の括弧「（確定後に記入）」のような付記も許容する。  [M2]
    見出し揺れ吸収:
    - 先頭の「■ 」等の記号を無視
    - 末尾の「:」「：」「テーブル」を無視
    - `#` 直後の全角スペースも許容
    """
    for h in headings:
        # 正規化後の見出しにマッチするパターン
        # 先頭: ■や●などの記号＋スペースを無視, 末尾: :／：／「テーブル」を無視
        pat = (
            r"^#{1,3}[\s　]+"              # ## または ### + 半/全角スペース
            r"(?:[■●▶◆]\s*)?"                 # 先頭記号（省略可）
            + re.escape(h) +
            r"(?:テーブル|一覧|[:：])?"         # 末尾の付記（省略可）
            r"(?:\s*[（(][^)）]*[)）])?\s*$"   # 括弧付記（省略可）
        )
        m = re.search(pat, md, re.MULTILINE)
        if m:
            start = m.end()
            rest = md[start:]
            end_m = re.search(r"^#{1,3}\s", rest, re.MULTILINE)
            body = rest[: end_m.start()] if end_m else rest
            stripped = body.strip()
            if stripped:
                return stripped
    return ""


def extract_section_after_keyword(md, keyword):
    """## 見出しではなく本文中のキーワード行以降のセクションを返す補助関数。  [M8]"""
    idx = md.find(keyword)
    if idx == -1:
        return ""
    rest = md[idx:]
    end_m = re.search(r"^#{1,3}\s", rest[len(keyword):], re.MULTILINE)
    if end_m:
        return rest[len(keyword): len(keyword) + end_m.start()].strip()
    return rest[len(keyword):].strip()


def parse_md_table(section_text):
    """Markdown テーブルを [{col_name: value, ...}] のリストに変換する。"""
    rows = []
    headers = []
    for line in section_text.splitlines():
        line = line.strip()
        if not line.startswith("|"):
            continue
        cells = [c.strip() for c in line.strip("|").split("|")]
        if all(re.match(r"^[-: ]+$", c) for c in cells):
            continue  # 区切り行
        if not headers:
            headers = cells
        else:
            rows.append(dict(zip(headers, cells)))
    return rows


def parse_checklist(section_text):
    """- [x] / - [ ] の行から (checked: bool, text: str) タプルのリストを返す。  [F11]"""
    items = []
    for line in section_text.splitlines():
        m = re.match(r"^\s*-\s+\[([ xX])\]\s+(.+)", line)
        if m:
            checked = m.group(1).lower() == "x"
            items.append((checked, m.group(2).strip()))
    return items


def parse_numbered_list(section_text):
    """1. 2. ... の番号付きリストを文字列リストで返す。"""
    items = []
    for line in section_text.splitlines():
        m = re.match(r"^\s*\d+[\.\)]\s+(.+)", line)
        if m:
            items.append(m.group(1).strip())
        elif line.strip() and not re.match(r"^#", line) and items:
            # 継続行
            items[-1] += " " + line.strip()
    return items


def extract_metadata(md, key):
    """key: value 形式の値を取る。
    以下の全形式に対応:  [M1]
      - key: value        (プレーン)
      - **key**: value    (太字)
      - - key: value      (リスト)
      - - **key**: value  (リスト+太字)
    半角・全角コロン両対応。
    """
    pat = rf"^\s*(?:[-*+]\s+)?(?:\*\*)?{re.escape(key)}(?:\*\*)?\s*[:|：]\s*(.+?)\s*$"
    m = re.search(pat, md, re.MULTILINE)
    if m:
        return re.sub(r"\*\*\s*$", "", m.group(1)).strip()
    return ""


def to_median_hours(text):
    """「2〜4h」「2~4 時間」「2-4h」を中央値「3h」へ変換。  [M5]
    範囲表記でなければそのまま返す。
    """
    m = re.match(r"^\s*(\d+(?:\.\d+)?)\s*[〜~\-－]\s*(\d+(?:\.\d+)?)\s*(h|時間|H)\s*$", text or "")
    if not m:
        return text
    lo, hi = float(m.group(1)), float(m.group(2))
    med = (lo + hi) / 2
    return f"{med:g}h"


def get_col(row, *candidates):
    """複数の列名候補から最初にヒットした値を返す。  [M11, M12]"""
    for c in candidates:
        if c in row and row[c]:
            return row[c]
    return ""


def parse_approach_options_h3(section_md):
    """### 案A: 方針名 配下の - **概要**: ... 形式を dict リストへ変換。  [M4]
    既存 parse_md_table が空の場合の fallback として使う。
    デメリットとリスクを統合して「デメリット」キーに格納する。  [F2]
    """
    options = []
    for m in re.finditer(
        r"^###\s+案([A-Z])[:：]\s*(.+?)(?:\s*【.+?】)?\s*$",
        section_md, re.MULTILINE
    ):
        no, name = m.group(1), m.group(2).strip()
        body_start = m.end()
        rest = section_md[body_start:]
        next_h = re.search(r"^#{2,3}\s", rest, re.MULTILINE)
        body = rest[: next_h.start()] if next_h else rest

        opt = {"案No": f"案{no}", "方針名": name}
        for key in ["概要", "メリット", "デメリット", "リスク", "前提", "見込み工数"]:
            sub_pat = rf"^\s*-\s+\*\*{re.escape(key)}\*\*\s*[:|：]\s*(.+?)(?=^\s*-\s+\*\*|\Z)"
            sm = re.search(sub_pat, body, re.MULTILINE | re.DOTALL)
            if sm:
                value = re.sub(r"\s+", " ", sm.group(1)).strip()
                opt["工数" if key == "見込み工数" else key] = value

        # デメリットにリスクを統合  [F2]
        if opt.get("リスク"):
            demerits = opt.get("デメリット", "")
            risk_text = opt["リスク"]
            if demerits:
                opt["デメリット"] = demerits + "　" + risk_text
            else:
                opt["デメリット"] = risk_text
            del opt["リスク"]

        options.append(opt)
    return options


def find_header_row(ws, candidates):
    """A 列を走査して candidates のいずれかに一致する行番号を返す。見つからなければ None。"""
    for row in ws.iter_rows(min_col=1, max_col=1):
        cell = row[0]
        if cell.value and any(str(c) in str(cell.value) for c in candidates):
            return cell.row
    return None


def copy_row_style(ws, src_row, dst_row, max_col=8):
    """src_row の書式を dst_row にコピーする（insert_rows 後のスタイル継承用）。

    copy.copy で StyleArray を独立コピーする。参照コピー（dst._style = src._style）は
    同じ StyleArray オブジェクトを共有し、後続の fill 代入が全共有セルを上書きするバグを招く。
    """
    for col in range(1, max_col + 1):
        src = ws.cell(row=src_row, column=col)
        dst = ws.cell(row=dst_row, column=col)
        if src.has_style:
            dst._style = copy.copy(src._style)
            dst.alignment = WRAP


def insert_rows_with_format(ws, insert_at, count, source_row, max_col):
    """insert_rows + 行高継承 + マージ補修を一括で行う (openpyxl の既知バグを回避)。

    openpyxl の insert_rows は:
    1. row_dimensions[height] のシフトが誤る場合がある
    2. マージセルをシフトせず元位置に残し、シフト後位置にも追加して重複を作る
    本関数はこれら両方を「挿入前スナップショット → クリア → 挿入 → 完全再構築」で補正する。
    """
    # 挿入前にマージ全件と行高全件をスナップショット
    all_merges = [(m.min_row, m.max_row, m.min_col, m.max_col)
                  for m in list(ws.merged_cells.ranges)]
    row_heights = {r: ws.row_dimensions[r].height
                   for r in ws.row_dimensions
                   if ws.row_dimensions[r].height is not None}
    src_h = row_heights.get(source_row)

    # マージを全クリア (insert_rows による重複マージ作成を防止)
    for mcr in list(ws.merged_cells.ranges):
        ws.merged_cells.ranges.discard(mcr)

    # 挿入実行
    ws.insert_rows(insert_at, amount=count)

    # 行高をスナップショットから完全再構築 (openpyxl のシフト誤りを上書き)
    # まず insert_at 以降のシフト元位置を None にリセット (stale コピーを除去)
    for r in row_heights:
        if r >= insert_at:
            ws.row_dimensions[r].height = None
    for r, h in row_heights.items():
        new_r = r + count if r >= insert_at else r
        ws.row_dimensions[new_r].height = h

    # 挿入行に source_row の行高 + セルスタイルをコピー
    for r in range(insert_at, insert_at + count):
        if src_h:
            ws.row_dimensions[r].height = src_h
        copy_row_style(ws, source_row, r, max_col=max_col)

    # マージをスナップショットから完全再構築 (insert_at 以降は count 行シフト)
    for (min_r, max_r, min_c, max_c) in all_merges:
        if min_r >= insert_at:
            ws.merge_cells(start_row=min_r + count, end_row=max_r + count,
                           start_column=min_c, end_column=max_c)
        elif max_r >= insert_at:
            ws.merge_cells(start_row=min_r, end_row=max_r + count,
                           start_column=min_c, end_column=max_c)
        else:
            ws.merge_cells(start_row=min_r, end_row=max_r,
                           start_column=min_c, end_column=max_c)


# ── セル書き込みユーティリティ ──────────────────────────────────────────────

def wset(ws, row, col, value, stripe=None):
    cell = ws.cell(row=row, column=col, value=value)
    cell.alignment = WRAP
    if stripe is not None:
        cell.fill = stripe
    return cell


def _merge_exists(ws, r1, c1, r2, c2):
    """指定範囲のマージが既に存在するか確認。"""
    return any(
        m.min_row == r1 and m.max_row == r2 and m.min_col == c1 and m.max_col == c2
        for m in ws.merged_cells.ranges
    )


def _shrink_table(ws, data_start, actual_count, limit):
    """実データ件数がテンプレ枠数より少ない場合、余り行を削除。  [R4]

    openpyxl の delete_rows は cell 値をシフトするが merged cell 範囲をシフトしない。
    insert_rows_with_format と同様のスナップショット再構築パターンで補正する。
    """
    excess = limit - actual_count
    if excess <= 0:
        return
    delete_start = data_start + actual_count

    all_merges = [(m.min_row, m.max_row, m.min_col, m.max_col)
                  for m in list(ws.merged_cells.ranges)]
    for mcr in list(ws.merged_cells.ranges):
        ws.merged_cells.ranges.discard(mcr)

    ws.delete_rows(delete_start, excess)

    for (min_r, max_r, min_c, max_c) in all_merges:
        # 削除範囲に完全に収まる merge は破棄
        if min_r >= delete_start and max_r <= delete_start + excess - 1:
            continue
        # 削除位置以降 → シフト
        elif min_r >= delete_start:
            ws.merge_cells(start_row=min_r - excess, end_row=max_r - excess,
                           start_column=min_c, end_column=max_c)
        # 削除範囲にまたがる merge → 上端だけ残してクリップ
        elif max_r >= delete_start:
            new_max_r = max(min_r, delete_start - 1)
            ws.merge_cells(start_row=min_r, end_row=new_max_r,
                           start_column=min_c, end_column=max_c)
        # 削除位置より前 → そのまま
        else:
            ws.merge_cells(start_row=min_r, end_row=max_r,
                           start_column=min_c, end_column=max_c)


# ── 行高自動調整ヘルパー ─────────────────────────────────────────────────────  [F11]

def _get_merged_width(ws, row, col):
    """row,col が属する merge 範囲の全列幅合計を返す。merge なしなら単独列幅。"""
    for m in ws.merged_cells.ranges:
        if m.min_row <= row <= m.max_row and m.min_col <= col <= m.max_col:
            return sum(
                ws.column_dimensions[get_column_letter(c)].width or 8
                for c in range(m.min_col, m.max_col + 1)
            )
    return ws.column_dimensions[get_column_letter(col)].width or 8


def _calc_row_height(text, width_chars, line_height=20, padding=4, min_height=28):
    """テキストの折り返し行数を概算して row.height を返す。
    visual width: 全角=2 / 半角=1。width_chars=10 → chars_per_row=20 visual chars。
    """
    if not text or not str(text).strip():
        return min_height
    text = str(text)
    chars_per_row = max(int(width_chars * 2), 4)
    total_lines = 0
    for line in text.split("\n"):
        if not line.strip():
            total_lines += 1
            continue
        visual_width = sum(2 if ord(c) > 127 else 1 for c in line)
        total_lines += max(1, (visual_width + chars_per_row - 1) // chars_per_row)
    return max(min_height, total_lines * line_height + padding)


def auto_fit_row(ws, row_idx, target_cols=None, min_height=28):
    """行 row_idx の各セル値から折り返し行数を概算し row.height を設定。
    target_cols=None で全列対象。merge セルは範囲全体の列幅で計算。
    """
    if target_cols is None:
        target_cols = list(range(1, ws.max_column + 1))
    max_h = min_height
    for col in target_cols:
        cell = ws.cell(row=row_idx, column=col)
        if cell.value:
            width = _get_merged_width(ws, row_idx, col)
            h = _calc_row_height(cell.value, width, min_height=min_height)
            if h > max_h:
                max_h = h
    ws.row_dimensions[row_idx].height = max_h


# ── タイムライン理由抽出ヘルパー ──────────────────────────────────────────  [F1]

def _extract_inv_reason(md):
    """調査完了時の理由: 根本原因・制約セクションの先頭文。"""
    body = extract_section(
        md,
        "根本原因", "根本原因 / 要件の本質", "要件の本質", "本質的に必要なこと",
        "Pardot 連携アーキテクチャの本質的制約", "アーキテクチャの本質的制約", "本質的制約",
    )
    if body:
        # 箇条書き「- 」を除去して先頭文を返す
        line = body.split("\n")[0].strip().lstrip("- ").replace("**", "")
        return line[:80]
    # フォールバック: 一言要約
    oneliner = extract_metadata(md, "一言要約")
    if oneliner:
        return oneliner.split("。")[0][:80]
    return ""


def _extract_adopted_reason(md):
    """採用方針確定時の理由: 採用方針セクションの「— 」以降テキスト。"""
    adopted = extract_section(md, "採用方針", "推奨案と根拠", "推奨案")
    if not adopted:
        return ""
    # 「案D（...）— 理由」の「— 」以降を返す
    m = re.search(r"[—\-]\s*(.+)", adopted)
    if m:
        text = re.sub(r"\s+", " ", m.group(1)).strip()
        return text[:80]
    # フォールバック: 採用方針テキスト冒頭
    return re.sub(r"^\s*採用方針[:|：]\s*", "", adopted).split("\n")[0][:80]


def _extract_impl_reason(md):
    """実装方針確定時の理由: 概要セクションの先頭文。"""
    body = extract_section(md, "概要", "実装方針まとめ")
    if body:
        return body.split("。")[0].strip()[:80]
    return ""


def _infer_kind_from_path(path):
    """ファイルパスから種別（Apex/LWC/Flow/Object/VF 等）を推定する。"""
    if "/lwc/" in path:
        return "LWC"
    if "/classes/" in path or path.endswith(".cls"):
        return "Apex"
    if "/triggers/" in path or path.endswith(".trigger"):
        return "Trigger"
    if "/aura/" in path:
        return "Aura"
    if "/flows/" in path:
        return "Flow"
    if "/objects/" in path:
        return "Object"
    if "/pages/" in path:
        return "VF"
    if path:
        ext = path.rsplit(".", 1)[-1] if "." in path else ""
        return ext.upper() if ext and len(ext) <= 6 else "その他"
    return "その他"


def _extract_main_changes(impl_md):
    """変更ファイル一覧からコンポーネント種別件数サマリーを生成（例: Apex 2件 / LWC 1件）。"""
    section = extract_section(impl_md, "変更ファイル一覧", "変更ファイル", "対象ファイル")
    if not section:
        return ""
    lines = [ln for ln in section.split("\n") if ln.strip().startswith("|") and not re.match(r"\|[-| ]+\|", ln.strip())]
    if lines and re.search(r"ファイル|No|パス", lines[0]):
        lines = lines[1:]
    type_counts: dict[str, int] = {}
    for ln in lines:
        cols = [c.strip().strip("`") for c in ln.strip().strip("|").split("|")]
        path_idx = 1 if len(cols) >= 2 and re.match(r"^\d+$", cols[0]) else 0
        path = cols[path_idx] if len(cols) > path_idx else ""
        t = _infer_kind_from_path(path)
        if t:
            type_counts[t] = type_counts.get(t, 0) + 1
    if type_counts:
        return " / ".join(f"{t} {n}件" for t, n in type_counts.items())
    count = len(lines)
    return f"{count}件" if count > 0 else ""


def _extract_main_changes_detailed(impl_md):
    """変更ファイル一覧から上位 5 件の {種別}: {ファイル名} — {役割} を改行区切りで返す。"""
    section = extract_section(impl_md, "変更ファイル一覧", "変更ファイル", "対象ファイル")
    if not section:
        return ""
    rows = parse_md_table(section)
    if not rows:
        return ""
    out = []
    for row in rows[:5]:
        path = (row.get("ファイルパス") or row.get("ファイル") or row.get("対象") or "").strip("`")
        kind = _infer_kind_from_path(path)
        name = path.rsplit("/", 1)[-1]
        role = (row.get("変更概要") or row.get("変更内容") or row.get("内容") or "").replace("**", "")
        out.append(f"{kind}: {name} — {role[:60]}")
    return "\n".join(out)


def _clean_summary_text(text, max_lines=4):
    """マークダウン強調記号を除去し、先頭 max_lines 行を返す（改行保持）。"""
    lines = [ln.rstrip() for ln in text.splitlines() if ln.strip()]
    cleaned = [re.sub(r"\*\*", "", ln).lstrip("- ").strip() for ln in lines[:max_lines]]
    return "\n".join(l for l in cleaned if l)


def _extract_before_state(inv_md, approach_md):
    """修正前の現状（現行挙動）。investigation.md の「本文から読み取れる要求」優先。"""
    # 「現行:」行を探す
    req_section = extract_section(inv_md, "本文から読み取れる要求")
    if req_section:
        current_lines = []
        capture = False
        for ln in req_section.splitlines():
            s = ln.strip()
            if re.match(r"[-*]\s*\*{0,2}現行\*{0,2}[:：]", s):
                capture = True
                txt = re.sub(r"^[-*]\s*\*{0,2}現行\*{0,2}[:：]\s*", "", s).replace("**", "")
                if txt:
                    current_lines.append(txt)
                continue
            if capture:
                if re.match(r"[-*]\s*\*{0,2}(希望|工数|目的)\*{0,2}[:：]", s):
                    break
                if s:
                    current_lines.append(s.lstrip("- ").replace("**", ""))
        if current_lines:
            return "\n".join(current_lines[:3])

    # フォールバック: TL;DR の前半部分
    tl = extract_section(inv_md, "TL;DR")
    if tl:
        return _clean_summary_text(tl, max_lines=2)

    # フォールバック: approach の現状
    return _clean_summary_text(
        extract_section(approach_md, "課題の現状", "現状") or "", max_lines=2
    )


def _extract_after_state(approach_md):
    """修正後の期待挙動。業務要件への回答を Q番号: 回答 形式に整形。"""
    text = extract_section(approach_md, "業務要件への回答", "業務要件への回答（方針確定時に記入）")
    if text:
        # テーブル形式（| Q1 | 質問 | 回答 |）とリスト形式（- Q1. xxx / 回答: yyy）の両方に対応
        rows = parse_md_table(text)
        if rows:
            out = []
            for row in rows[:6]:
                q = row.get("Q", row.get("#", "")).strip()
                topic = (row.get("質問") or row.get("内容") or "").strip()
                answer = (row.get("回答") or "").replace("**", "").strip()
                if q and answer:
                    out.append(f"{q}. {topic}: {answer}" if topic else f"{q}. {answer}")
                elif answer:
                    out.append(answer)
            if out:
                return "\n".join(out)

        # リスト形式: - Q1. xxx / 回答: yyy
        out = []
        for ln in text.splitlines():
            s = ln.strip().lstrip("- ")
            if re.match(r"\|[-| ]+\|", s) or s.startswith("|"):
                continue  # テーブル行をスキップ
            m = re.match(r"(Q\d+)[.\s]+(.+?)\s*/\s*回答[:：]\s*\*{0,2}(.+?)\*{0,2}(?:（[^）]*）)?$", s)
            if m:
                q = m.group(1)
                topic = m.group(2).strip()
                answer = m.group(3).strip().replace("**", "").strip("`")
                out.append(f"{q}. {topic}: {answer}")
            elif s and not re.match(r"^[#*_]", s):
                clean = re.sub(r"\*\*", "", s).strip("`")
                if clean:
                    out.append(clean)
        if out:
            return "\n".join(out[:6])

    # フォールバック: 推奨案と根拠
    text = extract_section(approach_md, "推奨案と根拠", "推奨案")
    return _clean_summary_text(text, max_lines=3) if text else ""


def _parse_impact_bullets(section_text):
    """影響範囲セクションの箇条書きを [{種別, 対象, 役割}] に変換する。
    テーブルが存在する場合は parse_md_table に委譲する。
    箇条書き: backtick で囲まれたパス/クラス名 + 説明 の形式を処理。
    """
    rows = parse_md_table(section_text)
    if rows:
        return rows
    result = []
    for ln in section_text.splitlines():
        ln = ln.strip()
        if not ln.startswith("-"):
            continue
        content = ln.lstrip("- ").strip()
        if not content:
            continue
        # バックティックの中身をコンポーネント名として抽出
        m = re.match(r"`([^`]+)`\s*(.*)", content)
        if m:
            target = m.group(1).strip()
            desc = re.sub(r"^\([^)]*\)\s*", "", m.group(2)).lstrip("—— ").replace("**", "").strip()
        else:
            # 括弧前をターゲット、括弧以降を役割とする
            m2 = re.match(r"([^\s（(]+)\s*[（(]?(.*)", content)
            target = m2.group(1).strip() if m2 else content[:40]
            desc = m2.group(2).rstrip("）)").strip().replace("**", "") if m2 else ""
        # 種別をパスから推定
        if "/lwc/" in target:
            kind = "LWC"
        elif ".cls" in target or "/classes/" in target:
            kind = "Apex"
        elif ".flow" in target or "/flows/" in target:
            kind = "Flow"
        elif "/objects/" in target:
            kind = "Object"
        else:
            kind = "ファイル"
        result.append({"種別": kind, "対象": target, "役割": desc})
    return result


def _extract_rollback_hint(impl_md):
    """ロールバック手順の1行サマリー。"""
    section = extract_section(impl_md, "ロールバック手順", "ロールバック", "切り戻し手順")
    if not section:
        return "（実装後に記入）"
    for ln in section.split("\n"):
        ln = ln.strip().lstrip("0123456789. -").strip()
        if ln and not ln.startswith("#"):
            return ln[:100]
    return "（実装後に記入）"


# ── サマリー・経緯シート ────────────────────────────────────────────────────

def fill_summary(ws, args, inv_md, approach_md, impl_md):
    # 課題情報 [M1, M3]
    issue_id   = args.issue_id
    title      = extract_metadata(inv_md, "件名") or extract_metadata(inv_md, "タイトル") or ""
    priority   = extract_metadata(inv_md, "優先度") or ""
    deadline   = extract_metadata(inv_md, "期限") or ""
    issue_type = extract_metadata(inv_md, "種別") or extract_metadata(inv_md, "課題種別") or ""

    # 背景・要件: 一言要約 を最優先  [F1]
    oneliner = extract_metadata(inv_md, "一言要約")
    if oneliner:
        summary_bg = oneliner
    else:
        summary_bg = extract_section(
            inv_md,
            "概要", "背景", "背景・要件", "課題概要",
            "課題サマリー", "要件理解", "一言要約",
        )
        if not summary_bg:
            summary_bg = "（概要セクションが investigation.md に見つかりません）"

    wset(ws, 3, 2, issue_id)
    wset(ws, 4, 2, title)
    wset(ws, 5, 2, f"優先度: {priority} / 期限: {deadline}")
    wset(ws, 6, 2, issue_type)
    wset(ws, 7, 2, "対応中")
    wset(ws, 8, 2, summary_bg)
    # r9 最終対応サマリー: 対応完了後に記入する欄  [F7]
    wset(ws, 9, 2, "（対応完了後に記入）")

    # r11-15: 対応サマリーブロック（高畑さん等レビュー向けの構造化サマリー）  [V-2]
    approach_summary = extract_section(approach_md, "採用方針", "推奨案と根拠", "推奨案")
    approach_clean = _clean_summary_text(approach_summary, max_lines=8) if approach_summary else "（対応方針確定後に記入）"
    wset(ws, 11, 2, approach_clean)
    wset(ws, 12, 2, _extract_main_changes_detailed(impl_md))
    wset(ws, 13, 2, _extract_before_state(inv_md, approach_md))   # 修正前（現状）
    wset(ws, 14, 2, _extract_after_state(approach_md))             # 修正後（期待挙動）
    wset(ws, 15, 2, _extract_rollback_hint(impl_md))

    # タイムライン: 各フェーズを MD ファイルの更新日時で書き込む  [A-4]
    # 対応する MD が空の場合はその行を空にする（update_records.py timeline が後から追記できるよう）
    def _file_mtime(path):
        try:
            return datetime.datetime.fromtimestamp(
                Path(path).stat().st_mtime
            ).strftime("%Y-%m-%d %H:%M") if path and Path(path).exists() else ""
        except OSError:
            return ""

    inv_result = extract_section(
        inv_md,
        "根本原因", "調査結果", "原因", "調査・まとめ",
        "根本原因 / 要件の本質", "要件の本質", "調査まとめ",
        "Pardot 連携アーキテクチャの本質的制約", "アーキテクチャの本質的制約",
    )
    if inv_result:
        inv_result_oneliner = inv_result.replace("\n", " ").lstrip("- ").replace("**", "")[:80]
    else:
        oneliner_v = extract_metadata(inv_md, "一言要約")
        inv_result_oneliner = oneliner_v.split("、")[0][:60] if oneliner_v else "調査完了"
    approach_adopted = extract_section(approach_md, "採用方針", "推奨案", "推奨案と根拠")
    approach_oneliner = approach_adopted.replace("\n", " ")[:80] if approach_adopted else "対応方針確定"
    impl_summary = extract_section(impl_md, "実装方針まとめ", "概要", "方針まとめ")
    if not impl_summary:
        change_files = extract_section(impl_md, "変更ファイル一覧", "変更ファイル")
        impl_summary = change_files[:80] if change_files else "実装方針確定"
    impl_oneliner = impl_summary.replace("\n", " ")[:80]

    tl_rows = [
        (1, _file_mtime(args.investigation), "Claude", "調査",
         f"調査完了: {inv_result_oneliner}", _extract_inv_reason(inv_md)),
        (2, _file_mtime(args.approach_plan) if approach_md else "", "ユーザ", "方針策定",
         f"対応方針確定: {approach_oneliner}" if approach_md else "", _extract_adopted_reason(approach_md)),
        (3, _file_mtime(args.implementation_plan) if impl_md else "", "ユーザ", "実装方針確定",
         f"全判断ポイント確定: {impl_oneliner}" if impl_md else "", _extract_impl_reason(impl_md)),
    ]
    # タイムライン開始行: ヘッダー動的検索（判断保留 block の有無で位置が変わるため）
    tl_header = find_header_row(ws, ("■ 対応経緯タイムライン",))
    tl_data_start = (tl_header + 2) if tl_header else 25  # fallback: 判断保留あり想定
    for i, row in enumerate(tl_rows):
        fill = _stripe_fill(i)
        for j, val in enumerate(row, start=1):
            wset(ws, tl_data_start + i, j, val, fill)


# ── 判断保留事項シート書き込み ────────────────────────────────────────────────

def fill_pending_decisions(ws, approach_md, impl_md):
    """判断保留事項ブロック（r17-21）を埋める。  [V-3]

    impl_md → approach_md の順で '## 判断保留事項' セクションを探す。
    該当なしの場合はヘッダーを残しデータ行に「（判断保留事項なし）」を入れる。
    """
    text = extract_section(impl_md, "判断保留事項")
    if not text:
        text = extract_section(approach_md, "判断保留事項")

    PENDING_HEADER_KEYWORDS = ("■ 判断保留事項",)
    header_row = find_header_row(ws, PENDING_HEADER_KEYWORDS)
    if not header_row:
        return  # テンプレにブロック未設定

    data_start = header_row + 2  # ヘッダー + 列見出し行の次
    PENDING_LIMIT = 3            # テンプレ 3 行枠

    rows = parse_md_table(text) if text else []

    # 列マッピング: A=No, B=内容, C=影響範囲, D=期待する判断者, E=関連ファイル
    col_map = [
        ("内容",           ["内容", "保留内容", "判断内容"]),
        ("影響範囲",       ["影響範囲", "影響", "対象"]),
        ("期待する判断者", ["期待する判断者", "判断者", "担当"]),
        ("関連ファイル",   ["関連ファイル", "関連", "ファイル"]),
    ]

    if not rows:
        # 保留なし: 1 行目に placeholder を入れ、余剰行を削除
        wset(ws, data_start, 2, "（判断保留事項なし）", _stripe_fill(0))
        if PENDING_LIMIT > 1:
            _shrink_table(ws, data_start + 1, 0, PENDING_LIMIT - 1)
        # delete_rows は row_dimensions をシフトしないため、
        # タイムラインセクション前後の行高をリセットして squash を防ぐ
        tl_hdr = find_header_row(ws, ("■ 対応経緯タイムライン",))
        if tl_hdr:
            ws.row_dimensions[tl_hdr - 1].height = 8   # blank separator
            ws.row_dimensions[tl_hdr].height = 28       # ■ 対応経緯タイムライン
            ws.row_dimensions[tl_hdr + 1].height = 18  # column header
        return

    extra = max(0, len(rows) - PENDING_LIMIT)
    if extra > 0:
        insert_rows_with_format(ws, data_start + PENDING_LIMIT, extra,
                                source_row=data_start, max_col=5)
    elif len(rows) < PENDING_LIMIT:
        _shrink_table(ws, data_start, len(rows), PENDING_LIMIT)

    for i, row in enumerate(rows):
        fill = _stripe_fill(i)
        wset(ws, data_start + i, 1, str(i + 1), fill)
        for j, (_, candidates) in enumerate(col_map, start=2):
            wset(ws, data_start + i, j, get_col(row, *candidates), fill)
        auto_fit_row(ws, data_start + i)


# ── 対応方針シート ──────────────────────────────────────────────────────────

def fill_approach(ws, approach_md):
    # 方針比較テーブル（r4〜、テンプレ標準 2 件枠）[F2: 6列構成、リスクをデメリットに統合]
    table_text = extract_section(
        approach_md,
        "方針比較", "方針比較テーブル", "対応方針比較",
        "対応方針の各案", "案一覧",
    )
    rows = parse_md_table(table_text)
    if not rows and table_text:
        # H3 + 箇条書き形式 (### 案A: ... / - **概要**: ...) を fallback でパース [M4]
        rows = parse_approach_options_h3(table_text)
    if not rows and approach_md:
        # セクション名が section_text に入らず approach_md 全体に対して走らせる
        rows = parse_approach_options_h3(approach_md)

    # テンプレ修正後 6列構成: 案No/方針名/概要/メリット/デメリット/工数  [F2]
    col_order = ["案No", "方針名", "概要", "メリット", "デメリット", "工数"]
    APPROACH_START = 4
    APPROACH_LIMIT = 2  # テンプレ r4-r5
    extra_approach = max(0, len(rows) - APPROACH_LIMIT)
    if extra_approach > 0:
        insert_rows_with_format(
            ws,
            APPROACH_START + APPROACH_LIMIT,
            extra_approach,
            source_row=APPROACH_START,
            max_col=6,
        )
    elif len(rows) < APPROACH_LIMIT:
        _shrink_table(ws, APPROACH_START, len(rows), APPROACH_LIMIT)

    for i, row in enumerate(rows):
        fill = _stripe_fill(i)
        for j, col in enumerate(col_order, start=1):
            val = row.get(col, "")
            if col == "工数":
                val = to_median_hours(val)  # [M5]
            wset(ws, APPROACH_START + i, j, val, fill)

    # 採用方針（テンプレ修正後 r8 or 行数シフト後の位置）  [F2: 案名+理由 短文形式]
    adopted_header_row = find_header_row(ws, ("■ 採用方針",))
    adopted_write_row = (adopted_header_row + 1) if adopted_header_row else 8

    adopted_full = extract_section(approach_md, "採用方針", "推奨案", "推奨案と根拠")
    if adopted_full:
        # 「採用方針: 案D（...）— 理由本文」を「採用案: ... / 理由: ...」短文形式に変換
        m = re.search(
            r"採用方針[:|：]\s*\*?\*?(案[A-Z][^*\n]+)\*?\*?\s*[—\-]\s*(.+?)(?=\n\n|\Z)",
            adopted_full, re.DOTALL
        )
        if m:
            plan_name = m.group(1).strip()
            reason = re.sub(r"\s+", " ", m.group(2)).strip()[:200]
            adopted_short = f"採用案: {plan_name}\n理由: {reason}"
        else:
            # フォールバック: 先頭300字
            adopted_short = adopted_full[:300]

        has_merge = any(
            mg.min_row == adopted_write_row and mg.max_row == adopted_write_row
            and mg.min_col == 1 and mg.max_col == 6
            for mg in ws.merged_cells.ranges
        )
        if not has_merge:
            ws.merge_cells(start_row=adopted_write_row, end_row=adopted_write_row,
                           start_column=1, end_column=6)
        wset(ws, adopted_write_row, 1, adopted_short)

    # 実施前確認事項（テンプレ修正後 r11 or ヘッダ検索で特定）[F2: 2列構成]
    checks_text = extract_section(
        approach_md,
        "実施前確認事項", "確認事項", "事前確認",
        "業務要件の確認事項", "前提確認",
    )
    checks = parse_checklist(checks_text)
    if not checks:
        checks = [(False, item) for item in parse_numbered_list(checks_text)]

    confirm_header_row = find_header_row(ws, ("■ 実施前確認事項",))
    confirm_data_start = (confirm_header_row + 2) if confirm_header_row else 12
    CONFIRM_LIMIT = 4  # テンプレ修正後 標準4枠

    extra_confirm = max(0, len(checks) - CONFIRM_LIMIT)
    if extra_confirm > 0:
        insert_rows_with_format(
            ws,
            confirm_data_start + CONFIRM_LIMIT,
            extra_confirm,
            source_row=confirm_data_start,
            max_col=2,
        )
    elif len(checks) < CONFIRM_LIMIT:
        _shrink_table(ws, confirm_data_start, len(checks), CONFIRM_LIMIT)

    for i, (checked, text) in enumerate(checks):
        target_row = confirm_data_start + i
        wset(ws, target_row, 1, "☑" if checked else "☐")
        wset(ws, target_row, 2, text)
        # B:F merge を動的付与 (テンプレ6列構成、確認内容を広く)  [F8]
        if not _merge_exists(ws, target_row, 2, target_row, 6):
            ws.merge_cells(start_row=target_row, end_row=target_row,
                           start_column=2, end_column=6)
        auto_fit_row(ws, target_row, target_cols=[1, 2])

    # 懸念事項（テンプレ修正後 r17「■ 懸念事項」の直下から書き込み）[M6]
    concerns_text = extract_section(approach_md, "懸念事項", "リスク・懸念事項", "懸念点")
    concerns = parse_numbered_list(concerns_text)
    if not concerns:
        concerns = [l.strip().lstrip("0123456789.。 ").lstrip("- ") for l in concerns_text.splitlines() if l.strip()]

    concern_header_row = find_header_row(ws, ("■ 懸念事項", "懸念事項"))
    concern_data_start = (concern_header_row + 1) if concern_header_row else 18
    CONCERN_LIMIT = 3  # テンプレ修正後 r18-r20 (各行 A:F マージ済)

    extra_concerns = max(0, len(concerns) - CONCERN_LIMIT)
    if extra_concerns > 0:
        insert_rows_with_format(
            ws,
            concern_data_start + CONCERN_LIMIT,
            extra_concerns,
            source_row=concern_data_start,
            max_col=6,
        )
    elif len(concerns) < CONCERN_LIMIT:
        _shrink_table(ws, concern_data_start, len(concerns), CONCERN_LIMIT)
    for i, item in enumerate(concerns):
        fill = _stripe_fill(i)
        target_row = concern_data_start + i
        has_merge = any(
            mg.min_row == target_row and mg.max_row == target_row
            and mg.min_col == 1 and mg.max_col == 6
            for mg in ws.merged_cells.ranges
        )
        if not has_merge:
            ws.merge_cells(start_row=target_row, end_row=target_row,
                           start_column=1, end_column=6)
        wset(ws, target_row, 1, f"{i + 1}. {item}", fill)


# ── 調査・影響範囲シート ────────────────────────────────────────────────────

def fill_investigation(ws, inv_md):
    # 仮説検証（r4-9）[M3, M8]
    hypo_text = extract_section(
        inv_md,
        "仮説検証", "仮説・検証",
        "代替アプローチ", "代替経路", "業務要件の不確実点",
    )
    rows = parse_md_table(hypo_text)
    if not rows:
        for kw in ("ただし以下の代替経路", "代替経路の検討", "再検討の余地"):
            alt_text = extract_section_after_keyword(inv_md, kw)
            rows = parse_md_table(alt_text)
            if rows:
                break

    # テンプレ修正後 4列構成: No/仮説内容/備考/判定  [F9: 検証方法削除]
    hypo_col_map = [
        ("No", ["No", "#"]),
        ("仮説内容", ["仮説内容", "代替アプローチ", "仮説", "アプローチ"]),
        ("備考", ["備考", "検証結果", "補足"]),
        ("判定", ["判定", "実現可能性"]),
    ]
    HYPO_START = 4
    HYPO_LIMIT = 5  # テンプレ r4-r8（r9 は spacer）
    extra_hypo = max(0, len(rows) - HYPO_LIMIT)
    if extra_hypo > 0:
        insert_rows_with_format(ws, HYPO_START + HYPO_LIMIT, extra_hypo,
                                source_row=HYPO_START, max_col=4)
    elif len(rows) < HYPO_LIMIT:
        _shrink_table(ws, HYPO_START, len(rows), HYPO_LIMIT)
    for i, row in enumerate(rows):
        fill = _stripe_fill(i)
        for j, (_, candidates) in enumerate(hypo_col_map, start=1):
            wset(ws, HYPO_START + i, j, get_col(row, *candidates), fill)
        auto_fit_row(ws, HYPO_START + i)

    # コード根拠（r12-17）[M3, M9] — 動的拡張対応  [F9]
    code_text = extract_section(
        inv_md,
        "コード根拠", "コード根拠テーブル",
        "使用中のフィールドAPI名", "参照コード", "フィールドAPI名",
    )
    code_rows = parse_md_table(code_text)
    if not code_rows:
        sub1 = extract_section(inv_md, "標準 Prospect オブジェクト", "標準Prospectオブジェクト")
        sub2 = extract_section(inv_md, "Pardot 連携カスタム項目", "Pardot連携カスタム項目")
        code_rows = parse_md_table(sub1) + parse_md_table(sub2)

    code_col_map = [
        ("ファイル名", ["ファイル名", "フィールド概念", "ファイル", "コンポーネント"]),
        ("行番号", ["行番号", "確認済み API名", "API名", "行"]),
        ("コード内容", ["コード内容", "確認元", "コード", "参照元"]),
        ("説明", ["説明", "補足", "備考"]),
    ]
    code_header_row = find_header_row(ws, ("■ コード根拠テーブル", "■ コード根拠"))
    code_data_start = (code_header_row + 2) if code_header_row else 12
    CODE_LIMIT = 5  # テンプレ r12-r16（r17 は spacer）
    extra_code = max(0, len(code_rows) - CODE_LIMIT)
    if extra_code > 0:
        insert_rows_with_format(
            ws,
            code_data_start + CODE_LIMIT,
            extra_code,
            source_row=code_data_start,
            max_col=4,
        )
    elif len(code_rows) < CODE_LIMIT:
        _shrink_table(ws, code_data_start, len(code_rows), CODE_LIMIT)
    for i, row in enumerate(code_rows):
        fill = _stripe_fill(i)
        for j, (_, candidates) in enumerate(code_col_map, start=1):
            wset(ws, code_data_start + i, j, get_col(row, *candidates), fill)
        auto_fit_row(ws, code_data_start + i)

    # 影響範囲: 変更によって影響を受ける外部ファイル・フロー  [A-2: ソース分離]
    impact_text = extract_section(inv_md, "影響範囲")
    impact_rows = _parse_impact_bullets(impact_text)
    if not impact_rows:
        # フォールバック: 業務文脈 > 関連フロー
        ctx_text = extract_section(inv_md, "業務文脈", "業務文脈（docs/ から）")
        flow_text = extract_section_after_keyword(ctx_text or inv_md, "関連フロー")
        impact_rows = _parse_impact_bullets(flow_text)

    impact_header_row = find_header_row(ws, ("■ 影響範囲テーブル", "■ 影響範囲"))
    impact_data_start = (impact_header_row + 2) if impact_header_row else 20
    IMPACT_LIMIT = 6  # テンプレ r20-r25（r26 は spacer）

    # ヘッダー行 (header_row + 1) の役割列を C:D merge  [R1]
    if impact_header_row:
        col_header_row = impact_header_row + 1
        if not _merge_exists(ws, col_header_row, 3, col_header_row, 4):
            ws.merge_cells(start_row=col_header_row, end_row=col_header_row,
                           start_column=3, end_column=4)

    extra_impact = max(0, len(impact_rows) - IMPACT_LIMIT)
    if extra_impact > 0:
        insert_rows_with_format(
            ws,
            impact_data_start + IMPACT_LIMIT,
            extra_impact,
            source_row=impact_data_start,
            max_col=4,
        )
    elif len(impact_rows) < IMPACT_LIMIT:
        _shrink_table(ws, impact_data_start, len(impact_rows), IMPACT_LIMIT)

    # テンプレ修正後の列構成: A=種別, B=対象, C=役割  [F9: 影響内容列削除]
    impact_col_map = [
        ("種別", ["種別"]),
        ("対象", ["対象", "フロー名", "ファイルパス", "コンポーネント名"]),
        ("役割", ["役割", "内容", "影響内容", "補足", "備考"]),
    ]
    for i, row in enumerate(impact_rows):
        fill = _stripe_fill(i)
        for j, (_, candidates) in enumerate(impact_col_map, start=1):
            wset(ws, impact_data_start + i, j, get_col(row, *candidates), fill)
        target_row = impact_data_start + i
        if not _merge_exists(ws, target_row, 3, target_row, 4):
            ws.merge_cells(start_row=target_row, end_row=target_row,
                           start_column=3, end_column=4)
        auto_fit_row(ws, target_row)

    # 関連コンポーネント一覧: 当課題で変更/参照する SF コンポーネント  [A-2: ソース分離]
    raw_comp_text = extract_section(inv_md, "関連コンポーネント", "関連コンポーネント一覧")
    comp_rows = parse_md_table(raw_comp_text)

    comp_header_row = find_header_row(ws, ("■ 関連コンポーネント", "■ 関連コンポーネント一覧"))
    comp_data_start = (comp_header_row + 2) if comp_header_row else 29
    COMP_LIMIT = 5

    # ヘッダー行 (comp_header_row + 1) の役割列を C:D merge  [R2]
    if comp_header_row:
        comp_col_header_row = comp_header_row + 1
        if not _merge_exists(ws, comp_col_header_row, 3, comp_col_header_row, 4):
            ws.merge_cells(start_row=comp_col_header_row, end_row=comp_col_header_row,
                           start_column=3, end_column=4)

    extra_comp = max(0, len(comp_rows) - COMP_LIMIT)
    if extra_comp > 0:
        insert_rows_with_format(
            ws,
            comp_data_start + COMP_LIMIT,
            extra_comp,
            source_row=comp_data_start,
            max_col=4,
        )
    elif len(comp_rows) < COMP_LIMIT:
        _shrink_table(ws, comp_data_start, len(comp_rows), COMP_LIMIT)

    for i, row in enumerate(comp_rows[:10]):
        fill = _stripe_fill(i)
        # 3列構成: 種別/名前(ファイルパス)/役割  [F3]
        wset(ws, comp_data_start + i, 1, get_col(row, "種別"), fill)
        wset(ws, comp_data_start + i, 2, get_col(row, "対象", "ファイルパス", "名前", "コンポーネント名"), fill)
        wset(ws, comp_data_start + i, 3, get_col(row, "役割", "内容", "補足"), fill)
        target_row = comp_data_start + i
        if not _merge_exists(ws, target_row, 3, target_row, 4):
            ws.merge_cells(start_row=target_row, end_row=target_row,
                           start_column=3, end_column=4)
        auto_fit_row(ws, target_row)


# ── 対応内容シート ──────────────────────────────────────────────────────────

def _has_code_change(impl_md):
    """変更ファイル一覧に *.cls/*.flow-meta.xml/*.field-meta.xml 等が含まれるか。  [F4]"""
    files_text = extract_section(impl_md, "変更ファイル一覧", "変更ファイル")
    return bool(re.search(
        r"\.(cls|flow-meta|object-meta|field-meta|page|component|trigger)\.xml|\.cls\b",
        files_text
    ))


def fill_content(ws, impl_md):
    # バックアップ情報 (r3-r5): コード変更なし案件は「該当なし」default を入れる  [F4]
    if _has_code_change(impl_md):
        wset(ws, 3, 2, "")  # バックアップ先: 実装時に記入
        wset(ws, 4, 2, "")  # コミットハッシュ: 実装時に記入
        wset(ws, 5, 2, "")  # ロールバック手順: 実装時に記入
    else:
        wset(ws, 3, 2, "該当なし（コード変更なし）")
        wset(ws, 4, 2, "該当なし")
        rb_text = extract_section(impl_md, "ロールバック手順")
        rb_first = parse_numbered_list(rb_text)
        wset(ws, 5, 2, rb_first[0] if rb_first else "ロールバック手順を参照")

    # 変更ファイル一覧（r9-11、テンプレ標準 3 件枠）
    rows = parse_md_table(extract_section(impl_md, "変更ファイル一覧", "変更ファイル"))
    CHANGE_FILES_START = 9
    CHANGE_FILES_LIMIT = 3  # テンプレ r9-r11
    extra_chg = max(0, len(rows) - CHANGE_FILES_LIMIT)
    if extra_chg > 0:
        insert_rows_with_format(
            ws,
            CHANGE_FILES_START + CHANGE_FILES_LIMIT,
            extra_chg,
            source_row=CHANGE_FILES_START,
            max_col=4,  # E列削除後 4列
        )
    elif len(rows) < CHANGE_FILES_LIMIT:
        _shrink_table(ws, CHANGE_FILES_START, len(rows), CHANGE_FILES_LIMIT)
    for i, row in enumerate(rows):
        fill = _stripe_fill(i)
        for j, col in enumerate(["No", "ファイルパス", "変更種別", "変更概要"], start=1):
            wset(ws, CHANGE_FILES_START + i, j, row.get(col, ""), fill)

    # Before/After セクションは動的に位置を特定
    ba_header_row = find_header_row(ws, ("■ Before / After",))
    if ba_header_row:
        wset(ws, ba_header_row + 1, 1, "実装完了後、各ファイルの変更前後を記載する")

    # 影響確認チェックリスト（r21〜）[F4: 2列構成]
    checks = parse_checklist(extract_section(
        impl_md,
        "影響確認チェックリスト", "影響確認",
    ))
    impact_header_row = find_header_row(ws, ("■ 影響確認チェックリスト",))
    IMPACT_CHECK_START = (impact_header_row + 2) if impact_header_row else 21
    IMPACT_CHECK_LIMIT = 6  # テンプレ標準 6 件枠

    # ヘッダー行 (impact_header_row + 1) の確認内容列を B:D merge  [R3]
    if impact_header_row:
        check_col_header_row = impact_header_row + 1
        if not _merge_exists(ws, check_col_header_row, 2, check_col_header_row, 4):
            ws.merge_cells(start_row=check_col_header_row, end_row=check_col_header_row,
                           start_column=2, end_column=4)

    extra_impact = max(0, len(checks) - IMPACT_CHECK_LIMIT)
    if extra_impact > 0:
        insert_rows_with_format(
            ws,
            IMPACT_CHECK_START + IMPACT_CHECK_LIMIT,
            extra_impact,
            source_row=IMPACT_CHECK_START,
            max_col=2,
        )
    elif len(checks) < IMPACT_CHECK_LIMIT:
        _shrink_table(ws, IMPACT_CHECK_START, len(checks), IMPACT_CHECK_LIMIT)
    for i, (checked, text) in enumerate(checks):
        target_row = IMPACT_CHECK_START + i
        wset(ws, target_row, 1, "☑" if checked else "☐")
        wset(ws, target_row, 2, text)
        if not _merge_exists(ws, target_row, 2, target_row, 4):
            ws.merge_cells(start_row=target_row, end_row=target_row,
                           start_column=2, end_column=4)
        auto_fit_row(ws, target_row, target_cols=[1, 2])


# ── テスト・検証記録シート ──────────────────────────────────────────────────

def fill_test(ws, impl_md):
    # テスト方針（r3-4）[M3]
    policy = extract_section(
        impl_md,
        "テスト方針", "テスト概要",
        "テスト方針・概要", "テストシナリオ",
    )
    if not policy:
        policy = "実装前後での動作確認を行う。実装前は現状把握、実装後は修正確認。"
    wset(ws, 3, 1, policy)

    # テストテーブル（r7〜、テンプレ標準 8 件枠）[F5: H列削除後 7列構成]
    rows = parse_md_table(extract_section(
        impl_md,
        "テスト仕様", "テストケース", "テスト仕様テーブル",
        "テストシナリオ",
    ))
    TEST_START = 7
    TEST_LIMIT = 8  # テンプレ r7-r14
    extra_test = max(0, len(rows) - TEST_LIMIT)
    if extra_test > 0:
        insert_rows_with_format(
            ws,
            TEST_START + TEST_LIMIT,
            extra_test,
            source_row=TEST_START,
            max_col=7,  # H列削除後 7列  [F5]
        )
    elif len(rows) < TEST_LIMIT:
        _shrink_table(ws, TEST_START, len(rows), TEST_LIMIT)
    for i, row in enumerate(rows):
        fill = _stripe_fill(i)
        # H列「根拠」を削除した 7列構成  [F5]
        vals = [
            row.get("No", str(i + 1)),
            row.get("タイミング", row.get("区分", "")),
            row.get("確認観点", row.get("テスト項目", "")),
            row.get("確認手順", row.get("確認方法", "")),
            row.get("期待結果", ""),
            row.get("実際の結果", ""),  # テスト実行後に記入
            row.get("判定", ""),       # テスト実行後に記入
        ]
        for j, val in enumerate(vals, start=1):
            wset(ws, TEST_START + i, j, val, fill)
        auto_fit_row(ws, TEST_START + i)


# ── リリース・ロールバックシート ────────────────────────────────────────────

def fill_release(ws, impl_md, approach_md=""):
    # リリース対象（r4-5、テンプレ標準 2 件枠）[F6: 4列構成 No/種別/対象/デプロイ方法]
    rows = parse_md_table(extract_section(
        impl_md,
        "リリース対象", "リリース対象一覧",
        "デプロイ対象", "変更対象一覧",
    ))
    RELEASE_START = 4
    RELEASE_LIMIT = 2  # テンプレ r4-r5
    extra_release = max(0, len(rows) - RELEASE_LIMIT)
    if extra_release > 0:
        insert_rows_with_format(
            ws,
            RELEASE_START + RELEASE_LIMIT,
            extra_release,
            source_row=RELEASE_START,
            max_col=4,  # E/F列削除後 4列  [F6]
        )
    elif len(rows) < RELEASE_LIMIT:
        _shrink_table(ws, RELEASE_START, len(rows), RELEASE_LIMIT)

    for i, row in enumerate(rows):
        fill = _stripe_fill(i)
        api_name = get_col(row, "対象", "API名", "ファイルパス")
        wset(ws, RELEASE_START + i, 1, row.get("No", str(i + 1)), fill)
        wset(ws, RELEASE_START + i, 2, row.get("種別", ""), fill)
        wset(ws, RELEASE_START + i, 3, api_name, fill)
        wset(ws, RELEASE_START + i, 4, row.get("デプロイ方法", ""), fill)
        # 変更種別・備考は削除  [F6]

    # リリース前確認事項（テンプレ修正後 r9+）[F6: 2列構成]
    pre_text = extract_section(
        impl_md,
        "リリース前確認事項", "リリース前確認", "デプロイ前確認",
        "事前準備", "実装前準備", "確認事項",
    )
    checks = parse_checklist(pre_text)
    if not checks:
        checks = [(False, item) for item in parse_numbered_list(pre_text)]
    if not checks and approach_md:
        pre_fallback = extract_section(
            approach_md,
            "実施前確認事項", "確認事項", "事前確認",
            "業務要件の確認事項",
        )
        checks = parse_checklist(pre_fallback)
        if not checks:
            checks = [(False, item) for item in parse_numbered_list(pre_fallback)]

    pre_header_row = find_header_row(ws, ("■ リリース前確認事項",))
    pre_data_start = (pre_header_row + 2) if pre_header_row else 9
    PRE_CHECK_LIMIT = 4  # テンプレ r9-r12
    extra_pre = max(0, len(checks) - PRE_CHECK_LIMIT)
    if extra_pre > 0:
        insert_rows_with_format(
            ws,
            pre_data_start + PRE_CHECK_LIMIT,
            extra_pre,
            source_row=pre_data_start,
            max_col=2,
        )
    elif len(checks) < PRE_CHECK_LIMIT:
        _shrink_table(ws, pre_data_start, len(checks), PRE_CHECK_LIMIT)
    for i, (checked, text) in enumerate(checks):
        target_row = pre_data_start + i
        wset(ws, target_row, 1, "☑" if checked else "☐")
        wset(ws, target_row, 2, text)
        # B:D merge を動的付与 (確認内容列を広く)  [F10]
        if not _merge_exists(ws, target_row, 2, target_row, 4):
            ws.merge_cells(start_row=target_row, end_row=target_row,
                           start_column=2, end_column=4)
        auto_fit_row(ws, target_row, target_cols=[1, 2])

    # デプロイ手順（テンプレ修正後 A:D マージ）[F6: max_col=4]
    steps = parse_numbered_list(extract_section(impl_md, "デプロイ手順", "リリース手順"))
    deploy_header_row = find_header_row(ws, ("■ デプロイ手順",))
    deploy_data_start = (deploy_header_row + 1) if deploy_header_row else 15
    DEPLOY_LIMIT = 4  # テンプレ標準 4 件
    extra_deploy = max(0, len(steps) - DEPLOY_LIMIT)
    if extra_deploy > 0:
        insert_rows_with_format(
            ws,
            deploy_data_start + DEPLOY_LIMIT,
            extra_deploy,
            source_row=deploy_data_start,
            max_col=4,  # E/F削除後  [F6]
        )
    elif len(steps) < DEPLOY_LIMIT:
        _shrink_table(ws, deploy_data_start, len(steps), DEPLOY_LIMIT)
    for i, step in enumerate(steps):
        target_row = deploy_data_start + i
        has_merge = any(
            mg.min_row == target_row and mg.max_row == target_row
            and mg.min_col == 1 and mg.max_col == 4
            for mg in ws.merged_cells.ranges
        )
        if not has_merge:
            ws.merge_cells(start_row=target_row, end_row=target_row,
                           start_column=1, end_column=4)
        wset(ws, target_row, 1, f"{i + 1}. {step}")

    # デプロイ後確認事項（テンプレ修正後 2列構成）[F6]
    post_text = extract_section(
        impl_md,
        "デプロイ後確認事項", "リリース後確認", "デプロイ後確認",
        "実装後確認", "モニタリング", "影響確認チェックリスト",
    )
    post_checks = parse_checklist(post_text)
    if not post_checks:
        post_checks = [(False, item) for item in parse_numbered_list(post_text)]

    post_header_row = find_header_row(ws, ("■ デプロイ後確認事項",))
    post_data_start = (post_header_row + 2) if post_header_row else 22
    POST_CHECK_LIMIT = 4
    extra_post = max(0, len(post_checks) - POST_CHECK_LIMIT)
    if extra_post > 0:
        insert_rows_with_format(
            ws,
            post_data_start + POST_CHECK_LIMIT,
            extra_post,
            source_row=post_data_start,
            max_col=2,
        )
    elif len(post_checks) < POST_CHECK_LIMIT:
        _shrink_table(ws, post_data_start, len(post_checks), POST_CHECK_LIMIT)
    for i, (checked, text) in enumerate(post_checks):
        target_row = post_data_start + i
        wset(ws, target_row, 1, "☑" if checked else "☐")
        wset(ws, target_row, 2, text)
        # B:D merge を動的付与  [F10]
        if not _merge_exists(ws, target_row, 2, target_row, 4):
            ws.merge_cells(start_row=target_row, end_row=target_row,
                           start_column=2, end_column=4)
        auto_fit_row(ws, target_row, target_cols=[1, 2])

    # 注意事項（テンプレ修正後 A:D マージ）[F6: max_col=4, 番号prefix再付与]
    notes_text = extract_section(
        impl_md,
        "注意事項", "リスク・注意事項", "注意点",
        "懸念事項", "リスク",
    )
    if not notes_text and approach_md:
        notes_text = extract_section(approach_md, "懸念事項", "リスク・懸念事項", "注意事項")

    notes = parse_numbered_list(notes_text)
    if not notes:
        notes = [l.strip().lstrip("- ") for l in notes_text.splitlines() if l.strip().startswith("-")]

    notes_header_row = find_header_row(ws, ("■ 注意事項・リスク", "■ 注意事項"))
    notes_data_start = (notes_header_row + 1) if notes_header_row else 28
    NOTES_LIMIT = 2  # テンプレ標準 2 件
    extra_notes = max(0, len(notes) - NOTES_LIMIT)
    if extra_notes > 0:
        insert_rows_with_format(
            ws,
            notes_data_start + NOTES_LIMIT,
            extra_notes,
            source_row=notes_data_start,
            max_col=4,  # E/F削除後  [F6]
        )
    elif len(notes) < NOTES_LIMIT:
        _shrink_table(ws, notes_data_start, len(notes), NOTES_LIMIT)
    for i, item in enumerate(notes):
        target_row = notes_data_start + i
        has_merge = any(
            mg.min_row == target_row and mg.max_row == target_row
            and mg.min_col == 1 and mg.max_col == 4
            for mg in ws.merged_cells.ranges
        )
        if not has_merge:
            ws.merge_cells(start_row=target_row, end_row=target_row,
                           start_column=1, end_column=4)
        wset(ws, target_row, 1, f"{i + 1}. {item}")  # 番号prefix再付与  [F6]

    # ロールバック手順（テンプレ修正後 A:D マージ）[F6]
    rb_steps = parse_numbered_list(extract_section(impl_md, "ロールバック手順"))
    rb_header_row = find_header_row(ws, ("■ ロールバック手順",))
    rb_data_start = (rb_header_row + 1) if rb_header_row else 32
    RB_LIMIT = 4  # テンプレ r32-r35
    extra_rb = max(0, len(rb_steps) - RB_LIMIT)
    if extra_rb > 0:
        insert_rows_with_format(
            ws,
            rb_data_start + RB_LIMIT,
            extra_rb,
            source_row=rb_data_start,
            max_col=4,  # E/F削除後  [F6]
        )
    elif len(rb_steps) < RB_LIMIT:
        _shrink_table(ws, rb_data_start, len(rb_steps), RB_LIMIT)
    for i, step in enumerate(rb_steps):
        target_row = rb_data_start + i
        has_merge = any(
            mg.min_row == target_row and mg.max_row == target_row
            and mg.min_col == 1 and mg.max_col == 4
            for mg in ws.merged_cells.ranges
        )
        if not has_merge:
            ws.merge_cells(start_row=target_row, end_row=target_row,
                           start_column=1, end_column=4)
        wset(ws, target_row, 1, f"{i + 1}. {step}")


# ── main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="対応記録.xlsx を生成する（Phase 3 完了後の全シート埋め版）")
    parser.add_argument("--folder",              required=True)
    parser.add_argument("--issue-id",            required=True, dest="issue_id")
    parser.add_argument("--investigation",       required=True, dest="investigation",
                        help="docs/logs/{issueID}/investigation.md のパス")
    parser.add_argument("--approach-plan",       required=True, dest="approach_plan",
                        help="docs/logs/{issueID}/approach-plan.md のパス")
    parser.add_argument("--implementation-plan", required=True, dest="implementation_plan",
                        help="docs/logs/{issueID}/implementation-plan.md のパス")
    args = parser.parse_args()

    if not TEMPLATE.exists():
        print(f"[ERROR] テンプレートが見つかりません: {TEMPLATE}")
        sys.exit(1)

    inv_md  = read_md(args.investigation)
    app_md  = read_md(args.approach_plan)
    impl_md = read_md(args.implementation_plan)

    missing = []
    if not inv_md:
        missing.append(args.investigation)
    if not app_md:
        missing.append(args.approach_plan)
    if not impl_md:
        missing.append(args.implementation_plan)
    if missing:
        print(f"[ERROR] 以下の MD ファイルが見つかりません:\n" + "\n".join(f"  {p}" for p in missing))
        sys.exit(1)

    os.makedirs(args.folder, exist_ok=True)
    try:
        wb = load_workbook(TEMPLATE)
    except Exception as e:
        print(f"[ERROR] テンプレートファイルの読み込みに失敗しました: {TEMPLATE}\n{e}")
        sys.exit(1)

    fill_summary(wb["サマリー・経緯"], args, inv_md, app_md, impl_md)
    fill_pending_decisions(wb["サマリー・経緯"], app_md, impl_md)  # [V-3]
    fill_approach(wb["対応方針"], app_md)
    fill_investigation(wb["調査・影響範囲"], inv_md)
    fill_content(wb["対応内容"], impl_md)
    fill_test(wb["テスト・検証記録"], impl_md)
    fill_release(wb["リリース・ロールバック"], impl_md, app_md)

    path = os.path.join(args.folder, f"{args.issue_id}_対応記録.xlsx")
    try:
        wb.save(path)
    except PermissionError as e:
        print(f"[ERROR] xlsx の保存に失敗しました（ファイルが開かれている可能性があります）: {path}\n{e}")
        sys.exit(1)
    print(f"生成完了: {path}")


if __name__ == "__main__":
    main()
