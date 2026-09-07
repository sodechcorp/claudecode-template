# -*- coding: utf-8 -*-
"""backlog-xlsx / resolve_target_tcs.py
test.md Phase A 手順7（差分再実行モードの判定）から抽出した差分対象 TC 算出ロジック。
inline-script-hygiene.md のルール（`python -c` は単一物理行限定・多行ロジックは .py 化）に
従い、if/try-except を含む多行ロジックを本スクリプトへ切り出した。

前回の judgment-result.json と test-spec.md を突き合わせ、今回再実行すべき TC 番号
（前回 NG ∪ 前回 SKIP ∪ 前回結果に存在しない新規 TC。ただし ng_type=要確認 のみだった
NG は証跡再採取対象から除外）をカンマ区切りで標準出力に返す。

Usage:
    python resolve_target_tcs.py \
      --judgment /path/to/judgment-result.json \
      --spec /path/to/test-spec.md
"""

import argparse
import json

from _common import parse_test_spec


def resolve_target_tcs(judgment_path: str, spec_path: str) -> str:
    d = json.load(open(judgment_path, encoding="utf-8"))
    prev = {r["no"]: r.get("status") for r in d.get("results", [])}
    prev_ng_type = {r["no"]: r.get("ng_type", "") for r in d.get("results", [])}
    try:
        spec_nos = [tc.get("No", "") for tc in parse_test_spec(spec_path)]
    except Exception:
        spec_nos = list(prev.keys())
    raw_target = [no for no in spec_nos if prev.get(no, "NEW") in ("NG", "SKIP", "NEW")]
    capture_target = [
        no for no in raw_target
        if not (prev.get(no) == "NG" and prev_ng_type.get(no, "") == "要確認")
    ]
    target = capture_target if capture_target else raw_target
    return ",".join(target)


def main():
    parser = argparse.ArgumentParser(description="差分再実行対象 TC の算出")
    parser.add_argument("--judgment", required=True, help="judgment-result.json のパス")
    parser.add_argument("--spec", required=True, help="test-spec.md のパス")
    args = parser.parse_args()
    print(resolve_target_tcs(args.judgment, args.spec))


if __name__ == "__main__":
    main()
