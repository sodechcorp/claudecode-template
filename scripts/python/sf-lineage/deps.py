"""順方向の依存: その部品が「使っているもの」と、リリースの資材（package.xml）の外にある依存の確かめ。

  python deps.py <地図のフォルダ> <force-app/main/default> uses <部品...>
  python deps.py <地図のフォルダ> <force-app/main/default> deps --manifest <package.xml>

部品の書き方: クラス名 ／ フロー名 ／ LWC:名前 ／ Aura:名前 ／ VF:名前 ／ QuickAction:Obj.名前 ／ Obj__c.Field__c（数式・積み上げ）／
             ValidationRule:Obj.名前 ／ Layout:Obj-名前 ／ FlexiPage:名前 ／ PermissionSet:名前 ／ <地図の種類>:<名前>
deps は、資材の部品が使うカスタムの部品（項目・オブジェクト・クラス・フロー・LWC・ラベルなど）のうち資材に入っていないものを出し、
lineage.py modified で本番の一覧を取ってあれば「本番にある／無い」も出す（本番に無く資材にも無い＝デプロイが失敗する候補）。
"""
from __future__ import annotations

import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from collections import defaultdict

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from modified import load_all  # noqa: E402

NS = "{http://soap.sforce.com/2006/04/metadata}"
# 資材の種類 → 地図の種類
MANIFEST_TO_MAP = {"ApexClass": "ApexClass", "ApexTrigger": "ApexTrigger", "ApexPage": "Visualforce", "LightningComponentBundle": "LWC",
                   "AuraDefinitionBundle": "Aura", "Flow": "Flow", "CustomField": "CustomField", "ValidationRule": "ValidationRule",
                   "QuickAction": "QuickAction", "Layout": "Layout", "FlexiPage": "FlexiPage", "PermissionSet": "PermissionSet",
                   "Profile": "Profile", "WorkflowRule": "WorkflowRule", "WorkflowFieldUpdate": "WorkflowFieldUpdate",
                   "WorkflowAlert": "WorkflowAlert", "ApprovalProcess": "ApprovalProcess", "ReportType": "ReportType",
                   "ListView": "ListView", "CompactLayout": "CompactLayout", "FieldSet": "FieldSet", "PathAssistant": "PathAssistant",
                   "DuplicateRule": "DuplicateRule", "RecordType": "RecordType", "EmailTemplate": "EmailTemplate"}
# 地図の種類 → modified の一覧のキーの種類（本番にあるかを見る）
EXIST_KEY = {"CustomField": "CustomField", "CustomObject": "CustomObject", "ApexClass": "ApexClass", "Flow": "Flow",
             "LightningComponentBundle": "LWC", "AuraDefinitionBundle": "Aura", "ApexPage": "Visualforce", "QuickAction": "QuickAction",
             "WorkflowAlert": "WorkflowAlert", "WorkflowFieldUpdate": "WorkflowFieldUpdate", "ReportType": "ReportType", "CustomLabel": "Label"}
SYSTEM_CLASSES = {"System", "Database", "Schema", "String", "Math", "Date", "Datetime", "JSON", "Test", "Limits", "UserInfo",
                  "Messaging", "Http", "HttpRequest", "EventBus", "Approval", "Site", "Auth", "Crypto", "EncodingUtil", "Url", "Type"}


def load_refs(mapdir: str) -> list[dict]:
    return [json.loads(l) for l in open(os.path.join(mapdir, "refs.jsonl"), encoding="utf-8")]


def resolve(spec: str, refs: list[dict]) -> set[tuple[str, str]]:
    """部品の書き方 → 地図の (種類, 名前)。"""
    alias = {"VF": "Visualforce"}
    if ":" in spec:
        st, name = spec.split(":", 1)
        st = alias.get(st, st)
        return {(r["src_type"], r["src_name"]) for r in refs if r["src_type"] == st and r["src_name"] == name}
    if "." in spec:
        return {(r["src_type"], r["src_name"]) for r in refs if r["src_type"] == "CustomField" and r["src_name"].lower() == spec.lower()}
    return {(r["src_type"], r["src_name"]) for r in refs if r["src_name"] == spec and r["src_type"] != "ApexTest"} or \
           {(r["src_type"], r["src_name"]) for r in refs if r["src_name"] == spec}


