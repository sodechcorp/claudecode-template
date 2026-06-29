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


# ---- case-index.md ----
def merge_table(local, remote):
    def parse(text):
        lines = (text or "").splitlines(keepends=True)
        pre, rows = [], {}
        in_table = False
        for line in lines:
            if line.startswith("|"):
                cols = [c.strip() for c in line.split("|")[1:-1]]
                key = cols[1] if len(cols) > 1 else ""
                if key and not re.match(r'^[-:]+$', key) and key not in ("課題ID", "issueKey"):
                    rows[key] = line
                    in_table = True
                else:
                    pre.append(line)
            else:
                if in_table:
                    in_table = False
                pre.append(line)
        return pre, rows

    local_pre, local_rows = parse(local)
    remote_pre, remote_rows = parse(remote)
    merged = {**remote_rows, **local_rows}  # local 優先
    pre = local_pre or remote_pre
    print(f"  case-index.md: remote {len(remote_rows)} 行 + local {len(local_rows)} 行 → {len(merged)} 行")
    return "".join(pre) + "".join(merged.values())


# ---- pitfalls.md ----
# テーブル形式（6列）を前提にした複合キー（issueID::カテゴリ）マージ。
# cat6 が出力するテーブル行は複合キーで重複排除し、旧セクション形式等の非テーブル行は
# pre として local を verbatim 保持する（サブ見出しキー衝突による破壊を防ぐ）。
def merge_pitfalls(local, remote):
    def parse(text):
        lines = (text or "").splitlines(keepends=True)
        pre, rows = [], {}
        in_table = False
        for line in lines:
            if line.startswith("|"):
                cols = [c.strip() for c in line.split("|")[1:-1]]
                if len(cols) >= 3:
                    key = f"{cols[1]}::{cols[2]}"  # issueID::カテゴリ の複合キー
                    if key and not re.match(r'^[-:]+$', cols[1]) and cols[1] not in ("課題ID",):
                        rows[key] = line
                        in_table = True
                    else:
                        pre.append(line)
                else:
                    pre.append(line)
            else:
                if in_table:
                    in_table = False
                pre.append(line)
        return pre, rows

    local_pre, local_rows = parse(local)
    remote_pre, remote_rows = parse(remote)
    merged = {**remote_rows, **local_rows}  # local 優先
    pre = local_pre or remote_pre
    new_count = len(set(remote_rows) - set(local_rows))
    print(f"  pitfalls.md: remote {len(remote_rows)} 行 + local {len(local_rows)} 行 → {len(merged)} 行（新規 {new_count} 件）")
    return "".join(pre) + "".join(merged.values())


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
# merge_table ロジック（case-index.md と同方式）を流用
# ただしキーは 第2列（issueID）+ 第3列（カテゴリ）の複合キー
def merge_global_pitfalls(local, remote):
    def parse(text):
        lines = (text or "").splitlines(keepends=True)
        pre, rows = [], {}
        in_table = False
        for line in lines:
            if line.startswith("|"):
                cols = [c.strip() for c in line.split("|")[1:-1]]
                if len(cols) >= 3:
                    key = f"{cols[1]}::{cols[2]}"  # issueID::カテゴリ の複合キー
                    if key and not re.match(r'^[-:]+$', cols[1]) and cols[1] not in ("由来 issueID",):
                        rows[key] = line
                        in_table = True
                    else:
                        pre.append(line)
                else:
                    pre.append(line)
            else:
                if in_table:
                    in_table = False
                pre.append(line)
        return pre, rows

    local_pre, local_rows = parse(local)
    remote_pre, remote_rows = parse(remote)
    merged = {**remote_rows, **local_rows}  # local 優先
    pre = local_pre or remote_pre
    new_count = len(set(remote_rows) - set(local_rows))
    print(f"  global-pitfalls.md: remote {len(remote_rows)} 行 + local {len(local_rows)} 行 → {len(merged)} 行（新規 {new_count} 件）")
    return "".join(pre) + "".join(merged.values())


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

    def merge_table_section(local_sec, remote_sec):
        """テーブル行の第1列をキーに和集合。local 優先"""
        def parse(sec):
            lines = sec.splitlines(keepends=True)
            pre, rows, row_order = [], {}, []
            for line in lines:
                if line.startswith("|"):
                    cols = [c.strip() for c in line.split("|")[1:-1]]
                    key = cols[0] if cols else ""
                    if key and not re.match(r'^[-:]+$', key):
                        if key not in rows:
                            row_order.append(key)
                        rows[key] = line
                    else:
                        pre.append(line)
                else:
                    pre.append(line)
            return pre, rows, row_order

        l_pre, l_rows, l_order = parse(local_sec)
        r_pre, r_rows, r_order = parse(remote_sec)
        merged = {**r_rows, **l_rows}  # local 優先
        new_keys = [k for k in r_order if k not in l_rows]
        final_order = l_order + new_keys
        new_count = len(new_keys)
        pre = l_pre if l_pre else r_pre
        return "".join(pre) + "".join(merged[k] for k in final_order if k in merged), new_count

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
            merged[key], new_count = merge_table_section(l_sec, r_sec)
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
