"""組織の地図（sf-lineage）の入口。プロジェクトのルートで動かす。

  python scripts/python/sf-lineage/lineage.py build                 # 地図を作る（force-app/main/default → .lineage/）
  python scripts/python/sf-lineage/lineage.py status                # 地図の作成日時と、force-app より古いか
  python scripts/python/sf-lineage/lineage.py who <対象...> [--value 値] [--depth 3] [--all] [--json]
  python scripts/python/sf-lineage/lineage.py save <オブジェクト> [--depth 3]
  python scripts/python/sf-lineage/lineage.py label <表示ラベルの一部>
  python scripts/python/sf-lineage/lineage.py export --repo <識別子> --name-ja <日本語名> [--json 書き出し先]
                                                                    # 項目リネージの共通基盤（Neo4j で見る用）に渡す中間JSON

who・save・label・export は、地図が無いか force-app より古いときに自動で作り直してから引く。
対象の書き方: Obj__c.Field__c ／ LWC:名前 ／ QuickAction:Obj.名前 ／ EmailTemplate:フォルダ/名前 ／ EmailAlert:Obj.名前 ／ Label:名前 ／ クラス名 ／ フロー名 ／ オブジェクト名
共通の引数: --root <プロジェクトのルート>（既定は今のフォルダ）・--out <地図のフォルダ>（既定は <root>/.lineage）
"""
from __future__ import annotations

import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)


def newest_mtime(path: str) -> float:
    latest = 0.0
    for dirpath, _, files in os.walk(path):
        for fn in files:
            try:
                t = os.path.getmtime(os.path.join(dirpath, fn))
            except OSError:
                continue
            if t > latest:
                latest = t
    return latest


def read_meta(out: str) -> dict:
    p = os.path.join(out, "meta.json")
    if not os.path.exists(p):
        return {}
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def build(root: str, out: str) -> None:
    src = os.path.join(root, "force-app", "main", "default")
    if not os.path.isdir(src):
        sys.exit(f"force-app/main/default が見つかりません: {src}（/sf-retrieve でメタデータを取得してから作ってください）")
    import build_refs
    t0 = time.time()
    latest = newest_mtime(src)
    argv = sys.argv
    sys.argv = ["build_refs.py", src, out]
    try:
        build_refs.main()
    finally:
        sys.argv = argv
    meta = {"built_at": time.strftime("%Y-%m-%d %H:%M:%S"), "built_epoch": time.time(),
            "force_app_latest": latest, "seconds": round(time.time() - t0, 1)}
    with open(os.path.join(out, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(meta, f, ensure_ascii=False)
    print(f"地図を作りました（{meta['seconds']} 秒・{out}）")


def ensure(root: str, out: str) -> None:
    meta = read_meta(out)
    src = os.path.join(root, "force-app", "main", "default")
    if not meta or not os.path.exists(os.path.join(out, "refs.jsonl")):
        print("地図が無いので作ります")
        build(root, out)
        return
    if os.path.isdir(src) and newest_mtime(src) > meta.get("force_app_latest", 0) + 1:
        print(f"force-app が地図（{meta.get('built_at')}）より新しいので作り直します")
        build(root, out)


def main() -> None:
    args = sys.argv[1:]
    root, out = os.getcwd(), None
    if "--root" in args:
        i = args.index("--root"); root = os.path.abspath(args[i + 1]); del args[i:i + 2]
    if "--out" in args:
        i = args.index("--out"); out = os.path.abspath(args[i + 1]); del args[i:i + 2]
    out = out or os.path.join(root, ".lineage")
    if not args:
        print(__doc__)
        return
    cmd, rest = args[0], args[1:]
    if cmd == "build":
        build(root, out)
    elif cmd == "status":
        meta = read_meta(out)
        if not meta:
            print("地図はまだありません（lineage.py build で作る）")
            return
        src = os.path.join(root, "force-app", "main", "default")
        stale = os.path.isdir(src) and newest_mtime(src) > meta.get("force_app_latest", 0) + 1
        print(f"地図の作成: {meta.get('built_at')}（{meta.get('seconds')} 秒）／ force-app より{'古い（作り直しが要る）' if stale else '新しい'}")
    elif cmd in ("who", "label"):
        ensure(root, out)
        import who_uses
        argv = sys.argv
        sys.argv = ["who_uses.py", out] + (["--label"] if cmd == "label" else []) + rest
        try:
            who_uses.main()
        finally:
            sys.argv = argv
        meta = read_meta(out)
        print(f"（地図の作成: {meta.get('built_at')}。地図は候補。判断・記載の前にソースで確かめる）")
    elif cmd == "save":
        ensure(root, out)
        import save_chain
        argv = sys.argv
        sys.argv = ["save_chain.py", out, out] + rest
        try:
            save_chain.main()
        finally:
            sys.argv = argv
    elif cmd == "export":
        # 項目リネージの共通基盤（DDD-Ontology の lineage-core）に渡す中間JSONを書き出す
        if "--repo" not in rest or "--name-ja" not in rest:
            sys.exit("使い方: lineage.py export --repo <システムの識別子> --name-ja <システムの日本語名> [--json <書き出し先>]")
        ensure(root, out)
        repo = rest[rest.index("--repo") + 1]
        dest = os.path.join(out, f"intermediate-{repo}.json")
        if "--json" in rest:
            i = rest.index("--json"); dest = os.path.abspath(rest[i + 1]); del rest[i:i + 2]
        import to_intermediate
        argv = sys.argv
        sys.argv = ["to_intermediate.py", "--root", root, "--map", out, "--out", dest] + rest
        try:
            to_intermediate.main()
        finally:
            sys.argv = argv
    else:
        print(__doc__)
        sys.exit(f"知らないコマンドです: {cmd}")


if __name__ == "__main__":
    main()