def as_dependency(r: dict, local_classes: set[str]) -> tuple[str, str] | None:
    """参照先 → デプロイの依存になる (資材の種類, 名前)。標準の項目・オブジェクト・システムのクラスは返さない。"""
    t, tk = r["target"], r["tkind"]
    if tk == "field" and "." in t and "=" not in t and not t.startswith("?"):
        o, f = t.split(".", 1)
        return ("CustomField", t) if f.endswith(("__c", "__r")) and "." not in f else None
    if tk == "object":
        return ("CustomObject", t) if t.endswith(("__c", "__mdt", "__e", "__b")) else None
    if tk == "class":
        return ("ApexClass", t) if t in local_classes and t not in SYSTEM_CLASSES else None
    if tk == "flow":
        return ("Flow", t)
    if tk == "component" and ":" in t:
        k, n = t.split(":", 1)
        return {"LWC": ("LightningComponentBundle", n), "VF": ("ApexPage", n), "QuickAction": ("QuickAction", n),
                "EmailAlert": ("WorkflowAlert", n), "Label": ("CustomLabel", n), "EmailTemplate": ("EmailTemplate", n),
                "WorkflowFieldUpdate": ("WorkflowFieldUpdate", n), "ReportType": ("ReportType", n)}.get(k)
    return None


def cmd_uses(mapdir: str, specs: list[str]) -> None:
    refs = load_refs(mapdir)
    for spec in specs:
        srcs = resolve(spec, refs)
        if not srcs:
            print(f"## {spec}: 地図に見つかりません（書き方: クラス名・フロー名・LWC:名前・Obj__c.Field__c など）")
            continue
        for st, sn in sorted(srcs):
            g = defaultdict(set)
            for r in refs:
                if (r["src_type"], r["src_name"]) != (st, sn) or r["conf"] == "low":
                    continue
                role, tk, t = r["role"], r["tkind"], r["target"]
                key = ("外への動き" if role in ("send_email", "callout", "async")
                       else "書き込む項目" if tk == "field" and (role == "write" or role.startswith("copy") or role == "write_dynamic")
                       else "条件に使う項目" if tk == "field" and role == "condition"
                       else "読む・表示する項目" if tk == "field"
                       else "書き込むオブジェクト" if tk == "object" and (role == "write" or role.startswith("dml_"))
                       else "保存で動く対象" if tk == "object" and role == "trigger_on"
                       else "読むオブジェクト" if tk == "object"
                       else "選択肢の値" if tk == "value"
                       else "表示ラベル" if t.startswith("Label:")
                       else "呼ぶ・埋め込む部品" if tk in ("class", "flow", "component")
                       else f"そのほか（{tk}）")
                g[key].add(t)
            print(f"## {st}:{sn} が使っているもの")
            for key in ("書き込む項目", "条件に使う項目", "読む・表示する項目", "書き込むオブジェクト", "読むオブジェクト", "保存で動く対象",
                        "呼ぶ・埋め込む部品", "表示ラベル", "選択肢の値", "外への動き"):
                if g.get(key):
                    vs = sorted(g.pop(key))
                    print(f"- {key}（{len(vs)}）: " + ", ".join(vs[:40]) + (" …" if len(vs) > 40 else ""))
            for key, vs in g.items():
                print(f"- {key}（{len(vs)}）: " + ", ".join(sorted(vs)[:20]))


def parse_manifest(path: str) -> dict[str, set[str]]:
    root = ET.parse(path).getroot()
    out: dict[str, set[str]] = defaultdict(set)
    for t in root.iter(NS + "types"):
        name = t.find(NS + "name").text.strip()
        for m in t.iter(NS + "members"):
            out[name].add(m.text.strip())
    return out


def exists_local(fa: str, mt: str, name: str) -> bool:
    o, f = (name.split(".", 1) + [""])[:2]
    paths = {"CustomField": f"objects/{o}/fields/{f}.field-meta.xml", "CustomObject": f"objects/{name}/{name}.object-meta.xml",
             "ApexClass": f"classes/{name}.cls", "Flow": f"flows/{name}.flow-meta.xml", "LightningComponentBundle": f"lwc/{name}",
             "ApexPage": f"pages/{name}.page", "QuickAction": f"quickActions/{name}.quickAction-meta.xml",
             "ReportType": f"reportTypes/{name}.reportType-meta.xml", "EmailTemplate": f"email/{name}.email"}
    if mt == "CustomLabel":
        p = os.path.join(fa, "labels", "CustomLabels.labels-meta.xml")
        return os.path.exists(p) and f"<fullName>{name}</fullName>" in open(p, encoding="utf-8", errors="ignore").read()
    if mt in ("WorkflowAlert", "WorkflowFieldUpdate"):
        p = os.path.join(fa, "workflows", f"{o}.workflow-meta.xml")
        return os.path.exists(p) and f"<fullName>{f}</fullName>" in open(p, encoding="utf-8", errors="ignore").read()
    p = paths.get(mt)
    return bool(p) and os.path.exists(os.path.join(fa, *p.split("/")))


