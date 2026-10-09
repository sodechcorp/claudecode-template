# -*- coding: utf-8 -*-
"""
git-sync / git-sync-merge.py
積み上げ同期型ファイルのマージ処理スクリプト

Usage:
    python git-sync-merge.py --branch BRANCH

    BRANCH: リモートブランチ名（例: main）
    カレントディレクトリ = プロジェクトルート で実行すること。

Exit codes:
    0: 正常完了
    1: git リポジトリ外 / 事前チェック失敗
    2: 引数不足（argparse による自動出力）
"""

import argparse
import re
import os
import subprocess
import sys


def git_show(branch, path):
    r = subprocess.run(["git", "show", f"origin/{branch}:{path}"],
                       capture_output=True, text=True, encoding="utf-8")
    return r.stdout if r.returncode == 0 else None


def read_local(path):
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as f:
        return f.read()


def write(path, content):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(content)


# ---- 見出しの塊の和集合（decisions / global-calibration 共通） ----
def _blocks(text, split_re, key_re):
    """split_re の見出し行の前で区切り、[(key_re で始まる塊はその見出し行・それ以外は None, 塊)] を返す"""
    parts = [p for p in re.split(split_re, text or "", flags=re.MULTILINE) if p]
    return [(p.split("\n", 1)[0].rstrip() if re.match(key_re, p) else None, p) for p in parts]


def _join_blocks(blocks, inserts):
    """blocks の n 番目の後ろに inserts[n]（-1 は先頭）を足して連結する。足した塊の前後は空行で区切る"""
    def pad(b):
        return b if b.endswith("\n\n") else b + ("\n" if b.endswith("\n") else "\n\n")
    out = [pad(a) for a in inserts.get(-1, [])]
    for n, block in enumerate(blocks):
        add = inserts.get(n, [])
        out += [pad(block) if add else block] + [pad(a) for a in add]
    text = "".join(out)
    return text.rstrip("\n") + "\n" if inserts.get(len(blocks) - 1) else text


# ---- decisions.md ----
# `## ` の見出し行ごとのエントリ（同じ見出しは local 優先）。local のエントリは位置も順序もそのまま残し、remote にだけある
# エントリを remote でその直前にある共通のエントリの後ろ（無ければ local の最初のエントリの前。最新を先頭に挿入する運用）に足す。
# local に `## ` のエントリが無く、空でない行が全て remote にあれば（雛形のみ）remote のまま。
# 手動アーカイブ先と同じ内容のエントリは remote から足さず、local からも除く（他の担当者がアーカイブしたもの）。
# by_body（手動アーカイブ先どうし）は見出しでなく本文で突き合わせ、同じ見出しでも本文が違えば両方残す。
def merge_decisions(local, remote, archived=None, name="decisions.md", by_body=False):
    def split(text):
        """[(見出し行 or None, 塊)]。ファイル末尾の HTML コメント（雛形の書式の注記）は最後の塊と分ける"""
        blocks = _blocks(text, r'(?=^## )', r'## ')
        m = re.search(r'\n<!--(?:(?!-->).)*-->\s*\Z', blocks[-1][1], re.DOTALL) if blocks else None
        if m:
            blocks[-1:] = [(blocks[-1][0], blocks[-1][1][:m.start() + 1]), (None, blocks[-1][1][m.start() + 1:])]
        return blocks

    def body(block):
        """比較用の本文（行末の空白・前後の空行・末尾の区切り線を除く）"""
        return "\n".join(line.rstrip() for line in block.split("\n")).strip().removesuffix("---").rstrip()

    a_blocks = [(key, block) for key, block in split(archived) if key]
    gone = {body(block) for _, block in a_blocks}
    l_blocks = split(local)
    gone_n = len(l_blocks)
    l_blocks = [(key, block) for key, block in l_blocks if not (key and body(block) in gone)]
    gone_n -= len(l_blocks)
    r_blocks = split(remote)
    if by_body:
        l_blocks, r_blocks = ([(key and body(block), block) for key, block in b] for b in (l_blocks, r_blocks))
    l_pos = {}
    for n, (key, _) in enumerate(l_blocks):
        if key:
            l_pos.setdefault(key, n)
    l_n, r_n = (sum(1 for key, _ in b if key) for b in (l_blocks, r_blocks))
    if l_pos:
        top = min(l_pos.values()) - 1
    else:
        kept = "".join(block for _, block in l_blocks)
        if {line.rstrip() for line in kept.split("\n") if line.strip()} <= {line.rstrip() for line in remote.split("\n")}:
            print(f"  {name}: local の行は全て remote にあるため remote のまま（{r_n} 件）")
            return "".join(block for key, block in r_blocks if not (key and body(block) in gone))
        # 雛形の旧書式（`### `）で書いた記録等は残し、最初の `### ` 行（無ければ末尾のコメント）の前に足す
        head = l_blocks[0][1]
        comments = [c.span() for c in re.finditer(r'<!--.*?-->', head, re.DOTALL)]
        m = next((h for h in re.finditer(r'^### ', head, re.MULTILINE)
                  if not any(s <= h.start() < e for s, e in comments)), None)
        if m and m.start():
            l_blocks[:1] = [(None, head[:m.start()]), (None, head[m.start():])]
        top = -1 if m and not m.start() else 0
    inserts, anchor = {}, top
    for key, block in r_blocks:
        if key in l_pos:
            anchor = l_pos[key]
        elif key and body(block) not in gone:
            inserts.setdefault(anchor, []).append(block)
    new_n = sum(len(v) for v in inserts.values())
    note = f"・アーカイブ済み {gone_n} 件を除外" if gone_n else ""
    print(f"  {name}: remote {r_n} 件 + local {l_n} 件 → {l_n + new_n} 件（新規 {new_n} 件{note}）")
    return _join_blocks([block for _, block in l_blocks], inserts)


