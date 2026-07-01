# -*- coding: utf-8 -*-
"""backlog-xlsx / apextest_runner.py
ApexTest を Sandbox で一括実行し（`sf apex run test --class-names` に全クラスを
まとめて1コマンドで渡す）、TC（クラス）ごとに証跡ファイルへ分離して保存する。

背景: sf apex run test は1回ごとにプロセス起動＋サーバ側テスト実行が走り、
TC 件数分だけ直列に叩くと線形に遅くなる。全クラスを1コマンドに集約して
プロセス起動・サーバ往復を1回に減らし、結果は judge_results.py が読める
`TEST NAME` / `OUTCOME` 形式で TC ごとに振り分けて出力する（結合出力をそのまま
全 TC に流用すると他クラスの失敗が無関係な TC を巻き込むため、必ず分離する）。

Usage（一括実行）:
    python apextest_runner.py run-batch \\
      --alias <sandbox-alias> \\
      --cases-file /path/to/apextest_cases.json

cases-file 形式（[{"no","label","class_names","out"}, ...]）:
    [
      {"no": "TC-005", "label": "受注バリデーション", "class_names": "OrderTest",
       "out": ".../after/apex/TC-005_受注バリデーション.txt"},
      {"no": "TC-006", "label": "権限差分確認", "class_names": "OrderTest,OrderSharingTest",
       "out": ".../after/apex/TC-006_権限差分確認.txt"}
    ]

`--serial` 指定時、または一括実行が構造的に失敗した場合は、クラス単位の
個別実行にフォールバックする（sandbox 確認・ロジックは soql_evidence.py /
anon_apex_runner.py と統一）。
"""

import argparse
import datetime
import json
import os
import subprocess
import sys
from pathlib import Path


# ── sandbox 判定（soql_evidence.py / anon_apex_runner.py と同一ロジック） ──────

def assert_sandbox(alias: str) -> str:
    """alias が Sandbox であることを確認する。本番なら SystemExit。確定した alias を返す。"""
    if not alias:
        result = subprocess.run(
            ["sf", "config", "get", "target-org", "--json"],
            capture_output=True, text=True
        )
        try:
            alias = json.loads(result.stdout)["result"][0]["value"]
        except (json.JSONDecodeError, KeyError, IndexError):
            raise SystemExit("[FATAL] target-org が設定されていません。--alias を指定してください。")
        if not alias:
            raise SystemExit("[FATAL] target-org が設定されていません。--alias を指定してください。")

    result = subprocess.run(
        ["sf", "org", "display", "--target-org", alias, "--json"],
        capture_output=True, text=True
    )
    try:
        org_info = json.loads(result.stdout)["result"]
        is_sandbox = org_info.get("isSandbox", False)
    except (json.JSONDecodeError, KeyError):
        raise SystemExit(f"[FATAL] org display 失敗 ({alias}). Sandbox 確認ができません。")

    if not is_sandbox:
        raise SystemExit(
            f"[FATAL] 接続先が Sandbox ではありません ({alias})。\n"
            "        本番組織への ApexTest 実行は禁止されています。"
        )
    return alias


# ── ApexTest 実行 ────────────────────────────────────────────────────────────

def run_apex_tests(alias: str, class_names: list) -> dict:
    """sf apex run test --class-names を実行し JSON 結果を返す。失敗時は SystemExit。

    `--json`（グローバルフラグ）を使う場合は `--result-format` を渡さない
    （CLI の JSON エンベロープは --result-format と独立に result.tests/coverage
    を返すため、併用による解釈違いのリスクを避ける）。
    """
    result = subprocess.run(
        ["sf", "apex", "run", "test",
         "--target-org", alias,
         "--class-names", ",".join(class_names),
         "--code-coverage",
         "--wait", "30",
         "--json"],
        capture_output=True, text=True
    )
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError:
        raise SystemExit(
            f"[FATAL] ApexTest レスポンスの JSON パース失敗:\n{result.stdout[:500]}"
        )

    apex_result = data.get("result") or {}
    if not apex_result.get("tests"):
        # テスト結果が1件も返らない = コンパイルエラー・ガバナ制限等の構造的失敗
        err = data.get("message") or result.stderr[:500] or result.stdout[:500]
        raise SystemExit(f"[FATAL] ApexTest 実行結果が空です（{','.join(class_names)}）:\n{err}")
    return data