def cmd_deps(mapdir: str, fa: str, manifest: str, show_all: bool = False) -> None:
    refs = load_refs(mapdir)
    man = parse_manifest(manifest)
    local_classes = {fn[:-4] for fn in os.listdir(os.path.join(fa, "classes"))} if os.path.isdir(os.path.join(fa, "classes")) else set()
    prod = next((d for d in load_all(mapdir) if not d.get("isSandbox")), None)
    in_man = {(t, m) for t, ms in man.items() for m in ms}
    wild = {t for t, ms in man.items() if "*" in ms}
    # 資材の部品（地図の種類, 名前）
    comps = set()
    for t, ms in man.items():
        st = MANIFEST_TO_MAP.get(t)
        for m in ms:
            if st and m != "*":
                comps.add((st, m))
    by_src = defaultdict(list)
    for r in refs:
        by_src[(r["src_type"], r["src_name"])].append(r)
    missing = defaultdict(set)   # (資材の種類, 名前) -> {使う部品}
    for c in comps:
        for r in by_src.get(c, []):
            if r["conf"] == "low":
                continue
            dep = as_dependency(r, local_classes)
            if not dep or dep in in_man or dep[0] in wild:
                continue
            if dep[0] == "CustomField" and ("CustomObject", dep[1].split(".", 1)[0]) in in_man:
                continue
            if dep == ("CustomField", c[1]) and c[0] == "CustomField":
                continue
            missing[dep].add(f"{c[0]}:{c[1]}")
    print(f"資材 {sum(len(v) for v in man.values())} 件のうち地図にある部品 {len([c for c in comps if c in by_src])} 件。資材の外にある依存 {len(missing)} 件"
          + ("" if prod else "（本番の一覧が無いので、本番にあるかは未判定。lineage.py modified --target-org <本番> で取ると判定できる）"))
    rows = []
    for (mt, name), users in missing.items():
        key = f"{EXIST_KEY.get(mt, mt)}:{name}"
        in_prod = None if prod is None or mt not in EXIST_KEY else (key in prod["items"])
        local = exists_local(fa, mt, name)
        level = ("✗ 本番に無く資材にも無い（入れないとデプロイが失敗する）" if in_prod is False and local
                 else "？ 本番にも手元にも無い（標準・管理パッケージ・名前の違いの可能性。確かめる）" if in_prod is False
                 else "○ 本番にある" if in_prod
                 else "－ 本番にあるか未判定")
        rows.append((level, mt, name, sorted(users)))
    order = {"✗": 0, "？": 1, "－": 2, "○": 3}
    ok = [r for r in rows if r[0].startswith("○")]
    for level, mt, name, users in sorted([r for r in rows if not r[0].startswith("○") or show_all], key=lambda r: (order[r[0][0]], r[1], r[2])):
        print(f"{level}  {mt}:{name}  ← {', '.join(users[:5])}{' …' if len(users) > 5 else ''}")
    if ok and not show_all:
        print(f"○ 本番にある依存 {len(ok)} 件（--all で一覧）")
    if not any(r[0].startswith("✗") for r in rows) and prod:
        print("✗（本番に無く資材にも無い依存）はありません")


def cmd_objects(mapdir: str, standard_only: bool) -> None:
    """Apex・トリガー・フロー・LWC・Aura・VF が読み書きするオブジェクトと、使っている部品（テストクラス・確度の低い候補は除く）。"""
    refs = load_refs(mapdir)
    c: dict[str, set[str]] = defaultdict(set)
    for r in refs:
        if r["src_type"] not in ("ApexClass", "ApexTrigger", "Flow", "LWC", "Aura", "Visualforce") or r["conf"] == "low":
            continue
        if r["tkind"] not in ("object", "field") or r["target"].startswith("?"):
            continue
        o = r["target"].split(".")[0]
        if standard_only and o.endswith(("__c", "__mdt", "__e", "__b", "__x")):
            continue
        c[o].add(f"{r['src_type']}:{r['src_name']}")
    print(f"{'標準' if standard_only else ''}オブジェクト {len(c)} 件（使っている部品の数・先頭3つ）")
    for o, s in sorted(c.items(), key=lambda kv: (-len(kv[1]), kv[0])):
        print(f"{o}\t{len(s)}\t{', '.join(sorted(s)[:3])}")


def main() -> None:
    args = sys.argv[1:]
    if len(args) < 3:
        print(__doc__)
        sys.exit(1)
    mapdir, fa, cmd = args[0], args[1], args[2]
    if cmd == "objects":
        cmd_objects(mapdir, "--standard" in args)
        return
    if cmd == "uses":
        cmd_uses(mapdir, [a for a in args[3:] if not a.startswith("--")])
    elif cmd == "deps":
        if "--manifest" not in args:
            sys.exit("使い方: deps --manifest <package.xml>")
        cmd_deps(mapdir, fa, args[args.index("--manifest") + 1], "--all" in args)
    else:
        print(__doc__)
        sys.exit(1)


if __name__ == "__main__":
    main()