# ---- 表の行の和集合（case-index / pitfalls / global-pitfalls / test-prerequisites 共通） ----
# local の行は位置も順序もそのまま残し、remote にだけあるキーの行を、remote の同じ表でその行の直前にある共通の行の後ろ
# （無ければ同じ表の共通の行がある local の表の先頭＝区切り行の直後。どのファイルも最新行をヘッダー直下に先頭挿入する運用）に足す。
# 見出し行は区切り行の直前の、日付を持たない行（位置で判定）。
def _lines(text):
    parts = (text or "").split("\n")
    return [p + "\n" for p in parts[:-1]] + ([parts[-1] + "\n"] if parts[-1] else [])


def _cells(line):
    return [c.strip() for c in line.split("|")[1:-1]]


def _is_separator(line):
    return line.startswith("|") and "-" in line and re.fullmatch(r'[|:\-\s]+', line) is not None


def _has_date(line):
    return any(re.fullmatch(r'\d{4}-\d{2}-\d{2}', c) for c in _cells(line))


def _restore_tables(lines):
    """以前のマージで見出し行が区切り行の後ろへ動いた表を戻す。
    直前が表の行でない区切り行の後ろ（# 見出しを挟まない）の最初の表の行の塊が区切り行を持たず、
    日付の列を持たない最初の行（各ファイルのデータ行は日付・確認日の列を持つ）までが区切り行と同じ列数なら、
    その行を見出し行として「見出し行・区切り行・データ行・間にあった行」の順に並べ直す。"""
    i = 0
    while i < len(lines):
        sep = lines[i]
        if _is_separator(sep) and (i == 0 or not lines[i - 1].startswith("|")):
            j = i + 1
            while j < len(lines) and not lines[j].startswith("|"):
                j += 1
            k = j
            while k < len(lines) and lines[k].startswith("|"):
                k += 1
            block, between = lines[j:k], lines[i + 1:j]
            h = next((n for n, line in enumerate(block) if not _has_date(line)), None)
            if (h is not None and not any(_is_separator(line) for line in block)
                    and all(len(_cells(line)) == len(_cells(sep)) for line in block[:h + 1])
                    and not any(line.startswith("#") for line in between)):
                lines[i:k] = [block[h], sep] + block[:h] + block[h + 1:] + between
                i += len(block)
        i += 1
    return lines


