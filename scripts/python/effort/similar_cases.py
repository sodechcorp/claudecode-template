"""
similar_cases.py — sf-effort-estimator Step 3 で、似た課題の候補を case-index.md から集めて並べる。

case-index.md の「作業の型」の列（最後の列）が対象と同じ行を全部集め、型がまだ無い行は
言葉の重なり（jaccard）の大きい順に 20 件出す。--extra の課題（名指しの前例・effort-calibration の
代表アンカー）は、型が同じ・違う・空・索引に無い に分けて出す。日本語は表示しない（Windows のコンソールで化けるため）。

列の位置は見出しではなく行のセルの数で決める（見出しが古い8列のまま新しい行が入った索引があるため）:
    12 セル = 現行（11 列目が工数、12 列目が作業の型） / 11 セル = 作業の型の列が無い現行 / 8 セル = 旧形式（8 列目が工数）

使い方（プロジェクトのルートで。標準入力の1行目が「型: {主な型}」、2行目以降が対象側の文）:
    python scripts/python/effort/similar_cases.py [--self GF-123] [--extra GF-1,GF-2] <<'EOF'
    型: 既存の一部を少し変える
    {件名・本文・対応方針・部品名}
    EOF
  --self（対象の課題ID。候補から除く）・--extra は、無ければ省く。

出力（1行ずつ。{課題ID}({jaccard},{索引の工数の数字 or -}) の並び。同じ jaccard は索引の行の順〔新しい順〕）:
    index: ok|missing
    typed_column: yes|no                # 型の付いた行が1つでもあるか
    same_type: ...                      # 型が対象と同じ行（言葉が重ならなくても全部）
    untyped_top: ...                    # 型が無い・空・`-`・表に無い名前の行のうち jaccard > 0 の上位 20 件
    extra_same: ... / extra_other: ... / extra_untyped: ... / extra_missing: {課題ID} ...
        # --extra の課題のうち、上の2行に出ていないもの。missing は索引に行が無い

作業の型の名前と順番は .claude/agents/sf-effort-estimator.md Step 2 の表と同じ。表を変えたら TYPES も直す。
"""
import argparse
import pathlib
import re
import sys

TYPES = [
    "設定だけの変更",
    "既存の一部を少し変える",
    "既存と同じ形の追加",
    "Apex の変更・新設",
    "フローの変更・新設",
    "画面の変更・新設",
    "新しい仕組み",
    "原因が分かっているバグ",
    "原因の切り分けが中心",
    "その他",
]
KEY = re.compile(r"[A-Z][A-Z0-9_]*-\d+")


def tokens(s):
    t = set(re.findall(r"[ァ-ヴー]{2,}|[A-Za-z][A-Za-z0-9_]+", s))
    for run in re.findall(r"[一-龥々]+", s):
        t.update(run[i:i + 2] for i in range(len(run) - 1))
    return t


def jaccard(a, b):
    return round(len(a & b) / len(a | b), 3) if a | b else 0.0


def cells(line):
    return [c.strip() for c in line.split("|")[1:-1]]


def parse_row(c):
    """1行のセルから (候補側の文, 索引の工数, 型) を返す。列の位置はセルの数で決める"""
    if len(c) >= 11:  # 現行: 症状/要件・採用方針・対象コンポーネント・関連用語・工数 = 4・6・8・9・10 列目（0 始まりで 3,5,7,8,9）
        text = " ".join([c[3], c[5], c[7], c[8]])
        hours = c[9]
        kind = c[11] if len(c) >= 12 else ""
    else:  # 旧形式（8 セル: 日付・課題ID・種別・症状・対象・方針・関連用語・工数）とそれ以外の短い行
        text, hours, kind = " ".join(c[3:-1]), c[-1], ""
    m = re.match(r"\s*(\d+(?:\.\d+)?)", hours)
    return text, (m.group(1) if m else "-"), (kind if kind in TYPES else "")


def read_rows(path):
    """[(課題ID, 候補側の文, 索引の工数, 型)] を索引の行の順に返す（同じ課題IDは先の行を使い、型だけ後の行で補う）"""
    order, rows = [], {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.lstrip().startswith("|"):
            continue
        c = cells(line)
        if len(c) < 4 or not KEY.fullmatch(c[1]):
            continue
        text, hours, kind = parse_row(c)
        if c[1] in rows:
            if not rows[c[1]][2] and kind:
                rows[c[1]] = (rows[c[1]][0], rows[c[1]][1], kind)
            continue
        order.append(c[1])
        rows[c[1]] = (text, hours, kind)
    return [(k, *rows[k]) for k in order]


def fmt(items):
    return " ".join(f"{key}({j},{hours})" for j, key, hours in items)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--self", dest="self_id", default="", help="対象課題の課題ID（候補から除く）")
    ap.add_argument("--extra", default="", help="名指しの前例・代表アンカーの課題ID（カンマ区切り）")
    ap.add_argument("--index", default="docs/knowledge/case-index.md")
    args = ap.parse_args()

    sys.stdin.reconfigure(encoding="utf-8")
    first, _, rest = sys.stdin.read().partition("\n")
    want = re.sub(r"^\s*型\s*[:：]\s*", "", first).strip()
    if want not in TYPES:
        print(f"error: unknown type (first line must be one of the {len(TYPES)} types in sf-effort-estimator Step 2)")
        sys.exit(2)

    path = pathlib.Path(args.index)
    if not path.exists():
        print("index: missing")
        return
    rows = read_rows(path)
    target = tokens(rest)
    scored = [(jaccard(target, tokens(text)), key, hours, kind)
              for key, text, hours, kind in rows if key != args.self_id]
    by_key = {key: (j, key, hours, kind) for j, key, hours, kind in scored}
    # sorted は安定なので、同じ jaccard は索引の行の順（新しい順）のまま
    same = sorted([s for s in scored if s[3] == want], key=lambda s: -s[0])
    untyped = sorted([s for s in scored if not s[3] and s[0] > 0], key=lambda s: -s[0])[:20]
    shown = {s[1] for s in same + untyped}

    extra = {"same": [], "other": [], "untyped": [], "missing": []}
    for key in dict.fromkeys(k.strip() for k in args.extra.split(",") if k.strip()):
        if key == args.self_id or key in shown:
            continue
        if key not in by_key:
            extra["missing"].append(key)
            continue
        j, _, hours, kind = by_key[key]
        group = "same" if kind == want else ("other" if kind else "untyped")
        extra[group].append((j, key, hours))

    print("index: ok")
    print(f"typed_column: {'yes' if any(r[3] for r in rows) else 'no'}")
    print(f"same_type: {fmt([s[:3] for s in same])}")
    print(f"untyped_top: {fmt([s[:3] for s in untyped])}")
    for group in ("same", "other", "untyped"):
        print(f"extra_{group}: {fmt(extra[group])}")
    print(f"extra_missing: {' '.join(extra['missing'])}")


if __name__ == "__main__":
    main()
