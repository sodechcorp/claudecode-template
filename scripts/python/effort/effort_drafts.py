"""課題の「作業のまとまり」ごとの対応の案（日付・時間・何をどう対応したか）を手元に控える。

保守ポータルに渡す対応の案と、docs/knowledge/cases/{key}.md の「## 対応履歴」の行に、同じ区切り・同じ文を使うための控え。
時間は測った時間ではなく「そのまとまりを担当者が手でやったらかかる時間」（見積と同じ物差し。呼ぶ側が決める）。

使い方（プロジェクトのルートで。{key} は課題キー）:
    python scripts/python/effort/effort_drafts.py add {key} "調査" 1.5 "原因の調査: …（根拠）" [--date 2026-11-26]
    python scripts/python/effort/effort_drafts.py total {key}                        # 控えた時間の合計
    python scripts/python/effort/effort_drafts.py pending {key} --for portal|cases    # まだ渡していない／書いていない控え
    python scripts/python/effort/effort_drafts.py mark-sent {key} --to portal|cases {id}...  # 渡した（ポータル）・書いた（cases）の印

- 時間は 0.5 時間単位に切り上げる（最小 0.5・24 以下）
- 日付を省くと今日（この PC の日付）
- 記録は docs/logs/{key}/effort-drafts.json（Git の対象外の作業場）
"""

from __future__ import annotations

import json
import math
import sys
from datetime import date
from pathlib import Path


def _path(key: str) -> Path:
    return Path("docs") / "logs" / key / "effort-drafts.json"


def _load(key: str) -> dict:
    p = _path(key)
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {"items": []}


def _save(key: str, state: dict) -> None:
    p = _path(key)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _take(rest: list[str], flag: str, default: str | None = None) -> str | None:
    if flag in rest:
        i = rest.index(flag)
        value = rest[i + 1] if i + 1 < len(rest) else None
        del rest[i:i + 2]
        return value
    return default


def _total(state: dict) -> float:
    return sum(i["hours"] for i in state["items"])


def main(argv: list[str]) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    if len(argv) < 3:
        print(__doc__)
        return 2
    cmd, key, rest = argv[1], argv[2], list(argv[3:])
    state = _load(key)

    if cmd == "add":
        work_date = _take(rest, "--date") or date.today().isoformat()
        if len(rest) < 3 or not rest[0].strip() or not rest[2].strip():
            print("[ERROR] まとまりの名前・時間・内容を渡してください", file=sys.stderr)
            return 2
        try:
            hours = float(rest[1])
            date.fromisoformat(work_date)
        except ValueError:
            print(f"[ERROR] 時間か日付の形が違います: {rest[1]} / {work_date}", file=sys.stderr)
            return 2
        if not 0 < hours <= 24:
            print(f"[ERROR] 時間は 0 より大きく 24 以下: {hours}", file=sys.stderr)
            return 2
        hours = max(0.5, math.ceil(hours * 2) / 2)
        item = {"id": len(state["items"]) + 1, "label": rest[0].strip(), "workDate": work_date,
                "hours": hours, "content": rest[2].strip(), "sent": False, "written": False}
        state["items"].append(item)
        _save(key, state)
        print(json.dumps({"added": item, "total": _total(state)}, ensure_ascii=False))
    elif cmd == "total":
        print(json.dumps({"total": _total(state), "count": len(state["items"])}, ensure_ascii=False))
    elif cmd in ("pending", "mark-sent"):
        target = _take(rest, "--for") or _take(rest, "--to") or ""
        if target not in ("portal", "cases"):
            print("[ERROR] --for / --to に portal か cases を渡してください", file=sys.stderr)
            return 2
        flag = "sent" if target == "portal" else "written"
        if cmd == "pending":
            print(json.dumps({"for": target, "pending": [i for i in state["items"] if not i.get(flag)]}, ensure_ascii=False))
        else:
            ids = {int(x) for x in rest}
            for i in state["items"]:
                if i["id"] in ids:
                    i[flag] = True
            _save(key, state)
            print(json.dumps({"marked": sorted(ids), "to": target}, ensure_ascii=False))
    else:
        print(f"[ERROR] 知らない操作です: {cmd}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
