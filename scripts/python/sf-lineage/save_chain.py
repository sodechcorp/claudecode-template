"""保存時の暗黙の連鎖（試作の段階3）: 「このオブジェクトのレコードを保存すると、何が動き、どこへ波及するか」を地図から出す。

Salesforce の実行順序（Apex 開発者ガイド「Triggers and Order of Execution」）のうち、静的に分かるものを「起こり得る」連鎖として出す:
- 保存で動くもの: 入力規則（有効なものはすべて再評価）・before/after のトリガー・レコードトリガーフロー・ワークフロールール・重複ルール
- ワークフローの項目自動更新 → 同じレコードの update のトリガーがもう1回動く（ワークフローのルールから呼ばれるものだけ。承認プロセスから呼ばれるものは保存では動かないので、別に出す）
- 積み上げ集計・他オブジェクトを更新するワークフロー → 親のレコードの保存（親でも同じことが起きる）
- フロー・Apex の作成・更新・削除 → 書き込んだオブジェクトの保存
使い方: python save_chain.py <参照の層の出力フォルダ> <Apex の段階2の出力フォルダ> Obj__c [--depth 3]
"""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict

ON_SAVE_TYPES = ("ApexTrigger", "Flow", "WorkflowRule", "ValidationRule", "DuplicateRule", "AssignmentRule")
APPROVAL_FU: dict[str, set] = defaultdict(set)   # obj -> {(項目自動更新, 承認プロセス)}（保存では動かない）


def load(paths):
    refs = []
    for p in paths:
        if os.path.exists(p):
            refs += [json.loads(l) for l in open(p, encoding="utf-8")]
    return refs


def build(refs, fields):
    on_save = defaultdict(set)      # obj -> {(種類, 名前)}
    writes_obj = defaultdict(set)   # (種類, 名前) -> {書き込むオブジェクト}
    # 項目自動更新は、ワークフローのルールから呼ばれるものだけが保存で動く。承認プロセスから呼ばれるものは、申請・承認・却下・取り下げのときに動く
    fu_by_rule = {r["target"].split(":", 1)[1] for r in refs
                  if r["src_type"] == "WorkflowRule" and r["role"] == "call" and r["target"].startswith("WorkflowFieldUpdate:")}
    for r in refs:
        if r["src_type"] == "ApprovalProcess" and r["role"] == "call" and r["target"].startswith("WorkflowFieldUpdate:"):
            fu = r["target"].split(":", 1)[1]
            APPROVAL_FU[fu.split(".", 1)[0]].add((fu, r["src_name"]))
    for r in refs:
        st, sn = r["src_type"], r["src_name"]
        if r["tkind"] == "object" and r["role"] == "trigger_on" and st in ON_SAVE_TYPES:
            label = sn
            if st == "Flow" and r.get("via"):
                ttype, rtype, order = (r["via"].split("|") + ["", "", ""])[:3]
                phase = {"RecordBeforeSave": "保存前", "RecordAfterSave": "保存後", "RecordBeforeDelete": "削除前"}.get(ttype, ttype)
                label = f"{sn}〔{phase}{'・' + rtype if rtype else ''}{'・順番' + order if order else ''}〕"
            on_save[r["target"]].add((st, label))
        if st == "ValidationRule":
            on_save[sn.split(".", 1)[0]].add((st, sn))
        if st == "DuplicateRule":
            on_save[sn.split(".", 1)[0]].add((st, sn))
        if (r["tkind"] == "object" and (r["role"] == "write" or r["role"].startswith("dml_"))
                and st in ("Flow", "ApexClass", "ApexTrigger")):
            writes_obj[(st, sn)].add(r["target"])
        if st == "WorkflowFieldUpdate" and r["role"] == "write" and r["tkind"] == "field":
            writes_obj[(st, sn)].add(r["target"].split(".", 1)[0])
            if sn in fu_by_rule:
                on_save[sn.split(".", 1)[0]].add((st, sn))
    # 積み上げ集計: 子の保存 → 親の保存
    rollup_parent = defaultdict(set)  # 子 -> {(親, 集計項目)}
    for obj, fs in fields.items():
        for f, info in fs.items():
            if info.get("summaryOperation"):
                pass
    for r in refs:
        if r["src_type"] == "CustomField" and r["role"] == "summary":
            parent = r["src_name"].split(".", 1)[0]
            child = r["target"].split(".", 1)[0]
            if child != parent:
                rollup_parent[child].add((parent, r["src_name"]))
    return on_save, writes_obj, rollup_parent


def chain(obj, on_save, writes_obj, rollup_parent, depth, seen=None, indent=""):
    seen = seen or set()
    lines = []
    if obj in seen or depth < 0:
        return lines
    seen.add(obj)
    autos = sorted(on_save.get(obj, set()))
    lines.append(f"{indent}■ {obj} を保存すると動くもの（{len(autos)}）")
    groups = defaultdict(list)
    for st, sn in autos:
        groups[st].append(sn)
    for st in ON_SAVE_TYPES + ("WorkflowFieldUpdate",):
        if groups.get(st):
            lines.append(f"{indent}  - {st}: " + ", ".join(sorted(set(groups[st]))))
    if groups.get("WorkflowFieldUpdate"):
        lines.append(f"{indent}  ※ ワークフローの項目自動更新があるので、update のトリガーがもう1回動く（公式の実行順序）")
    if APPROVAL_FU.get(obj):
        lines.append(f"{indent}  ※ 保存では動かないが、承認プロセスの申請・承認・却下・取り下げで動く項目自動更新: "
                     + ", ".join(sorted(f"{fu}〔{ap}〕" for fu, ap in APPROVAL_FU[obj])))
    nexts = set()
    for st, sn in autos:
        for o2 in writes_obj.get((st, sn), set()):
            if o2 != obj:
                nexts.add((o2, f"{st}:{sn} が書き込む"))
    for parent, fld in rollup_parent.get(obj, set()):
        nexts.add((parent, f"積み上げ集計 {fld}"))
    for o2, why in sorted(nexts):
        lines.append(f"{indent}  → {o2}（{why}）")
        lines += chain(o2, on_save, writes_obj, rollup_parent, depth - 1, seen, indent + "    ")
    return lines


def main() -> None:
    args = sys.argv[1:]
    depth = 3
    if "--depth" in args:
        i = args.index("--depth")
        depth = int(args[i + 1])
        del args[i:i + 2]
    out1, out2, obj = args[0], args[1], args[2]
    refs = load([os.path.join(out1, "refs.jsonl"), os.path.join(out2, "refs_apex.jsonl")])
    fields = json.load(open(os.path.join(out1, "fields.json"), encoding="utf-8"))
    on_save, writes_obj, rollup_parent = build(refs, fields)
    print("\n".join(chain(obj, on_save, writes_obj, rollup_parent, depth)))


if __name__ == "__main__":
    main()