# ── 証跡テキスト整形 ──────────────────────────────────────────────────────────

def _build_case_text(no: str, label: str, class_names: list, tests_by_class: dict,
                     batch_mode: bool, overall_coverage: str = "") -> str:
    """1 TC（1〜複数クラス）分の証跡テキストを組み立てる。

    judge_results.py の判定パターンに一致させる:
    - 全 Pass -> 先頭に `Outcome: Passed` を書く（Pass Rate/Outcome 優先判定に一致）
    - 1件でも Fail -> `Outcome: Failed` ＋ `Failures: ...` 行を書く
    - 補助として `TEST NAME` / `OUTCOME` 表（sf --result-format human 相当）も残す
    """
    ts = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    all_tests = []
    missing_classes = []
    for cls in class_names:
        cls_tests = tests_by_class.get(cls)
        if cls_tests:
            all_tests.extend(cls_tests)
        else:
            missing_classes.append(cls)

    outcomes = [t.get("Outcome", "") for t in all_tests]
    all_pass = bool(outcomes) and all(o.lower() == "pass" for o in outcomes) and not missing_classes

    lines = []
    lines.append("=" * 60)
    lines.append("ApexTest 実行証跡")
    if no:
        lines.append(f"No      : {no}")
    if label:
        lines.append(f"観点    : {label}")
    lines.append(f"クラス  : {', '.join(class_names)}")
    lines.append(f"実行日時: {ts}")
    mode_str = ("一括実行（--class-names 複数クラス同時。本ファイルは対象クラスのみ抽出）"
                if batch_mode else "逐次実行（一括失敗時のフォールバック）")
    lines.append(f"実行方式: {mode_str}")
    lines.append("=" * 60)
    lines.append(f"Outcome: {'Passed' if all_pass else 'Failed'}")
    lines.append("")

    lines.append("--- TEST NAME / OUTCOME ---")
    lines.append(f"{'TEST NAME':<50} OUTCOME")
    for t in all_tests:
        full_name = t.get("FullName", "")
        outcome = t.get("Outcome", "")
        lines.append(f"{full_name:<50} {outcome}")
    for cls in missing_classes:
        lines.append(f"{cls:<50} (結果未検出)")
    lines.append("")

    fails = [t for t in all_tests if t.get("Outcome", "").lower() != "pass"]
    if fails or missing_classes:
        lines.append("--- Failures ---")
        for t in fails:
            msg = t.get("Message") or t.get("StackTrace") or ""
            lines.append(f"Failures: {t.get('FullName', '')}: {msg}"[:300])
        for cls in missing_classes:
            lines.append(f"Failures: {cls}: テスト結果が見つかりません"
                          "（コンパイルエラー等の可能性。--serial で再実行を検討）")
        lines.append("")

    if overall_coverage:
        lines.append("--- カバレッジ（補助指標・バッチ全体の参考値） ---")
        lines.append(overall_coverage)
        lines.append("")

    return "\n".join(lines)


def _extract_overall_coverage(apex_result: dict) -> str:
    """result.summary / result.coverage.summary からバッチ全体の参考カバレッジ値を抽出する。
    フィールドが無い場合は空文字（補助指標のため無くても判定に影響しない）。
    """
    summary = apex_result.get("summary") or {}
    cov_summary = (apex_result.get("coverage") or {}).get("summary") or {}
    org_wide = cov_summary.get("orgWideCoverage") or summary.get("orgWideCoverage")
    run_cov = cov_summary.get("testRunCoverage") or summary.get("testRunCoverage")
    parts = []
    if run_cov:
        parts.append(f"Test Run Coverage: {run_cov}")
    if org_wide:
        parts.append(f"Org Wide Coverage: {org_wide}")
    return " / ".join(parts)


# ── 一括実行（run-batch サブコマンド） ────────────────────────────────────────

def _write_case(no: str, label: str, class_names: list, out_path: str,
                tests_by_class: dict, batch_mode: bool, overall_coverage: str) -> dict:
    text = _build_case_text(no, label, class_names, tests_by_class, batch_mode, overall_coverage)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    Path(out_path).write_text(text, encoding="utf-8")
    all_tests = [t for cls in class_names for t in tests_by_class.get(cls, [])]
    missing = [cls for cls in class_names if not tests_by_class.get(cls)]
    ok = bool(all_tests) and not missing and all(
        t.get("Outcome", "").lower() == "pass" for t in all_tests
    )
    return {"no": no, "label": label, "ok": ok, "out": out_path, "error": "" if ok else "ApexTest FAIL"}


