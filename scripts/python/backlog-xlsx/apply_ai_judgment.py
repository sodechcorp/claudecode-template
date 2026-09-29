#!/usr/bin/env python3
"""/test Phase D-2: AI 判定の結果を judgment-result.json に反映する。

judge_results.py が機械判定できなかった TC（status = "AI判定"）について、AI が証跡と期待結果を
読んで下した OK/NG を書き戻し、件数・一覧（ok / ng / ai_pending / ng_list / ai_list）を再計算する。

decisions JSON の形式（配列）:
[
  {"no": "TC-003", "status": "OK", "basis": "SOQL 結果の IsLease__c 列が全行 false"},
  {"no": "TC-005", "status": "NG", "basis": "画面に『申込できません』が表示されていない",
   "ng_type": ""}   # ng_type: "" = 実装が期待値と不一致 / "未実行" = 証跡が不十分で再採取が必要 / "画面エラー"
]

使い方:
  python apply_ai_judgment.py --judgment docs/logs/GF-123/judgment-result.json --decisions docs/logs/GF-123/.tmp/ai-decisions.json
"""
import argparse
import json
import sys
from pathlib import Path

_VALID_STATUS = {"OK", "NG"}
_VALID_NG_TYPE = {"", "未実行", "画面エラー"}


def apply(judgment: dict, decisions: list) -> list:
    """decisions を judgment に反映する。反映できなかった理由のリストを返す（空なら全件反映）。"""
    errors = []
    by_no = {r.get("no"): r for r in judgment.get("results", [])}
    for d in decisions:
        no = d.get("no", "")
        status = d.get("status", "")
        basis = (d.get("basis") or "").strip()
        ng_type = d.get("ng_type", "") or ""
        r = by_no.get(no)
        if r is None:
            errors.append(f"{no}: judgment-result.json に存在しない TC です")
            continue
        if r.get("status") != "AI判定":
            errors.append(f"{no}: status が AI判定 ではありません（現在: {r.get('status')}）")
            continue
        if status not in _VALID_STATUS:
            errors.append(f"{no}: status は OK / NG のいずれかにしてください（指定: {status}）")
            continue
        if not basis:
            errors.append(f"{no}: 判定根拠（basis）が空です。証跡のどこを見て判定したかを書いてください")
            continue
        if status == "NG" and ng_type not in _VALID_NG_TYPE:
            errors.append(f"{no}: ng_type は 空（実装不一致）/ 未実行 / 画面エラー のいずれかにしてください（指定: {ng_type}）")
            continue
        r["status"] = status
        r["actual"] = f"AI判定: {basis}"
        r["reason"] = "" if status == "OK" else basis
        r["ng_type"] = ng_type if status == "NG" else ""
        r["ai_judged"] = True
    _recount(judgment)
    return errors


def _recount(judgment: dict) -> None:
    results = judgment.get("results", [])
    ai_by_no = {a.get("no"): a for a in judgment.get("ai_list", [])}
    judgment["ok"] = sum(1 for r in results if r.get("status") == "OK")
    judgment["ng_list"] = [
        {"no": r["no"], "label": r.get("label", ""), "reason": r.get("reason", ""), "ng_type": r.get("ng_type", "")}
        for r in results if r.get("status") == "NG"
    ]
    judgment["ng"] = len(judgment["ng_list"])
    judgment["ai_list"] = [ai_by_no.get(r["no"], {"no": r["no"], "label": r.get("label", "")})
                           for r in results if r.get("status") == "AI判定"]
    judgment["ai_pending"] = len(judgment["ai_list"])
    judgment["skip_list"] = [r["no"] for r in results if r.get("status") == "SKIP"]
    judgment["skip"] = len(judgment["skip_list"])
    judgment["total"] = len(results)


def main() -> int:
    parser = argparse.ArgumentParser(description="AI 判定の結果を judgment-result.json に反映する")
    parser.add_argument("--judgment", required=True, help="judgment-result.json のパス")
    parser.add_argument("--decisions", required=True, help="AI 判定結果（JSON 配列）のパス")
    args = parser.parse_args()

    judgment_path = Path(args.judgment)
    judgment = json.loads(judgment_path.read_text(encoding="utf-8"))
    decisions = json.loads(Path(args.decisions).read_text(encoding="utf-8"))
    if not isinstance(decisions, list):
        print("[ERROR] decisions は JSON 配列にしてください", file=sys.stderr)
        return 2

    errors = apply(judgment, decisions)
    judgment_path.write_text(json.dumps(judgment, ensure_ascii=False, indent=2), encoding="utf-8")

    for e in errors:
        print(f"[ERROR] {e}", file=sys.stderr)
    print(f"判定サマリー: OK={judgment['ok']} / NG={judgment['ng']} / AI判定待ち={judgment['ai_pending']} / "
          f"要手動={judgment['skip']} / 対象外={judgment.get('taigaigai', 0)} / 合計={judgment['total']}")
    if judgment["ai_pending"]:
        pending = ", ".join(a["no"] for a in judgment["ai_list"])
        print(f"[WARN] AI判定待ちが残っています: {pending}（全件判定してから Phase E に進むこと）")
    if errors:
        return 2
    return 1 if judgment["ng"] else 0


if __name__ == "__main__":
    sys.exit(main())
