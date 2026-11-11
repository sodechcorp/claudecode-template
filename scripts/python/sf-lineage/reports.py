"""レポートとダッシュボードの本体を組織から読み取りで取り、地図に入れる（組織は変えない・案件の force-app にも書かない）。

  python reports.py <地図のフォルダ> --target-org <別名>

- レポートは利用者が本番で作ることが多いので、ふつうは本番を指定する
- 取り先: <地図のフォルダ>/extra/_proj/retrieved/（reports/<フォルダ>/<名前>.report-meta.xml・dashboards/…）。
  取り込み用の仮のプロジェクト <地図のフォルダ>/extra/_proj から取るので、案件のフォルダには何も書かない
- 管理パッケージのもの（namespacePrefix の付く installed）は取らない
- 取ったあとは地図を作り直す（lineage.py reports が続けて行う）
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor
from xml.sax.saxutils import escape

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from modified import sf_json  # noqa: E402

API = "62.0"


def list_type(alias: str, mt: str, folder: str | None = None) -> list[dict]:
    args = ["org", "list", "metadata", "--metadata-type", mt, "--target-org", alias] + (["--folder", folder] if folder else [])
    d = sf_json(args)
    r = d.get("result") or []
    r = r if isinstance(r, list) else [r]
    return [x for x in r if not (x.get("namespacePrefix") and x.get("manageableState") == "installed")]


def fetch(mapdir: str, alias: str) -> None:
    extra = os.path.join(mapdir, "extra")
    proj = os.path.join(extra, "_proj")
    src = os.path.join(proj, "retrieved")   # sf の決まりで、取り先はプロジェクトの中（パッケージのフォルダの外）
    members: dict[str, list[str]] = {"ReportFolder": [], "Report": [], "DashboardFolder": [], "Dashboard": []}
    for kind in ("Report", "Dashboard"):
        folders = [x["fullName"] for x in list_type(alias, f"{kind}Folder")]
        members[f"{kind}Folder"] = folders
        if kind == "Report":
            folders = folders + ["unfiled$public"]   # 「非公開でないフォルダに入れていない」レポート
        with ThreadPoolExecutor(max_workers=6) as ex:
            for rows in ex.map(lambda f: list_type(alias, kind, f), folders):
                members[kind] += [x["fullName"] for x in rows]
    n_rep, n_dash = len(members["Report"]), len(members["Dashboard"])
    if not n_rep and not n_dash:
        print("レポート・ダッシュボードが見つかりませんでした")
        return
    os.makedirs(proj, exist_ok=True)
    with open(os.path.join(proj, "sfdx-project.json"), "w", encoding="utf-8") as f:
        json.dump({"packageDirectories": [{"path": "force-app", "default": True}], "sourceApiVersion": API}, f)
    os.makedirs(os.path.join(proj, "force-app"), exist_ok=True)
    pkg = os.path.join(extra, "package.xml")
    with open(pkg, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n<Package xmlns="http://soap.sforce.com/2006/04/metadata">\n')
        for t, ms in members.items():
            if ms:
                f.write("    <types>\n" + "".join(f"        <members>{escape(m)}</members>\n" for m in sorted(set(ms)))
                        + f"        <name>{t}</name>\n    </types>\n")
        f.write(f"    <version>{API}</version>\n</Package>\n")
    if os.path.isdir(src):
        shutil.rmtree(src)   # 前に取ったもの（地図のフォルダの中だけ）
    cwd = os.getcwd()
    try:
        os.chdir(proj)
        d = sf_json(["project", "retrieve", "start", "--manifest", pkg, "--target-org", alias, "--output-dir", src, "--wait", "30"], timeout=1800)
    finally:
        os.chdir(cwd)
    if d.get("status") not in (0, None):
        raise SystemExit(f"取れませんでした: {str(d.get('message'))[:300]}")
    got = sum(len(fs) for _, _, fs in os.walk(src)) if os.path.isdir(src) else 0
    print(f"レポート {n_rep} 件・ダッシュボード {n_dash} 件を {alias} から取った（ファイル {got} 個 → {src}）")


def main() -> None:
    args = sys.argv[1:]
    if len(args) < 3 or "--target-org" not in args:
        print(__doc__)
        sys.exit(1)
    fetch(args[0], args[args.index("--target-org") + 1])


if __name__ == "__main__":
    main()
