#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
汎用ダイアグラム PNG 生成モジュール（matplotlib ベース）

システム構成図・業務フロー図などに使用。
er_utils.py と同じアーキテクチャ: generate_diagram_image() を呼ぶだけで PNG が生成される。

座標系: PowerPoint 座標系（inch 単位、左上=0,0）
"""
from __future__ import annotations
import math
import os
from typing import Optional

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    from matplotlib.patches import FancyBboxPatch, FancyArrowPatch
    HAS_MPL = True
except ImportError:
    HAS_MPL = False

# ── 日本語フォント ────────────────────────────────────────────────────────────
_JP_REG  = os.environ.get("JAPANESE_FONT_PATH",      "C:/Windows/Fonts/YuGothR.ttc")
_JP_BOLD = os.environ.get("JAPANESE_FONT_PATH_BOLD", "C:/Windows/Fonts/YuGothB.ttc")


def _fpkw(size: float = 10.0, bold: bool = False) -> dict:
    if not HAS_MPL:
        return {}
    try:
        import matplotlib.font_manager as fm
        path = _JP_BOLD if (bold and os.path.exists(_JP_BOLD)) else _JP_REG
        if os.path.exists(path):
            return {"fontproperties": fm.FontProperties(fname=path, size=size)}
    except Exception:
        pass
    return {"fontsize": size}


# ── カラーパレット ────────────────────────────────────────────────────────────
_STYLES: dict[str, dict] = {
    "primary":   {"bg": "#1E3A5F", "fg": "#FFFFFF", "border": "#1E3A5F"},
    "accent":    {"bg": "#E86C00", "fg": "#FFFFFF", "border": "#E86C00"},
    "secondary": {"bg": "#2C6FAC", "fg": "#FFFFFF", "border": "#2C6FAC"},
    "light":     {"bg": "#F0F4F8", "fg": "#1E3A5F", "border": "#AAAAAA"},
    "success":   {"bg": "#1E7E5A", "fg": "#FFFFFF", "border": "#1E7E5A"},
    "warning":   {"bg": "#B85C00", "fg": "#FFFFFF", "border": "#B85C00"},
    "neutral":   {"bg": "#E8EDF2", "fg": "#2D2D2D", "border": "#8090A0"},
}
_GROUP_ALPHA = 0.12  # グループ背景の透明度

SLIDE_W = 13.333
SLIDE_H = 7.5
TITLE_H = 1.10
DPI     = 220


def _hex(s: str) -> tuple:
    s = s.lstrip("#")
    return tuple(int(s[i:i+2], 16) / 255 for i in (0, 2, 4))


def _style(key: str) -> dict:
    return _STYLES.get(key, _STYLES["light"])


# ── ボックス描画 ──────────────────────────────────────────────────────────────

def _draw_box(ax, box: dict, shadow: bool = True) -> dict:
    """ボックスを描画し、辺の中心座標 dict を返す。"""
    x, y, w, h = box["x"], box["y"], box["w"], box["h"]
    sc = _style(box.get("style", "primary"))
    pad = 0.045

    # 影（オフセット矩形）
    if shadow:
        shadow_patch = FancyBboxPatch(
            (x + pad + 0.06, y + pad + 0.06), w - 2 * pad, h - 2 * pad,
            boxstyle=f"round,pad={pad}",
            linewidth=0, edgecolor="none",
            facecolor=(0, 0, 0, 0.13),
            zorder=1,
        )
        ax.add_patch(shadow_patch)

    # 本体
    outer = FancyBboxPatch(
        (x + pad, y + pad), w - 2 * pad, h - 2 * pad,
        boxstyle=f"round,pad={pad}",
        linewidth=1.8,
        edgecolor=_hex(sc["border"]),
        facecolor=_hex(sc["bg"]),
        zorder=2,
    )
    ax.add_patch(outer)

    # テキスト（複数行対応）
    lines = box.get("label", "").split("\n")
    n = len(lines)
    line_h = h / (n + 0.5)
    for i, line in enumerate(lines):
        ty = y + h / (n + 1) * (i + 1)
        fs = 11.0 if (i == 0 or n == 1) else 8.5
        bold = (i == 0 or n == 1)
        ax.text(x + w / 2, ty, line,
                ha="center", va="center",
                color=_hex(sc["fg"]),
                clip_on=True, zorder=3,
                **_fpkw(fs, bold=bold))

    cx, cy = x + w / 2, y + h / 2
    return {
        "x": x, "y": y, "w": w, "h": h,
        "top":    (cx, y),
        "bottom": (cx, y + h),
        "left":   (x, cy),
        "right":  (x + w, cy),
    }


def _draw_group(ax, grp: dict):
    """グループ（背景領域）を描画する。"""
    x, y, w, h = grp["x"], grp["y"], grp["w"], grp["h"]
    sc = _style(grp.get("style", "light"))
    bg = _hex(sc["bg"])
    pad = 0.06

    patch = FancyBboxPatch(
        (x + pad, y + pad), w - 2 * pad, h - 2 * pad,
        boxstyle=f"round,pad={pad}",
        linewidth=1.2,
        linestyle=(0, (6, 3)),
        edgecolor=_hex(sc["border"]),
        facecolor=(*bg, _GROUP_ALPHA),
        zorder=0,
    )
    ax.add_patch(patch)

    if grp.get("label"):
        ax.text(x + 0.20, y + 0.22, grp["label"],
                ha="left", va="top",
                color=_hex(sc["border"]),
                clip_on=True, zorder=1,
                **_fpkw(9.0, bold=True))


# ── 接続辺の座標計算 ──────────────────────────────────────────────────────────

def _side_pt(edge: dict, side: str, frac: float = 0.5) -> tuple:
    x, y, w, h = edge["x"], edge["y"], edge["w"], edge["h"]
    if side == "top":    return (x + w * frac, y)
    if side == "bottom": return (x + w * frac, y + h)
    if side == "left":   return (x,             y + h * frac)
    if side == "right":  return (x + w,         y + h * frac)
    return (x + w / 2, y + h / 2)


def _auto_sides(from_e: dict, to_e: dict) -> tuple[str, str]:
    fx = from_e["x"] + from_e["w"] / 2
    fy = from_e["y"] + from_e["h"] / 2
    tx = to_e["x"]   + to_e["w"] / 2
    ty = to_e["y"]   + to_e["h"] / 2
    dx, dy = tx - fx, ty - fy
    if abs(dx) >= abs(dy):
        return ("right" if dx > 0 else "left", "left" if dx > 0 else "right")
    else:
        return ("bottom" if dy > 0 else "top", "top" if dy > 0 else "bottom")


# ── 矢印描画 ──────────────────────────────────────────────────────────────────

def _route_line_d(x1: float, y1: float, side_from: str,
                   x2: float, y2: float, side_to: str) -> list:
    """直交折れ線ルート（L字 or Z字）を計算する。"""
    if side_from in ("left", "right"):
        mid_x = (x1 + x2) / 2
        return [(x1, y1), (mid_x, y1), (mid_x, y2), (x2, y2)]
    else:
        mid_y = (y1 + y2) / 2
        return [(x1, y1), (x1, mid_y), (x2, mid_y), (x2, y2)]


def _draw_arrowhead(ax, p_near: tuple, p_tip: tuple, color: str,
                     scale: float = 14.0, zorder: int = 5):
    """p_near → p_tip 方向に矢印ヘッドだけ描画する。"""
    ax.annotate(
        "", xy=p_tip, xytext=p_near,
        arrowprops=dict(
            arrowstyle="-|>",
            color=_hex(color),
            mutation_scale=scale,
            lw=0,
            fc=_hex(color),
        ),
        zorder=zorder,
    )


def _draw_arrow(ax, edges: dict, arrow: dict):
    src_id = arrow.get("from")
    dst_id = arrow.get("to")
    src = edges.get(src_id)
    dst = edges.get(dst_id)
    if not src or not dst:
        return

    side_from = arrow.get("side_from")
    side_to   = arrow.get("side_to")
    sf_frac   = arrow.get("side_from_frac", 0.5)
    st_frac   = arrow.get("side_to_frac",   0.5)

    if side_from and side_to:
        x1, y1 = _side_pt(src, side_from, sf_frac)
        x2, y2 = _side_pt(dst, side_to,   st_frac)
    else:
        side_from, side_to = _auto_sides(src, dst)
        x1, y1 = _side_pt(src, side_from)
        x2, y2 = _side_pt(dst, side_to)

    style = arrow.get("arrow_style", "")
    color = "#1E3A5F" if style == "primary" else "#6080A0"
    lw    = 2.2 if style == "primary" else 1.5

    # 直交折れ線ルート（FancyArrowPatch の代わりに折れ線 + 矢印ヘッド）
    pts = _route_line_d(x1, y1, side_from, x2, y2, side_to)
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    ax.plot(xs, ys, color=_hex(color), linewidth=lw, zorder=4,
            solid_capstyle="round", solid_joinstyle="round")

    # 矢印ヘッド（終点）
    _draw_arrowhead(ax, pts[-2], pts[-1], color, zorder=5)

    # 双方向の場合は始点にも矢印ヘッド
    if arrow.get("bidirectional") and len(pts) >= 2:
        _draw_arrowhead(ax, pts[1], pts[0], color, zorder=5)

    # ラベル（中間セグメントの中点に配置）
    label = arrow.get("label", "")
    if label:
        mi = len(pts) // 2
        mx = (pts[mi - 1][0] + pts[mi][0]) / 2
        my = (pts[mi - 1][1] + pts[mi][1]) / 2
        if abs(pts[mi][1] - pts[mi - 1][1]) < 0.01:
            my -= 0.18
        else:
            mx += 0.18
        ax.text(mx, my, label,
                ha="center", va="center",
                color=_hex("#2D2D2D"),
                bbox=dict(boxstyle="round,pad=0.08", facecolor="white",
                          edgecolor=_hex("#CCCCCC"), linewidth=0.8),
                zorder=5, **_fpkw(7.5))


# ── メイン生成関数 ─────────────────────────────────────────────────────────────

def generate_diagram_image(boxes: list, arrows: list, out_path: str,
                            title: str = "",
                            groups: Optional[list] = None,
                            slide_w: float = SLIDE_W,
                            slide_h: float = SLIDE_H) -> bool:
    """ダイアグラムを PNG で出力する。

    Returns:
        True=成功 / False=matplotlib 未インストール
    """
    if not HAS_MPL:
        return False

    fig, ax = plt.subplots(figsize=(slide_w, slide_h), dpi=DPI)
    fig.subplots_adjust(left=0, right=1, top=1, bottom=0)
    ax.set_xlim(0, slide_w)
    ax.set_ylim(slide_h, 0)
    ax.axis("off")
    fig.patch.set_facecolor("white")
    ax.set_facecolor("white")

    # タイトルバー
    ax.add_patch(mpatches.Rectangle(
        (0, 0), slide_w, TITLE_H,
        linewidth=0, facecolor=_hex("#1E3A5F"), zorder=10,
    ))
    if title:
        ax.text(0.55, TITLE_H / 2, title,
                ha="left", va="center", color="white",
                zorder=11, **_fpkw(16.0, bold=True))

    # グループ（背景）→ ボックス → 矢印 の順
    for grp in (groups or []):
        _draw_group(ax, grp)

    edges: dict[str, dict] = {}
    for box in boxes:
        edge = _draw_box(ax, box)
        edges[box["id"]] = edge

    for arrow in arrows:
        _draw_arrow(ax, edges, arrow)

    fig.savefig(out_path, dpi=DPI, bbox_inches=None,
                facecolor="white", pad_inches=0)
    plt.close(fig)
    return True


# ====================================================================
# ドメイン設計書向け図形生成（業務フロー・画面遷移・コンポーネント依存）
# ====================================================================

try:
    import networkx as _nx
    _HAS_NX = True
except ImportError:
    _HAS_NX = False

from collections import OrderedDict as _OrderedDict

# ── 色定数 ──────────────────────────────────────────────────────
_COMP_COLORS = {
    "Apex":    "#4472C4",
    "LWC":     "#70AD47",
    "Flow":    "#ED7D31",
    "Aura":    "#7030A0",
    "Trigger": "#4472C4",
}
_COMP_DEFAULT_COLOR = "#808080"
_LANE_COLORS = ["#EBF5FB", "#FFFFFF"]


def _dom_wrap(text: str, limit: int = 14) -> str:
    """limit 文字を目安に折り返す。"""
    if not text:
        return ""
    out: list[str] = []
    for para in text.split("\n"):
        line = ""
        for ch in para:
            line += ch
            if len(line) >= limit:
                out.append(line)
                line = ""
        if line:
            out.append(line)
    return "\n".join(out)


# ================================================================
# 1. 業務フロー図（スイムレーン横レーン形式）
# ================================================================
def generate_business_flow_diagram(
    flows: list[dict],
    out_path: str,
    fig_w: float = 12,
) -> bool:
    """スイムレーン図を生成する。

    flows: [{"step": "1", "actor": "営業担当者", "action": "見積依頼を入力",
             "system": "QuotationRequestPage"}]
    戻り値: True(成功) / False(失敗)
    """
    if not HAS_MPL or not flows:
        return False

    # アクターごとにステップをグループ化（出現順を維持）
    actor_steps: _OrderedDict[str, list[dict]] = _OrderedDict()
    for f in flows:
        actor = f.get("actor", "不明")
        actor_steps.setdefault(actor, []).append(f)

    actors = list(actor_steps.keys())

    # レイアウト定数
    lane_h = 1.2
    label_w = 2.5
    box_w = 2.8
    box_h = 0.7

    # レーンごとの高さを計算
    lane_heights: list[float] = []
    for actor in actors:
        steps = actor_steps[actor]
        h = max(1.5, len(steps) * lane_h + 0.3)
        lane_heights.append(h)

    total_h = sum(lane_heights) + 0.6
    fig, ax = plt.subplots(figsize=(fig_w, total_h))
    ax.set_xlim(0, fig_w)
    ax.set_ylim(0, total_h)
    ax.axis("off")
    fig.patch.set_facecolor("white")

    y_top = total_h - 0.3
    step_positions: list[tuple[float, float]] = []

    for lane_idx, actor in enumerate(actors):
        lh = lane_heights[lane_idx]
        y_bot = y_top - lh

        # レーン背景
        bg_color = _LANE_COLORS[lane_idx % 2]
        ax.add_patch(FancyBboxPatch(
            (0, y_bot), fig_w, lh,
            boxstyle="square,pad=0",
            facecolor=bg_color, edgecolor="#CCCCCC", linewidth=0.5,
        ))
        ax.plot([0, fig_w], [y_bot, y_bot], color="#BBBBBB", linewidth=0.8)

        # アクターラベル
        ax.text(
            label_w / 2, (y_top + y_bot) / 2, _dom_wrap(actor, 8),
            ha="center", va="center", fontsize=9,
            color=_hex("#1F3864"),
            **_fpkw(9.0, bold=True),
        )
        ax.plot([label_w, label_w], [y_bot, y_top], color="#BBBBBB", linewidth=0.8)

        # ステップ描画
        steps = actor_steps[actor]
        content_w = fig_w - label_w - 0.5
        cx = label_w + content_w / 2
        n_steps = len(steps)
        step_area_h = lh - 0.3
        actual_lane_h = step_area_h / max(n_steps, 1)

        for si, step in enumerate(steps):
            cy = y_top - 0.15 - actual_lane_h * si - actual_lane_h / 2

            ax.add_patch(FancyBboxPatch(
                (cx - box_w / 2, cy - box_h / 2), box_w, box_h,
                boxstyle="round,pad=0.05,rounding_size=0.1",
                facecolor="#DEEAF1", edgecolor="#6A8CAF", linewidth=1.0,
            ))

            step_no = step.get("step", "")
            action = step.get("action", "")
            label_text = f"{step_no}. {action}" if step_no else action
            ax.text(cx, cy + 0.02, _dom_wrap(label_text, 18),
                    ha="center", va="center", fontsize=7.5,
                    color="black", **_fpkw(7.5))

            system = step.get("system", "")
            if system:
                ax.text(cx, cy - box_h / 2 - 0.08, system,
                        ha="center", va="top", fontsize=6, color="#808080",
                        **_fpkw(6.0))

            step_positions.append((cx, cy))

        y_top = y_bot

    # ステップ間の矢印
    for i in range(len(step_positions) - 1):
        x0, y0 = step_positions[i]
        x1, y1 = step_positions[i + 1]
        ax.annotate(
            "", xy=(x1, y1 + box_h / 2 + 0.02),
            xytext=(x0, y0 - box_h / 2 - 0.02),
            arrowprops=dict(arrowstyle="->", color="#444444", lw=1.2,
                            shrinkA=0, shrinkB=0),
        )

    plt.tight_layout(pad=0.2)
    plt.savefig(out_path, dpi=96, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return True


# ================================================================
# 2. 画面遷移図（スネーク型レイアウト・番号バッジ付き）
# ================================================================
def generate_screen_transition_diagram(
    screens: list[dict],
    out_path: str,
    fig_w: float = 14,
    transitions: list[dict] | None = None,
) -> bool:
    """画面遷移図を生成する（スネーク型レイアウト）。

    screens: [{"name": "見積一覧", "component": "QuotationList",
               "transitions_to": ["見積入力画面"]}]
    transitions: [{"from": "A", "to": "B", "label": "条件"}]
        指定された場合、transitions_to より優先してエッジを構築する。
    transitions_to が未指定の場合、screens リストの順番通りに自動連結する。
    戻り値: True(成功) / False(失敗)
    """
    if not HAS_MPL or not screens:
        return False

    from matplotlib.patches import Circle as _Circle

    # 全ノードを収集（順序維持）
    screen_map: dict[str, dict] = {}
    all_nodes: list[str] = []
    edges: list[tuple[str, str, str]] = []  # (from, to, label)

    for s in screens:
        name = s.get("name", "")
        if not name:
            continue
        screen_map[name] = s
        if name not in all_nodes:
            all_nodes.append(name)

    if transitions:
        # transitions パラメータが指定された場合はそれを使う
        for t in transitions:
            fr = t.get("from", "")
            to = t.get("to", "")
            label = t.get("label", "")
            if fr and to:
                if fr not in all_nodes:
                    all_nodes.append(fr)
                if to not in all_nodes:
                    all_nodes.append(to)
                edges.append((fr, to, label))
    else:
        # transitions_to が1件でも指定されているか判定
        has_explicit_transitions = any(
            s.get("transitions_to") for s in screens
        )

        if has_explicit_transitions:
            # 明示的遷移を使う
            for s in screens:
                name = s.get("name", "")
                for target in s.get("transitions_to", []):
                    if target:
                        if target not in all_nodes:
                            all_nodes.append(target)
                        if name:
                            edges.append((name, target, ""))
        else:
            # 未指定: リスト順で自動連結
            for i in range(len(all_nodes) - 1):
                edges.append((all_nodes[i], all_nodes[i + 1], ""))

    if not all_nodes:
        return False

    # スネーク型レイアウト（1行最大3画面、左→右→左→右）
    n = len(all_nodes)
    cols_per_row = 3
    n_rows = (n + cols_per_row - 1) // cols_per_row

    box_w_sc, box_h_sc = 3.0, 0.85
    margin_x = 1.5
    margin_top = 0.8
    row_step = 2.0
    usable_w = fig_w - 2 * margin_x
    col_step = usable_w / max(cols_per_row - 1, 1) if cols_per_row > 1 else 0

    fig_h = margin_top + n_rows * row_step + 0.8

    node_pos: dict[str, tuple[float, float]] = {}
    node_order: dict[str, int] = {}
    for i, name in enumerate(all_nodes):
        row_idx = i // cols_per_row
        col_idx = i % cols_per_row
        # 偶数行: 左→右、奇数行: 右→左
        if row_idx % 2 == 1:
            col_idx = cols_per_row - 1 - col_idx
        cx = margin_x + col_step * col_idx
        cy = fig_h - margin_top - row_step * row_idx
        node_pos[name] = (cx, cy)
        node_order[name] = i + 1

    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    ax.axis("off")
    ax.set_xlim(0, fig_w)
    ax.set_ylim(0, fig_h)
    fig.patch.set_facecolor("white")

    # エッジ描画（青い矢印 + ラベル）
    _ARROW_COLOR = "#2E75B6"
    for u, v, elabel in edges:
        if u not in node_pos or v not in node_pos:
            continue
        x0, y0 = node_pos[u]
        x1, y1 = node_pos[v]
        ax.annotate(
            "", xy=(x1, y1), xytext=(x0, y0),
            arrowprops=dict(
                arrowstyle="-|>", color=_ARROW_COLOR, lw=1.5,
                connectionstyle="arc3,rad=0.12",
                shrinkA=max(box_w_sc, box_h_sc) * 18,
                shrinkB=max(box_w_sc, box_h_sc) * 18,
                mutation_scale=14,
            ),
        )
        if elabel:
            mx = (x0 + x1) / 2
            my = (y0 + y1) / 2
            ax.text(mx, my, elabel,
                    ha="center", va="bottom", fontsize=7.5,
                    color="#C55A11", **_fpkw(7.5, bold=True),
                    bbox=dict(boxstyle="round,pad=0.2", facecolor="#FFF2CC",
                              edgecolor="#C55A11", linewidth=0.8, alpha=0.9))

    # ノード描画
    badge_r = 0.22
    for name, (cx, cy) in node_pos.items():
        # 角丸四角形
        ax.add_patch(FancyBboxPatch(
            (cx - box_w_sc / 2, cy - box_h_sc / 2), box_w_sc, box_h_sc,
            boxstyle="round,pad=0.06,rounding_size=0.12",
            facecolor="#DEEAF1", edgecolor="#4472C4", linewidth=1.3,
        ))
        # 画面名
        ax.text(cx, cy + 0.08, _dom_wrap(name, 14),
                ha="center", va="center", fontsize=8.5,
                color=_hex("#1F3864"), **_fpkw(8.5, bold=True))
        # コンポーネント名（小さくグレー）
        comp = screen_map.get(name, {}).get("component", "")
        if comp:
            ax.text(cx, cy - 0.22, comp,
                    ha="center", va="center", fontsize=6.5, color="#808080",
                    **_fpkw(6.5))

        # 番号バッジ（左上に青丸+白数字）
        num = node_order.get(name, 0)
        badge_cx = cx - box_w_sc / 2 - badge_r * 0.3
        badge_cy = cy + box_h_sc / 2 + badge_r * 0.3
        badge = _Circle((badge_cx, badge_cy), badge_r,
                         facecolor=_ARROW_COLOR, edgecolor="white",
                         linewidth=1.2, zorder=10)
        ax.add_patch(badge)
        # 丸数字（unicode）または番号テキスト
        num_labels = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"
        num_text = num_labels[num - 1] if 1 <= num <= 20 else str(num)
        ax.text(badge_cx, badge_cy, num_text,
                ha="center", va="center", fontsize=8,
                color="white", zorder=11, **_fpkw(8.0, bold=True))

    plt.tight_layout(pad=0.3)
    plt.savefig(out_path, dpi=96, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return True


# ================================================================
# 3. コンポーネント依存関係図（純matplotlib実装・networkx不要）
# ================================================================
def generate_component_diagram(
    components: list[dict],
    out_path: str,
    fig_w: float = 10,
) -> bool:
    """コンポーネント依存関係図を生成する（LWC上段・Apex下段レイアウト）。

    components: [{"api_name": "QuotationCtrl", "type": "Apex",
                  "role": "...", "callees": ["QuotationService"]}]
    戻り値: True(成功) / False(失敗)
    """
    if not HAS_MPL or not components:
        return False

    # ノード収集
    comp_type_map: dict[str, str] = {}
    all_nodes: list[str] = []
    edges: list[tuple[str, str]] = []

    for c in components:
        api = c.get("api_name", "")
        if not api:
            continue
        ctype = c.get("type", "")
        comp_type_map[api] = ctype
        if api not in all_nodes:
            all_nodes.append(api)
        for target in c.get("callees", []):
            if target:
                if target not in all_nodes:
                    all_nodes.append(target)
                edges.append((api, target))
                if target not in comp_type_map:
                    comp_type_map[target] = ""

    if not all_nodes:
        return False

    # LWC/Aura を上段、Apex/Trigger/Flow/Other を下段に分類
    _TOP_TYPES = {"LWC", "Aura"}
    top_nodes = [n for n in all_nodes if comp_type_map.get(n, "") in _TOP_TYPES]
    bot_nodes = [n for n in all_nodes if comp_type_map.get(n, "") not in _TOP_TYPES]

    # どちらかが空なら caller/callee で分割にフォールバック
    if not top_nodes or not bot_nodes:
        caller_set = {u for u, _ in edges}
        top_nodes = [n for n in all_nodes if n in caller_set]
        bot_nodes = [n for n in all_nodes if n not in caller_set]

    n_nodes = len(all_nodes)
    fig_w = min(10, max(6, n_nodes * 1.8))
    fig_h = max(5, fig_w * 0.65)
    margin = 1.0
    box_w_cp, box_h_cp = 2.2, 0.7

    def _row_positions(nodes: list[str], y: float) -> dict[str, tuple[float, float]]:
        n = len(nodes)
        if n == 0:
            return {}
        span = fig_w - 2 * margin
        gap = span / max(n, 1)
        result = {}
        for i, name in enumerate(nodes):
            cx = margin + gap * i + gap / 2
            result[name] = (cx, y)
        return result

    node_pos: dict[str, tuple[float, float]] = {}
    node_pos.update(_row_positions(top_nodes, fig_h * 0.68))
    node_pos.update(_row_positions(bot_nodes, fig_h * 0.28))

    fig, ax = plt.subplots(figsize=(fig_w, fig_h))
    ax.axis("off")
    ax.set_xlim(0, fig_w)
    ax.set_ylim(0, fig_h)
    fig.patch.set_facecolor("white")

    # 分割線
    ax.plot([0.2, fig_w - 0.2], [fig_h * 0.48, fig_h * 0.48],
            color="#CCCCCC", linewidth=0.8, linestyle="--")

    # エッジ描画
    for u, v in edges:
        x0, y0 = node_pos[u]
        x1, y1 = node_pos[v]
        ax.annotate(
            "", xy=(x1, y1), xytext=(x0, y0),
            arrowprops=dict(
                arrowstyle="-|>", color="#666666", lw=1.2,
                connectionstyle="arc3,rad=0.12",
                shrinkA=max(box_w_cp, box_h_cp) * 16,
                shrinkB=max(box_w_cp, box_h_cp) * 16,
            ),
        )

    # ノード描画
    for name, (cx, cy) in node_pos.items():
        ctype = comp_type_map.get(name, "")
        color = _COMP_COLORS.get(ctype, _COMP_DEFAULT_COLOR)
        ax.add_patch(FancyBboxPatch(
            (cx - box_w_cp / 2, cy - box_h_cp / 2), box_w_cp, box_h_cp,
            boxstyle="round,pad=0.06,rounding_size=0.10",
            facecolor=color, edgecolor="#333333", linewidth=1.2,
            alpha=0.88,
        ))
        ax.text(cx, cy, _dom_wrap(name, 16),
                ha="center", va="center",
                color="white", **_fpkw(8.0, bold=True))

    # 凡例（左下、見やすく）
    legend_items = [
        ("Apex", _COMP_COLORS["Apex"]),
        ("LWC", _COMP_COLORS["LWC"]),
        ("Flow", _COMP_COLORS["Flow"]),
        ("Aura", _COMP_COLORS["Aura"]),
        ("Other", _COMP_DEFAULT_COLOR),
    ]
    legend_x = 0.5
    legend_y = 0.4
    for i, (label, color) in enumerate(legend_items):
        lx = legend_x + i * 1.6
        ax.add_patch(FancyBboxPatch(
            (lx, legend_y - 0.12), 0.45, 0.24,
            boxstyle="round,pad=0.02",
            facecolor=color, edgecolor="#333333", linewidth=0.6,
            alpha=0.88,
        ))
        ax.text(lx + 0.58, legend_y, label,
                ha="left", va="center", fontsize=7.5, color="#333333",
                **_fpkw(7.5))

    plt.tight_layout(pad=0.3)
    plt.savefig(out_path, dpi=96, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return True


# ================================================================
# 4. スイムレーン図（詳細設計書 — 業務フロー用）— 縦型
# ================================================================
def generate_swimlane_diagram(
    business_flow: list[dict],
    out_path: str,
) -> bool:
    """縦型スイムレーン図を生成する（詳細設計書 業務フロー用）。

    アクターを列ヘッダーとして横に並べ、ステップを上から下に流す。
    各ステップはそのアクターの列に配置し、next の矢印で結ぶ。

    business_flow: [{"step": 1, "actor": "お客様", "action": "...",
                     "next": [{"condition": "...", "to": 2}]}]
    """
    if not HAS_MPL or not business_flow:
        return False

    # アクター抽出（出現順・重複除去）
    unique_actors: list[str] = []
    for step in business_flow:
        a = step.get("actor", "")
        if a and a not in unique_actors:
            unique_actors.append(a)

    n_actors = len(unique_actors)
    n_steps = len(business_flow)

    col_w = 2.2   # 1アクターの列幅（縦長になるよう狭く）
    row_h = 2.5   # 1ステップの行高さ（縦方向に余裕を持たせる）
    header_h = 0.8  # アクターヘッダーの高さ
    margin = 0.5

    fig_w = n_actors * col_w + margin * 2
    fig_h = n_steps * row_h + header_h + margin * 2

    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=96)
    ax.set_xlim(0, fig_w)
    ax.set_ylim(fig_h, 0)  # Y軸反転（上が0）
    ax.axis("off")
    fig.patch.set_facecolor("white")

    # アクター列の色
    actor_colors = {
        "お客様": "#D9E1F2",
        "顧客": "#D9E1F2",
        "ユーザー": "#D9E1F2",
        "システム": "#E2EFDA",
        "System": "#E2EFDA",
        "GFコンサル": "#FFF2CC",
    }
    default_color = "#F2F2F2"

    def _get_actor_color(actor: str) -> str:
        if actor in actor_colors:
            return actor_colors[actor]
        if "システム" in actor or "system" in actor.lower():
            return "#E2EFDA"
        return default_color

    # 列の背景帯を描画
    for i, actor in enumerate(unique_actors):
        x = margin + i * col_w
        color = _get_actor_color(actor)
        rect = mpatches.Rectangle((x, header_h), col_w, fig_h - header_h,
                                   fc=color, ec="none", alpha=0.3, zorder=0)
        ax.add_patch(rect)

    # アクターヘッダー
    for i, actor in enumerate(unique_actors):
        x_center = margin + i * col_w + col_w / 2
        color = _get_actor_color(actor)
        rect = FancyBboxPatch(
            (margin + i * col_w + 0.1, 0.05),
            col_w - 0.2, header_h - 0.1,
            boxstyle="round,pad=0.05",
            fc=color, ec="#8B9DC3", linewidth=1.2, zorder=1
        )
        ax.add_patch(rect)
        ax.text(x_center, header_h / 2, actor,
                ha="center", va="center", zorder=2,
                **_fpkw(9.0, bold=True))

    # ステップボックスの座標を計算
    box_w_s, box_h_s = col_w - 0.4, row_h - 0.6
    step_pos: dict[int, tuple[float, float]] = {}
    for idx, item in enumerate(business_flow):
        step_no = item.get("step", idx + 1)
        actor = item.get("actor", "")
        col_idx = unique_actors.index(actor) if actor in unique_actors else 0
        x_center = margin + col_idx * col_w + col_w / 2
        y_center = header_h + margin * 0.5 + idx * row_h + row_h / 2
        step_pos[step_no] = (x_center, y_center)

        # ボックス描画
        rect = FancyBboxPatch(
            (x_center - box_w_s / 2, y_center - box_h_s / 2),
            box_w_s, box_h_s,
            boxstyle="round,pad=0.1",
            fc="white", ec="#1F3864", linewidth=1.2, zorder=3
        )
        ax.add_patch(rect)

        # ステップ番号
        ax.text(x_center - box_w_s / 2 + 0.15, y_center - box_h_s / 2 + 0.15,
                f"{step_no}", color="#1F3864",
                ha="left", va="top", zorder=4,
                **_fpkw(7.0, bold=True))

        # アクション（折り返し）
        action = item.get("action", "")
        ax.text(x_center, y_center, _dom_wrap(action, 14),
                ha="center", va="center", zorder=4,
                multialignment="center",
                **_fpkw(8.0))

    # 矢印
    for item in business_flow:
        step_no = item.get("step")
        nexts = item.get("next", [])
        if not step_no or not nexts or step_no not in step_pos:
            continue
        x1, y1 = step_pos[step_no]

        for nxt in nexts:
            to_step = nxt.get("to")
            condition = nxt.get("condition", "")
            if not to_step or to_step not in step_pos:
                continue
            x2, y2 = step_pos[to_step]

            # 矢印の始点・終点（ボックスの端）
            y_start = y1 + box_h_s / 2
            y_end = y2 - box_h_s / 2

            rad = 0.0 if abs(x2 - x1) < 0.1 else 0.2
            ax.annotate("", xy=(x2, y_end), xytext=(x1, y_start),
                        arrowprops=dict(
                            arrowstyle="->",
                            color="#1F3864",
                            lw=1.2,
                            connectionstyle=f"arc3,rad={rad}"
                        ), zorder=5)

            if condition:
                mx = (x1 + x2) / 2
                my = (y_start + y_end) / 2
                ax.text(mx + 0.1, my, condition,
                        ha="left", va="center",
                        color="#C00000",
                        bbox=dict(fc="white", ec="none", pad=1),
                        zorder=6,
                        **_fpkw(7.0, bold=True))

    fig.tight_layout(pad=0.3)
    fig.savefig(out_path, dpi=96, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return True


# ================================================================
# 5. フローチャート（詳細設計書 — 処理概要用）
# ================================================================
def generate_flowchart(
    process_steps: list[dict],
    out_path: str,
    fig_w: float = 10,
) -> bool:
    """処理フローチャートを生成する（詳細設計書 処理概要用）。

    process_steps: [{"step": 1, "title": "処理名", "description": "説明",
                     "component": "ControllerName", "branch": null,
                     "next": [{"condition": null, "to": 2}]}]
    """
    if not HAS_MPL or not process_steps:
        return False

    from matplotlib.patches import Polygon

    n_steps = len(process_steps)
    y_gap = 1.8
    fig_h = max(5, n_steps * y_gap + 1.5)
    fig_w_adj = 7  # スイムレーン図と同程度の幅に合わせる

    center_x = fig_w_adj / 2

    fig, ax = plt.subplots(figsize=(fig_w_adj, fig_h), dpi=96)
    ax.set_xlim(0, fig_w_adj)
    ax.set_ylim(fig_h, 0)  # Y軸反転
    ax.axis("off")
    fig.patch.set_facecolor("white")

    # ステップ位置
    step_positions: dict[int, tuple[float, float]] = {}
    step_is_branch: dict[int, bool] = {}
    box_w, box_h = 3.0, 0.9
    diamond_w, diamond_h = 2.0, 0.7

    for idx, ps in enumerate(process_steps):
        step_no = ps.get("step", idx + 1)
        cy = idx * y_gap + 1.2
        step_positions[step_no] = (center_x, cy)
        step_is_branch[step_no] = bool(ps.get("branch"))

    # 描画
    for idx, ps in enumerate(process_steps):
        step_no = ps.get("step", idx + 1)
        title = ps.get("title", "")
        component = ps.get("component", "")
        is_branch = bool(ps.get("branch"))
        cx, cy = step_positions[step_no]

        # ボックス表示: [step] title (component)
        label_text = f"[{step_no}] {title}"

        if is_branch:
            # 菱形（ダイヤモンド）
            pts = [
                [cx, cy - diamond_h / 2],  # top
                [cx + diamond_w / 2, cy],   # right
                [cx, cy + diamond_h / 2],   # bottom
                [cx - diamond_w / 2, cy],   # left
            ]
            diamond = Polygon(pts, closed=True,
                              facecolor="#FFF2CC", edgecolor="#C55A11",
                              linewidth=1.2, zorder=2)
            ax.add_patch(diamond)
            ax.text(cx, cy, _dom_wrap(label_text, 14),
                    ha="center", va="center",
                    color="#1F3864", zorder=3,
                    **_fpkw(8.0, bold=True))
        else:
            # 長方形Box
            ax.add_patch(FancyBboxPatch(
                (cx - box_w / 2, cy - box_h / 2), box_w, box_h,
                boxstyle="round,pad=0.05,rounding_size=0.1",
                facecolor="#D9E1F2", edgecolor="#2E75B6", linewidth=1.2,
                zorder=2,
            ))
            main_text = _dom_wrap(label_text, 18)
            if component:
                main_text += f"\n({component})"
            ax.text(cx, cy, main_text,
                    ha="center", va="center",
                    color="#1F3864", zorder=3,
                    **_fpkw(8.0))

    # 矢印
    for ps in process_steps:
        step_no = ps.get("step", 0)
        nexts = ps.get("next", [])
        is_branch = bool(ps.get("branch"))
        if step_no not in step_positions:
            continue
        cx0, cy0 = step_positions[step_no]

        for ni, nxt in enumerate(nexts):
            to_step = nxt.get("to")
            condition = nxt.get("condition", "")
            if to_step is None or to_step not in step_positions:
                continue
            cx1, cy1 = step_positions[to_step]

            if is_branch and len(nexts) > 1:
                if ni == 0:
                    # 1件目: 真下に矢印、conditionラベルを左に表示
                    y_from = cy0 + diamond_h / 2 + 0.05
                    y_to = cy1 - box_h / 2 - 0.05
                    ax.annotate(
                        "", xy=(cx1, y_to), xytext=(cx0, y_from),
                        arrowprops=dict(arrowstyle="-|>", color="#1F3864",
                                        lw=1.3, mutation_scale=12),
                        zorder=4,
                    )
                    if condition:
                        my = (y_from + y_to) / 2
                        ax.text(cx0 - 0.3, my, condition,
                                ha="right", va="center", fontsize=8,
                                color="#333333",
                                bbox=dict(boxstyle="round,pad=0.2",
                                          fc="white", ec="none"))
                else:
                    # 2件目: 菱形の右端→右→下→左 の折れ線矢印
                    # conditionラベルを右に表示
                    offset_x = 1.5 + ni * 0.3  # 複数の折れ線が重ならないようオフセット
                    mid_x = cx0 + diamond_w / 2 + offset_x
                    pts_line = [
                        (cx0 + diamond_w / 2, cy0),
                        (mid_x, cy0),
                        (mid_x, cy1),
                        (cx1 + box_w / 2 + 0.05, cy1),
                    ]
                    xs = [p[0] for p in pts_line]
                    ys = [p[1] for p in pts_line]
                    ax.plot(xs, ys, color="#1F3864", linewidth=1.3, zorder=1)
                    ax.annotate(
                        "", xy=pts_line[-1], xytext=pts_line[-2],
                        arrowprops=dict(arrowstyle="-|>", color="#1F3864",
                                        lw=1.3, mutation_scale=12),
                        zorder=4,
                    )
                    if condition:
                        lx = mid_x + 0.15
                        ly = (cy0 + cy1) / 2
                        ax.text(lx, ly, condition,
                                ha="left", va="center", fontsize=8,
                                color="#333333",
                                bbox=dict(boxstyle="round,pad=0.2",
                                          fc="white", ec="none"))
            else:
                # 通常の下向き矢印
                y_from = cy0 + (diamond_h / 2 if is_branch else box_h / 2) + 0.05
                y_to = cy1 - (diamond_h / 2 if step_is_branch.get(to_step) else box_h / 2) - 0.05
                ax.annotate(
                    "", xy=(cx1, y_to), xytext=(cx0, y_from),
                    arrowprops=dict(arrowstyle="-|>", color="#1F3864",
                                    lw=1.3, mutation_scale=12),
                    zorder=4,
                )
                if condition:
                    my = (y_from + y_to) / 2
                    ax.text(cx0 + 0.3, my, condition,
                            ha="left", va="center", fontsize=8,
                            color="#333333",
                            bbox=dict(boxstyle="round,pad=0.2",
                                      fc="white", ec="none"))

    plt.tight_layout(pad=0.3)
    plt.savefig(out_path, dpi=96, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return True


# ── LWC ワイヤーフレーム生成 ─────────────────────────────────────────────────
import re

# ── LWC HTML → SLDS 静的 HTML 変換 + Playwright ワイヤーフレーム ───────────────

def _template_to_div(attrs: str) -> str:
    """lwc:if/else 分岐に応じて div を生成する。else 系は非表示にする。"""
    if re.search(r'\blwc:elseif\b', attrs) or re.search(r'\blwc:else\b', attrs):
        return '<div style="display:none">'
    return '<div>'


def _lwc_html_to_slds(html_content: str) -> tuple[str, bool]:
    """LWC HTML を SLDS スタイルの静的 HTML に変換する。返り値は (body_html, is_modal)。"""
    html = html_content

    # 1. モーダル判定
    is_modal = bool(re.search(r'<lightning-modal-header', html, re.I))

    # 2. <template> タグを <div> に変換（条件分岐は先頭のみ表示）
    html = re.sub(r'<template\b([^>]*)>', lambda m: _template_to_div(m.group(1)), html, flags=re.DOTALL)
    html = re.sub(r'</template>', '</div>', html)

    # 3. LWC属性を除去
    html = re.sub(r'\s+lwc:[a-zA-Z:]+(?:=[^\s>]*)?', '', html)
    html = re.sub(r'\s+for:[a-zA-Z]+(?:=[^\s>]*)?', '', html)
    html = re.sub(r'\s+key=\{[^}]+\}', '', html)

    # 4. バインディング式の変換
    html = re.sub(r'\s+\w[\w-]*=\{[^}]+\}', '', html)  # 属性値のバインディング
    html = re.sub(r'\{[^}]+\}', '(データ)', html)       # テキスト内のバインディング

    # 5. LWCコンポーネントの SLDS HTML 変換

    # lightning-modal-header
    def _modal_header(m):
        label = m.group(1) or m.group(2) or ""
        return f'<div class="slds-modal__header"><h2 class="slds-text-heading_medium">{label}</h2></div>'
    html = re.sub(
        r'<(?:c-)?lightning-modal-header\b[^>]*?label\s*=\s*(?:"([^"]*)"|\'([^\']*)\')[^>]*/?>',
        _modal_header, html, flags=re.DOTALL)
    html = re.sub(r'<(?:c-)?lightning-modal-header\b[^>]*/?\s*>', '', html)

    # lightning-modal-body
    html = re.sub(r'<(?:c-)?lightning-modal-body\b[^>]*>', '<div class="slds-modal__content slds-p-around_medium">', html)
    html = re.sub(r'</(?:c-)?lightning-modal-body>', '</div>', html)

    # lightning-modal-footer
    html = re.sub(r'<(?:c-)?lightning-modal-footer\b[^>]*>', '<div class="slds-modal__footer">', html)
    html = re.sub(r'</(?:c-)?lightning-modal-footer>', '</div>', html)

    # lightning-card
    def _card(m):
        attrs = m.group(1)
        tm = re.search(r'title\s*=\s*(?:"([^"]*)"|\'([^\']*)\')' , attrs)
        title = (tm.group(1) or tm.group(2)) if tm else ""
        return (f'<div class="slds-card"><div class="slds-card__header">'
                f'<h2 class="slds-card__header-title">{title}</h2></div>'
                f'<div class="slds-card__body slds-card__body_inner">')
    html = re.sub(r'<(?:c-)?lightning-card\b([^>]*)>', _card, html, flags=re.DOTALL)
    html = re.sub(r'</(?:c-)?lightning-card>', '</div></div>', html)

    # lightning-input
    def _input(m):
        attrs = m.group(1)
        lm = re.search(r'label\s*=\s*(?:"([^"]*)"|\'([^\']*)\')' , attrs)
        label = (lm.group(1) or lm.group(2)) if lm else ""
        tm = re.search(r'type\s*=\s*(?:"([^"]*)"|\'([^\']*)\')' , attrs)
        itype = (tm.group(1) or tm.group(2)) if tm else "text"
        req = bool(re.search(r'\brequired\b', attrs))
        req_cls = " slds-is-required" if req else ""
        req_html = '<abbr class="slds-required">*</abbr>' if req else ""
        return (f'<div class="slds-form-element{req_cls}">'
                f'<label class="slds-form-element__label">{req_html}{label}</label>'
                f'<div class="slds-form-element__control">'
                f'<input type="{itype}" class="slds-input" placeholder=""></div></div>')
    html = re.sub(r'<(?:c-)?lightning-input(?:-text)?\b([^>]*)/?>', _input, html, flags=re.DOTALL)

    # lightning-combobox
    def _combobox(m):
        attrs = m.group(1)
        lm = re.search(r'label\s*=\s*(?:"([^"]*)"|\'([^\']*)\')' , attrs)
        label = (lm.group(1) or lm.group(2)) if lm else ""
        hidden = bool(re.search(r'label-hidden', attrs))
        req = bool(re.search(r'\brequired\b', attrs))
        select_html = '<div class="slds-form-element__control"><select class="slds-select"><option>-- 選択してください --</option></select></div>'
        if hidden or not label:
            return select_html
        req_cls = " slds-is-required" if req else ""
        req_html = '<abbr class="slds-required">*</abbr>' if req else ""
        return (f'<div class="slds-form-element{req_cls}">'
                f'<label class="slds-form-element__label">{req_html}{label}</label>'
                f'{select_html}</div>')
    html = re.sub(r'<(?:c-)?lightning-combobox\b([^>]*)/?>', _combobox, html, flags=re.DOTALL)

    # lightning-textarea
    def _textarea(m):
        attrs = m.group(1)
        lm = re.search(r'label\s*=\s*(?:"([^"]*)"|\'([^\']*)\')' , attrs)
        label = (lm.group(1) or lm.group(2)) if lm else ""
        req = bool(re.search(r'\brequired\b', attrs))
        req_cls = " slds-is-required" if req else ""
        req_html = '<abbr class="slds-required">*</abbr>' if req else ""
        return (f'<div class="slds-form-element{req_cls}">'
                f'<label class="slds-form-element__label">{req_html}{label}</label>'
                f'<div class="slds-form-element__control">'
                f'<textarea class="slds-textarea" rows="3"></textarea></div></div>')
    html = re.sub(r'<(?:c-)?lightning-textarea\b([^>]*)/?>', _textarea, html, flags=re.DOTALL)

    # lightning-button
    def _button(m):
        attrs = m.group(1)
        lm = re.search(r'label\s*=\s*(?:"([^"]*)"|\'([^\']*)\')' , attrs)
        label = (lm.group(1) or lm.group(2)) if lm else "Button"
        vm = re.search(r'variant\s*=\s*(?:"([^"]*)"|\'([^\']*)\')' , attrs)
        variant = (vm.group(1) or vm.group(2)) if vm else "neutral"
        if variant not in ("brand", "destructive", "neutral"):
            variant = "neutral"
        return f'<button class="slds-button slds-button_{variant}">{label}</button>'
    html = re.sub(r'<(?:c-)?lightning-button\b([^>]*)/?>', _button, html, flags=re.DOTALL)

    # lightning-record-picker
    def _record_picker(m):
        attrs = m.group(1)
        lm = re.search(r'label\s*=\s*(?:"([^"]*)"|\'([^\']*)\')' , attrs)
        label = (lm.group(1) or lm.group(2)) if lm else ""
        pm = re.search(r'placeholder\s*=\s*(?:"([^"]*)"|\'([^\']*)\')' , attrs)
        placeholder = (pm.group(1) or pm.group(2)) if pm else ""
        return (f'<div class="slds-form-element">'
                f'<label class="slds-form-element__label">{label}</label>'
                f'<div class="slds-form-element__control">'
                f'<input type="search" class="slds-input" placeholder="{placeholder}"></div></div>')
    html = re.sub(r'<(?:c-)?lightning-record-picker\b([^>]*)/?>', _record_picker, html, flags=re.DOTALL)

    # lightning-dual-listbox
    def _dual_listbox(m):
        attrs = m.group(1)
        lm = re.search(r'label\s*=\s*(?:"([^"]*)"|\'([^\']*)\')' , attrs)
        label = (lm.group(1) or lm.group(2)) if lm else ""
        req = bool(re.search(r'\brequired\b', attrs))
        req_cls = " slds-is-required" if req else ""
        req_html = '<abbr class="slds-required">*</abbr>' if req else ""
        return (f'<div class="slds-form-element{req_cls}">'
                f'<label class="slds-form-element__label">{req_html}{label}</label>'
                f'<div style="display:flex;gap:8px">'
                f'<select class="slds-select" multiple style="flex:1;min-height:80px"><option>選択肢A</option><option>選択肢B</option></select>'
                f'<select class="slds-select" multiple style="flex:1;min-height:80px"><option>選択済み</option></select>'
                f'</div></div>')
    html = re.sub(r'<(?:c-)?lightning-dual-listbox\b([^>]*)/?>', _dual_listbox, html, flags=re.DOTALL)

    # lightning-datatable
    html = re.sub(
        r'<(?:c-)?lightning-datatable\b[^>]*/?>',
        ('<table class="slds-table"><thead><tr>'
         '<th>列1</th><th>列2</th><th>列3</th></tr></thead>'
         '<tbody><tr><td>-</td><td>-</td><td>-</td></tr>'
         '<tr><td>-</td><td>-</td><td>-</td></tr></tbody></table>'),
        html, flags=re.DOTALL)

    # lightning-spinner
    html = re.sub(
        r'<(?:c-)?lightning-spinner\b[^>]*/?>',
        '<p style="color:#706e6b;text-align:center">\u27F3 読み込み中...</p>',
        html, flags=re.DOTALL)

    # 残りの lightning-* / c-* タグを除去
    html = re.sub(r'</(?:c-)?lightning-[a-zA-Z-]*>', '', html)
    html = re.sub(r'<(?:c-)?lightning-[a-zA-Z-]+\b[^>]*/?\s*>', '', html, flags=re.DOTALL)
    html = re.sub(r'</c-[a-zA-Z-]+>', '', html)
    html = re.sub(r'<c-[a-zA-Z-]+\b[^>]*/?\s*>', '', html, flags=re.DOTALL)

    # 6. モーダルの場合はラップ
    body_html = html.strip()
    return body_html, is_modal


def generate_screen_wireframe_playwright(
    title: str,
    html_content: str,
    out_path: str,
    viewport_width: int = 820,
) -> tuple[bool, int]:
    """Playwright で SLDS スタイルのワイヤーフレームを生成する。

    Returns:
        (success, image_height_px)
        image_height_px は成功時の画像縦ピクセル数、失敗時は 0
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        return False, 0

    body_html, is_modal = _lwc_html_to_slds(html_content)

    if is_modal:
        content = f'<div class="wf-modal-box">{body_html}</div>'
    else:
        content = body_html

    slds_css = """
* { box-sizing: border-box; margin: 0; padding: 0; }
body { font-family: 'Salesforce Sans', Arial, sans-serif; font-size: 13px; background: #f3f2f2; padding: 16px; color: #3e3e3c; }
.wf-title { font-size: 16px; font-weight: 700; color: #0070d2; padding: 8px 0 12px; border-bottom: 2px solid #0070d2; margin-bottom: 12px; }
.slds-card { background: white; border-radius: 4px; box-shadow: 0 2px 3px rgba(0,0,0,0.16); overflow: hidden; margin-bottom: 12px; }
.slds-card__header { padding: 10px 16px; border-bottom: 1px solid #dddbda; }
.slds-card__header-title { font-size: 15px; font-weight: 700; color: #181818; }
.slds-card__body_inner { padding: 12px 16px; }
.slds-form-element { margin-bottom: 10px; }
.slds-form-element__label { display: block; font-size: 12px; color: #3e3e3c; margin-bottom: 3px; font-weight: 600; }
.slds-required { color: #c23934; margin-right: 2px; }
.slds-is-required .slds-form-element__label::before { content: ''; }
.slds-form-element__control { position: relative; }
.slds-input, .slds-textarea, .slds-select { border: 1px solid #dddbda; border-radius: 4px; padding: 6px 10px; width: 100%; font-size: 13px; color: #3e3e3c; background: white; font-family: inherit; }
.slds-textarea { min-height: 72px; resize: vertical; }
.slds-select { appearance: none; background-image: url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='12' height='12' viewBox='0 0 12 12'%3E%3Cpath d='M6 8L1 3h10z' fill='%23706e6b'/%3E%3C/svg%3E"); background-repeat: no-repeat; background-position: right 8px center; padding-right: 24px; }
.slds-button { display: inline-flex; align-items: center; padding: 7px 14px; border: 1px solid; border-radius: 4px; cursor: pointer; font-size: 13px; font-weight: 700; font-family: inherit; margin-right: 6px; margin-top: 6px; }
.slds-button_brand { background: #0070d2; color: white; border-color: #0070d2; }
.slds-button_destructive { background: #c23934; color: white; border-color: #c23934; }
.slds-button_neutral { background: white; color: #0070d2; border-color: #dddbda; }
.slds-grid { display: flex; flex-wrap: wrap; align-items: flex-start; margin-bottom: 4px; }
.slds-col { flex: 1; padding: 4px 6px; }
.slds-size_3-of-12 { flex: 0 0 25%; max-width: 25%; display: flex; align-items: center; }
.slds-size_9-of-12 { flex: 0 0 75%; max-width: 75%; }
.slds-size_12-of-12 { flex: 0 0 100%; max-width: 100%; }
.slds-p-around_medium { padding: 12px; }
.slds-p-around_small { padding: 6px; }
.slds-m-top_small { margin-top: 6px; }
.slds-text-heading_small { font-size: 14px; font-weight: 700; }
.slds-table { width: 100%; border-collapse: collapse; font-size: 12px; }
.slds-table th, .slds-table td { border: 1px solid #dddbda; padding: 5px 8px; text-align: left; }
.slds-table th { background: #f3f2f2; font-weight: 700; }
label[style*="font-size"] { display: flex; align-items: center; font-size: 12px !important; font-weight: 600; color: #3e3e3c; }
.wf-modal-box { background: white; border-radius: 4px; box-shadow: 0 8px 30px rgba(0,0,0,.25); max-width: 560px; margin: 0 auto; display: flex; flex-direction: column; overflow: hidden; }
.slds-modal__header { padding: 14px 16px; border-bottom: 1px solid #dddbda; background: #f3f2f2; }
.slds-modal__content { padding: 16px; }
.slds-modal__footer { padding: 10px 16px; border-top: 1px solid #dddbda; display: flex; justify-content: flex-end; gap: 8px; flex-wrap: wrap; background: #f3f2f2; }
"""

    html_doc = f"""<!DOCTYPE html>
<html lang="ja"><head><meta charset="UTF-8"><title>{title}</title>
<style>{slds_css}</style></head>
<body>
<div class="wf-title">{title}</div>
{content}
</body></html>"""

    import tempfile, os
    from tmp_utils import get_project_tmp_dir
    with tempfile.NamedTemporaryFile(suffix='.html', mode='w', encoding='utf-8', delete=False, dir=get_project_tmp_dir()) as f:
        f.write(html_doc)
        tmp_html = f.name

    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            if is_modal:
                page = browser.new_page(viewport={'width': viewport_width, 'height': 700})
                page.goto(f'file:///{tmp_html.replace(chr(92), "/")}')
                page.wait_for_timeout(300)
                page.screenshot(path=out_path, full_page=False)
            else:
                page = browser.new_page(viewport={'width': viewport_width, 'height': 900})
                page.goto(f'file:///{tmp_html.replace(chr(92), "/")}')
                page.wait_for_timeout(300)
                page.screenshot(path=out_path, full_page=True)
            browser.close()
        # 画像の縦サイズを取得
        img_h_px = 0
        try:
            from PIL import Image as PilImage
            with PilImage.open(out_path) as im:
                img_h_px = im.size[1]
        except Exception:
            img_h_px = 0
        return True, img_h_px
    except Exception as e:
        print(f"  [WARN] Playwright wireframe失敗({title}): {e}")
        return False, 0
    finally:
        try:
            os.unlink(tmp_html)
        except Exception:
            pass


