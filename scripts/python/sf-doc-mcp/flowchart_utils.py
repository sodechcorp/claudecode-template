"""
フローチャートPNG生成（機能設計書 / 画面設計書 共通モジュール）。

使用側は generate_flowchart(steps, out_path) を呼ぶだけ。
steps は {no, title, detail?, node_type?, branch?, main_label?, object_ref?} の配列。

node_type: "start" | "end" | "terminator" | "decision" | "object" | "error" | "process"
branch:    {text, node_type?, label?}  — 右側に分岐ノードを描く
object_ref:{text}                      — 右側にオブジェクト(円柱)を描く
main_label: 直前→このノードの矢印に添えるラベル
"""
from __future__ import annotations
import os as _os

try:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.font_manager as fm
    from matplotlib.patches import Ellipse, FancyBboxPatch, Polygon, Rectangle
    HAS_MPL = True
except ImportError:
    HAS_MPL = False

_JP_FONT_PATH = _os.environ.get("JAPANESE_FONT_PATH", "C:/Windows/Fonts/YuGothR.ttc")
JP_FONT_PROP = None
if _os.path.exists(_JP_FONT_PATH) and HAS_MPL:
    JP_FONT_PROP = fm.FontProperties(fname=_JP_FONT_PATH)


def _fpkw():
    return {"fontproperties": JP_FONT_PROP} if JP_FONT_PROP else {}


def auto_enrich_steps(steps: list) -> None:
    """フロー図の品質をスクリプト側で自動補完する（エージェント依存を減らす）。

    補完内容:
    1. branch が設定されているステップの node_type を "decision" に強制
    2. title に「〇〇を呼び出す」パターンがある場合に calls を自動補完
    3. SOQL サブステップの FROM 句からオブジェクト名を抽出して object_ref を補完
    4. DML サブステップの「対象: ObjectName」パターンから object_ref を補完

    エージェントが node_type / calls / object_ref を省略しても最低限の図形分類が保証される。
    """
    import re as _re
    _FROM    = _re.compile(r'\bFROM\s+(\w+)', _re.IGNORECASE)
    _TARGET  = _re.compile(r'対象[：:]\s*(\w+)')
    _SF_NAME = _re.compile(r'^[A-Za-z][A-Za-z0-9_]*$')
    # 「XxxController/Service/Handler/Flow を呼び出す」パターン（英語識別子）
    _CALL_EN  = _re.compile(r'^([A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)?)\s*を呼び出す')
    # 「サブフロー / フロー を呼び出す」パターン（日本語）
    _CALL_SUB = _re.compile(r'サブフロー.*を呼び出す|フローを呼び出す')

    _EXCEPTION_LABELS = {"catch", "throw", "finally", "error"}

    for step in steps:
        # 1. branch が設定されているなら decision に補完
        # ただし catch/throw/finally は例外パス（矩形のまま右逃げ）なので decision にしない
        br = step.get("branch")
        if br and step.get("node_type", "process") == "process":
            br_label = (br.get("label") or "").lower()
            if br_label not in _EXCEPTION_LABELS:
                step["node_type"] = "decision"

        # 2. calls の自動補完（title に「を呼び出す」が含まれる場合）
        if not step.get("calls"):
            title = step.get("title", "") or step.get("text", "")
            m = _CALL_EN.match(title)
            if m:
                step["calls"] = {"text": m.group(1)}
            elif _CALL_SUB.search(title):
                step["calls"] = {"text": "サブフロー"}

        # 3-4. object_ref の自動補完（calls/branch/object_ref が既に設定済みなら不要）
        if step.get("object_ref") or step.get("calls") or step.get("branch"):
            continue
        for sub in step.get("sub_steps", []):
            if sub.get("title", "").upper() not in ("SOQL", "DML"):
                continue
            detail = sub.get("detail", "")
            m = _FROM.search(detail) or _TARGET.search(detail)
            if m and _SF_NAME.match(m.group(1)):
                step["object_ref"] = {"text": m.group(1)}
                break


def _draw_cylinder(ax, cx, cy, w, h, face="#DEEAF1", edge="#6A8CAF", lw=1.0):
    ry = h * 0.12
    x0 = cx - w / 2
    y_top, y_bot = cy + h / 2, cy - h / 2
    ax.add_patch(Rectangle((x0, y_bot + ry), w, h - 2 * ry,
                           facecolor=face, edgecolor=edge, linewidth=lw))
    ax.add_patch(Ellipse((cx, y_bot + ry), w, 2 * ry,
                         facecolor=face, edgecolor=edge, linewidth=lw))
    ax.add_patch(Ellipse((cx, y_top - ry), w, 2 * ry,
                         facecolor=face, edgecolor=edge, linewidth=lw))