def _parse_rows(lines, key_of):
    """データ行 [(位置, キー, 表の見出しのキー, 表の先頭に足す位置)] と {表の見出しのキー: 区切り行の位置} を返す。
    表の先頭に足す位置は区切り行（見出しの無い行の塊はその直前の行）で、表を区別する"""
    rows, seps = [], {}
    head_key, top = None, None
    for i, line in enumerate(lines):
        if not line.startswith("|"):
            head_key, top = None, None
        elif _is_separator(line):
            continue
        elif i + 1 < len(lines) and _is_separator(lines[i + 1]) and not _has_date(line):
            head_key, top = key_of(_cells(line)), i + 1
            if head_key is not None:
                seps.setdefault(head_key, i + 1)
        else:
            if top is None:
                top = i - 1
            key = key_of(_cells(line))
            if key is not None:
                rows.append((i, key, head_key, top))
    return rows, seps


def merge_table_rows(local, remote, key_of, archived=None):
    """(本文, local 行数, remote 行数, 新規行数, 除いた行数) を返す。同キーは local 優先。archived（手動アーカイブ先）と同じ内容の行は
    remote から足さず、local からも除く（他の担当者がアーカイブした行）"""
    r_lines = _restore_tables(_lines(remote))
    r_rows, r_seps = _parse_rows(r_lines, key_of)
    a_lines = _lines(archived)
    a_rows = _parse_rows(a_lines, key_of)[0]
    gone = {tuple(_cells(a_lines[i])) for i, _, _, _ in a_rows}
    if not (local or "").strip():
        drop = {i for i, _, _, _ in r_rows if tuple(_cells(r_lines[i])) in gone}
        return "".join(line for i, line in enumerate(r_lines) if i not in drop), 0, len(r_rows), len(r_rows) - len(drop), 0
    l_lines = _restore_tables(_lines(local))
    drop = {i for i, _, _, _ in _parse_rows(l_lines, key_of)[0] if tuple(_cells(l_lines[i])) in gone}
    l_lines = [line for i, line in enumerate(l_lines) if i not in drop]
    l_rows, l_seps = _parse_rows(l_lines, key_of)
    l_pos, l_top = {}, {}
    for i, key, _, top in l_rows:
        l_pos.setdefault(key, i)
        l_top.setdefault(key, top)
    skip = set(l_pos) | set(l_seps) | set(r_seps)  # 崩れた remote に残る見出し行も足さない
    # 同じ表に共通の行が無い行の位置: 同じ見出しの local の表の区切り行の直後。無ければ local の最初のデータ行の前、
    # 最初の表の区切り行の直後、末尾の順
    if l_rows:
        fallback = l_rows[0][0] - 1
    else:
        fallback = min(l_seps.values()) if l_seps else len(l_lines) - 1
    inserts, anchor, table = {}, None, None
    for n, (i, key, head_key, top) in enumerate(r_rows):
        if top != table:
            anchor, table = None, top
        if key in l_pos:
            anchor = l_pos[key]
        elif key not in skip and tuple(_cells(r_lines[i])) not in gone:
            if anchor is not None:
                pos = anchor
            else:
                nxt = next((k for _, k, _, t in r_rows[n + 1:] if t == top and k in l_pos), None)
                pos = l_top[nxt] if nxt is not None else l_seps.get(head_key, fallback)
            inserts.setdefault(pos, []).append(r_lines[i])
    out = list(inserts.get(-1, []))
    for i, line in enumerate(l_lines):
        out.append(line)
        out += inserts.get(i, [])
    return "".join(out), len(l_rows), len(r_rows), sum(len(v) for v in inserts.values()), len(drop)


# ---- case-index.md ----
def merge_table(local, remote, archived=None):
    text, l_n, r_n, new_n, gone_n = merge_table_rows(local, remote, lambda c: c[1] if len(c) > 1 and c[1] else None, archived)
    note = f"（アーカイブ済み {gone_n} 行を除外）" if gone_n else ""
    print(f"  case-index.md: remote {r_n} 行 + local {l_n} 行 → {l_n + new_n} 行{note}")
    return text


# ---- pitfalls.md ----
# 第2列（issueID）＋第3列（カテゴリ）の複合キー。表の外の行（旧セクション形式等）は local のまま残す。
def merge_pitfalls(local, remote, name="pitfalls.md", archived=None):
    text, l_n, r_n, new_n, gone_n = merge_table_rows(local, remote, lambda c: f"{c[1]}::{c[2]}" if len(c) >= 3 else None, archived)
    note = f"・アーカイブ済み {gone_n} 行を除外" if gone_n else ""
    print(f"  {name}: remote {r_n} 行 + local {l_n} 行 → {l_n + new_n} 行（新規 {new_n} 件{note}）")
    return text


