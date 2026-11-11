"""地図から「この項目（・選択肢・部品）を使っているのは誰か」を引く。試作 v2（2026-11-11）。

辿るもの:
- 1段目: 直接の参照
- 2段目以降（--depth、既定 3）:
  - 数式項目・積み上げ集計が作る項目を使う部品
  - フロー・Apex が値を写した先の項目（copy_to）を使う部品
  - 部品の呼び出しの連鎖（画面部品 → それを埋め込むフロー・ページ → それを呼ぶアクション → それを置くレイアウト、
    メールテンプレート → アラート → それを呼ぶルール・フロー など）
出力は「処理」「画面・帳票」「権限・レコードタイプなど」に分ける。画面・帳票と権限は件数と先頭だけ（--all で全部）。
使い方:
  python who_uses.py <地図のフォルダ> Obj__c.Field__c [LWC:request] [QuickAction:Obj.Name] [ClassName] ... [--value 値] [--depth 2] [--all] [--json]
  python who_uses.py <地図のフォルダ> --label 金額
"""
from __future__ import annotations

import json
import os
import sys
from collections import defaultdict

LOGIC = {"Flow", "ApexClass", "ApexTrigger", "WorkflowRule", "WorkflowFieldUpdate", "WorkflowAlert", "ValidationRule",
         "CustomField", "ApprovalProcess", "AssignmentRule", "AutoResponseRule", "EscalationRule", "DuplicateRule",
         "MatchingRule", "QuickAction", "LeadConvertSetting", "LWC", "Aura", "Visualforce", "CustomMetadata"}
DISPLAY = {"Layout", "FlexiPage", "ListView", "CompactLayout", "FieldSet", "PathAssistant", "ReportType", "Report",
           "EmailTemplate", "FieldTranslation"}
# 参照元の部品 → それを呼ぶ側から見た名前（target）
def component_key(st: str, sn: str) -> list[str]:
    return {
        "Flow": [sn], "ApexClass": [sn], "LWC": [f"LWC:{sn}"], "Aura": [f"LWC:{sn}"],
        "QuickAction": [f"QuickAction:{sn}"], "WorkflowAlert": [f"EmailAlert:{sn}"],
        "WorkflowFieldUpdate": [f"WorkflowFieldUpdate:{sn}"], "EmailTemplate": [f"EmailTemplate:{sn}"],
        "Visualforce": [f"VF:{sn}"], "Layout": [f"LayoutsOf:{sn.split('-', 1)[0]}"],
    }.get(st, [])


# 当たったら、その呼び出し元（画面・フロー・アクションなどの入口）まで辿る部品
FOLLOW_CALLERS = {"ApexClass", "Flow", "LWC", "Aura", "QuickAction", "WorkflowAlert", "EmailTemplate", "Visualforce", "Layout"}


WIDE_ROLES = {"read_all", "read_dynamic", "write_dynamic"}   # 全項目・どの項目か不明の読み書き
_FIELDS: dict = {}


def load(out: str):
    refs = [json.loads(l) for l in open(os.path.join(out, "refs.jsonl"), encoding="utf-8")]
    fields = json.load(open(os.path.join(out, "fields.json"), encoding="utf-8"))
    _FIELDS.clear()
    _FIELDS.update({o.lower(): {f.lower(): i for f, i in fs.items()} for o, fs in fields.items()})
    by_target = defaultdict(list)
    copies = defaultdict(list)
    for r in refs:
        by_target[r["target"].lower()].append(r)
        if r["role"] == "copy_to" and r.get("via") and r["src_type"] != "ApexTest":   # テストデータの作成は連鎖にしない
            copies[r["via"].lower()].append(r)
    return refs, fields, by_target, copies


def stored_field(target: str) -> bool:
    """保存値を持つ項目か（数式・積み上げ集計は複製・動的な書き込みの対象にならない）。"""
    o, f = target.lower().split(".", 1)
    info = _FIELDS.get(o, {}).get(f)
    return not (info and (info.get("formula") or info.get("summaryOperation")))


def users_of(by_target, target: str, value: str | None = None):
    hits = list(by_target.get(target.lower(), []))
    if "." in target and ":" not in target and "=" not in target and stored_field(target):
        # 項目なら、そのオブジェクトの「全項目を読む」「項目名を変数で読み書きする」部品も出す
        obj = target.split(".", 1)[0].lower()
        hits += [h for h in by_target.get(obj, []) if h["role"] in WIDE_ROLES]
    pre = (target + "=").lower()
    if value is not None:
        hits += by_target.get(pre + value.lower(), [])
    else:
        for k, v in by_target.items():
            if k.startswith(pre):
                hits += v
    return [h for h in hits if h["role"] != "copy_to"]