def _draw_diamond(ax, cx, cy, w, h, face="#FFF2CC", edge="#BF8F00", lw=1.0):
    pts = [(cx, cy + h/2), (cx + w/2, cy), (cx, cy - h/2), (cx - w/2, cy)]
    ax.add_patch(Polygon(pts, closed=True, facecolor=face, edgecolor=edge, linewidth=lw))


def _draw_ellipse(ax, cx, cy, w, h, face="#0070C0", edge="#004F86", lw=1.2):
    ax.add_patch(Ellipse((cx, cy), w, h, facecolor=face, edgecolor=edge, linewidth=lw))


def _draw_roundrect(ax, cx, cy, w, h, face="#DEEAF1", edge="#6A8CAF", lw=1.0):
    ax.add_patch(FancyBboxPatch(
        (cx - w/2, cy - h/2), w, h,
        boxstyle="round,pad=0.02,rounding_size=0.08",
        facecolor=face, edgecolor=edge, linewidth=lw,
    ))


def _text(ax, cx, cy, txt, fs=7.0, color="#000000"):
    if txt is None:
        return
    ax.text(cx, cy, txt, ha="center", va="center",
            fontsize=fs, color=color, **_fpkw())


def _arrow(ax, x0, y0, x1, y1, color="#444444", lw=1.1):
    ax.annotate("", xy=(x1, y1), xytext=(x0, y0),
                arrowprops=dict(arrowstyle="->", color=color, lw=lw,
                                shrinkA=0, shrinkB=0))


def _label(ax, cx, cy, text, color="#444444"):
    ax.text(cx, cy, text, ha="center", va="center",
            fontsize=6.5, color=color,
            bbox=dict(boxstyle="square,pad=0.15", fc="white", ec=color, lw=0.6),
            **_fpkw())


def _render_shape(ax, cx, cy, w, h, node_type, text):
    if node_type in ("start", "end", "terminator"):
        _draw_ellipse(ax, cx, cy, w, h)
        _text(ax, cx, cy, text, fs=8.5, color="white")
    elif node_type == "decision":
        _draw_diamond(ax, cx, cy, w, h)
        _text(ax, cx, cy, text, fs=6.5)
    elif node_type == "object":
        _draw_cylinder(ax, cx, cy, w, h)
        _text(ax, cx, cy, text, fs=6.5)
    elif node_type == "error":
        _draw_roundrect(ax, cx, cy, w, h, face="#FFE699", edge="#BF9000")
        _text(ax, cx, cy, text, fs=6.5)
    elif node_type == "success":
        _draw_roundrect(ax, cx, cy, w, h, face="#C6EFCE", edge="#538135")
        _text(ax, cx, cy, text, fs=6.5)
    elif node_type == "call":
        _draw_roundrect(ax, cx, cy, w, h, face="#E1D5E7", edge="#9673A6")
        _text(ax, cx, cy, text, fs=6.5)
    else:
        _draw_roundrect(ax, cx, cy, w, h, face="#DEEAF1", edge="#6A8CAF")
        _text(ax, cx, cy, text, fs=6.8)


