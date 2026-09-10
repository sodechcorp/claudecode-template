# -*- coding: utf-8 -*-
"""backlog-xlsx / dedup_append_lines.py
auto-evidence-runner.md の複数箇所（Step 3-4 の作成レコード目視URL集約・Step 4 の
ui_screen_urls.txt dedup）に埋め込まれていた「メインファイルを読み込み→キー重複を
除外→新規行を追記して書き戻す」ロジックを共通化したもの。
inline-script-hygiene.md のルール（`python -c` は単一物理行限定・if/try-except 等の
多行ロジックは .py 化）に従い、resolve_target_tcs.py と同様の方針で切り出した。

3つの動作モード:
  1. フルライン dedup（--key-index 省略・--new-file 指定）:
     --new-file の行のうち --main-file に完全一致で存在しない行のみ追記する。
     追記対象が1件も無ければファイルへの書き込み自体を行わない（no-op）。
  2. キー単位 dedup-append（--key-index 指定・--new-file 指定）:
     --new-file の各行から --key-index 番目（0始まり）の '|' 区切りフィールドを
     キーとして抽出し、そのキーを持つ --main-file の既存行を除去したうえで
     --new-file の全行を追記する（同一キーを新しい内容で置き換える動作）。
     キー抽出に必要なフィールド数が無い既存行は削除対象にせず残す。
  3. キー指定 prune のみ（--key-index 指定・--keys 指定・--new-file 省略）:
     --keys（カンマ区切り）に一致する既存行を --main-file から除去するだけで、
     追記は行わない（呼び出し元が別途ヒアドキュメント等で追記する運用を想定）。
     --main-file が未作成の場合は何もしない。

Usage:
    python dedup_append_lines.py --main-file PATH [--new-file PATH]
                                  [--key-index N] [--keys "TC-003,TC-011"]
"""

import argparse
import os


def _read_lines(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [line.rstrip("\n") for line in f if line.strip()]


def _write_lines(path, lines):
    with open(path, "w", encoding="utf-8") as f:
        if lines:
            f.write("\n".join(lines) + "\n")
        else:
            f.write("")


def _extract_key(line, key_index):
    parts = line.split("|")
    if len(parts) <= key_index:
        return None
    return parts[key_index].strip()


def dedup_append(main_file, new_file, key_index, keys):
    existing = _read_lines(main_file)
    new_lines = _read_lines(new_file) if new_file else []

    if key_index is None:
        # フルライン dedup（完全一致で既存に無い行のみ追記）
        existing_set = set(existing)
        new_unique = [l for l in new_lines if l not in existing_set]
        if not new_unique:
            return  # 変更なし。書き込み自体を行わない
        _write_lines(main_file, existing + new_unique)
        return

    if new_file:
        # キー単位 dedup-append
        remove_keys = {_extract_key(l, key_index) for l in new_lines}
        remove_keys.discard(None)
        kept = [l for l in existing if _extract_key(l, key_index) not in remove_keys]
        _write_lines(main_file, kept + new_lines)
        return

    # キー指定 prune のみ（追記は呼び出し元に委ねる）
    if not os.path.exists(main_file):
        return
    remove_keys = set(k.strip() for k in (keys or "").split(",") if k.strip())
    kept = [l for l in existing if _extract_key(l, key_index) not in remove_keys]
    _write_lines(main_file, kept)


def main():
    parser = argparse.ArgumentParser(description="ファイル間の重複行を除外しつつ追記/prune する")
    parser.add_argument("--main-file", required=True, help="集約先のメインファイル")
    parser.add_argument("--new-file", help="追記元の新規行ファイル（省略時は --keys による prune のみ）")
    parser.add_argument("--key-index", type=int, help="'|' 区切りのキー抽出フィールド番号（0始まり）。省略時はフルライン一致で dedup")
    parser.add_argument("--keys", help="除去対象キーのカンマ区切り指定（--new-file 省略時に使用）")
    args = parser.parse_args()
    dedup_append(args.main_file, args.new_file, args.key_index, args.keys)


if __name__ == "__main__":
    main()
