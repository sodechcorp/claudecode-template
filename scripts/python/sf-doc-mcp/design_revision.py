"""
設計書（機能設計書・画面設計書）共通の差分判定＋改版履歴構築モジュール。

- 前回JSON と 今回JSON を比較し、配列セクション（items, steps, 等）と
  スカラーフィールド（purpose, overview, ...）の差分を抽出する
- 改版履歴の行データを構築する
- セルへの赤字適用ユーティリティを提供する（メジャー更新時は黒へリセット）
"""
from __future__ import annotations

from openpyxl.styles import Font

# 既存ジェネレータと同じ色
RED   = "C00000"
BLACK = "000000"
FONT_NAME = "游ゴシック"


# ── 差分計算 ──────────────────────────────────────────────────
def diff_scalars(old: dict, new: dict, fields: list[str]) -> list[dict]:
    """単純フィールドの差分を返す。
    戻り値: [{"field": "purpose", "old": "...", "new": "..."}]
    """
    out = []
    for f in fields:
        ov = (old or {}).get(f, "") or ""
        nv = (new or {}).get(f, "") or ""
        if ov != nv:
            out.append({"field": f, "old": ov, "new": nv})
    return out


def _list_to_map(items: list[dict], id_field: str | tuple) -> dict:
    """identifier → item マップ。重複IDは最後勝ち。
    id_field が tuple なら各キーの値を "::" でつないだ複合キーにする。"""
    if isinstance(id_field, tuple):
        return {"::".join(str(it.get(k, "")) for k in id_field): it for it in (items or [])}
    return {it.get(id_field): it for it in (items or []) if it.get(id_field) is not None}


def diff_list(old_list: list[dict], new_list: list[dict],
              id_field: str | tuple) -> dict:
    """配列セクションの差分を返す（id_field で突合。1キーで一意にならない一覧は tuple で複合キー）。
    戻り値: {"added": [id,...], "removed": [id,...], "modified": [id,...]}
    modified: 同一ID同士で全キーを比較して差分あり
    """
    om = _list_to_map(old_list, id_field)
    nm = _list_to_map(new_list, id_field)
    added    = [k for k in nm if k not in om]
    removed  = [k for k in om if k not in nm]
    modified = [k for k in nm if k in om and om[k] != nm[k]]
    return {"added": added, "removed": removed, "modified": modified}


def has_any_diff(diffs: dict) -> bool:
    """differences dict に差分が1件でもあるか。"""
    if diffs.get("scalars"):
        return True
    for sec_diff in (diffs.get("lists") or {}).values():
        if sec_diff.get("added") or sec_diff.get("removed") or sec_diff.get("modified"):
            return True
    return False


def changed_ids(diffs: dict, section_key: str) -> set:
    """指定セクションで「追加 or 変更」された識別子のセット（赤字対象）。
    削除はxlsx上に行が存在しないのでマーク不要。
    """
    sec = (diffs.get("lists") or {}).get(section_key, {})
    return set(sec.get("added", [])) | set(sec.get("modified", []))


def changed_scalar_fields(diffs: dict) -> set:
    """差分のあったスカラーフィールド名のセット。"""
    return {s["field"] for s in diffs.get("scalars", [])}


# ── 改版履歴エントリ構築 ─────────────────────────────────────
def build_entries(current_version: str, diffs: dict, author: str,
                  today: str, start_no: int, is_major: bool,
                  is_initial: bool,
                  section_sheet_map: dict[str, str],
                  scalar_sheet: str = "処理概要") -> list[dict]:
    """改版履歴エントリを構築する。
    section_sheet_map: セクションキー → 改版履歴に書く「変更箇所」表示名
                       例: {"items": "画面項目定義", "steps": "処理内容"}
    scalar_sheet: スカラー変更の時の変更箇所表示名
    戻り値: [{項番, 版数, 変更箇所, 変更内容, 変更理由, 変更日, 変更者, 備考}]
    """
    if is_initial:
        return [{
            "項番": start_no, "版数": current_version, "変更箇所": "全シート",
            "変更内容": "新規作成", "変更理由": "初版作成", "変更日": today,
            "変更者": author,
        }]

    if is_major:
        return [{
            "項番": start_no, "版数": current_version, "変更箇所": "全シート",
            "変更内容": "メジャーバージョンアップ（注記リセット）",
            "変更理由": "メジャーバージョンアップ", "変更日": today, "変更者": author,
        }]

    # 変更箇所を集約（シート名のセット）
    areas: set[str] = set()
    for s in diffs.get("scalars", []):
        areas.add(scalar_sheet)
    for sec_key, sec_diff in (diffs.get("lists") or {}).items():
        if any([sec_diff.get("added"), sec_diff.get("removed"), sec_diff.get("modified")]):
            areas.add(section_sheet_map.get(sec_key, sec_key))

    if not areas:
        return [{
            "項番": start_no, "版数": current_version, "変更箇所": "—",
            "変更内容": "変更なし", "変更理由": "設計内容の更新", "変更日": today,
            "変更者": author,
        }]

    # 変更内容を集計して1行に収める
    total_added   = sum(len(sd.get("added", []))    for sd in (diffs.get("lists") or {}).values())
    total_removed = sum(len(sd.get("removed", []))  for sd in (diffs.get("lists") or {}).values())
    total_changed = sum(len(sd.get("modified", [])) for sd in (diffs.get("lists") or {}).values())
    total_changed += len(diffs.get("scalars", []))
    parts = []
    if total_added:   parts.append(f"追加{total_added}件")
    if total_removed: parts.append(f"削除{total_removed}件")
    if total_changed: parts.append(f"変更{total_changed}件")

    return [{
        "項番":     start_no,
        "版数":     current_version,
        "変更箇所": "・".join(sorted(areas)),
        "変更内容": "・".join(parts) if parts else "更新",
        "変更理由": "設計内容の更新",
        "変更日":   today,
        "変更者":   author,
    }]


# ── 赤字マーキング ────────────────────────────────────────────
def apply_red(cell, bold: bool = False, size: int = 10, italic: bool = False):
    """セルのフォントを赤にする（既存の太字/サイズは引数で引き継ぐ）。"""
    cell.font = Font(name=FONT_NAME, bold=bold, color=RED, size=size, italic=italic)


def reset_red_in_range(ws, row_range: tuple[int, int],
                        col_range: tuple[int, int]):
    """指定範囲のセルの赤字を黒にリセット（メジャー更新時）。
    既存の太字・サイズは維持。
    """
    r0, r1 = row_range
    c0, c1 = col_range
    for r in range(r0, r1 + 1):
        for c in range(c0, c1 + 1):
            cell = ws.cell(row=r, column=c)
            fnt = cell.font
            if fnt and fnt.color and fnt.color.rgb and str(fnt.color.rgb).upper().endswith(RED):
                cell.font = Font(
                    name=fnt.name or FONT_NAME,
                    bold=fnt.bold, size=fnt.sz or 10, italic=fnt.italic,
                    color=BLACK,
                )


# ── 改版履歴テーブル書込 ─────────────────────────────────────
def fill_revision_table(ws, history: list[dict], rev_cols: dict,
                        data_row_start: int):
    """改版履歴テーブルに history を書き込む（上から順）。
    rev_cols: {"項番": (cs, ce), ...}
    """
    r = data_row_start
    for h in history:
        for label, (cs, ce) in rev_cols.items():
            ws.cell(row=r, column=cs, value=h.get(label, ""))
        r += 1
