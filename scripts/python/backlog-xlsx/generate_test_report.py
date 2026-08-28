# -*- coding: utf-8 -*-
"""backlog-xlsx / generate_test_report.py
/test Phase F（レポート・後始末）のうち、決定論的な部分（tmp/ 削除・test-report.md 生成）を
LLM サブエージェントを起動せずに実行する。

judgment-result.json（judge_results.py が Phase E で生成）と test-spec.md を突き合わせて
test-report.md を組み立てる。ロジックは .claude/agents/auto-evidence-runner.md の Step 5・
Step 6 の仕様（テンプレート・省略ルール）と完全に一致させること（仕様を変更したら本スクリプトも
同期して変更する）。

知見還流（テストデータレシピ・落とし穴、write-after）は判断を要するため対象外。
Phase F では本スクリプト実行後に auto-evidence-runner を Step 7 専用モードで委譲し、
本スクリプトが書き出した test-report.md の「### テストデータ」セクションへ追記させる。

Usage:
    python generate_test_report.py \\
      --issue-id GF-350 \\
      --judgment /path/to/judgment-result.json \\
      --spec /path/to/test-spec.md \\
      --log-dir /path/to/docs/logs/GF-350 \\
      --alias sandboxAlias \\
      --instance-url https://xxxxx--sandboxname.sandbox.my.salesforce.com
"""

import argparse
import datetime
import glob
import json
import os
import re
import shutil
import sys
from pathlib import Path

from _common import parse_test_spec

_STATUS_ICON = {"OK": "✅ OK", "NG": "❌ NG", "SKIP": "（要手動）", "対象外": "▲"}


def _current_round(judgment_path: str) -> int:
    """judgment-result.R{N}.json の本数から現在の実行回次を返す（judge_results.py の
    _archive_previous_round / test.md Phase F-2 の PREV_ROUND 算出と同一基準）。"""
    base = os.path.splitext(judgment_path)[0]
    files = glob.glob(base + ".R*.json")
    nums = [int(m.group(1)) for f in files for m in [re.search(r"\.R(\d+)\.json$", f)] if m]
    return (max(nums) if nums else 0) + 1


def _spec_by_no(spec_path: str) -> dict:
    rows = parse_test_spec(spec_path)
    return {r.get("No", ""): r for r in rows}


def _extract_paren_reason(auto_kahi: str, prefix: str) -> str:
    """自動化可否列（例: '要手動（外部サービス通信のため）'）から括弧内の理由を取り出す。"""
    m = re.search(rf"{prefix}\s*[（(](.+?)[）)]", auto_kahi or "")
    return m.group(1).strip() if m else "理由未記載"


def _read_lines_if_exists(path: str) -> list:
    if not path or not os.path.isfile(path):
        return []
    text = Path(path).read_text(encoding="utf-8", errors="replace")
    return [ln for ln in text.splitlines() if ln.strip()]


def _teisaku_teijun(no: str, spec_row: dict) -> str:
    """操作手順列を組み立てる。
    優先順位: 1) test-spec.md の「テスト手順」列  2) 前提・データ準備＋実行アクションの機械的連結
    （3の「自然文で要約する」＝LLM要約は本スクリプトでは行わない。自然文要約が必要な場合は
    人手 or サブエージェント側で補ってもらう前提の簡易フォールバック）。"""
    if not spec_row:
        return "—"
    teisuha = (spec_row.get("テスト手順") or "").strip()
    if teisuha:
        return teisuha
    zentei = (spec_row.get("前提・データ準備") or "").strip()
    action = (spec_row.get("実行アクション") or "").strip()
    parts = [p for p in [zentei, action] if p]
    return " → ".join(parts) if parts else "—"


