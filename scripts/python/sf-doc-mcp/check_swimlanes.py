"""
check_swimlanes.py — cat1 Phase 4.3 末尾で呼ぶ。
swimlanes.json の構造を機械的に検証し、不整合を警告する。
exit 0 で常に終了（警告のみ、cat1 の処理はブロックしない）。
Usage: python check_swimlanes.py {project_dir}
"""
import json, re, sys
from pathlib import Path

VALID_FLOW_TYPES = {
    "overall", "usecase", "uc_specific",  # uc_specific は usecase の旧称
    "asis", "tobe", "exception", "dataflow", "data_flow",
}
# 英字チェック: 純英字 identifier（括弧内外問わずアルファベット連続3字以上）を検出
_EN_PATTERN = re.compile(r"[A-Za-z]{3,}")
# 許容する英字（助詞・URL キーワード等の2字以下は MAX_STEPS チェックだけ）
_ALLOWED_EN = re.compile(r"^(SF|ID|URL|OK|NG|CS|AD|PR|UC|IT)$")


def _get_label(step: dict) -> str:
    """step から表示ラベルを取得（title / action / label 優先順）"""
    return str(
        step.get("title", "")
        or step.get("action", "")
        or step.get("label", "")
        or step.get("name", "")
    )


def _has_english(text: str) -> bool:
    """業務語として不適切な英字表現が含まれるか（3字以上の連続アルファベット）"""
    for m in _EN_PATTERN.findall(text):
        if not _ALLOWED_EN.match(m):
            return True
    return False


def main():
    project_dir = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    swimlane_file = project_dir / "docs" / "flow" / "swimlanes.json"

    if not swimlane_file.exists():
        print(f"[check_swimlanes] SKIP: {swimlane_file} not found")
        sys.exit(0)

    try:
        raw = json.loads(swimlane_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"[check_swimlanes] ERROR: invalid JSON — {e}")
        sys.exit(0)

    flows = raw if isinstance(raw, list) else raw.get("flows", [])
    errors: list[str] = []

    for i, flow in enumerate(flows):
        label = flow.get("id") or flow.get("uc_id") or f"index={i}"
        ftype = flow.get("flow_type", "")
        steps = flow.get("steps", flow.get("nodes", []))
        transitions = flow.get("transitions", [])
        lanes = flow.get("lanes", flow.get("actors", []))

        # flow_type 検証
        if ftype not in VALID_FLOW_TYPES:
            errors.append(f"[{label}] invalid flow_type '{ftype}' (valid: {sorted(VALID_FLOW_TYPES)})")

        # lanes / steps 存在
        if not lanes:
            errors.append(f"[{label}] missing lanes/actors")
        if not steps:
            errors.append(f"[{label}] missing steps/nodes")

        # transitions 非空
        if steps and not transitions:
            errors.append(f"[{label}] transitions[] が空（steps があるのに遷移なし）")

        # title/action 英字チェック
        en_hits = []
        for s in steps:
            lbl = _get_label(s)
            if _has_english(lbl):
                en_hits.append(f"id={s.get('id','?')}: {lbl[:50]}")
        if en_hits:
            errors.append(
                f"[{label}] title/action に英字技術名が含まれる step が {len(en_hits)} 件:\n"
                + "\n".join(f"      {h}" for h in en_hits[:5])
                + ("\n      ..." if len(en_hits) > 5 else "")
            )

        # lane 参照整合
        lane_names = {ln.get("name", "") for ln in lanes}
        bad_lanes = [
            str(s.get("id", "?"))
            for s in steps
            if str(s.get("lane", "")) not in lane_names
        ]
        if bad_lanes:
            errors.append(f"[{label}] lane 参照不整合の step id: {bad_lanes[:5]}")

    if errors:
        print(f"[check_swimlanes] WARN: {len(errors)} issue(s):")
        for err in errors:
            print(f"  {err}")
    else:
        print(f"[check_swimlanes] OK: {len(flows)} flow(s) validated")

    sys.exit(0)


if __name__ == "__main__":
    main()