_SLDS_BRAND  = "#0070D2"
_SLDS_GRAY   = "#F3F2F2"
_SLDS_BORDER = "#DDDBDA"

# タグ名 → (type, 抽出する属性リスト)
# c-lightning-* は lightning-* のカスタムラッパーとして同一マッピング
_LWC_TAG_MAP: dict[str, tuple[str, list[str]]] = {
    "lightning-input":           ("input",    ["label", "type", "required"]),
    "c-lightning-input-text":    ("input",    ["label", "required"]),
    "lightning-combobox":        ("picklist", ["label", "required"]),
    "c-lightning-combobox":      ("picklist", ["label", "required"]),
    "lightning-textarea":        ("textarea", ["label", "required"]),
    "c-lightning-textarea":      ("textarea", ["label", "required"]),
    "lightning-datatable":       ("table",    ["title", "label", "required"]),
    "c-lightning-datatable":     ("table",    ["title", "label", "required"]),
    "lightning-button":          ("button",   ["label", "variant"]),
    "c-lightning-button":        ("button",   ["label", "variant"]),
    "lightning-record-form":     ("record_form", ["object-api-name", "label", "required"]),
    "lightning-record-picker":   ("input",    ["label", "required"]),
    "c-lightning-record-picker": ("input",    ["label", "required"]),
    "lightning-dual-listbox":    ("picklist", ["label", "required"]),
    "c-lightning-dual-listbox":  ("picklist", ["label", "required"]),
}


