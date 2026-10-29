# -*- coding: utf-8 -*-
"""backlog-xlsx / check_target_required.py
test.md Phase B のバックストップ自己チェック。
test-spec-builder.md Step 3 軸0（種別に UI を含む全 TC の「確認ポイント（着眼点）」列に
target= が付記されているかの自己チェック）の抜け漏れを、オーケストレータ側からも
検知できるようにする。

test-spec.md を読み、種別に UI を含む TC のうち「確認ポイント（着眼点）」列に target= が
付記されていない TC 番号をカンマ区切りで標準出力に返す（0件なら空文字）。
テストケースを読めない spec は exit 2（Phase C に進ませない）。

Usage:
    python check_target_required.py --spec /path/to/test-spec.md
"""

import argparse
import sys

from _common import parse_test_spec


def check_target_required(rows: list) -> list:
    missing = []
    for r in rows:
        if "UI" not in (r.get("種別") or ""):
            continue
        checkpoint = r.get("確認ポイント（着眼点）") or ""
        if "target=" not in checkpoint:
            missing.append(r.get("No", ""))
    return missing


def main():
    parser = argparse.ArgumentParser(description="target= 必須ルールのバックストップ自己チェック")
    parser.add_argument("--spec", required=True, help="test-spec.md のパス")
    args = parser.parse_args()
    try:
        rows, err = parse_test_spec(args.spec), "No 列のある表に TC の行がありません"
    except (OSError, UnicodeDecodeError) as e:
        rows, err = [], str(e)
    if not rows:
        print(f"[FATAL] test-spec.md からテストケースを読めません（{err}）: {args.spec}", file=sys.stderr)
        sys.exit(2)
    print(",".join(check_target_required(rows)))


if __name__ == "__main__":
    main()
