"""課題の「作業のまとまり」ごとにかかった時間を測る（対応の案・cases の対応履歴の「時間」に使う）。

使い方（プロジェクトのルートで。{key} は課題キー）:
    python scripts/python/effort/effort_clock.py start  {key} "調査"   # まとまりを始める（動いているまとまりがあれば先に終える）
    python scripts/python/effort/effort_clock.py pause  {key}          # 担当者の返事を待って止まるとき
    python scripts/python/effort/effort_clock.py resume {key}          # 返事が来て続けるとき
    python scripts/python/effort/effort_clock.py stop   {key}          # まとまりを終える → 結果を JSON で出す
    python scripts/python/effort/effort_clock.py note   {key} {id} "何をどう対応したか"  # 内容を残す（ポータルの対応の案と cases の対応履歴で同じ文を使う）
    python scripts/python/effort/effort_clock.py pending {key} [--for portal|cases]  # 終えたが、まだ渡していない／書いていないまとまり（既定 portal）
    python scripts/python/effort/effort_clock.py mark-sent {key} [--to portal|cases] {id}...  # 渡した（ポータル）・書いた（cases）の印を付ける（既定 portal）

測り方:
    - 数えるのは、start〜stop のうち pause〜resume を除いた時間（担当者の返事を待っている時間は数えない）
    - 1回の続けての時間は 4 時間で打ち切る（pause を忘れて一晩たった、などで膨らまないように。打ち切ったら capped: true）
    - 0.5 時間単位に切り上げる。0 分でも 0.5 時間（最小の単位）
    - 作業した日は、まとまりを始めた日（この PC の日付）

記録は docs/logs/{key}/effort-clock.json（Git の対象外の作業場）。
"""

from __future__ import annotations

import json
import math
import sys
from datetime import datetime
from pathlib import Path

CAP_SECONDS = 4 * 60 * 60
UNIT_SECONDS = 30 * 60


def _now() -> datetime:
    return datetime.now().astimezone()


def _path(key: str) -> Path:
    return Path("docs") / "logs" / key / "effort-clock.json"


def _load(key: str) -> dict:
    p = _path(key)
    if not p.exists():
        return {"current": None, "done": []}
    return json.loads(p.read_text(encoding="utf-8"))


def _save(key: str, state: dict) -> None:
    p = _path(key)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _add_stretch(cur: dict, now: datetime) -> None:
    if cur.get("paused"):
        return
    seconds = (now - datetime.fromisoformat(cur["resumedAt"])).total_seconds()
    if seconds > CAP_SECONDS:
        seconds = CAP_SECONDS
        cur["capped"] = True
    cur["activeSeconds"] = cur.get("activeSeconds", 0) + max(0, seconds)


def _finish(state: dict, now: datetime) -> dict | None:
    cur = state.get("current")
    if not cur:
        return None
    _add_stretch(cur, now)
    units = max(1, math.ceil(cur["activeSeconds"] / UNIT_SECONDS))
    item = {
        "id": len(state["done"]) + 1,
        "label": cur["label"],
        "workDate": cur["startedAt"][:10],
        "hours": units * 0.5,
        "minutes": round(cur["activeSeconds"] / 60),
        "capped": bool(cur.get("capped")),
        "startedAt": cur["startedAt"],
        "endedAt": now.isoformat(timespec="seconds"),
        "content": "",
        "sent": False,
        "written": False,
    }
    state["done"].append(item)
    state["current"] = None
    return item


def main(argv: list[str]) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            pass
    if len(argv) < 3:
        print(__doc__)
        return 2
    cmd, key = argv[1], argv[2]
    state = _load(key)
    now = _now()
    cur = state.get("current")

    if cmd == "start":
        if len(argv) < 4 or not argv[3].strip():
            print("[ERROR] まとまりの名前を渡してください（例: 調査）", file=sys.stderr)
            return 2
        finished = _finish(state, now)
        stamp = now.isoformat(timespec="seconds")
        state["current"] = {"label": argv[3].strip(), "startedAt": stamp, "resumedAt": stamp,
                            "activeSeconds": 0, "paused": False, "capped": False}
        _save(key, state)
        print(json.dumps({"started": argv[3].strip(), "finished": finished}, ensure_ascii=False))
    elif cmd == "pause":
        if cur and not cur.get("paused"):
            _add_stretch(cur, now)
            cur["paused"] = True
            _save(key, state)
        print(json.dumps({"paused": bool(cur)}, ensure_ascii=False))
    elif cmd == "resume":
        if cur and cur.get("paused"):
            cur["paused"] = False
            cur["resumedAt"] = now.isoformat(timespec="seconds")
            _save(key, state)
        print(json.dumps({"resumed": bool(cur)}, ensure_ascii=False))
    elif cmd == "stop":
        finished = _finish(state, now)
        _save(key, state)
        print(json.dumps({"finished": finished}, ensure_ascii=False))
    elif cmd == "note":
        if len(argv) < 5:
            print("[ERROR] id と内容を渡してください", file=sys.stderr)
            return 2
        found = [d for d in state["done"] if d["id"] == int(argv[3])]
        if not found:
            print(f"[ERROR] まとまりがありません: {argv[3]}", file=sys.stderr)
            return 2
        found[0]["content"] = argv[4].strip()
        _save(key, state)
        print(json.dumps({"noted": found[0]["id"]}, ensure_ascii=False))
    elif cmd in ("pending", "mark-sent"):
        rest = argv[3:]
        target = "portal"
        for flag in ("--for", "--to"):
            if flag in rest:
                i = rest.index(flag)
                target = rest[i + 1]
                del rest[i:i + 2]
        if target not in ("portal", "cases"):
            print(f"[ERROR] portal か cases を渡してください: {target}", file=sys.stderr)
            return 2
        flag_key = "sent" if target == "portal" else "written"
        if cmd == "pending":
            print(json.dumps({"current": cur["label"] if cur else None, "for": target,
                              "pending": [d for d in state["done"] if not d.get(flag_key)]}, ensure_ascii=False))
        else:
            ids = {int(x) for x in rest}
            for d in state["done"]:
                if d["id"] in ids:
                    d[flag_key] = True
            _save(key, state)
            print(json.dumps({"marked": sorted(ids), "to": target}, ensure_ascii=False))
    else:
        print(f"[ERROR] 知らない操作です: {cmd}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
