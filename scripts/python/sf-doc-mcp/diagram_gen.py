"""
高品質図生成モジュール（graphviz + drawsvg ベース）。

diagram_utils.py / er_utils.py の matplotlib 実装を置き換える新実装。

提供関数:
  render_system_diagram(system: dict, out_path: str) -> (width_px, height_px)
  render_er_diagram(objects: list, relations: list, out_path: str) -> (width_px, height_px)
  render_swimlane(flow: dict, out_path: str) -> (width_px, height_px)

依存:
  graphviz (pip + バイナリ)  ── 全図を直接PNG出力（Cairo不要）
  Pillow                     ── PNG サイズ確認
"""
from __future__ import annotations

import math
import os
import shutil
from pathlib import Path

# ── 依存チェック ──────────────────────────────────────────────────
try:
    import graphviz as _gv
    _HAS_GV = True
except ImportError:
    _HAS_GV = False

_HAS_SVG = False  # 未使用（graphvizが全図PNG直接出力するため不要）

try:
    from PIL import Image as _PILImage
    _HAS_PIL = True
except ImportError:
    _HAS_PIL = False

# Graphviz バイナリ PATH: PATH 上に dot がなければ winget 標準パスをフォールバックとして追加
_GV_BIN_WIN = r"C:\Program Files\Graphviz\bin"
if not shutil.which("dot") and os.path.isdir(_GV_BIN_WIN):
    os.environ["PATH"] = _GV_BIN_WIN + os.pathsep + os.environ.get("PATH", "")

# ── カラーパレット ────────────────────────────────────────────────
C_SF_CORE   = "#1F3864"   # Salesforce中核（濃紺）
C_SF_LABEL  = "#FFFFFF"
C_ACTOR_BG  = "#D9E1F2"   # 利用者（薄青）
C_ACTOR_FG  = "#1F3864"
C_EXT_BG    = "#E2EFDA"   # 外部システム（薄緑）
C_EXT_FG    = "#375623"
C_DS_BG     = "#FFF2CC"   # データストア（薄黄）
C_DS_FG     = "#7F6000"
C_EDGE      = "#5A5A5A"
C_LANE_HDR  = "#1F3864"
C_HDR_BLUE    = "#2E75B6"
C_STEP_BG     = "#2E75B6"
C_STEP_FG     = "#FFFFFF"
C_STEP_BORDER = "#1F3864"

FONT_JP = "Meiryo"   # graphviz 用（Windows・TrueType で高品質レンダリング）
DPI     = 150


# ════════════════════════════════════════════════════════════════
# 1. システム構成図（graphviz）
# ════════════════════════════════════════════════════════════════

def render_system_diagram(system: dict, out_path: str) -> tuple[int, int]:
    """
    system.json の内容からシステム構成図 PNG を生成する。

    system スキーマ:
      core: {name, role}
      actors: [{name, count?, channels?}]
      external_systems: [{name, direction, protocol, frequency, purpose}]
      data_stores: [{name, purpose}]
    """
    if not _HAS_GV:
        raise RuntimeError("graphviz が利用できません")

    g = _gv.Digraph(
        "system",
        graph_attr={
            "bgcolor": "white",
            "rankdir": "LR",
            "splines": "polyline",
            "nodesep": "0.5",
            "ranksep": "1.2",
            "fontname": FONT_JP,
            "pad": "0.4",
            "dpi": str(DPI),
        },
    )

    core = system.get("core") or {}
    _role = core.get("role", "")
    if len(_role) > 25:
        _role = _role[:24] + "…"
    core_label = _gv_label(core.get("name", "Salesforce"), _role)

    # 中核 Salesforce ノード
    g.node(
        "core",
        label=core_label,
        shape="box",
        style="filled,rounded",
        fillcolor=C_SF_CORE,
        fontcolor=C_SF_LABEL,
        fontname=FONT_JP,
        fontsize="12",
        width="2.2",
        height="0.9",
        penwidth="2",
    )

    # 利用者（左）
    with g.subgraph(name="cluster_actors") as sg:
        sg.attr(rank="min", style="invis")
        for i, actor in enumerate(system.get("actors", [])[:6]):
            nid = f"actor_{i}"
            cnt = f"\n({actor['count']}名)" if actor.get("count") else ""
            sg.node(
                nid,
                label=_gv_label(actor["name"] + cnt),
                shape="ellipse",
                style="filled",
                fillcolor=C_ACTOR_BG,
                fontcolor=C_ACTOR_FG,
                fontname=FONT_JP,
                fontsize="10",
                width="1.8",
            )
            g.edge(nid, "core", color=C_EDGE, arrowsize="0.8")

    # 外部システム（右）
    with g.subgraph(name="cluster_ext") as sg:
        sg.attr(rank="max", style="invis")
        active_ext = [e for e in system.get("external_systems", []) if e.get("direction", "out") != "none"]
        for i, ext in enumerate(active_ext[:8]):
            nid = f"ext_{i}"
            proto = ext.get("protocol", "")
            freq = ext.get("frequency", "")
            edge_lbl = f"{proto}" + (f"\n{freq}" if freq else "")
            sg.node(
                nid,
                label=_gv_label(ext["name"]),
                shape="box",
                style="filled,rounded",
                fillcolor=C_EXT_BG,
                fontcolor=C_EXT_FG,
                fontname=FONT_JP,
                fontsize="10",
                width="1.8",
            )
            direction = ext.get("direction", "out")
            if direction == "in":
                g.edge(nid, "core", xlabel=edge_lbl, color=C_EDGE, arrowsize="0.8",
                       fontname=FONT_JP, fontsize="8", fontcolor=C_EDGE)
            elif direction == "both":
                g.edge("core", nid, xlabel=edge_lbl, color=C_EDGE, arrowsize="0.8",
                       dir="both", fontname=FONT_JP, fontsize="8", fontcolor=C_EDGE)
            else:
                g.edge("core", nid, xlabel=edge_lbl, color=C_EDGE, arrowsize="0.8",
                       fontname=FONT_JP, fontsize="8", fontcolor=C_EDGE)

    # データストア（下）
    for i, ds in enumerate(system.get("data_stores", [])[:4]):
        nid = f"ds_{i}"
        g.node(
            nid,
            label=_gv_label(ds["name"]),
            shape="cylinder",
            style="filled",
            fillcolor=C_DS_BG,
            fontcolor=C_DS_FG,
            fontname=FONT_JP,
            fontsize="10",
        )
        g.edge("core", nid, color=C_EDGE, arrowsize="0.8", style="dashed")

    png_bytes = g.pipe(format="png")
    with open(out_path, "wb") as f:
        f.write(png_bytes)
    if _HAS_PIL:
        return _PILImage.open(out_path).size
    return (0, 0)


def _gv_label(*lines: str) -> str:
    return "\n".join(l for l in lines if l)


# ════════════════════════════════════════════════════════════════
# 2. ER図（graphviz record ノード）
# ════════════════════════════════════════════════════════════════

