# -*- coding: utf-8 -*-
"""
sf-code-analyzer / format_results.py
`sf code-analyzer run -f <results.json>` の出力を reviewer.md 形式
（Critical/Warning/Info の3段組・`file:line` 根拠付き）の Markdown に整形する。

Usage:
    python format_results.py <results.json>

    results.json: `sf code-analyzer run --output-file <results.json>` で生成した JSON。
    標準出力に Markdown レポートを出力する。

severity マッピング（Code Analyzer の 1(最重要)〜5(最軽微) を reviewer.md の3段に圧縮）:
    1, 2 (Critical/High)   -> Critical（必ず修正）
    3    (Moderate)        -> Warning（修正推奨）
    4, 5 (Low/Info)        -> Info（確認・提案）

Exit codes:
    0: 正常完了（違反0件を含む）
    1: 入力ファイルが存在しない / JSON として不正 / 期待するキーがない
"""

import json
import os
import sys
from collections import defaultdict
from typing import Any, Dict, List

TIER_ORDER = ["Critical", "Warning", "Info"]
TIER_LABEL = {
    "Critical": "### Critical（必ず修正）",
    "Warning": "### Warning（修正推奨）",
    "Info": "### Info（確認・提案）",
}


def severity_to_tier(severity: int) -> str:
    if severity <= 2:
        return "Critical"
    if severity == 3:
        return "Warning"
    return "Info"


def is_engine_error(v: Dict[str, Any]) -> bool:
    """PMD/CPD 等の解析エンジン自体が内部エラーで異常終了した際に挿入される疑似 violation を判定する。
    実機再現（日本語マルチバイトパス環境）では rule=="UnexpectedEngineError" かつ
    locations に file キーが無い（{"comment": "Undefined Code Location"}）形で出力される。
    severity 値のみでは実コード違反と区別できないため、rule 名と location 欠落の両方で判定する。
    """
    if v.get("rule") == "UnexpectedEngineError":
        return True
    locations: List[Dict[str, Any]] = v.get("locations") or []
    if not locations or "file" not in locations[0]:
        return True
    return False


def load_results(path: str) -> Dict[str, Any]:
    if not os.path.exists(path):
        print(f"[ERROR] 入力ファイルが見つかりません: {path}", file=sys.stderr)
        sys.exit(1)
    with open(path, encoding="utf-8") as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            print(f"[ERROR] JSON として解釈できません: {path} ({e})", file=sys.stderr)
            sys.exit(1)
    if "violations" not in data:
        print(f"[ERROR] 想定した Code Analyzer 出力形式ではありません（'violations' キーがない）: {path}", file=sys.stderr)
        sys.exit(1)
    return data


def format_violation(v: Dict[str, Any]) -> str:
    locations: List[Dict[str, Any]] = v.get("locations") or []
    idx = v.get("primaryLocationIndex", 0)
    loc = locations[idx] if 0 <= idx < len(locations) else (locations[0] if locations else {})
    file_path = loc.get("file", "(unknown file)")
    line = loc.get("startLine", "?")
    engine = v.get("engine", "?")
    rule = v.get("rule", "?")
    message = v.get("message", "")
    resources = v.get("resources") or []
    ref = f"（{resources[0]}）" if resources else ""
    return f"- `{file_path}:{line}` [{engine}:{rule}] {message}{ref}"


def build_engine_error_section(engine_errors: List[Dict[str, Any]]) -> List[str]:
    lines = ["### ⚠️ エンジンエラー（解析基盤の失敗・コード違反ではない）", ""]
    for v in engine_errors:
        engine = v.get("engine", "?")
        rule = v.get("rule", "?")
        message = v.get("message", "")
        lines.append(f"- [{engine}:{rule}] {message}")
    lines.append("")
    lines.append(
        "> PMD/CPD 等の解析エンジン自体が内部エラーで異常終了しました。日本語（マルチバイト）ワークスペースパスが原因になるケースが確認されています。"
        "コード修正では解消しません。ASCIIパスでの再実行や `--rule-selector` の絞り込みを検討してください。"
    )
    return lines


def build_report(data: Dict[str, Any]) -> str:
    violations: List[Dict[str, Any]] = data.get("violations", [])
    versions = data.get("versions", {})
    run_dir = data.get("runDir", ".")

    version_str = " / ".join(f"{k} {v}" for k, v in versions.items() if k != "code-analyzer")
    engine_errors = [v for v in violations if is_engine_error(v)]
    code_violations = [v for v in violations if not is_engine_error(v)]

    lines: List[str] = []
    lines.append("## コード品質スキャン結果（sf code-analyzer）")
    lines.append("")
    lines.append(f"対象: `{run_dir}`")
    if version_str:
        lines.append(f"エンジン: {version_str}")

    if not code_violations:
        lines.append("検出件数: 合計0件")
        lines.append("")
        lines.append("### 問題なし")
        lines.append("")
        lines.append("実エンジン解析（PMD/CPD/regex 等）で違反は検出されませんでした。")
        if engine_errors:
            lines.append("")
            lines.extend(build_engine_error_section(engine_errors))
        return "\n".join(lines)

    tiers: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for v in code_violations:
        tiers[severity_to_tier(v.get("severity", 5))].append(v)

    tier_counts = ", ".join(f"{t}: {len(tiers.get(t, []))}" for t in TIER_ORDER if tiers.get(t))
    lines.append(f"検出件数: 合計{len(code_violations)}件（{tier_counts}）")
    lines.append("")

    for tier in TIER_ORDER:
        items = tiers.get(tier)
        if not items:
            continue
        lines.append(TIER_LABEL[tier])
        # 同一ファイル内は行番号順にまとめる
        items_sorted = sorted(
            items,
            key=lambda v: (
                (v.get("locations") or [{}])[0].get("file", ""),
                (v.get("locations") or [{}])[0].get("startLine", 0),
            ),
        )
        for v in items_sorted:
            lines.append(format_violation(v))
        lines.append("")

    if engine_errors:
        lines.extend(build_engine_error_section(engine_errors))

    lines.append("> 実エンジン（PMD/CPD/regex）による自動検出です。reviewer.md のチェックリストによる目視レビューと併用してください。誤検知の可能性があります。")
    return "\n".join(lines)


def main() -> None:
    if len(sys.argv) != 2:
        print("Usage: python format_results.py <results.json>", file=sys.stderr)
        sys.exit(1)
    data = load_results(sys.argv[1])
    print(build_report(data))


if __name__ == "__main__":
    main()