# ---- 手動アーカイブ先（knowledge-reflux-formats.md） ----
# 内容（decisions はエントリの本文、表は行全体）で和集合し、同じ見出し・課題IDでも内容が違えば両方残す（元ファイルは手元の
# アーカイブ先と同じ内容を除くため、担当者ごとにアーカイブ先の内容が食い違うと、保存のたびに remote が入れ替わる）。
def merge_archive(local, remote, name):
    if name == "decisions-archive.md":
        return merge_decisions(local, remote, name=name, by_body=True)
    text, l_n, r_n, new_n, _ = merge_table_rows(local, remote, lambda c: tuple(c) if len(c) > 1 else None)
    print(f"  {name}: remote {r_n} 行 + local {l_n} 行 → {l_n + new_n} 行")
    return text


# ---- effort-calibration.md ----
# アンカー行（例: "- GF-123「...」= 2h"）の課題ID単位で和集合（同キーは local 優先）。アンカー以外（全体傾向等）と local のアンカーは
# 位置も順序もそのまま残し、remote にだけあるアンカーを、remote の同じ ### 帯（次の見出しまで）でその直前にある共通のアンカーの後ろ
# （無ければ同じ帯の次の共通のアンカーの前、local の同じ帯の最後のアンカー〔アンカーが無ければ帯の最後の行〕の後ろ、
# local の最後のアンカーの後ろの順）に足す。帯は見出しの「（」より前で突き合わせる（括弧内の閾値は cat6 が再計算で変える。
# 「（」より前が同じ帯が同じファイルに複数あるときは見出しの全文）。
def merge_calibration(local, remote):
    if not local:
        return remote
    if not remote:
        return local
    anchor_re = re.compile(r'^- ([A-Za-z][A-Za-z0-9]*-\d+)「')

    def label(line):
        return re.split(r'[（(]', line)[0].rstrip()

    def parse(lines):
        """[(位置, 課題ID, 帯)] と {帯: 帯の最後の空でない行の位置} を返す"""
        anchors, band_end, band = [], {}, None
        for i, line in enumerate(lines):
            if re.match(r'#{1,6} ', line):
                band = (label(line) if by_label else line.rstrip()) if line.startswith("### ") else None
            elif anchor_re.match(line):
                anchors.append((i, anchor_re.match(line).group(1), band))
            if band and line.strip():
                band_end[band] = i
        return anchors, band_end

    l_lines, r_lines = _lines(local), _lines(remote)
    labels = [[label(line) for line in lines if line.startswith("### ")] for lines in (l_lines, r_lines)]
    by_label = all(len(set(x)) == len(x) for x in labels)
    (l_anchors, l_band_end), (r_anchors, _) = parse(l_lines), parse(r_lines)
    l_pos, l_band_last = {}, {}
    for i, key, band in l_anchors:
        l_pos.setdefault(key, i)
        l_band_last[band] = i
    last = l_anchors[-1][0] if l_anchors else len(l_lines) - 1
    inserts, anchor, cur = {}, None, None
    for n, (i, key, band) in enumerate(r_anchors):
        if band != cur:
            anchor, cur = None, band
        if key in l_pos:
            anchor = l_pos[key]
            continue
        if anchor is not None:
            pos = anchor
        else:
            nxt = next((k for _, k, b in r_anchors[n + 1:] if b == band and k in l_pos), None)
            pos = l_pos[nxt] - 1 if nxt is not None else l_band_last.get(band, l_band_end.get(band, last))
        inserts.setdefault(pos, []).append(r_lines[i])
    out = list(inserts.get(-1, []))
    for i, line in enumerate(l_lines):
        out += [line] + inserts.get(i, [])
    new_n = sum(len(v) for v in inserts.values())
    print(f"  effort-calibration.md: remote {len(r_anchors)} 件 + local {len(l_anchors)} 件 → {len(l_anchors) + new_n} 件（新規 {new_n} 件追加）")
    return "".join(out)


