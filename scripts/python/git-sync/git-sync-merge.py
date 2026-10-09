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


# ---- decisions.md ----
def merge_decisions(local, remote):
    def split(text):
        parts = re.split(r'(?=^## \d{4}-\d{2}-\d{2})', text or "", flags=re.MULTILINE)
        pre = parts[0] if parts and not re.match(r'^## \d{4}', parts[0]) else ""
        entries = {}
        for p in parts:
            m = re.match(r'^## (\d{4}-\d{2}-\d{2})', p)
            if m:
                entries[m.group(1)] = p
        return pre, entries

    local_pre, local_e = split(local)
    remote_pre, remote_e = split(remote)
    merged = {**remote_e, **local_e}  # local 優先
    pre = local_pre or remote_pre
    body = "\n".join(merged[k] for k in sorted(merged.keys(), reverse=True))
    print(f"  decisions.md: remote {len(remote_e)} 件 + local {len(local_e)} 件 → {len(merged)} 件")
    return pre + body


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


def merge_table_rows(local, remote, key_of):
    """(本文, local 行数, remote 行数, 新規行数) を返す。同キーは local 優先"""
    r_lines = _restore_tables(_lines(remote))
    r_rows, r_seps = _parse_rows(r_lines, key_of)
    if not (local or "").strip():
        return "".join(r_lines), 0, len(r_rows), len(r_rows)
    l_lines = _restore_tables(_lines(local))
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
        elif key not in skip:
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
    return "".join(out), len(l_rows), len(r_rows), sum(len(v) for v in inserts.values())


# ---- case-index.md ----
def merge_table(local, remote):
    text, l_n, r_n, new_n = merge_table_rows(local, remote, lambda c: c[1] if len(c) > 1 and c[1] else None)
    print(f"  case-index.md: remote {r_n} 行 + local {l_n} 行 → {l_n + new_n} 行")
    return text


# ---- pitfalls.md ----
# 第2列（issueID）＋第3列（カテゴリ）の複合キー。表の外の行（旧セクション形式等）は local のまま残す。
def merge_pitfalls(local, remote, name="pitfalls.md"):
    text, l_n, r_n, new_n = merge_table_rows(local, remote, lambda c: f"{c[1]}::{c[2]}" if len(c) >= 3 else None)
    print(f"  {name}: remote {r_n} 行 + local {l_n} 行 → {l_n + new_n} 行（新規 {new_n} 件）")
    return text


# ---- effort-calibration.md ----
def merge_calibration(local, remote):
    if not local:
        return remote
    if not remote:
        return local

    # アンカー行を課題IDで抽出（例: "- GF-123「...」= 2h"）
    anchor_re = re.compile(r'^- ([A-Za-z]+-\d+)「')

    def extract_anchors(text):
        anchors = {}
        for line in (text or "").splitlines(keepends=True):
            m = anchor_re.match(line)
            if m:
                anchors[m.group(1)] = line
        return anchors

    local_anchors = extract_anchors(local)
    remote_anchors = extract_anchors(remote)

    # 和集合（同キーは local 優先）
    merged_anchors = {**remote_anchors, **local_anchors}
    new_count = len(set(remote_anchors) - set(local_anchors))

    # local のテキストをベースに処理
    # 「全体傾向」統計セクション（先頭ブロック）は local をそのまま保持
    result_lines = []
    seen_keys = set()
    for line in local.splitlines(keepends=True):
        m = anchor_re.match(line)
        if m:
            key = m.group(1)
            seen_keys.add(key)
            result_lines.append(merged_anchors.get(key, line))
        else:
            result_lines.append(line)

    # remote にのみ存在するアンカーを末尾に追加
    for key, line in merged_anchors.items():
        if key not in seen_keys:
            result_lines.append(line)

    print(f"  effort-calibration.md: remote {len(remote_anchors)} 件 + local {len(local_anchors)} 件 → {len(extract_anchors(''.join(result_lines)))} 件（新規 {new_count} 件追加）")
    return "".join(result_lines)


# ---- global-calibration.md ----
def merge_global_calibration(local, remote):
    if not local:
        return remote
    if not remote:
        return local

    # 「全体傾向」セクション（先頭から最初の `## コンポーネント種別別` まで）は local 優先
    # 各 `### ` 見出しセクションは内容を remote で補完（local 優先）
    local_sections = re.split(r'(?=^### )', local, flags=re.MULTILINE)
    remote_sections = re.split(r'(?=^### )', remote, flags=re.MULTILINE)

    local_map = {}
    local_pre = ""
    for i, s in enumerate(local_sections):
        m = re.match(r'^### (.+)', s)
        if m:
            local_map[m.group(1).strip()] = s
        else:
            local_pre += s

    remote_map = {}
    for s in remote_sections:
        m = re.match(r'^### (.+)', s)
        if m:
            remote_map[m.group(1).strip()] = s

    # remote にある新規セクションを追加（local 優先で既存は上書きしない）
    merged = {**remote_map, **local_map}
    new_count = len(set(remote_map) - set(local_map))
    print(f"  global-calibration.md: {len(local_map)} 既存帯 + {new_count} 新規帯 → {len(merged)} 帯")
    return local_pre + "".join(merged.values())


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
            merged[key], _, _, new_count = merge_table_rows(l_sec, r_sec, lambda c: c[0] if c and c[0] else None)
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

    # ---- decisions.md ----
    path = "docs/decisions.md"
    remote = git_show(branch, path)
    local  = read_local(path)
    if remote is None:
        print(f"  {path}: remote 未存在、スキップ")
    elif local is None:
        write(path, remote); print(f"  {path}: 新規作成（remote 版）")
    else:
        write(path, merge_decisions(local, remote))

    # ---- case-index.md ----
    path = "docs/knowledge/case-index.md"
    remote = git_show(branch, path)
    local  = read_local(path)
    if remote is None:
        print(f"  {path}: remote 未存在、スキップ")
    elif local is None:
        write(path, remote); print(f"  {path}: 新規作成（remote 版）")
    else:
        write(path, merge_table(local, remote))

    # ---- pitfalls.md ----
    path = "docs/knowledge/pitfalls.md"
    remote = git_show(branch, path)
    local  = read_local(path)
    if remote is None:
        print(f"  {path}: remote 未存在、スキップ")
    elif local is None:
        write(path, remote); print(f"  {path}: 新規作成（remote 版）")
    else:
        write(path, merge_pitfalls(local, remote))

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