def render_er_diagram(
    objects: list[dict],
    relations: list[dict],
    out_path: str,
) -> tuple[int, int]:
    """
    オブジェクト一覧と関連定義からER図PNGを生成する。

    objects: [{api, label, type}]
    relations: [{parent, child, rel, field}]
      rel: "1-N" | "N-N" | "lookup" | "master-detail"
    """
    if not _HAS_GV:
        raise RuntimeError("graphviz が利用できません")

    g = _gv.Digraph(
        "er",
        graph_attr={
            "bgcolor": "white",
            "rankdir": "TB",
            "splines": "ortho",
            "nodesep": "0.6",
            "ranksep": "1.0",
            "fontname": FONT_JP,
            "pad": "0.4",
            "dpi": str(DPI),
        },
    )

    # 関連に登場するオブジェクトAPIのみ描画（孤立ノードを除外して図を見やすく）
    related_apis: set[str] = set()
    for rel in relations:
        if not rel["parent"].isdigit() and not rel["child"].isdigit():
            related_apis.add(rel["parent"])
            related_apis.add(rel["child"])

    # objects リストから label を引く辞書
    obj_label_map = {o["api"]: (o.get("label", ""), o.get("type", "")) for o in objects}

    obj_ids = set()
    for api in sorted(related_apis):  # ソートして毎回同じ順で配置
        nid = api.replace("__c", "_c").replace("__", "_")
        obj_ids.add(api)
        lbl, kind = obj_label_map.get(api, ("", ""))
        kind_color = "#1F3864" if kind in ("カスタム", "Custom") else "#2E75B6"
        # 日本語ラベルを主表示、APIを副表示（空セルはgraphvizエラーになるため条件分岐）
        if lbl:
            label = (
                f'<<TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0" CELLPADDING="4">'
                f'<TR><TD BGCOLOR="{kind_color}"><FONT COLOR="white"><B>{lbl}</B></FONT></TD></TR>'
                f'<TR><TD BGCOLOR="#D9E1F2"><FONT COLOR="#666666">{api}</FONT></TD></TR>'
                f"</TABLE>>"
            )
        else:
            label = (
                f'<<TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0" CELLPADDING="4">'
                f'<TR><TD BGCOLOR="{kind_color}"><FONT COLOR="white"><B>{api}</B></FONT></TD></TR>'
                f"</TABLE>>"
            )
        g.node(
            nid,
            label=label,
            shape="none",
            fontname=FONT_JP,
            fontsize="10",
        )

    # 関連エッジ
    for rel in relations:
        parent = rel["parent"]
        child = rel["child"]
        # 数字のみのノード（表の行番号が誤混入した場合）はスキップ
        if parent.isdigit() or child.isdigit():
            continue
        pid = parent.replace("__c", "_c").replace("__", "_")
        cid = child.replace("__c", "_c").replace("__", "_")
        rel_type = rel.get("rel", "").lower()
        if "master" in rel_type or "md" in rel_type:
            arrow = "diamond"
            style = "bold"
        elif "n-n" in rel_type or "many" in rel_type:
            arrow = "crow"
            style = "dashed"
        else:
            arrow = "vee"
            style = "solid"
        field_label = rel.get("field", "")
        g.edge(
            pid, cid,
            xlabel=field_label,   # ortho splines は label 非対応のため xlabel を使用
            arrowhead=arrow,
            style=style,
            color=C_EDGE,
            fontname=FONT_JP,
            fontsize="8",
            fontcolor=C_EDGE,
        )

    png_bytes = g.pipe(format="png")
    with open(out_path, "wb") as f:
        f.write(png_bytes)
    if _HAS_PIL:
        return _PILImage.open(out_path).size
    return (0, 0)


# ════════════════════════════════════════════════════════════════
# 3. スイムレーン図（graphviz cluster subgraph 方式）
# ════════════════════════════════════════════════════════════════

# レーン背景色（薄い色でクラスター塗りつぶし）
_LANE_COLORS = ["#EEF4FB", "#F5FBF0", "#FFFBF0", "#FBF5FF", "#F8FAFD"]

# レーン type → (グループ表示名, 塗り色) のマップ。
# 固有名詞（会社名・プロジェクト名）はここに書かない。
# 分類の根拠は swimlanes.json の lanes[].type（sf-analyst-cat1 のスキーマ）に統一する。
_TYPE_GROUP_MAP: dict[str, tuple[str, str]] = {
    "external_actor":  ("社外・お客様",   "#D9E9F8"),
    "internal_actor":  ("社内担当",       "#E8F5E9"),
    "system":          ("Salesforce",    "#FFF9E6"),
    "external_system": ("外部システム",   "#F3E5F5"),
}
_TYPE_GROUP_ORDER = ["external_actor", "internal_actor", "system", "external_system"]

# cluster_group の垂直配置レベル（0=top, 大きいほど下）
# 同レベルのグループは横並びになる（external_actor + external_system が level 0 で隣接）
_GROUP_LEVEL: dict[str, int] = {
    "external_actor":  0,
    "external_system": 0,
    "internal_actor":  1,
    "system":          2,
}


def _lane_to_group(lane_type: str) -> tuple[str, str] | None:
    """レーンの type からグループ（表示名・塗り色）を決める。
    type 未設定・未知の値の場合は None を返し、呼び出し側はグループ化せず
    レーン単体で描画する（固有名詞のデフォルト値は使わない）。
    """
    if not lane_type:
        return None
    return _TYPE_GROUP_MAP.get(lane_type.strip().lower())