# ---- global-calibration.md ----
# ### 見出しの帯（次の #〜### 見出しまで）単位で和集合（同じ見出しは local 優先）。帯の外（全体傾向・LLM 観察等）と local の帯は
# 位置も順序もそのまま残し、remote にだけある帯を、remote でその直前にある共通の帯の後ろ（無ければ次の共通の帯の前、
# local の最後の帯の後ろの順）に足す。local に帯が無ければ（未生成の雛形）remote のまま。
def merge_global_calibration(local, remote):
    if not local:
        return remote
    if not remote:
        return local
    l_blocks, r_blocks = _blocks(local, r'(?=^#{1,3} )', r'### '), _blocks(remote, r'(?=^#{1,3} )', r'### ')
    l_pos = {}
    for n, (key, _) in enumerate(l_blocks):
        if key:
            l_pos.setdefault(key, n)
    r_bands = [(key, block) for key, block in r_blocks if key]
    if not l_pos:
        print(f"  global-calibration.md: local に帯が無いため remote のまま（{len(r_bands)} 帯）")
        return remote
    inserts, anchor = {}, None
    for n, (key, block) in enumerate(r_bands):
        if key in l_pos:
            anchor = l_pos[key]
            continue
        if anchor is not None:
            pos = anchor
        else:
            nxt = next((k for k, _ in r_bands[n + 1:] if k in l_pos), None)
            pos = l_pos[nxt] - 1 if nxt is not None else max(l_pos.values())
        inserts.setdefault(pos, []).append(block)
    new_n = sum(len(v) for v in inserts.values())
    print(f"  global-calibration.md: {len(l_pos)} 既存帯 + {new_n} 新規帯 → {len(l_pos) + new_n} 帯")
    return _join_blocks([block for _, block in l_blocks], inserts)


# ---- global-pitfalls.md ----
# pitfalls.md と同じキー（第2列 由来 issueID ＋第3列 カテゴリ）
def merge_global_pitfalls(local, remote):
    return merge_pitfalls(local, remote, name="global-pitfalls.md")


# ---- test-prerequisites.md ----
# ## {番号}. {タイトル} 見出し単位でセクション分割。
# § 1/§ 2/§ 4 はテーブル行の第1列（対象画面 / オブジェクトAPI名 / 落とし穴先頭）をキーに和集合。
# § 3（散文）は local 優先で保持。
def merge_test_prerequisites(local, remote):
    if not local:
        return remote
    if not remote:
        return local

    def split_sections(text):
        parts = re.split(r'(?=^## )', text, flags=re.MULTILINE)
        pre = parts[0] if parts and not re.match(r'^## ', parts[0]) else ""
        sections = {}
        order = []
        for p in parts:
            m = re.match(r'^(## [^\n]+)', p)
            if m:
                key = m.group(1).strip()
                sections[key] = p
                if key not in order:
                    order.append(key)
        return pre, sections, order

    local_pre, local_secs, local_order = split_sections(local)
    remote_pre, remote_secs, remote_order = split_sections(remote)

    merged = {}
    total_new = 0
    all_keys = local_order + [k for k in remote_order if k not in local_secs]

    for key in all_keys:
        l_sec = local_secs.get(key)
        r_sec = remote_secs.get(key)
        if l_sec is None:
            merged[key] = r_sec
        elif r_sec is None:
            merged[key] = l_sec
        elif re.match(r'^## 3\.', key):  # § 3 証跡ディレクトリ規約（散文）は local 優先
            merged[key] = l_sec
        else:
            merged[key], _, _, new_count, _ = merge_table_rows(l_sec, r_sec, lambda c: c[0] if c and c[0] else None)
            total_new += new_count

    pre = local_pre or remote_pre
    print(f"  test-prerequisites.md: {total_new} 件新規マージ")
    return pre + "".join(merged[k] for k in all_keys if k in merged)


