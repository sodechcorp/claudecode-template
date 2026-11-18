"""
case_index_types.py — case-index.md の見出しを12列（最後が「作業の型」）に直し、行の最後のセルに作業の型を書く。
sf-analyst-cat6（既存の行の型を埋める）と backlog-releaser §4.5（追記の前に見出しを直す・中断時の行の型を直す）が使う。
LLM がファイル全体を書き直すと日本語が崩れたり詳細のリンクを上書きしたりするので、行の最後のセルだけを機械的に書く。

使い方（プロジェクトのルートで）:
    # 見出しだけ直す（12列でなければ、見出し行と区切り行を knowledge-reflux-formats.md の新規作成ヘッダーに置き換える）
    python scripts/python/effort/case_index_types.py --fix-header

    # 型を書く（見出しも直す）。標準入力は {課題ID: 型の名前} の JSON（型の名前は sf-effort-estimator Step 2 の表のとおり、または "-"）
    python scripts/python/effort/case_index_types.py [--overwrite] <<'EOF'
    {"GF-123": "既存の一部を少し変える", "GF-124": "-"}
    EOF

書き方（「課題ID」の見出しを持つ最初の表の行だけ。ほかの表・本文には触れない）:
    11 セルの行（作業の型の列が無い）→ 最後にセルを1つ足す
    12 セル以上の行 → 最後のセルが空・表に無い名前なら書き換える。型の名前か "-" が入っていれば変えない（--overwrite なら書き換える）
    10 セル以下の行（旧形式）→ 列がずれるので書かない
改行コード（CRLF/LF）・文字コード（UTF-8）・ほかのセルはそのまま残す。日本語は表示しない。
"""
import argparse
import json
import pathlib
import re
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from similar_cases import KEY, TYPES, cells  # noqa: E402

HEADER = ("| 日付 | 課題ID | 種別 | 症状/要件（60字） | 根本原因（60字） | 採用方針（40字） | 教訓（40字） "
          "| 対象コンポーネント | 関連用語 | 工数(h) | 詳細 | 作業の型 |")
SEPARATOR = "|" + "---|" * 12


def split_eol(line):
    body = line.rstrip("\r\n")
    return body, line[len(body):]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--index", default="docs/knowledge/case-index.md")
    ap.add_argument("--fix-header", action="store_true", help="見出しだけ直す（標準入力は読まない）")
    ap.add_argument("--overwrite", action="store_true", help="型や - が入っている行も書き換える")
    args = ap.parse_args()

    types = {}
    if not args.fix_header:
        sys.stdin.reconfigure(encoding="utf-8")
        types = json.loads(sys.stdin.read() or "{}")
        bad = sorted(k for k, v in types.items() if v not in TYPES and v != "-")
        if bad:
            print(f"error: unknown type for {' '.join(bad)} (use the names in sf-effort-estimator Step 2 or -)")
            sys.exit(2)

    path = pathlib.Path(args.index)
    if not path.exists():
        print("index: missing")
        return
    lines = path.read_bytes().decode("utf-8").splitlines(keepends=True)
    eol = next((split_eol(l)[1] for l in lines if split_eol(l)[1]), "\n")

    head = next((i for i, l in enumerate(lines) if l.lstrip().startswith("|") and "課題ID" in cells(l)), None)
    if head is None or head + 1 >= len(lines) or not re.fullmatch(r"\s*\|[\s:\-|]+\|\s*", split_eol(lines[head + 1])[0]):
        print("index: no table")
        return
    header_fixed = False
    if cells(lines[head]) != cells(HEADER):
        lines[head] = HEADER + (split_eol(lines[head])[1] or eol)
        lines[head + 1] = SEPARATOR + (split_eol(lines[head + 1])[1] or eol)
        header_fixed = True

    written, has_type, old, seen = [], [], [], set()
    i = head + 2
    while i < len(lines) and lines[i].lstrip().startswith("|"):
        body, end = split_eol(lines[i])
        c = cells(body)
        key = c[1] if len(c) > 1 and KEY.fullmatch(c[1]) else None
        if key in types:
            seen.add(key)
            value = types[key]
            if len(c) <= 10:
                old.append(key)
            elif len(c) == 11:
                lines[i] = body.rstrip() + f" {value} |" + end
                written.append(key)
            elif (c[-1] in TYPES or c[-1] == "-") and not args.overwrite:
                has_type.append(key)
            else:
                stripped = body.rstrip()
                cut = stripped[:-1].rfind("|")  # 最後のセルの前の区切り
                lines[i] = stripped[:cut + 1] + f" {value} |" + end
                written.append(key)
        i += 1

    if header_fixed or written:
        path.write_bytes("".join(lines).encode("utf-8"))
    print(f"header: {'fixed' if header_fixed else 'ok'}")
    print(f"written: {len(written)}")
    print(f"skipped_has_type: {' '.join(has_type)}")
    print(f"skipped_old_format: {' '.join(old)}")
    print(f"not_found: {' '.join(k for k in types if k not in seen)}")


if __name__ == "__main__":
    main()