def expand(by_target, copies, targets: list[str], value: str | None, depth: int):
    rows = []          # (段, 経由, 参照)
    seen_t = set()
    frontier = [(t, "") for t in targets]
    for level in range(1, depth + 1):
        nxt = []
        for t, via in frontier:
            if t.lower() in seen_t:
                continue
            seen_t.add(t.lower())
            for r in users_of(by_target, t, value if level == 1 else None):
                rows.append((level, via or "", r))
                if r["src_type"] == "CustomField" and r["role"] in ("formula", "summary"):
                    nxt.append((r["src_name"], f"{r['src_name']}（数式・積み上げ）"))
                if r["src_type"] in FOLLOW_CALLERS and r["conf"] != "low" and r["src_type"] != "ApexTest":
                    # 部品（項目を読み書きするクラス・フロー、画面部品、アクション、レイアウトなど）の呼び出し元・表示先も辿る
                    for k in component_key(r["src_type"], r["src_name"]):
                        nxt.append((k, f"{r['src_type']}:{r['src_name']}（を呼ぶ・表示する）"))
            for c in copies.get(t.lower(), []):
                rows.append((level, via or "", dict(c, role=f"copy_to（{t} から写す）")))
                nxt.append((c["target"], f"{c['target']}（{c['src_type']}:{c['src_name']} が {t} から写す）"))
        frontier = nxt
        if not frontier:
            break
    return rows


def show(rows, show_all: bool, targets: list[str] | None = None):
    g = defaultdict(lambda: defaultdict(lambda: {"roles": set(), "level": 9, "via": ""}))
    for level, via, r in rows:
        e = g[r["src_type"]][r["src_name"]]
        e["roles"].add(r["role"] + ("" if r["conf"] == "high" else f"({r['conf']})"))
        if level < e["level"]:
            e["level"], e["via"] = level, via
    def is_wide(e):
        return all(r.split("(")[0] in WIDE_ROLES for r in e["roles"])

    def is_low(e):
        return all(r.endswith("(low)") for r in e["roles"])

    def section(title, pick, full=False):
        items = []
        for st in g:
            names = {n: e for n, e in g[st].items() if pick(st, e)}
            if names:
                items.append((st, names))
        n = sum(len(v) for _, v in items)
        print(f"## {title}（{n}）")
        for st, names in sorted(items, key=lambda kv: -len(kv[1])):
            print(f"- {st}（{len(names)}）")
            lst = sorted(names.items(), key=lambda kv: (kv[1]["level"], kv[0]))
            limit = None if (show_all or full) else 8
            for name, e in lst[:limit]:
                via = f" ← {e['via']}" if e["via"] else ""
                print(f"    [{e['level']}段] {name}: {', '.join(sorted(e['roles']))}{via}")
            if limit is not None and len(lst) > limit:
                print(f"    … ほか {len(lst) - limit}（--all で全部）")
    tset = {t.lower() for t in (targets or [])}
    writers = sorted({f"{r['src_type']}:{r['src_name']}" for lv, _, r in rows
                      if lv == 1 and r["target"].lower() in tset and r["src_type"] != "ApexTest"
                      and (r["role"] == "write" or r["role"].startswith("dml_"))})
    if writers:
        print(f"## この対象に書き込む部品（{len(writers)}）: " + ", ".join(writers[:15]) + (" …" if len(writers) > 15 else ""))
    section("処理（フロー・Apex・トリガー・ワークフロー・入力規則・数式・画面部品など。2段目まで）",
            lambda st, e: st in LOGIC and not is_wide(e) and not is_low(e) and e["level"] <= 2, full=True)
    section("処理の3段目以降", lambda st, e: st in LOGIC and not is_wide(e) and not is_low(e) and e["level"] >= 3)
    section("全項目・どの項目か不明の読み書きをする部品（全項目の複製・項目名を変数で渡す処理）",
            lambda st, e: st in LOGIC and is_wide(e))
    section("画面・帳票（レイアウト・ページ・リストビュー・レポートタイプ・メールなど）",
            lambda st, e: st in DISPLAY and not is_low(e))
    section("権限・レコードタイプなど", lambda st, e: st not in LOGIC and st not in DISPLAY and st != "ApexTest" and not is_low(e))
    section("確度が低い候補（同名の項目の出現など。確かめてから使う）", lambda st, e: st != "ApexTest" and is_low(e) and not is_wide(e))
    section("テストクラス", lambda st, e: st == "ApexTest")


def main() -> None:
    args = sys.argv[1:]
    out = args.pop(0)
    refs, fields, by_target, copies = load(out)
    if args and args[0] == "--label":
        q = args[1]
        olabels = {}
        p = os.path.join(out, "objects.json")
        if os.path.exists(p):
            olabels = json.load(open(p, encoding="utf-8"))
        for o, lab in olabels.items():
            if lab and q in lab:
                print(f"{o}\t（オブジェクト）{lab}")
        for o, fs in fields.items():
            for f, info in fs.items():
                if info.get("label") and q in info["label"]:
                    print(f"{o}.{f}\t{olabels.get(o) or o} の {info['label']}\t{info.get('type')}")
        return
    value, depth = None, 3
    show_all = "--all" in args
    as_json = "--json" in args
    if "--value" in args:
        i = args.index("--value"); value = args[i + 1]; del args[i:i + 2]
    if "--depth" in args:
        i = args.index("--depth"); depth = int(args[i + 1]); del args[i:i + 2]
    targets = [a for a in args if not a.startswith("--")]
    rows = expand(by_target, copies, targets, value, depth)
    if as_json:
        print(json.dumps([{"level": l, "via": v, **r} for l, v, r in rows], ensure_ascii=False))
        return
    show(rows, show_all, targets)


if __name__ == "__main__":
    main()