def build_report(issue_id: str, judgment: dict, spec_by_no: dict, log_dir: str,
                  alias: str, instance_url: str, round_no: int) -> str:
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    lines = []
    lines.append(f"## テスト結果: {issue_id}")
    lines.append("")
    lines.append("### テスト実行サマリー")
    lines.append(f"- 実行日時: {now}")
    lines.append(f"- Sandbox alias: {alias}")
    lines.append(f"- テストケース合計: {judgment.get('total', 0)} 件")
    lines.append(f"- OK: {judgment.get('ok', 0)} 件 / NG: {judgment.get('ng', 0)} 件 / "
                 f"要手動: {judgment.get('skip', 0)} 件 / 対象外: {judgment.get('taigaigai', 0)} 件")
    lines.append(f"- テスト実行回数: {round_no} 回目（NG 修正後の再実行回数）")
    lines.append("")
    lines.append("### 自動実行結果")
    lines.append("")
    lines.append("| No | 観点 | 種別 | 実際の結果 | 判定 |")
    lines.append("|---|---|---|---|---|")
    for r in judgment.get("results", []):
        no = r.get("no", "")
        label = r.get("label", "") or spec_by_no.get(no, {}).get("観点", "")
        shubetsu = spec_by_no.get(no, {}).get("種別", spec_by_no.get(no, {}).get("実行種別", ""))
        actual = r.get("actual", "")
        icon = _STATUS_ICON.get(r.get("status", ""), r.get("status", ""))
        lines.append(f"| {no} | {label} | {shubetsu} | {actual} | {icon} |")
    lines.append("")

    ng_list = judgment.get("ng_list", [])
    lines.append("### NG 一覧")
    lines.append("")
    lines.append(f"{len(ng_list)} 件の NG が検出されました。")
    lines.append("")
    lines.append("| No | 観点 | NG 理由 |")
    lines.append("|---|---|---|")
    for ng in ng_list:
        lines.append(f"| {ng.get('no', '')} | {ng.get('label', '')} | {ng.get('reason', '')} |")
    lines.append("")

    skip_list = judgment.get("skip_list", [])
    lines.append("### 要手動確認（自動化不可ケース）")
    lines.append("")
    lines.append("| No | 観点 | 理由 |")
    lines.append("|---|---|---|")
    for no in skip_list:
        row = spec_by_no.get(no, {})
        label = row.get("観点", "")
        reason = _extract_paren_reason(row.get("自動化可否", ""), "要手動")
        lines.append(f"| {no} | {label} | {reason} |")
    lines.append("")
    lines.append("エビデンス.xlsx「証跡」シートの該当ケース枠にスクリーンショットを貼り付けてください。"
                 "操作手順は test-spec.md の該当 No「テスト手順」列（無ければ「前提・データ準備」＋「実行アクション」）"
                 "を参照。要手動ケースは Claude がレコードを作成していない"
                 "（外部サービス通信・本番限定データ・実時刻起動が理由のため）ので、"
                 "下記「🔎 目視確認のご案内」には通常含まれません。")
    lines.append("")

    taigaigai_list = judgment.get("taigaigai_list", [])
    if taigaigai_list:
        lines.append("### 対象外（検証不能）")
        lines.append("")
        lines.append(f"{len(taigaigai_list)} 件が対象外です。前提状態の消失等により、"
                     "自動・手動を問わず今回のテストでは検証する手段がありません"
                     "（NG・要手動確認のいずれにも含めていません）。")
        lines.append("")
        lines.append("| No | 観点 | 対象外の理由 |")
        lines.append("|---|---|---|")
        for t in taigaigai_list:
            lines.append(f"| {t.get('no', '')} | {t.get('label', '')} | {t.get('reason', '')} |")
        lines.append("")

    lines.append("### 網羅性チェック")
    lines.append("")
    lines.append("Phase B（test-spec-builder）で確認済み。")
    lines.append("")
    lines.append("### テストデータ")
    lines.append(f"- 削除は行わず Sandbox に保持（プレフィックス: `AUTOTEST_{issue_id}_`）。"
                 "対象レコードの直接URLは下記「🔎 目視確認のご案内」を参照。")
    lines.append("")

    # 目視ハンドオフブロック
    created_records = _read_lines_if_exists(os.path.join(log_dir, "created_records.txt"))
    screen_urls = _read_lines_if_exists(os.path.join(log_dir, "ui_screen_urls.txt"))

    handoff_rows = []
    for ln in created_records:
        parts = ln.split("|") if "|" in ln else ln.split(",")
        if len(parts) < 2:
            continue
        sobject, rec_id = parts[0].strip(), parts[1].strip()
        name = parts[2].strip() if len(parts) > 2 else sobject
        tc_no = parts[3].strip() if len(parts) > 3 else ""
        if not sobject or not rec_id:
            continue
        url = f"{instance_url}/lightning/r/{sobject}/{rec_id}/view"
        teijun = _teisaku_teijun(tc_no, spec_by_no.get(tc_no, {}))
        handoff_rows.append((name, url, rec_id, tc_no, teijun))
    for ln in screen_urls:
        parts = ln.split("|")
        if len(parts) < 3:
            continue
        no, label, url = parts[0].strip(), parts[1].strip(), parts[2].strip()
        if not url:
            continue
        teijun = _teisaku_teijun(no, spec_by_no.get(no, {}))
        handoff_rows.append((label, url, "—", no, teijun))

    if handoff_rows:
        lines.append("## 🔎 目視確認のご案内")
        lines.append("")
        lines.append(f"Sandbox（{alias}）に未ログインの場合は、リンククリック後にログイン画面が出ます。"
                     "ログイン後に対象が表示されます。")
        lines.append("")
        lines.append("| 確認対象 | 画面/レコードURL | レコードID | 対象TC | 操作手順 |")
        lines.append("|---|---|---|---|---|")
        for name, url, rec_id, tc_no, teijun in handoff_rows:
            lines.append(f"| {name} | {url} | {rec_id} | {tc_no} | {teijun} |")
        lines.append("")

    lines.append("### 総合判定")
    if judgment.get("ng", 0) == 0:
        lines.append("PASS — Phase 6 リリース準備へ進めます")
    else:
        lines.append("FAIL — Phase 4/3/2 に差し戻し")
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="judgment-result.json から test-report.md を決定論的に生成する")
    parser.add_argument("--issue-id", required=True, dest="issue_id")
    parser.add_argument("--judgment", required=True, help="judgment-result.json のパス")
    parser.add_argument("--spec", required=True, help="test-spec.md のパス")
    parser.add_argument("--log-dir", required=True, dest="log_dir")
    parser.add_argument("--alias", required=True)
    parser.add_argument("--instance-url", default="", dest="instance_url")
    parser.add_argument("--out", default="", help="省略時は {log-dir}/test-report.md")
    args = parser.parse_args()

    if not os.path.isfile(args.judgment):
        print(f"[FATAL] judgment-result.json が見つかりません: {args.judgment}")
        sys.exit(1)
    judgment = json.loads(Path(args.judgment).read_text(encoding="utf-8"))
    spec_by_no = _spec_by_no(args.spec)
    round_no = _current_round(args.judgment)

    report = build_report(args.issue_id, judgment, spec_by_no, args.log_dir,
                          args.alias, args.instance_url, round_no)

    out_path = args.out or os.path.join(args.log_dir, "test-report.md")
    Path(out_path).write_text(report, encoding="utf-8")

    # Step 5 相当: tmp/ 一時ファイルの後始末
    shutil.rmtree(os.path.join(args.log_dir, "tmp"), ignore_errors=True)

    print(f"生成完了: {out_path}")
    print(f"テストケース: {judgment.get('total', 0)}件 "
         f"(OK={judgment.get('ok', 0)} / NG={judgment.get('ng', 0)} / "
         f"要手動={judgment.get('skip', 0)} / 対象外={judgment.get('taigaigai', 0)})")
    print(f"回次: {round_no}回")


if __name__ == "__main__":
    main()