def _is_binding_expr(s: str | None) -> bool:
    """バインディング式 ({xxx}) かどうか判定。"""
    if not s:
        return False
    return bool(re.match(r"^\{.*\}$", s.strip()))


def extract_lwc_ui_elements(html_content: str) -> list[dict]:
    """LWC HTML から UI エレメント情報を抽出する。

    - lightning-card の title を section_header として収集
    - <label> タグのテキストを収集し、label 属性が空の要素の補完に使う
    - 全要素を HTML 内の出現位置順にソートして返す
    """
    elements: list[dict] = []
    if not html_content:
        return elements

    # ── 1. <lightning-card title="..."> → section_header ──
    for m in re.finditer(
        r"<lightning-card\b([^>]*?)(/?>)", html_content, re.DOTALL
    ):
        attr_str = m.group(1)
        tm = re.search(
            r"""title\s*=\s*(?:"([^"]*)"|'([^']*)')""", attr_str, re.DOTALL
        )
        if tm:
            title_val = tm.group(1) if tm.group(1) is not None else tm.group(2)
            if title_val and not _is_binding_expr(title_val):
                elements.append({
                    "type": "section_header",
                    "label": title_val,
                    "required": False,
                    "subtype": "",
                    "_pos": m.start(),
                })

    # ── 2. <label> タグのテキスト収集 ──
    label_tags: list[tuple[int, str]] = []  # (position, text)
    for m in re.finditer(
        r"<label\b[^>]*>(.*?)</label>", html_content, re.DOTALL
    ):
        raw_text = m.group(1)
        # HTMLタグを除去してテキストのみ取得
        clean = re.sub(r"<[^>]+>", "", raw_text).strip()
        # 先頭の * や NBSP を除去（required マーカー由来）
        clean = clean.lstrip("*\u00a0 \t")
        if clean and not _is_binding_expr(clean) and len(clean) < 60:
            label_tags.append((m.start(), clean))

    def _find_nearby_label(pos: int, search_range: int = 500) -> str:
        """pos の直前 search_range 文字以内にある <label> テキストを返す。"""
        best_label = ""
        best_dist = search_range + 1
        for lpos, ltext in label_tags:
            dist = pos - lpos
            if 0 < dist <= search_range and dist < best_dist:
                # 先頭の * や空白を除去（span required マーカー由来）
                clean = ltext.lstrip("*\u00a0 \t")
                if clean:
                    best_label = clean
                    best_dist = dist
        return best_label

    # ── 3. lightning-* 要素の抽出 ──
    for tag_name, (elem_type, _attrs) in _LWC_TAG_MAP.items():
        # 自己終了タグ・通常タグ両方にマッチ
        pattern = rf"<{re.escape(tag_name)}\b([^>]*?)(/?>)"
        for m in re.finditer(pattern, html_content, re.DOTALL):
            attr_str = m.group(1)
            tag_pos = m.start()

            # --- 属性値の抽出ヘルパー ---
            def _attr(name: str, _attr_str: str = attr_str) -> str | None:
                am = re.search(
                    rf"""{re.escape(name)}\s*=\s*(?:"([^"]*)"|'([^']*)')""",
                    _attr_str, re.DOTALL,
                )
                if am:
                    return am.group(1) if am.group(1) is not None else am.group(2)
                return None

            # lightning-button: variant フィルタ
            if elem_type == "button":
                label = _attr("label")
                if not label:
                    continue
                # バインディング式のラベルは空文字扱い
                if _is_binding_expr(label):
                    label = ""
                variant = _attr("variant") or "neutral"
                if variant not in ("brand", "destructive", "neutral"):
                    continue
                elements.append({
                    "type": "button",
                    "label": label,
                    "required": False,
                    "subtype": variant,
                    "_pos": tag_pos,
                })
                continue

            # 共通処理
            label = _attr("label")
            required = "required" in attr_str and _attr("required") != "false"

            if elem_type == "table":
                label = _attr("title") or _attr("label") or "データテーブル"
            elif elem_type == "record_form":
                label = _attr("object-api-name") or label or "RecordForm"

            # バインディング式は空文字扱い
            if _is_binding_expr(label):
                label = ""

            # label が空の場合、直前の <label> タグで補完
            if not label:
                label = _find_nearby_label(tag_pos)

            if label is None:
                label = ""

            subtype = ""
            if elem_type == "input":
                subtype = _attr("type") or "text"

            elements.append({
                "type": elem_type,
                "label": label,
                "required": required,
                "subtype": subtype,
                "_pos": tag_pos,
            })

    # ── 4. 出現位置順にソート ──
    elements.sort(key=lambda e: e.get("_pos", 0))

    # _pos は内部用なので除去
    for e in elements:
        e.pop("_pos", None)

    return elements