def render_swimlane(flow: dict, out_path: str) -> tuple[int, int]:
    """
    swimlanes.json の1フローからスイムレーン図PNGを生成する。
    graphviz cluster subgraph 方式（Cairo不要）。

    flow スキーマ:
      title: str
      lanes: [{name, type}]
      steps: [{id, lane, col, label}]
      transitions: [{from, to, condition?}]
    """
    if not _HAS_GV:
        raise RuntimeError("graphviz が利用できません")

    lanes_in = flow.get("lanes", [])
    steps_in = flow.get("steps", [])
    trans_in = flow.get("transitions", [])
    title    = flow.get("title", "業務フロー")

    # TB: 時間軸=縦（steps が上→下）、レーン=横に並ぶ列
    # cluster_group + cluster_lane の両方を visible にして見本（GF AS-IS）と同じ構造にする
    _sw_rankdir = "TB"

    # 20ステップ超のフロー（TO-BE など）は anchor レイアウトを使い ranksep を広げて縦方向を確保
    _use_anchor_pre = len(steps_in) >= 20
    _ranksep = "1.2" if _use_anchor_pre else "0.4"

    _sw_graph_attr = {
        "bgcolor": "white",
        "rankdir": _sw_rankdir,
        "splines": "polyline",
        "nodesep": "0.3" if _use_anchor_pre else "0.4",  # anchor フロー: 詰めてコンパクトに
        "ranksep": _ranksep,    # anchor フロー: 1.2インチ（2D 縦積みで高さを確保）/ 小フロー: 0.4
        "size": "16,12",        # 上限 16×12 インチ = 2400×1800px @DPI150（超えたらスケールダウン）
        "fontname": FONT_JP,
        "pad": "0.3",
        "dpi": str(DPI),
        "label": title,
        "labelloc": "t",
        "fontsize": "14",
        "fontcolor": C_LANE_HDR,
        "compound": "true",        # cluster 跨ぎエッジを cluster 境界に正しく接続
    }
    # AA: graphviz 自然サイズ算出。size/ratio 強制なし → FG 間でノード密度が揃う

    g = _gv.Digraph(
        "swimlane",
        graph_attr=_sw_graph_attr,
    )

    # レーンを lanes[].type に基づきグループ化して描画する。
    # type が未設定・未知のレーンはグループ化せず単体で平置き（固有名詞を絶対に挿入しない）。
    from collections import OrderedDict

    lane_names = [l.get("name", f"Lane{i+1}") for i, l in enumerate(lanes_in)]
    lane_name_to_type: dict[str, str] = {
        l.get("name", f"Lane{i+1}"): (l.get("type") or "")
        for i, l in enumerate(lanes_in)
    }
    # step.lane が id（"L-CUST" 等）で書かれている場合に name へ解決するマップ
    lane_id_to_name: dict[str, str] = {
        l["id"]: l.get("name", f"Lane{i+1}")
        for i, l in enumerate(lanes_in) if l.get("id")
    }

    # グループキー: type_key（_TYPE_GROUP_MAP のキー） or None（未分類）
    # 値: list[lane_name]（入力順を維持）
    group_to_lanes: "OrderedDict[str | None, list[str]]" = OrderedDict()
    for lane_name in lane_names:
        lt = lane_name_to_type.get(lane_name, "")
        grp = _lane_to_group(lt)
        key: str | None = lt.strip().lower() if grp else None
        group_to_lanes.setdefault(key, []).append(lane_name)

    # 分類済みは _TYPE_GROUP_ORDER の順、未分類（None）は末尾に配置
    sorted_keys: list[str | None] = [k for k in _TYPE_GROUP_ORDER if k in group_to_lanes]
    sorted_keys += [k for k in group_to_lanes if k is not None and k not in sorted_keys]
    if None in group_to_lanes:
        sorted_keys.append(None)

    # ステップ → group key のマップ（cross-GROUP判定に使用）
    _sid_to_group: dict[str, str | None] = {}
    for step in steps_in:
        sid = str(step.get("id", ""))
        step_lane_raw = str(step.get("lane", ""))
        step_lane_name = lane_id_to_name.get(step_lane_raw, step_lane_raw)
        lt = lane_name_to_type.get(step_lane_name, "")
        grp = lt.strip().lower() if _lane_to_group(lt) else None
        _sid_to_group[sid] = grp

    def _render_lane(parent, gi: int, lane_idx: int, lane_name: str):
        bg = _LANE_COLORS[lane_idx % len(_LANE_COLORS)]
        with parent.subgraph(name=f"cluster_lane_{gi}_{lane_idx}") as sg:
            sg.attr(
                label=lane_name,
                style="filled",
                fillcolor=bg,
                color=C_LANE_HDR,
                penwidth="1",
                fontname=FONT_JP,
                fontcolor=C_LANE_HDR,
                fontsize="12",
                margin="4",
            )
            for step in steps_in:
                step_lane_raw = str(step.get("lane", ""))
                step_lane_name = lane_id_to_name.get(step_lane_raw, step_lane_raw)
                if step_lane_name == lane_name:
                    sid = str(step.get("id", ""))
                    label = str(step.get("label", "") or step.get("title", "") or step.get("action", "") or step.get("name", "") or sid)
                    label = _wrap_jp(label, 16)
                    sg.node(
                        sid,
                        label=label,
                        shape="box",
                        style="filled,rounded",
                        fillcolor=C_STEP_BG,
                        fontcolor=C_STEP_FG,
                        fontname=FONT_JP,
                        fontsize="9",
                        penwidth="1.0",
                        color=C_STEP_BORDER,
                        margin="0.12,0.08",
                    )

    known_lanes = set(lane_names) | set(lane_id_to_name.keys())
    lane_color_idx = 0
    group_anchor: dict[str, str] = {}  # group key → anchor node id

    # ステップ数が多いフロー（TO-BE など）はクラスタグループが全横並びになりやすい。
    # 20ステップ超の場合のみ anchor 強制レイアウトを適用する。
    # 小フロー（AS-IS・UC個別）は DOT の自然レイアウトを使う（変更なし）。
    use_anchor_layout = len(steps_in) >= 20

    for gi, key in enumerate(sorted_keys):
        lanes_in_group = group_to_lanes[key]
        if key is None:
            # 未分類: グループクラスタを作らずレーンを直接トップレベル subgraph として描画
            for lane_name in lanes_in_group:
                _render_lane(g, gi, lane_color_idx, lane_name)
                lane_color_idx += 1
        else:
            # cluster_group を visible に: _TYPE_GROUP_MAP のラベル・カラーを使用
            group_label, group_color = _TYPE_GROUP_MAP.get(key, (key, "#E8E8E8"))
            with g.subgraph(name=f"cluster_group_{gi}") as gg:
                gg.attr(
                    label=group_label,
                    style="filled",
                    fillcolor=group_color,
                    color=C_LANE_HDR,
                    penwidth="1.5",
                    fontname=FONT_JP,
                    fontcolor=C_LANE_HDR,
                    fontsize="13",
                    margin="6",
                )
                if use_anchor_layout:
                    # 不可視アンカーノード: グループ間の垂直順序制御に使用
                    anchor_id = f"__anchor_{gi}"
                    gg.node(anchor_id, style="invis", width="0", height="0", label="", fixedsize="true")
                    group_anchor[key] = anchor_id
                for lane_name in lanes_in_group:
                    _render_lane(gg, gi, lane_color_idx, lane_name)
                    lane_color_idx += 1

    if use_anchor_layout and group_anchor:
        # アンカー → 全グループノード（不可視）: グループノードのランクをアンカーランク+1以上に固定
        for key, anchor_id in group_anchor.items():
            for step in steps_in:
                sid = str(step.get("id", ""))
                if _sid_to_group.get(sid) == key:
                    g.edge(anchor_id, sid, style="invis", weight="1", constraint="true")

        # 同一グループ内の最長チェーン長を計算（アンカー間 minlen の算出に使用）
        def _max_group_chain_len(group_key: str) -> int:
            adj: dict[str, list[str]] = {}
            for t in trans_in:
                src, dst = str(t.get("from", "")), str(t.get("to", ""))
                if _sid_to_group.get(src) == group_key and _sid_to_group.get(dst) == group_key:
                    adj.setdefault(src, []).append(dst)
            memo: dict[str, int] = {}
            def dp(n: str) -> int:
                if n in memo:
                    return memo[n]
                memo[n] = 1 + max((dp(x) for x in adj.get(n, [])), default=0)
                return memo[n]
            nodes = [s for s, grp in _sid_to_group.items() if grp == group_key]
            return max((dp(n) for n in nodes), default=1) if nodes else 1

        # _GROUP_LEVEL に基づきクラスタグループを垂直に積む（不可視エッジで rank 強制）
        # minlen = 上段グループの最長チェーン + 1 でランク範囲の重複を防ぐ
        level_to_keys: dict[int, list[str]] = {}
        for k in group_anchor:
            lvl = _GROUP_LEVEL.get(k, 99)
            level_to_keys.setdefault(lvl, []).append(k)

        for lvl in sorted(level_to_keys):
            next_lvl = lvl + 1
            if next_lvl not in level_to_keys:
                continue
            max_chain = max(_max_group_chain_len(k) for k in level_to_keys[lvl])
            minlen = str(max_chain + 1)
            for src_key in level_to_keys[lvl]:
                for dst_key in level_to_keys[next_lvl]:
                    g.edge(
                        group_anchor[src_key],
                        group_anchor[dst_key],
                        style="invis",
                        weight="10",
                        constraint="true",
                        minlen=minlen,
                    )

        # レーン内 root ノードが多い場合、縦2列（MAX_LANE_ROW_WIDTH=2）に折り返す
        # root ノード = 同レーン内に predecessor がないノード（cross=false 遷移の dst でない）
        _sid_to_lane_map: dict[str, str] = {
            str(s.get("id", "")): lane_id_to_name.get(str(s.get("lane", "")), str(s.get("lane", "")))
            for s in steps_in
        }
        same_lane_dst: set[str] = {str(t.get("to", "")) for t in trans_in if not t.get("cross")}
        MAX_LANE_ROW_WIDTH = 2
        for _ln in lane_names:
            roots = [
                str(s.get("id", ""))
                for s in steps_in
                if _sid_to_lane_map.get(str(s.get("id", ""))) == _ln
                and str(s.get("id", "")) not in same_lane_dst
            ]
            if len(roots) > MAX_LANE_ROW_WIDTH:
                for col in range(MAX_LANE_ROW_WIDTH):
                    for row_start in range(0, len(roots) - MAX_LANE_ROW_WIDTH, MAX_LANE_ROW_WIDTH):
                        src_idx = row_start + col
                        dst_idx = row_start + col + MAX_LANE_ROW_WIDTH
                        if src_idx < len(roots) and dst_idx < len(roots):
                            g.edge(roots[src_idx], roots[dst_idx],
                                   style="invis", constraint="true", weight="2")

    # 未分類ステップ（lane 指定なし or 未知のレーン）
    for step in steps_in:
        step_lane_raw = str(step.get("lane", ""))
        step_lane_resolved = lane_id_to_name.get(step_lane_raw, step_lane_raw)
        if step_lane_resolved not in known_lanes:
            sid = str(step.get("id", ""))
            g.node(sid, label=str(step.get("label", "") or step.get("title", "") or step.get("action", "") or step.get("name", "") or sid),
                   shape="box", style="filled,rounded",
                   fillcolor=C_STEP_BG, fontcolor=C_STEP_FG,
                   fontname=FONT_JP, fontsize="10")

    # transitions[] が空で step.next が存在する場合、自動派生する
    if not trans_in:
        trans_in = [
            {"from": str(step.get("id", "")), "to": str(dst)}
            for step in steps_in
            for dst in (step.get("next") or [])
        ]

    # 遷移エッジ
    # cross=True（アクターが変わる遷移）は constraint=false でランク強制を外す
    # → LR モードでレーンが横並びになる（横長画像）問題を防ぐ
    for t in trans_in:
        src = str(t.get("from", ""))
        dst = str(t.get("to", ""))
        cond = t.get("condition", "")
        edge_kw: dict = dict(
            label=cond,
            color=C_EDGE,
            fontname=FONT_JP,
            fontsize="8",
            fontcolor=C_EDGE,
            arrowsize="0.8",
        )
        if t.get("cross"):
            edge_kw["style"] = "dashed"
            edge_kw["weight"] = "0.3"
            if use_anchor_layout:
                # グループをまたぐエッジはランク計算に含めない（同グループ内の cross-lane はそのまま）
                src_grp = _sid_to_group.get(src)
                dst_grp = _sid_to_group.get(dst)
                if src_grp is not None and dst_grp is not None and src_grp != dst_grp:
                    edge_kw["constraint"] = "false"
        g.edge(src, dst, **edge_kw)

    png_bytes = g.pipe(format="png")
    with open(out_path, "wb") as f:
        f.write(png_bytes)
    if _HAS_PIL:
        return _PILImage.open(out_path).size
    return (0, 0)


