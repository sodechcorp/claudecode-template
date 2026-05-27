"""
check_swimlanes.py — cat1 Phase 4.3 末尾で呼ぶ。
swimlanes.json の構造を機械的に検証し、不整合を警告する。
exit 0 で常に終了（警告のみ、cat1 の処理はブロックしない）。
Usage: python check_swimlanes.py {project_dir}
"""
import json, sys
from pathlib import Path

VALID_FLOW_TYPES = {"overview", "uc_specific", "exception", "data_flow"}


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
        label = flow.get("uc_id") or flow.get("id") or f"index={i}"
        ftype = flow.get("flow_type", "")
        if ftype not in VALID_FLOW_TYPES:
            errors.append(f"[{label}] invalid flow_type '{ftype}' (valid: {sorted(VALID_FLOW_TYPES)})")
        if not flow.get("actors") and not flow.get("lanes"):
            errors.append(f"[{label}] missing actors/lanes")
        if not flow.get("steps") and not flow.get("nodes") and not flow.get("edges"):
            errors.append(f"[{label}] missing steps/nodes/edges")

    if errors:
        print(f"[check_swimlanes] WARN: {len(errors)} issue(s):")
        for err in errors:
            print(f"  {err}")
    else:
        print(f"[check_swimlanes] OK: {len(flows)} flow(s) validated")

    sys.exit(0)


if __name__ == "__main__":
    main()