def _wrap(text, limit=12):
    """limit文字を目安に折り返す。
    折り返し優先順位:
      1. スペース / アンダースコア（区切り文字自体は次行の先頭へ、スペースは捨てる）
      2. CamelCase 境界（小文字→大文字の直前、例: "ConsultationController" → "Consultation|Controller"）
      3. 強制折り返し（limit+3 文字）
    API名（例: HolidayMaster7__c）はアンダースコアで自然に分割され、Apex/LWC の
    キャメルケースクラス名（例: ConsultationController）は大文字境界で自然に分割される。
    """
    if text is None:
        return ""
    out = []
    for para in text.split("\n"):
        if not para:
            out.append("")
            continue
        line = ""
        i = 0
        while i < len(para):
            ch = para[i]
            # (1) スペース・アンダースコアで limit 以上なら折り返す
            if ch in (' ', '_') and len(line) >= limit:
                out.append(line)
                line = ch if ch == '_' else ""
                i += 1
                continue
            # (2) CamelCase 境界: 直前が英小文字/数字で、現在が英大文字。
            # line が十分長く（limit*2/3 以上）、かつ残りが line を limit 超過させる場合のみ分割。
            _cc_threshold = max(4, (limit * 2) // 3)
            if (ch.isascii() and ch.isupper() and len(line) >= _cc_threshold
                    and line and line[-1].isascii() and (line[-1].islower() or line[-1].isdigit())
                    and len(para) - i + len(line) > limit):
                out.append(line)
                line = ch
                i += 1
                continue
            line += ch
            i += 1
            # (3) limit+3 以上で強制折り返し（区切り文字が見つからない長い単語の保険）
            if len(line) >= limit + 3:
                out.append(line)
                line = ""
        if line:
            out.append(line)
    return "\n".join(out)


def generate_flowchart(steps, out_path, fig_w=6.2, add_start_end=True,
                       wrap_limit=14, target_h=None):
    """steps[] からフローチャートPNGを生成する。

    target_h: 生成する図の目標高さ（インチ）。指定すると自動計算値より優先される。
              処理内容の行高さに合わせて縦幅を揃えるために使用する。
    戻り値: True/False（mpl未インストールなら False）
    """
    if not HAS_MPL:
        return False

    # フロー図品質の自動補完（呼び出し側での明示的呼び出しが不要になる）
    auto_enrich_steps(steps)

    nodes = []
    if add_start_end:
        nodes.append({"type": "start", "text": "開始"})
    for step in steps:
        label_no = str(step.get("no", "")).strip()
        title = step.get("title", "") or step.get("text", "")
        if label_no:
            label = f"{label_no}. {title}"
        else:
            label = title
        nodes.append({
            "type": step.get("node_type", "process"),
            "text": _wrap(label, wrap_limit),
            "branch": step.get("branch"),
            "main_label": step.get("main_label"),
            "object_ref": step.get("object_ref"),
            "calls": step.get("calls"),
        })
    if add_start_end:
        nodes.append({"type": "end", "text": "終了"})

    if not nodes:
        return False

    BOX_W_PROC, BOX_H_PROC = 1.9, 0.60
    BOX_W_DEC,  BOX_H_DEC  = 1.9, 0.80
    BOX_W_OBJ,  BOX_H_OBJ  = 1.3, 0.72
    BOX_W_TERM, BOX_H_TERM = 1.5, 0.48
    GAP_DEFAULT = 0.75
    GAP_MIN     = 0.60  # ノード重なりを防ぐ最小間隔

    # ノード高さを先に計算（GAP動的調整に使用）
    node_heights = []
    for n in nodes:
        t = n["type"]
        h_n = BOX_H_TERM if t in ("start", "end", "terminator") else \
              BOX_H_DEC  if t == "decision" else \
              BOX_H_OBJ  if t == "object"   else BOX_H_PROC
        node_heights.append(h_n)

    sum_node_h = sum(node_heights)
    n_nodes    = len(nodes)

    # デフォルトのtotal_h（固定GAPで計算）
    total_h = max(5.0, 0.8 + sum_node_h + n_nodes * GAP_DEFAULT + 0.6)

    if target_h is not None and target_h > total_h:
        # target_h に合わせてGAPを動的に拡大する
        # MARGIN_TOP=0.50, MARGIN_BOT=0.35 を確保して残りをGAP n個で分配
        # GAP_MAX を超える場合は上限でクランプし、total_h を再計算する
        avail = target_h - 0.50 - 0.35 - sum_node_h
        raw_gap = avail / n_nodes if n_nodes > 0 else GAP_DEFAULT
        GAP = max(GAP_MIN, raw_gap)
        total_h = 0.50 + 0.35 + sum_node_h + GAP * n_nodes
    else:
        GAP = GAP_DEFAULT

    fig, ax = plt.subplots(figsize=(fig_w, total_h))
    ax.set_xlim(0, fig_w); ax.set_ylim(0, total_h)
    ax.axis("off")
    fig.patch.set_facecolor("white")

    cx_main   = fig_w * 0.28
    cx_branch = fig_w * 0.74

    y = total_h - 0.50
    prev_cy, prev_h = None, None

    for i, n in enumerate(nodes):
        t = n["type"]
        h = node_heights[i]
        if t in ("start", "end", "terminator"):
            w = BOX_W_TERM
        elif t == "decision":
            w = BOX_W_DEC
        elif t == "object":
            w = BOX_W_OBJ
        else:
            w = BOX_W_PROC

        cy = y - h / 2
        _render_shape(ax, cx_main, cy, w, h, t, n["text"])

        if prev_cy is not None:
            y0 = prev_cy - prev_h / 2
            y1 = cy + h / 2
            _arrow(ax, cx_main, y0 - 0.02, cx_main, y1 + 0.02)
            ml = nodes[i - 1].get("main_label") if i - 1 >= 0 else None
            # decision ノードの下向き矢印は "True" を自動付与（main_label 未指定時）
            if ml is None and i - 1 >= 0 and nodes[i - 1].get("type") == "decision":
                ml = "True"
            if ml:
                # decision の下向き Yes ラベルはひし形のすぐ下に配置
                lbl_y = y0 - 0.22 if (i - 1 >= 0 and nodes[i - 1].get("type") == "decision") else (y0 + y1) / 2
                _label(ax, cx_main - 0.22, lbl_y, ml)

        # ── 右側要素の描画 ──────────────────────────────────────────────────────
        # 優先度: calls（外部呼び出し）> object_ref（DMLオブジェクト）> branch（decision のみ）
        # catch/throw/finally 分岐は右列を占有せず、メインボックス隅にアノテーションで示す
        _EXCEPTION_LABELS_FC = {"catch", "throw", "finally"}
        obj   = n.get("object_ref")
        calls = n.get("calls")
        br    = n.get("branch")
        br_label_raw = (br.get("label") or "").lower() if br else ""
        br_is_exception = br_label_raw in _EXCEPTION_LABELS_FC

        if calls:
            # calls: 他Apex・他LWC呼び出し → 常に右側に表示（最優先）
            if isinstance(calls, str):
                calls_text = calls
            else:
                calls_text = calls.get("text") or calls.get("name") or ""
            if calls_text:
                # Apex/LWC クラス名は18文字程度までが多い。折返しは18文字基準。
                wrapped = _wrap(calls_text, 18)
                lines = wrapped.split("\n")
                cl = len(lines)
                max_chars = max((len(ln) for ln in lines), default=0)
                # ボックス幅を最長行に合わせて動的に拡張（fs=6.5 基準: 1文字≈0.10 inch, 左右マージン0.25）
                cw = max(BOX_W_PROC * 1.0, max_chars * 0.10 + 0.25)
                # 2行以上のときは行間を 0.22 inch 確保して下端切れを防ぐ
                ch = BOX_H_PROC * 1.10 + max(0, cl - 1) * 0.22
                _render_shape(ax, cx_branch, cy, cw, ch, "call", wrapped)
                _arrow(ax, cx_main + w / 2 + 0.02, cy,
                       cx_branch - cw / 2 - 0.02, cy,
                       color="#444444", lw=1.1)
                midx = (cx_main + w / 2 + cx_branch - cw / 2) / 2
                _label(ax, midx, cy + 0.16, "呼出")

        elif obj and t != "object":
            # object_ref: DML操作のオブジェクト円柱 → calls がない場合に表示
            if isinstance(obj, str):
                obj_text = obj
            else:
                obj_text = obj.get("text") or obj.get("name") or obj.get("label") or ""
            if obj_text:
                _draw_cylinder(ax, cx_branch, cy, BOX_W_OBJ, BOX_H_OBJ)
                _text(ax, cx_branch, cy, _wrap(obj_text, 10), fs=6.8)
                _arrow(ax, cx_main + w / 2 + 0.02, cy,
                       cx_branch - BOX_W_OBJ / 2 - 0.02, cy,
                       color="#888888", lw=0.9)

        elif br and not br_is_exception:
            # branch(decision): calls も object_ref もない条件分岐のみ右側ボックス
            br_text  = _wrap(br.get("text", ""), 12)
            br_type  = br.get("node_type", "error")
            br_lines = len(br_text.split("\n")) if br_text else 1
            bw = BOX_W_PROC * 1.0
            bh = BOX_H_PROC * 1.05 + max(0, br_lines - 1) * 0.18
            _render_shape(ax, cx_branch, cy, bw, bh, br_type, br_text)
            _arrow(ax, cx_main + w / 2 + 0.02, cy,
                   cx_branch - bw / 2 - 0.02, cy,
                   color="#444444", lw=1.1)
            br_lbl = br.get("label") or ("False" if t == "decision" else None)
            if br_lbl:
                midx = (cx_main + w / 2 + cx_branch - bw / 2) / 2
                _label(ax, midx, cy + 0.16, br_lbl)

        # catch/throw アノテーション: 右列を占有せず、メインボックス右上端に小ラベルで示す
        if br and br_is_exception:
            _label(ax, cx_main + w / 2 - 0.02, cy + h / 2 - 0.02,
                   br_label_raw, color="#BF8F00")

        prev_cy, prev_h = cy, h
        y -= h + GAP

    plt.tight_layout(pad=0.3)
    plt.savefig(out_path, dpi=140, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    return True