# ════════════════════════════════════════════════════════════════
# 4. フローチャート（graphviz）
# ════════════════════════════════════════════════════════════════

def _short_label(text: str, max_len: int = 18) -> str:
    """テキストを max_len 文字で打ち切り、超えたら末尾に…を付ける。"""
    text = (text or "").strip()
    return text if len(text) <= max_len else text[:max_len] + "…"


def _wrap_jp(text: str, width: int = 12) -> str:
    """日本語テキストを width 文字で折り返す（\\n区切り）。
    助詞境界（を/に/で/と/の/、/。/・）を優先して折り返し、「す/る」分断を避ける。
    """
    text = (text or "").strip()
    if len(text) <= width:
        return text
    lines = []
    remaining = text
    _PARTICLES = "をにでとのはがも、。・"
    while len(remaining) > width:
        # width ± 2 の範囲で最適な助詞境界を後ろから探す
        best_idx = -1
        search_end = min(width + 2, len(remaining) - 2)
        search_start = max(3, width // 2)
        for i in range(search_end, search_start - 1, -1):
            if i - 1 < len(remaining) and remaining[i - 1] in _PARTICLES:
                best_idx = i
                break
        if best_idx == -1:
            best_idx = width
        lines.append(remaining[:best_idx])
        remaining = remaining[best_idx:]
    if remaining:
        lines.append(remaining)
    return "\\n".join(lines)


def _wrap_name(name: str, max_per_line: int = 14) -> str:
    """CamelCase/スネークケース/アンダースコアの長い名前を max_per_line 文字で折り返す（\\n区切り）。"""
    if len(name) <= max_per_line:
        return name
    import re
    # アンダースコアで先に区切る（Create_CustomerUser → [Create, CustomerUser]）
    underscore_parts = name.split("_")
    tokens: list[str] = []
    for i, up in enumerate(underscore_parts):
        # CamelCase を単語に分割（アンダースコアの直後の部分は次行の頭になる）
        split_words = re.sub(r'([A-Z][a-z]+)', r' \1', up).split()
        tokens.extend(split_words if split_words else [up])
        # 末尾以外はアンダースコアを次のトークン頭に付与しない（単純区切り扱い）
    lines, cur = [], ""
    for w in tokens:
        if cur and len(cur) + len(w) + 1 > max_per_line:
            lines.append(cur)
            cur = w
        else:
            cur = (cur + " " + w).strip() if cur else w
    if cur:
        lines.append(cur)
    return "\\n".join(lines) if lines else name


def render_flowchart(steps: list[dict], out_path: str) -> tuple[int, int]:
    """
    process_steps から処理フロー図PNGを生成する。

    設計方針:
      - 図の中: 番号バッジ + 6〜8文字の一言アクション（何をするか）
      - 図の外: コンポーネント名を各ノード下に小テキストで表示（HTMLラベル使用）
      - 詳細な処理内容・分岐条件は図下の表で補完

    steps: [{step, title, description, component, branch, next:[{to, condition}]}]
    """
    if not _HAS_GV:
        raise RuntimeError("graphviz が利用できません")

    # step番号 → バッジ文字（①②…⑳、超えたら(N)）
    _BADGES = "①②③④⑤⑥⑦⑧⑨⑩⑪⑫⑬⑭⑮⑯⑰⑱⑲⑳"

    def _badge(n: int) -> str:
        return _BADGES[n - 1] if 1 <= n <= len(_BADGES) else f"({n})"

    import re as _re

    _FC_FONT = "Meiryo"

    # I-2a: ROW_SIZE をステップ数から動的決定
    # Phase X: ≤6 ステップは ROW_SIZE=ceil(n/2) で 2 行に分割。
    # AA-2: 7+ ステップは ROW_SIZE=4 に固定。全 FG の自然 PNG 幅が揃い zoom 表示サイズが統一できる。
    #       以前は平方根ベースで最大 6 列だったが、列数が増えると自然幅が FG 間で最大 1.77× 差になっていた。
    _step_n = len(steps)
    if _step_n <= 6 and _step_n >= 2:
        ROW_SIZE = max(2, math.ceil(_step_n / 2))  # 4steps→2行, 6steps→3行
    else:
        ROW_SIZE = 4 if steps else 4
    need_wrap = _step_n > ROW_SIZE

    g = _gv.Digraph(
        "flowchart",
        graph_attr={
            "bgcolor": "white",
            "rankdir": "TB",
            "splines": "ortho",
            "nodesep": "0.3",
            "ranksep": "0.83",
            "fontname": _FC_FONT,
            "pad": "0.4",
            "dpi": "150",
            # AA-2e: size 指定なし（graphviz 全体縮小を止める）。
            # ノード width=1.5 × 4 列 + nodesep で自然幅 ~1155px に収まり Excel 表示 1120 とほぼ等倍。
            # fontsize=14pt がそのまま出るため文字が潰れない。
        },
    )

    # AA-2g: プラットフォームプレフィックス除去パターン
    _PLAT_PREFIX = _re.compile(
        r'^(?:Experience\s*Cloud(?:の)?|コミュニティ(?:の)?|ポータル(?:の)?)'
    )

    def _short_flow_label(desc: str) -> str:
        """一言まとめラベルを抽出する（6〜10 字の名詞句）。"""
        if not desc:
            return ""
        # 括弧注記・英字 API 名注釈を除去
        s = _re.sub(r'[（(][^）)]{1,50}[）)]', '', desc).strip()
        s = _re.sub(r'[。\s]+$', '', s).strip()

        # 「〜画面で〜」パターン → 画面名（「画面」を除く）が最良の一言
        m_scr = _re.match(r'^(.{2,20}画面)で', s)
        if m_scr:
            scr = _PLAT_PREFIX.sub('', m_scr.group(1)).strip()
            scr = _re.sub(r'画面$', '', scr).strip()
            return scr[:10] if scr else m_scr.group(1)[:10]

        # 末尾の冗長な動詞句を除去
        s = _re.sub(
            r'(?:処理を担当する|を担当する|の処理を行う|を行う|を担う'
            r'|する処理を担う|処理する|処理を行う|します)$',
            '', s
        ).strip()

        # 「Xが〜」「Xは〜」構造 → 述語部分だけ取る
        m_subj = _re.match(r'^.{1,8}(?:が|は)(.{3,})$', s)
        if m_subj:
            sub = m_subj.group(1).strip()
            sub = _re.sub(
                r'(?:処理を担当する|を担当する|を行う|をする|する)$', '', sub
            ).strip()
            if 2 < len(sub) <= 12:
                s = sub

        # 読点/句点で分割し、最初の意味節を使用
        s = _re.split(r'[、。,]', s)[0].strip()
        return s[:10]

    def _make_step_label(step) -> tuple[str, int]:
        """ノードのラベル文字列と折り返し後の最大行字数を返す。"""
        n     = int(step.get("step", 0))
        badge = _badge(n)

        # AA-2h: LLM 生成の flow_label が最優先。空なら heuristic フォールバック。
        short = step.get("flow_label", "").strip()
        if not short:
            raw = step.get("description", "") or step.get("title", "") or step.get("box_label", "")
            short = _short_flow_label(raw)
        if not short:
            short = (step.get("description", "") or "")[:10]

        # 5 字/行で折り返し（fixedsize ノードに収める）
        wrapped = _wrap_jp(short, 5)
        lines = wrapped.split("\\n")
        if len(lines) > 2:
            lines = lines[:2]

        # AA-3a: 8字超の行は 7字+… に強制カット（図形はみ出し防止）
        truncated = []
        for line in lines:
            if len(line) > 8:
                line = line[:7] + "…"
            truncated.append(line)

        wrapped_final = "\\n".join(truncated)
        label = badge + "\\n" + wrapped_final
        max_len = max((len(li) for li in truncated), default=0)
        return label, max_len

    # AA-3a: 全ノードで共通フォントサイズを動的決定（最大行字数ベース）
    _step_labels = {str(s.get("step", "")): _make_step_label(s) for s in steps}
    _max_line_chars = max((c for _, c in _step_labels.values()), default=0)
    if _max_line_chars <= 5:
        _step_fontsize = "14"
    elif _max_line_chars == 6:
        _step_fontsize = "13"
    elif _max_line_chars == 7:
        _step_fontsize = "12"
    else:  # 8（AA-3a の強制カット後の最大）
        _step_fontsize = "11"

    def _draw_step_node(parent, step):
        sid    = str(step.get("step", ""))
        branch = step.get("branch", "")
        label, _ = _step_labels[sid]

        # AA-2g: 全 FG で同一固定サイズ（FG-010 baseline）
        # AA-3a: fontsize は全ノード共通の動的値（最大行字数から算出）
        common = dict(
            label=label, fontname=_FC_FONT, fontsize=_step_fontsize,
            width="1.5", height="0.85",
            margin="0.12,0.10",
            fixedsize="true",
        )
        if branch:
            parent.node(sid, shape="diamond", style="filled",
                        fillcolor="#FFF2CC", fontcolor="#7F6000", **common)
        else:
            parent.node(sid, shape="box", style="filled,rounded",
                        fillcolor=C_STEP_BG, fontcolor="white", **common)

    def _draw_comp_label(step):
        sid       = str(step.get("step", ""))
        component = step.get("component", "")
        cid       = f"_c{sid}"
        g.node(cid,
               label=_wrap_name(component, 12) if component else "",
               shape="none", margin="0",
               fontname=_FC_FONT, fontsize="10", fontcolor="#555555")
        g.edge(sid, cid, style="invis", weight="100")

    if need_wrap:
        # 複数行: ROW_SIZE ごとに rank=same サブグラフ → 行末→次行頭エッジで折り返し
        chunks = [steps[i:i + ROW_SIZE] for i in range(0, len(steps), ROW_SIZE)]
        for ri, chunk in enumerate(chunks):
            with g.subgraph(name=f"_row_{ri}") as row:
                row.attr(rank="same")
                for step in chunk:
                    _draw_step_node(row, step)
        # I-2a: 行間を縦方向に強制するため、各行の先頭同士を invisible edge で連結
        for ri in range(len(chunks) - 1):
            head_a = str(chunks[ri][0].get("step", ""))
            head_b = str(chunks[ri + 1][0].get("step", ""))
            if head_a and head_b:
                g.edge(head_a, head_b, style="invis", weight="50", minlen="2")
        for step in steps:
            _draw_comp_label(step)
    else:
        # 1行: 従来通り全ステップを rank=same
        with g.subgraph() as top:
            top.attr(rank="same")
            for step in steps:
                _draw_step_node(top, step)
        with g.subgraph() as bot:
            bot.attr(rank="same")
            for step in steps:
                _draw_comp_label(step)

    # フロー矢印（ステップ間）
    has_next = any(step.get("next") for step in steps)
    if has_next:
        for step in steps:
            src = str(step.get("step", ""))
            for nxt in (step.get("next") or []):
                cond = _short_label(nxt.get("condition", ""), 8)
                g.edge(src, str(nxt["to"]), label=cond,
                       color=C_EDGE, fontname=_FC_FONT, fontsize="10", fontcolor=C_EDGE,
                       arrowsize="0.9", penwidth="1.3")
    else:
        for i, step in enumerate(steps[:-1]):
            src = str(step.get("step", ""))
            dst = str(steps[i + 1].get("step", ""))
            g.edge(src, dst, color=C_EDGE, arrowsize="0.9", penwidth="1.3")

    png_bytes = g.pipe(format="png")
    with open(out_path, "wb") as f:
        f.write(png_bytes)
    if _HAS_PIL:
        return _PILImage.open(out_path).size
    return (0, 0)


# ════════════════════════════════════════════════════════════════
# 5. コンポーネント依存図（graphviz）
# ════════════════════════════════════════════════════════════════

_COMP_COLORS: dict[str, tuple[str, str]] = {
    "Apex":        (C_SF_CORE,  C_SF_LABEL),
    "LWC":         (C_HDR_BLUE, C_SF_LABEL),
    "Aura":        (C_HDR_BLUE, C_SF_LABEL),
    "Visualforce": ("#70AD47",  "#FFFFFF"),
    "Flow":        ("#00B0F0",  "#000000"),
    "画面フロー":  ("#00B0F0",  "#000000"),
    "Trigger":     ("#1F3864",  "#FFFFFF"),
    "Batch":       ("#5A5A5A",  "#FFFFFF"),
    "User":        ("#FFC000",  "#000000"),
    "Entry":       ("#A5A5A5",  "#FFFFFF"),
}

# コンポーネント図: 起動元ノードの日本語ラベル
_TRIGGER_LABEL_JA: dict[str, str] = {
    "User":        "操作者",
    "LWC":         "画面操作",
    "Aura":        "画面操作",
    "Visualforce": "画面操作",
    "Trigger":     "レコード更新",
    "Batch":       "バッチ処理",
    "Flow":        "自動起動フロー",
    "Entry":       "処理起点",
}

def render_component_diagram(
    components: list[dict],
    out_path: str,
    steps: list[dict] | None = None,
) -> tuple[int, int]:
    """
    コンポーネント一覧から依存関係図PNGを生成する。

    components: [{api_name, type, role, callees:[str]}]
    steps:      process_steps（任意）。呼び出し順序と起動元の補完に使用。

    描画ルール:
      - callees で明示された依存は矢印で描画
      - steps の component 順序から、直接呼び出し関係がないコンポーネント同士を
        順番ラベル付き矢印で補完
      - steps の trigger / 最初のステップから起動元（Flow/Trigger）を推定してノード追加
    """
    if not _HAS_GV:
        raise RuntimeError("graphviz が利用できません")

    steps = steps or []
    known = {c.get("api_name", "") for c in components}

    # steps から呼び出し順マップを構築: api_name → step番号
    step_order: dict[str, int] = {}
    for s in steps:
        comp = s.get("component", "")
        if comp and comp not in step_order:
            step_order[comp] = int(s.get("step", 0))

    # components の type 分布を取得（起動元ノード推定に使用）
    _UI_TYPES = {"Visualforce", "LWC", "Aura"}
    type_counts: dict[str, int] = {}
    for c in components:
        t = c.get("type", "")
        if t:
            type_counts[t] = type_counts.get(t, 0) + 1
    n_comp = max(len(components), 1)

    # 起動元ノードを推定（steps のキーワード → components の type 分布 の順）
    trigger_node: str | None = None
    trigger_type: str | None = None
    if steps:
        first = steps[0]
        desc = (first.get("description", "") + first.get("title", "")).lower()
        if "trigger" in desc or "triggger" in desc:
            trigger_type = "Trigger"
        elif "batch" in desc or "schedule" in desc:
            trigger_type = "Batch"
        elif "lwc" in desc or "lightning" in desc:
            trigger_type = "LWC"
        elif "flow" in desc:
            trigger_type = "Flow"

    if trigger_type is None:
        # components の type 分布から推定（過半数ルール）
        ui_count = sum(type_counts.get(t, 0) for t in _UI_TYPES)
        if ui_count >= n_comp * 0.5:
            trigger_type = "User"  # ユーザー操作起点
        elif type_counts.get("Trigger", 0):
            trigger_type = "Trigger"
        elif type_counts.get("Batch", 0):
            trigger_type = "Batch"
        elif (type_counts.get("Flow", 0) + type_counts.get("画面フロー", 0)) >= n_comp * 0.3:
            trigger_type = "Flow"
        elif n_comp > 0:
            # X-4c fallback: UI もバッチも Trigger もないが components はある（Apex+Flow 混在 FG 等）
            # "Entry" ラベルで「処理起点」として表示する
            trigger_type = "Entry"

    _trigger_label: str = ""
    if trigger_type:
        trigger_node = "_trigger"  # ノードIDは固定（日本語は label で別途指定）
        _trigger_label = _TRIGGER_LABEL_JA.get(trigger_type, f"[{trigger_type}]")

    # callees で参照されているコンポーネント（被呼び出し側）
    called_by: set[str] = set()
    for comp in components:
        for c in comp.get("callees", []):
            called_by.add(c)

    # トップレベルコンポーネント（誰からも呼ばれていない）の型を確認
    _type_lookup = {c.get("api_name", ""): c.get("type", "") for c in components}
    top_level_types = {
        _type_lookup.get(c.get("api_name", ""), "")
        for c in components if c.get("api_name", "") not in called_by
    }

    # LWC/Aura がトップレベルにある場合は「画面操作」ノードを省略（UI コンポーネントが起点を担う）
    if trigger_type in {"LWC", "Aura"} and any(
        t in {"LWC", "Aura"} for t in top_level_types
    ):
        trigger_node = None
        _trigger_label = ""

    # callees が全部空かつノード数が多い場合は「グリッド配置」モード
    # （多量 UI コンポーネントの一覧表示に適したレイアウト）
    # Phase V: 10 コンポーネント以上なら callees の有無に関わらず grid で描画
    #           callees を solid edge として上書き描画する
    # Phase X: 6 コンポーネント以上に閾値を下げ、少数 FG でも格子配置で横長を防ぐ
    all_callees_empty = not any(c.get("callees") for c in components)
    num_nodes = len(components) + (1 if trigger_node else 0)
    use_grid = len(components) >= 6

    if use_grid:
        # Q-3 (image4 縦長化): grid モードは rankdir=TB にして行 subgraph を縦方向に並べる
        _rankdir, _splines = "TB", "line"
    elif num_nodes <= 6:
        _rankdir, _splines = "LR", "ortho"
    elif num_nodes <= 18:
        _rankdir, _splines = "TB", "ortho"
    else:
        _rankdir, _splines = "TB", "polyline"

    _comp_graph_attr = {
        "bgcolor": "white",
        "rankdir": _rankdir,
        "splines": _splines,
        "nodesep": "0.3" if use_grid or num_nodes > 18 else "0.5",
        "ranksep": "0.5" if use_grid else ("0.6" if num_nodes > 18 else "1.0"),
        "fontname": FONT_JP,
        "pad": "0.4",
        "dpi": "150",
        "concentrate": "true",
    }
    # AA: size/ratio 強制スケーリング撤廃 → FG 間でノード密度が揃う（幅は PIL resize で制御）

    g = _gv.Digraph(
        "components",
        graph_attr=_comp_graph_attr,
    )

    # 起動元ノード
    if trigger_node:
        fill, fg = _COMP_COLORS.get(trigger_type, ("#00B0F0", "#000000"))
        g.node(trigger_node,
               label=_trigger_label,
               shape="box", style="filled,rounded",
               fillcolor=fill, fontcolor=fg,
               fontname=FONT_JP, fontsize="10", width="1.2")

    # コンポーネントノード（名前 + 種別のみ。ロールは表に記載するため除外）
    if use_grid:
        import math as _math
        type_lookup = {c.get("api_name", ""): c.get("type", "Apex") for c in components}
        entry_types = {"Visualforce", "LWC", "Aura"}
        # U-2: primary / standard を分類
        # - primary UI = VF/LWC/Aura で callees を持つ（実業務 UI、Apex controller を呼ぶ）
        # - standards  = VF/LWC/Aura で callees を持たない（EC 標準テンプレ・エラーページ）
        #   step_order_bases での判定は使わない理由: Phase M 以降 process_steps が全コンポーネントを
        #   カバーするようになったため、step_order に全 VF が含まれ primary/standards の区別に使えない
        primaries_set: set[str] = set()
        standards_set: set[str] = set()
        for c in components:
            api = c.get("api_name", "")
            ctype = c.get("type", "")
            if ctype not in entry_types:
                continue
            if api in called_by:
                continue  # 誰かから呼ばれている VF は primary 側のグリッドに含める
            if c.get("callees"):
                primaries_set.add(api)
            else:
                standards_set.add(api)

        # primary block（primary + called_by UI + Apex/Trigger/Batch/Flow）
        _type_rank = {"Visualforce": 0, "LWC": 0, "Aura": 0,
                      "Apex": 1, "Trigger": 2, "Batch": 2,
                      "Flow": 3}
        primary_names = sorted(
            [c.get("api_name", "") for c in components
             if c.get("api_name", "") not in standards_set],
            key=lambda n: (_type_rank.get(type_lookup.get(n, ""), 9),
                           step_order.get(n, 999), n)
        )
        standard_names = sorted(standards_set)

        def _make_rows(names: list[str]) -> list[list[str]]:
            if not names:
                return []
            rw = min(6, max(4, int(_math.sqrt(len(names)) + 0.5)))
            return [names[i:i + rw] for i in range(0, len(names), rw)]

        primary_rows = _make_rows(primary_names)
        standard_rows = _make_rows(standard_names)

        def _draw_node(scope, name: str) -> None:
            ctype = type_lookup.get(name, "Apex")
            fill, fg = _COMP_COLORS.get(ctype, ("#5A5A5A", "#FFFFFF"))
            lbl = f"{_wrap_name(name, 14)}\\n[{ctype}]"
            scope.node(name,
                       label=lbl,
                       shape="box", style="filled,rounded",
                       fillcolor=fill, fontcolor=fg,
                       fontname=FONT_JP, fontsize="9", width="1.8")

        # primary の各行（不可視 cluster）
        for ri, row in enumerate(primary_rows):
            with g.subgraph(name=f"cluster_row_{ri}") as sg:
                sg.attr(rank="same")
                sg.attr(style="invis")
                for name in row:
                    _draw_node(sg, name)
        for ri in range(len(primary_rows) - 1):
            g.edge(primary_rows[ri][0], primary_rows[ri + 1][0],
                   style="invis", weight="10")

        # standard 群を visible cluster で描画（primary block の下にまとまる）
        if standard_rows:
            with g.subgraph(name="cluster_standards") as cl:
                cl.attr(label="標準テンプレート・エラーページ",
                        style="dashed,rounded",
                        color="#A0A0A0",
                        fontname=FONT_JP,
                        fontsize="10",
                        fontcolor="#606060",
                        labeljust="l")
                for si, srow in enumerate(standard_rows):
                    with cl.subgraph(name=f"cluster_std_row_{si}") as sg:
                        sg.attr(rank="same")
                        sg.attr(style="invis")
                        for name in srow:
                            _draw_node(sg, name)
                for si in range(len(standard_rows) - 1):
                    cl.edge(standard_rows[si][0], standard_rows[si + 1][0],
                            style="invis", weight="10")
            # primary block 末尾 → cluster 先頭の不可視エッジで縦方向の順序を保証
            if primary_rows and standard_rows:
                g.edge(primary_rows[-1][0], standard_rows[0][0],
                       style="invis", weight="5")

        # U-2: trigger_node → primary UI に fan-out（+ cluster_standards に 1 本）
        if trigger_node:
            primaries_ordered = [n for n in primary_names if n in primaries_set]
            primaries_ordered = sorted(primaries_ordered,
                                       key=lambda n: (step_order.get(n, 999), n))
            # Z-4d: UI が一つも無い FG では Apex/Flow/Trigger を fan-out 対象にする（[:6] 上限を撤廃）
            if not primaries_ordered:
                fallback_types = {"Apex", "Flow", "Trigger", "Batch", "Schedulable",
                                  "AutoLaunchedFlow", "ScheduledFlow"}
                primaries_ordered = sorted(
                    [c.get("api_name", "") for c in components
                     if c.get("type", "") in fallback_types
                     and c.get("api_name", "") not in standards_set],
                    key=lambda n: (step_order.get(n, 999), n)
                )
            for name in primaries_ordered:  # Z-4d: [:6] 上限撤廃 — 孤立コンポーネントをゼロにする
                g.edge(trigger_node, name,
                       color=C_EDGE, arrowsize="0.7", style="dashed")
            # 標準テンプレ群 → 1 本の dashed（cluster をヘッドに）
            if standard_names:
                g.attr(compound="true")
                g.edge(trigger_node, standard_names[0],
                       color="#A0A0A0", arrowsize="0.6",
                       style="dashed", lhead="cluster_standards")
        # Z-4d: callees/called_by/fan-out のどの経路にも無い完全孤立ノードを救済
        _connected = set(primaries_ordered if trigger_node else []) | set(called_by)
        for _c in components:
            _api = _c.get("api_name", "")
            if not _api or _api in _connected or _api in standards_set:
                continue
            if any(_api in (_other.get("callees") or []) for _other in components):
                continue  # callee として他コンポーネントから参照されている
            if trigger_node:
                g.edge(trigger_node, _api, color=C_EDGE, arrowsize="0.5",
                       style="dotted", constraint="false")
        # K-D: callees の明示依存エッジ（grid モードでも描画）
        # VF→Apex 等のコントローラ呼び出しを solid 矢印で描く
        drawn_grid_edges: set[tuple[str, str]] = set()
        for comp in components:
            src = comp.get("api_name", "")
            for callee in comp.get("callees", []):
                if not callee or (src, callee) in drawn_grid_edges:
                    continue
                if callee not in known:
                    g.node(callee, label=callee,
                           shape="box", style="filled,rounded",
                           fillcolor=C_EXT_BG, fontcolor=C_EXT_FG,
                           fontname=FONT_JP, fontsize="9")
                g.edge(src, callee,
                       color=C_EDGE, arrowsize="0.7",
                       style="solid", constraint="false")
                drawn_grid_edges.add((src, callee))
        # U-1: step_order 点線は廃止（callees の solid 矢印だけで依存関係は伝わる。
        # 隣接エッジを追加するとノイズになり、かつ 「矢印が消えた」印象を生む元だった）
    else:
        for comp in components:
            name  = comp.get("api_name", "")
            ctype = comp.get("type", "Apex")
            fill, fg = _COMP_COLORS.get(ctype, ("#5A5A5A", "#FFFFFF"))
            lbl = f"{_wrap_name(name, 14)}\\n[{ctype}]"
            g.node(name,
                   label=lbl,
                   shape="box", style="filled,rounded",
                   fillcolor=fill, fontcolor=fg,
                   fontname=FONT_JP, fontsize="9", width="1.8")

        # callees の明示依存エッジ
        for comp in components:
            src = comp.get("api_name", "")
            for callee in comp.get("callees", []):
                if callee not in known:
                    g.node(callee, label=callee,
                           shape="box", style="filled,rounded",
                           fillcolor=C_EXT_BG, fontcolor=C_EXT_FG,
                           fontname=FONT_JP, fontsize="9")
                g.edge(src, callee, color=C_EDGE, arrowsize="0.7")

        # 起動元 → 直接呼び出されていないトップレベルコンポーネントをエッジ追加
        if trigger_node:
            top_level = [
                c.get("api_name", "") for c in components
                if c.get("api_name", "") not in called_by
            ]
            top_level_sorted = sorted(top_level, key=lambda n: step_order.get(n, 999))
            for i, name in enumerate(top_level_sorted, 1):
                g.edge(trigger_node, name,
                       color=C_EDGE, arrowsize="0.7",
                       style="dashed")

    png_bytes = g.pipe(format="png")
    with open(out_path, "wb") as f:
        f.write(png_bytes)
    if _HAS_PIL:
        return _PILImage.open(out_path).size
    return (0, 0)


# ════════════════════════════════════════════════════════════════
# 6. コンポーネント×オブジェクト参照マトリクス
# ════════════════════════════════════════════════════════════════

def render_object_access_matrix(
    object_access: list[dict],
    components: list[dict],
    related_objects: list[dict],
    out_path: str,
) -> tuple[int, int]:
    """コンポーネント×オブジェクト参照マトリクス図を生成する。

    object_access: [{"component": "X", "object": "Y", "operation": "R|W|RW|INSERT"}]
    components:    [{"api_name": "X", "type": "Apex", ...}]
    related_objects: [{"api_name": "Y", "label": "Z", ...}]
    """
    if not _HAS_GV:
        raise RuntimeError("graphviz が利用できません")

    # DML操作のあるコンポーネントのみ列に使う（object_access に登場する順序を保持）
    seen: list[str] = []
    for entry in object_access:
        comp = entry.get("component", "")
        if comp and comp not in seen:
            seen.append(comp)
    comp_names = seen

    obj_names  = [o.get("api_name", "") for o in related_objects]
    obj_labels = {o.get("api_name", ""): o.get("label", o.get("api_name", ""))
                  for o in related_objects}

    # アクセスマトリクス構築
    matrix: dict[str, dict[str, str]] = {o: {c: "" for c in comp_names} for o in obj_names}
    for entry in object_access:
        obj  = entry.get("object", "")
        comp = entry.get("component", "")
        op   = entry.get("operation", "")
        if obj in matrix and comp in matrix[obj]:
            matrix[obj][comp] = op

    # 操作種別の色
    _OP_COLOR = {
        "R":      "#D9E1F2",
        "W":      "#FFC7CE",
        "RW":     "#FFEB9C",
        "INSERT": "#C6EFCE",
    }
    HDR_BG = "#1F3864"
    HDR_FG = "white"

    def _td(content: str, bg: str = "white", bold: bool = False, align: str = "CENTER",
            fsize: str = "9") -> str:
        inner = f"<B>{content}</B>" if bold else content
        return (f'<TD BGCOLOR="{bg}" ALIGN="{align}" '
                f'CELLPADDING="4"><FONT POINT-SIZE="{fsize}">{inner}</FONT></TD>')

    # ヘッダ行
    header_cells = [_td("オブジェクト", bg=HDR_BG, bold=True,
                        align="LEFT", fsize="9").replace(f'COLOR="{HDR_BG}"',
                        f'COLOR="{HDR_BG}"').replace("<FONT", f'<FONT COLOR="{HDR_FG}"')]
    for comp in comp_names:
        header_cells.append(
            f'<TD BGCOLOR="{HDR_BG}" ALIGN="CENTER" CELLPADDING="4">'
            f'<FONT POINT-SIZE="8" COLOR="{HDR_FG}"><B>{comp}</B></FONT></TD>'
        )
    rows = [f'<TR>{"".join(header_cells)}</TR>']

    # データ行
    for obj in obj_names:
        label = obj_labels.get(obj, obj)
        cells = [
            f'<TD BGCOLOR="#F2F2F2" ALIGN="LEFT" CELLPADDING="4">'
            f'<FONT POINT-SIZE="9"><B>{label}</B></FONT><BR/>'
            f'<FONT POINT-SIZE="7" COLOR="#666666">{obj}</FONT></TD>'
        ]
        for comp in comp_names:
            op = matrix[obj][comp]
            bg = _OP_COLOR.get(op, "white")
            if op:
                cells.append(
                    f'<TD BGCOLOR="{bg}" ALIGN="CENTER" CELLPADDING="4">'
                    f'<FONT POINT-SIZE="9"><B>{op}</B></FONT></TD>'
                )
            else:
                cells.append(
                    '<TD ALIGN="CENTER" CELLPADDING="4">'
                    '<FONT POINT-SIZE="9" COLOR="#AAAAAA">-</FONT></TD>'
                )
        rows.append(f'<TR>{"".join(cells)}</TR>')

    table_html = (
        '<<TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0" BGCOLOR="white">'
        + "".join(rows)
        + "</TABLE>>"
    )

    g = _gv.Digraph(
        "obj_matrix",
        graph_attr={
            "bgcolor": "white",
            "fontname": FONT_JP,
            "pad": "0.3",
            "dpi": str(DPI),
        },
    )
    g.node("matrix", label=table_html, shape="none", margin="0")

    png_bytes = g.pipe(format="png")
    with open(out_path, "wb") as f:
        f.write(png_bytes)
    if _HAS_PIL:
        return _PILImage.open(out_path).size
    return (0, 0)


# ════════════════════════════════════════════════════════════════
# PNG 正規化ヘルパー（swimlane / フローチャート 共通）
# ════════════════════════════════════════════════════════════════

def _pad_png_to_aspect(png_path: str, target_w_h: float, align: str = "center") -> str:
    """PNG を target_w_h（幅/高さ）のアスペクトに白背景で padding して返す。
    FG ごとに異なる graphviz 出力アスペクトを正規化し、全 FG で同一表示サイズを保証する。
    元ファイルは保持し、padding 済みファイルを隣接 .pad.png として返す。
    align="left" にすると画像を左寄せで貼り付け（右端に白帯）。デフォルトは中央。
    """
    try:
        img = _PILImage.open(png_path)
        w, h = img.width, img.height
        cur = w / h if h else 1.0
        if abs(cur - target_w_h) < 0.02:
            return png_path
        if cur < target_w_h:
            new_w = int(h * target_w_h)
            new_h = h
        else:
            new_w = w
            new_h = int(w / target_w_h)
        canvas = _PILImage.new("RGBA", (new_w, new_h), (255, 255, 255, 255))
        paste_x = 0 if align == "left" else (new_w - w) // 2
        paste_y = (new_h - h) // 2
        canvas.paste(img, (paste_x, paste_y))
        out = png_path[:-4] + ".pad.png"
        canvas.convert("RGB").save(out, "PNG")
        return out
    except Exception as e:
        print(f"  [WARN] PNG padding 失敗({png_path}): {e}")
        return png_path


def _resize_png_to_width(png_path: str, target_width: int) -> str:
    """PNG を target_width にアスペクト維持リサイズ。
    埋め込み前に幅を固定することで全 FG で同一表示サイズを保証する。
    """
    try:
        img = _PILImage.open(png_path)
        if img.width == target_width:
            return png_path
        scale = target_width / img.width
        new_h = max(1, int(img.height * scale))
        resized = img.resize((target_width, new_h), _PILImage.LANCZOS)
        out = png_path[:-4] + ".wfix.png"
        resized.save(out, "PNG")
        return out
    except Exception as e:
        print(f"  [WARN] PNG リサイズ失敗({png_path}): {e}")
        return png_path


# ════════════════════════════════════════════════════════════════
# Excel 埋め込みヘルパー
# ════════════════════════════════════════════════════════════════

def embed_image_in_sheet(ws, img_path: str, anchor_row: int, anchor_col: int = 2,
                         max_width_px: int = 1200, dpi: int = DPI) -> int:
    """
    PNG をワークシートに埋め込み、画像の高さに合わせた行数を返す。

    anchor_row: 画像を配置する開始行
    anchor_col: 画像を配置する開始列（デフォルト=2）
    戻り値: 画像が占める行数（行高 20pt 換算）
    """
    from openpyxl.drawing.image import Image as XLImage
    from openpyxl.utils import get_column_letter

    if not _HAS_PIL:
        raise RuntimeError("Pillow が必要です")

    img = _PILImage.open(img_path)
    w_px, h_px = img.size

    # 最大幅に合わせてスケール
    scale = min(1.0, max_width_px / w_px)
    display_w = int(w_px * scale)
    display_h = int(h_px * scale)

    xl_img = XLImage(img_path)
    # EMU: 1pt = 12700 EMU, 1px@96dpi ≈ 9525 EMU
    emu_per_px = 914400 / dpi
    xl_img.width  = int(display_w * emu_per_px / 9525)
    xl_img.height = int(display_h * emu_per_px / 9525)
    xl_img.anchor = f"{get_column_letter(anchor_col)}{anchor_row}"

    ws.add_image(xl_img)

    # 行高を調整（画像高さに合わせて必要行数を確保）
    pt_per_row = 20
    pt_total   = display_h * 0.75  # px → pt 概算
    n_rows     = max(1, int(pt_total / pt_per_row) + 1)
    for r in range(anchor_row, anchor_row + n_rows):
        ws.row_dimensions[r].height = pt_per_row

    return n_rows