def main():
    parser = argparse.ArgumentParser(
        description="積み上げ同期型ファイルのマージ処理（git-sync Step 2）"
    )
    parser.add_argument("--branch", required=True, help="リモートブランチ名（例: main）")
    args = parser.parse_args()
    branch = args.branch

    # git リポジトリ内にいるか確認
    r = subprocess.run(["git", "rev-parse", "--git-dir"],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print("ERROR: git リポジトリのルートで実行してください。", file=sys.stderr)
        sys.exit(1)

    # ---- 手動アーカイブ先: 元ファイルのマージより先に行い、元ファイルのマージに渡す ----
    for path in ("docs/knowledge/archive/decisions-archive.md", "docs/knowledge/archive/case-index-archive.md",
                 "docs/knowledge/archive/pitfalls-archive.md"):
        remote = git_show(branch, path)
        local  = read_local(path)
        if remote is None:
            continue
        elif local is None:
            write(path, remote); print(f"  {path}: 新規作成（remote 版）")
        else:
            write(path, merge_archive(local, remote, os.path.basename(path)))

    # ---- decisions.md ----
    path = "docs/decisions.md"
    remote = git_show(branch, path)
    local  = read_local(path)
    if remote is None:
        print(f"  {path}: remote 未存在、スキップ")
    elif local is None:
        write(path, remote); print(f"  {path}: 新規作成（remote 版）")
    else:
        write(path, merge_decisions(local, remote, read_local("docs/knowledge/archive/decisions-archive.md")))

    # ---- case-index.md ----
    path = "docs/knowledge/case-index.md"
    remote = git_show(branch, path)
    local  = read_local(path)
    if remote is None:
        print(f"  {path}: remote 未存在、スキップ")
    elif local is None:
        write(path, remote); print(f"  {path}: 新規作成（remote 版）")
    else:
        write(path, merge_table(local, remote, read_local("docs/knowledge/archive/case-index-archive.md")))

    # ---- pitfalls.md ----
    path = "docs/knowledge/pitfalls.md"
    remote = git_show(branch, path)
    local  = read_local(path)
    if remote is None:
        print(f"  {path}: remote 未存在、スキップ")
    elif local is None:
        write(path, remote); print(f"  {path}: 新規作成（remote 版）")
    else:
        write(path, merge_pitfalls(local, remote, archived=read_local("docs/knowledge/archive/pitfalls-archive.md")))

    # ---- cases/*.md ----
    cases_dir = "docs/knowledge/cases"
    r = subprocess.run(["git", "ls-tree", "--name-only", f"origin/{branch}", f"{cases_dir}/"],
                       capture_output=True, text=True, encoding="utf-8")
    if r.returncode == 0:
        added = 0
        for rpath in r.stdout.splitlines():
            rpath = rpath.strip()
            if rpath and not os.path.exists(rpath):
                content = git_show(branch, rpath)
                if content:
                    write(rpath, content)
                    added += 1
                    print(f"  新規取得: {rpath}")
        print(f"  cases/: {added} 件追加（既存は上書きしない）")
    else:
        print(f"  cases/: remote 未存在、スキップ")

    # ---- effort-calibration.md ----
    path = "docs/knowledge/effort-calibration.md"
    remote = git_show(branch, path)
    local  = read_local(path)
    if remote is None:
        print(f"  {path}: remote 未存在、スキップ")
    elif local is None:
        write(path, remote); print(f"  {path}: 新規作成（remote 版）")
    else:
        write(path, merge_calibration(local, remote))

    # ---- global-calibration.md ----
    path = "docs/knowledge/global-calibration.md"
    remote = git_show(branch, path)
    local  = read_local(path)
    if remote is None:
        print(f"  {path}: remote 未存在、スキップ")
    elif local is None:
        write(path, remote); print(f"  {path}: 新規作成（remote 版）")
    else:
        write(path, merge_global_calibration(local, remote))

    # ---- global-pitfalls.md ----
    path = "docs/knowledge/global-pitfalls.md"
    remote = git_show(branch, path)
    local  = read_local(path)
    if remote is None:
        print(f"  {path}: remote 未存在、スキップ")
    elif local is None:
        write(path, remote); print(f"  {path}: 新規作成（remote 版）")
    else:
        write(path, merge_global_pitfalls(local, remote))

    # ---- test-prerequisites.md ----
    path = "docs/knowledge/test-prerequisites.md"
    remote = git_show(branch, path)
    local  = read_local(path)
    if remote is None:
        print(f"  {path}: remote 未存在、スキップ")
    elif local is None:
        write(path, remote); print(f"  {path}: 新規作成（remote 版）")
    else:
        write(path, merge_test_prerequisites(local, remote))

    print("\n✅ 積み上げ型マージ完了")
    sys.exit(0)


if __name__ == "__main__":
    main()