def generate_screen_wireframe(
    title: str,
    elements: list[dict],
    out_path: str,
    fig_w: float = 9,
) -> bool:
    """SLDS 風簡易ワイヤーフレームを PNG で出力する。"""
    if not HAS_MPL:
        return False

    # ── ボタン・セクション見出し・フィールドを分離 ──────────────────────────
    buttons = [e for e in elements if e["type"] == "button"]
    fields  = [e for e in elements if e["type"] not in ("button",)]

    # ── フィールド高さ計算 ─────────────────────────────────────────────────
    _FIELD_H = {
        "input": 0.38, "picklist": 0.38, "textarea": 0.7,
        "table": 1.2, "record_form": 0.38,
        "section_header": 0.0,  # section_header は _LABEL_H 不使用、独自高さ
    }
    _SECTION_H = 0.35  # セクション見出しの高さ
    _LABEL_H   = 0.28   # ラベル行の高さ
    _GAP       = 0.12   # フィールド間の余白
    _CARD_PAD  = 0.30   # カード内の上下左右余白
    _HEADER_H  = 0.60

    # 2カラム判定
    use_two_col = len(fields) > 8
    if use_two_col:
        mid = (len(fields) + 1) // 2
        col_left  = fields[:mid]
        col_right = fields[mid:]
    else:
        col_left  = fields
        col_right = []

    def _col_height(col: list[dict]) -> float:
        h = 0.0
        for f in col:
            if f["type"] == "section_header":
                h += _SECTION_H + _GAP
            else:
                h += _LABEL_H + _FIELD_H.get(f["type"], 0.38) + _GAP
        return h

    body_h = max(_col_height(col_left), _col_height(col_right)) if col_right else _col_height(col_left)
    fig_h  = _HEADER_H + body_h + _CARD_PAD * 2 + 0.3  # 0.3 = 外枠余白

    # ── Figure / Axes ──────────────────────────────────────────────────────
    fig, ax = plt.subplots(figsize=(fig_w, max(fig_h, 2.0)))
    ax.set_xlim(0, fig_w)
    ax.set_ylim(fig_h, 0)  # Y軸反転（上→下）
    ax.set_aspect("equal")
    ax.axis("off")
    fig.patch.set_facecolor(_SLDS_GRAY)

    # ── ヘッダーバー ───────────────────────────────────────────────────────
    ax.add_patch(FancyBboxPatch(
        (0.2, 0.15), fig_w - 0.4, _HEADER_H,
        boxstyle="round,pad=0.05",
        facecolor=_SLDS_BRAND, edgecolor="none",
    ))
    ax.text(0.55, 0.15 + _HEADER_H / 2, title,
            ha="left", va="center", color="white",
            **_fpkw(11.0, bold=True))

    # ヘッダー内ボタン（右寄せ）
    btn_x = fig_w - 0.5
    for btn in reversed(buttons):
        lbl = btn["label"]
        bw = max(len(lbl) * 0.18 + 0.3, 0.8)
        bx = btn_x - bw
        by = 0.15 + (_HEADER_H - 0.32) / 2
        is_brand = btn.get("subtype") in ("brand", "destructive")
        ax.add_patch(FancyBboxPatch(
            (bx, by), bw, 0.32,
            boxstyle="round,pad=0.05",
            facecolor=_SLDS_BRAND if is_brand else "white",
            edgecolor=_SLDS_BRAND,
            linewidth=1.0,
        ))
        ax.text(bx + bw / 2, by + 0.16, lbl,
                ha="center", va="center",
                color="white" if is_brand else _SLDS_BRAND,
                **_fpkw(8.0, bold=True))
        btn_x = bx - 0.15

    # ── カード（白背景） ──────────────────────────────────────────────────
    card_top  = _HEADER_H + 0.30
    card_left = 0.3
    card_w    = fig_w - 0.6
    card_h    = body_h + _CARD_PAD * 2
    ax.add_patch(FancyBboxPatch(
        (card_left, card_top), card_w, max(card_h, 0.5),
        boxstyle="round,pad=0.06",
        facecolor="white", edgecolor=_SLDS_BORDER, linewidth=0.8,
    ))

    # ── フィールド描画 ────────────────────────────────────────────────────
    def _draw_fields(col: list[dict], x_start: float, col_w: float, y_start: float):
        y = y_start
        for f in col:
            ftype = f["type"]
            label = f.get("label", "")
            req   = f.get("required", False)
            fh    = _FIELD_H.get(ftype, 0.38)
            fw    = col_w - 0.2  # フィールド幅

            # セクション見出し（section_header）
            if ftype == "section_header":
                # SLDS 青の帯 + テキスト
                ax.add_patch(FancyBboxPatch(
                    (x_start - 0.05, y), fw + 0.1, _SECTION_H,
                    boxstyle="square,pad=0",
                    facecolor=_SLDS_BRAND, edgecolor="none",
                    alpha=0.12,
                ))
                ax.plot([x_start - 0.05, x_start + fw + 0.05],
                        [y + _SECTION_H, y + _SECTION_H],
                        color=_SLDS_BRAND, linewidth=1.2)
                ax.text(x_start, y + _SECTION_H / 2, label,
                        ha="left", va="center", color=_hex("#1F3864"),
                        **_fpkw(9.5, bold=True))
                y += _SECTION_H + _GAP
                continue

            # ラベル
            if req:
                ax.text(x_start, y, label,
                        ha="left", va="top", color="#3E3E3C",
                        **_fpkw(8.5, bold=True))
                ax.text(x_start + len(label) * 0.14 + 0.05, y, "*",
                        ha="left", va="top", color="red",
                        **_fpkw(9.0, bold=True))
            else:
                ax.text(x_start, y, label,
                        ha="left", va="top", color="#3E3E3C",
                        **_fpkw(8.5, bold=True))

            y += _LABEL_H

            # 入力ボックス
            if ftype == "table":
                _draw_table_placeholder(ax, x_start, y, fw, fh, label)
            else:
                ax.add_patch(FancyBboxPatch(
                    (x_start, y), fw, fh,
                    boxstyle="round,pad=0.03",
                    facecolor="white", edgecolor=_SLDS_BORDER, linewidth=0.8,
                ))
                if ftype == "picklist":
                    ax.text(x_start + fw - 0.2, y + fh / 2, "\u25bc",
                            ha="center", va="center", color="#706E6B",
                            **_fpkw(8.0))

            y += fh + _GAP

    def _draw_table_placeholder(ax, x: float, y: float, w: float, h: float, label: str):
        """データテーブルのプレースホルダーを描画。"""
        cols = ["No", "\u9805\u76ee1", "\u9805\u76ee2", "\u9805\u76ee3"]
        col_ws = [w * 0.1, w * 0.35, w * 0.3, w * 0.25]
        row_h = h / 3.0

        # 外枠
        ax.add_patch(plt.Rectangle(
            (x, y), w, h,
            facecolor="white", edgecolor=_SLDS_BORDER, linewidth=0.8,
        ))

        # ヘッダー行
        cx = x
        for ci, (col_label, cw) in enumerate(zip(cols, col_ws)):
            ax.add_patch(plt.Rectangle(
                (cx, y), cw, row_h,
                facecolor=_SLDS_GRAY, edgecolor=_SLDS_BORDER, linewidth=0.5,
            ))
            ax.text(cx + cw / 2, y + row_h / 2, col_label,
                    ha="center", va="center", color="#3E3E3C",
                    **_fpkw(7.0, bold=True))
            cx += cw

        # データ行（空）
        for ri in range(1, 3):
            ry = y + row_h * ri
            cx = x
            for cw in col_ws:
                ax.add_patch(plt.Rectangle(
                    (cx, ry), cw, row_h,
                    facecolor="white", edgecolor=_SLDS_BORDER, linewidth=0.3,
                ))
                cx += cw

    # カラム描画
    field_y_start = card_top + _CARD_PAD
    if use_two_col:
        half_w = (card_w - _CARD_PAD) / 2
        _draw_fields(col_left,  card_left + _CARD_PAD / 2, half_w, field_y_start)
        _draw_fields(col_right, card_left + half_w + _CARD_PAD / 2, half_w, field_y_start)
    else:
        _draw_fields(col_left, card_left + _CARD_PAD / 2, card_w - _CARD_PAD, field_y_start)

    # ── 保存 ──────────────────────────────────────────────────────────────
    plt.savefig(out_path, dpi=180, bbox_inches="tight", facecolor=_SLDS_GRAY)
    plt.close(fig)
    return True