def run_batch(alias: str, cases: list, serial: bool = False) -> list:
    """ApexTest ケース群を実行する。
    - serial=False（デフォルト）: 全クラスの和集合を1コマンドで一括実行し、TC ごとに振り分ける。
    - 一括実行が構造的に失敗した場合は自動でクラス単位の逐次実行にフォールバックする。
    - serial=True: 最初からクラス単位で個別実行する（governor 競合時の明示フォールバック用）。
    - assert_sandbox は呼び出し元で1回だけ実施済みの前提。
    返り値: TC ごとの結果 dict リスト（{"no","label","ok","out","error"}、No 昇順）。
    """
    case_classes = []
    all_classes = []
    seen = set()
    for c in cases:
        classes = [x.strip() for x in c["class_names"].split(",") if x.strip()]
        case_classes.append(classes)
        for cls in classes:
            if cls not in seen:
                seen.add(cls)
                all_classes.append(cls)

    if not serial:
        try:
            data = run_apex_tests(alias, all_classes)
        except SystemExit as e:
            print(f"[WARN] 一括実行に失敗しました。クラス単位の逐次実行にフォールバックします: {e}")
            return run_batch(alias, cases, serial=True)

        apex_result = data.get("result", {})
        tests_by_class = {}
        for t in apex_result.get("tests", []):
            cls = (t.get("ApexClass") or {}).get("Name") or t.get("FullName", "").split(".")[0]
            tests_by_class.setdefault(cls, []).append(t)
        overall_coverage = _extract_overall_coverage(apex_result)

        results = []
        for c, classes in zip(cases, case_classes):
            results.append(_write_case(c["no"], c.get("label", ""), classes, c["out"],
                                       tests_by_class, batch_mode=True,
                                       overall_coverage=overall_coverage))
        return sorted(results, key=lambda r: r["no"])

    # serial: クラス単位で個別実行し、実行結果をクラス名で集約してから TC ごとに振り分ける
    tests_by_class = {}
    overall_coverage = ""
    for cls in all_classes:
        try:
            data = run_apex_tests(alias, [cls])
            apex_result = data.get("result", {})
            tests_by_class[cls] = apex_result.get("tests", [])
            if not overall_coverage:
                overall_coverage = _extract_overall_coverage(apex_result)
        except SystemExit as e:
            print(f"[NG] クラス {cls} の実行に失敗しました: {e}")
            tests_by_class[cls] = []

    results = []
    for c, classes in zip(cases, case_classes):
        results.append(_write_case(c["no"], c.get("label", ""), classes, c["out"],
                                   tests_by_class, batch_mode=False,
                                   overall_coverage=overall_coverage))
    return sorted(results, key=lambda r: r["no"])


# ── main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="ApexTest の一括実行（--class-names 集約）")
    sub = parser.add_subparsers(dest="subcommand", required=True)

    p_batch = sub.add_parser("run-batch", help="複数の ApexTest クラスを1コマンドに集約して実行する")
    p_batch.add_argument("--alias", default="", help="Sandbox org alias")
    p_batch.add_argument("--cases-file", required=True, dest="cases_file",
                         help='実行ケース定義 JSON ファイル（[{"no","label","class_names","out"},...] 形式）')
    p_batch.add_argument("--serial", action="store_true",
                         help="最初からクラス単位で逐次実行する（governor 競合時のフォールバック用）")

    args = parser.parse_args()
    alias = assert_sandbox(args.alias)  # Sandbox 確認はループ前に1回だけ実施

    if args.subcommand == "run-batch":
        cases = json.loads(Path(args.cases_file).read_text(encoding="utf-8"))
        mode = "逐次" if args.serial else "一括（--class-names 集約）"
        print(f"[INFO] {len(cases)} 件の ApexTest ケースを{mode}で実行します。")
        results = run_batch(alias, cases, serial=args.serial)
        ng_count = sum(1 for r in results if not r["ok"])
        print(f"[INFO] run-batch 完了: {len(results)} 件実行 / NG {ng_count} 件")
        if ng_count:
            for r in results:
                if not r["ok"]:
                    print(f"  [NG] {r['no']} ({r['label']}): {r['error']}")
            sys.exit(1)


if __name__ == "__main__":
    main()
