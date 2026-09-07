# -*- coding: utf-8 -*-
"""backlog-xlsx / summarize_after.py
test.md Phase F-1b 手順1（After 状態のテキスト要約生成）から抽出したロジック。
inline-script-hygiene.md のルール（`python -c` は単一物理行限定）に従い、
複数行の `python -c` 埋め込みを本スクリプトへ切り出した。

judgment-result.json の results[] から OK/対象外の行だけを機械的に組み立てて
標準出力へ返す（LLM 生成ではなく決定的な変換）。

Usage:
    python summarize_after.py --judgment /path/to/judgment-result.json
"""

import argparse
import json


def summarize_after(judgment_path: str) -> str:
    d = json.load(open(judgment_path, encoding="utf-8"))
    lines = [
        f"- {r['label']}: {r['actual']}"
        for r in d.get("results", [])
        if r.get("status") in ("OK", "対象外")
    ]
    return "\n".join(lines) if lines else "(該当する実行結果なし)"


def main():
    parser = argparse.ArgumentParser(description="After 状態のテキスト要約生成")
    parser.add_argument("--judgment", required=True, help="judgment-result.json のパス")
    args = parser.parse_args()
    print(summarize_after(args.judgment))


if __name__ == "__main__":
    main()