# ================================================================
# 6. コンポーネント×オブジェクト参照マトリクス（詳細設計書 — 対象オブジェクト用）
# ================================================================
def generate_object_component_matrix(
    object_access: list[dict],
    components: list[dict],
    related_objects: list[dict],
    out_path: str,
) -> bool:
    """コンポーネント×オブジェクト参照マトリクスをmatplotlibで生成する。

    行: オブジェクト単位（項目は表示しない）。
    列: コンポーネント。セルに操作種別（参照/更新/新規作成）を表示。
    """
    if not HAS_MPL:
        return False

    _OP_JA = {"R": "参照", "W": "更新", "RW": "参照・更新", "INSERT": "新規作成"}
    _OP_COLOR = {
        "参照":     "#D9E1F2",
        "更新":     "#FFC7CE",
        "参照・更新": "#FFEB9C",
        "新規作成":  "#C6EFCE",
    }
    HDR_BG, HDR_FG = "#1F3864", "white"
    OBJ_BG   = "#E8EDF5"
    FIELD_BG = "#F8F9FB"

    # DML操作のあるコンポーネントのみ列に使う（object_access 登場順）
    seen_comps: list[str] = []
    for entry in object_access:
        comp = entry.get("component", "")
        if comp and comp not in seen_comps:
            seen_comps.append(comp)
    comp_names = seen_comps

    # オブジェクト→コンポーネント→操作のマトリクス構築
    matrix: dict[str, dict[str, str]] = {
        o.get("api_name", ""): {c: "" for c in comp_names}
        for o in related_objects
    }
    for entry in object_access:
        obj  = entry.get("object", "")
        comp = entry.get("component", "")
        op   = _OP_JA.get(entry.get("operation", ""), entry.get("operation", ""))
        if obj in matrix and comp in matrix[obj]:
            matrix[obj][comp] = op

    # オブジェクト×フィールドのデータ構造
    obj_groups = []
    for obj in related_objects:
        obj_api   = obj.get("api_name", "")
        obj_label = obj.get("label", obj_api)
        fields    = obj.get("fields", []) or [{"label": "（項目なし）", "api_name": ""}]
        obj_groups.append((obj_api, obj_label, fields))

    import textwrap as _tw
    import re as _re_local

    def _strip_type_suffix(name: str) -> str:
        """（Apex）（Flow）等の型ラベルを除去して短くする。"""
        return _re_local.sub(r'[（(][A-Za-zApexFlowBatch\u30a0-\u30ff]+[）)]', '', name).strip('_').strip()

    def _wrap_hdr(name: str, width: int = 14) -> str:
        """コンポーネント名を折り返す。AA-3b: width 10→14 に拡大（21字名が3→2行に）。"""
        short = _strip_type_suffix(name)
        lines = _tw.wrap(short, width=width)
        return '\n'.join(lines) if lines else name

    # コンポーネント列幅: 名前の長さに応じて動的調整
    # Q-3 (image3 視認性向上): cell_w を拡大して文字が潰れないように
    # AA-3e: zoom=0.6 表示に合わせて寸法を縮小し、全 FG で同一 zoom → 文字サイズ統一
    _max_name_len = max((len(_strip_type_suffix(c)) for c in comp_names), default=8)
    cell_w = min(2.6, max(1.8, _max_name_len * 0.12))

    # レイアウト定数（オブジェクト単位 = 項目列なし）
    obj_col_w = 3.5    # AA-3e: 4.8 → 3.5
    obj_h     = 0.9    # AA-3e: 1.5 → 0.9（zoom 0.6 後も余白十分）
    hdr_h     = 2.0    # AA-3e: 3.0 → 2.0
    legend_h  = 0.7    # AA-3e: 1.2 → 0.7
    margin    = 0.1

    n_cols      = len(comp_names)
    n_rows      = len(obj_groups)
    total_data_h = n_rows * obj_h
    fig_w = margin * 2 + obj_col_w + cell_w * n_cols
    fig_h = margin + legend_h + total_data_h + hdr_h + margin

    fig, ax = plt.subplots(figsize=(fig_w, fig_h), dpi=150)
    ax.set_xlim(0, fig_w)
    ax.set_ylim(0, fig_h)
    ax.axis("off")
    fig.patch.set_facecolor("white")

    def _rect(x, y, w, h, fc, ec="#CCCCCC", lw=0.8):
        ax.add_patch(mpatches.Rectangle((x, y), w, h, fc=fc, ec=ec, lw=lw))

    # ── ヘッダ行 ─────────────────────────────────────────────────
    hdr_y = fig_h - margin - hdr_h

    _rect(margin, hdr_y, obj_col_w, hdr_h, HDR_BG, ec=HDR_BG)
    ax.text(margin + obj_col_w / 2, hdr_y + hdr_h / 2, "オブジェクト",
            ha="center", va="center", color=HDR_FG, **_fpkw(22, bold=True))

    for ci, comp in enumerate(comp_names):
        x = margin + obj_col_w + ci * cell_w
        _rect(x, hdr_y, cell_w, hdr_h, HDR_BG, ec=HDR_BG)
        ax.text(x + cell_w / 2, hdr_y + hdr_h / 2, _wrap_hdr(comp),
                ha="center", va="center", color=HDR_FG,
                multialignment="center", **_fpkw(18, bold=True))

    # ── データ行（オブジェクト単位） ─────────────────────────────
    for ri, (obj_api, obj_label, _fields) in enumerate(obj_groups):
        row_y = fig_h - margin - hdr_h - (ri + 1) * obj_h

        # オブジェクト名セル
        bg_row = "#F0F3F8" if ri % 2 == 0 else "#FAFBFC"
        _rect(margin, row_y, obj_col_w, obj_h, bg_row)
        ax.text(margin + 0.2, row_y + obj_h / 2, obj_label,
                ha="left", va="center", **_fpkw(22))

        # コンポーネント操作セル
        for ci, comp in enumerate(comp_names):
            x  = margin + obj_col_w + ci * cell_w
            op = matrix[obj_api][comp]
            bg = _OP_COLOR.get(op, "white")
            _rect(x, row_y, cell_w, obj_h, bg)
            ax.text(x + cell_w / 2, row_y + obj_h / 2,
                    op if op else "－",
                    ha="center", va="center",
                    color="#AAAAAA" if not op else "#000000",
                    **_fpkw(20, bold=bool(op)))

    # ── 凡例 ─────────────────────────────────────────────────────
    legend_items = [
        ("参照",      _OP_COLOR["参照"]),
        ("更新",      _OP_COLOR["更新"]),
        ("参照・更新", _OP_COLOR["参照・更新"]),
        ("新規作成",   _OP_COLOR["新規作成"]),
    ]
    lx = margin
    ly = margin * 0.5
    for lbl, color in legend_items:
        _rect(lx, ly, 0.8, 0.7, color, ec="#888888", lw=0.6)
        ax.text(lx + 1.0, ly + 0.35, lbl, va="center", **_fpkw(17))
        lx += 3.2

    plt.tight_layout(pad=0.1)
    plt.savefig(out_path, dpi=150, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return True
