"""組織の地図（.lineage/）を、DDD-Ontology の共通基盤（lineage-core）が読む中間JSON（schemaVersion 1.0）に書き出す。
＝ Salesforce 用のアダプター（試作 2026-11-11）。

当てはめ:
- オブジェクト → 表（Table）、項目 → 項目（Column）。組織を1つのデータベース（dbId＝repoId）とみなす
- Apex クラス・トリガー・フロー・LWC・Aura・VF・アクション → プログラム＋メソッド（クラス・フロー単位）
- 数式項目・積み上げ集計・入力規則・ワークフローの項目自動更新 → それぞれ仮のメソッド（共通基盤の決まりで、演算には置き場所のメソッドが要る）
- 機能: 「<オブジェクト>の保存」（保存時に動くトリガー・レコードトリガーフロー・入力規則・ワークフロー・子の保存で計算し直す積み上げ集計）、
        画面フロー・LWC・Aura・VF・クイックアクション（画面。画面の置き場所と同じ識別子にする）、スケジュールのフロー・Schedulable/Batchable の Apex（バッチ）、@RestResource（API）
- 演算: 値を写す → 転記（Transfer）、値を設定（写し元が分からない）→ 計算（Calculation。式は代入の行）、数式項目 → 計算（式は数式のまま）、
        積み上げ集計 → 集計（Aggregation）、入力規則 → チェック（Validation）、
        LWC・VF・Apex・フローが読む項目 → 画面項目・IF項目への転記（どこで使われるかを項目単位で残すため）
- 条件: フロー・ワークフローの条件だけを書き込みの条件にする（Apex はクラス単位なので付けると関係の薄い連鎖になる）。Id・参照項目での絞り込みは外す
- テストクラス・Id への代入は書き出さない
- 動的 SOQL（全項目を読む）・項目名を変数で渡す put/get → 解析しきれなかった箇所（unresolved）
- 管理パッケージの部品は扱わない（名前空間付きで地図に定義の無いものは捨てる）
- 名前空間（ベース IRI）は共通基盤の設定（config.yaml の baseIri）で決まる。語彙・検証の規則が既定の名前空間で書かれているので、既定のまま使う
使い方（ふつうは lineage.py export から呼ぶ）:
  python to_intermediate.py --root <プロジェクトのルート> --map <地図のフォルダ> --repo <識別子> --name-ja <日本語名> --out <中間JSONのパス>
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from collections import defaultdict

NS = "{http://soap.sforce.com/2006/04/metadata}"
CONF = {"high": "High", "mid": "Medium", "low": "Low"}
FA = "force-app/main/default"
# 標準オブジェクトの既定の日本語ラベル（組織で名前を変えている場合は、メタデータの表示ラベルが優先される）
STD_LABELS = {
    "Account": "取引先", "Contact": "取引先責任者", "Lead": "リード", "Opportunity": "商談", "Case": "ケース",
    "User": "ユーザー", "Task": "ToDo", "Event": "行動", "Campaign": "キャンペーン", "Product2": "商品",
    "Pricebook2": "価格表", "PricebookEntry": "価格表エントリ", "OpportunityLineItem": "商談商品", "Quote": "見積",
    "Order": "注文", "Contract": "契約", "ContentVersion": "ファイル（バージョン）", "ContentDocument": "ファイル",
    "ContentDocumentLink": "ファイルのリンク", "Attachment": "添付ファイル", "EmailMessage": "メール",
    "FeedItem": "フィード", "FeedComment": "フィードコメント", "Group": "グループ", "GroupMember": "グループメンバー",
    "UserRole": "ロール", "Profile": "プロファイル", "RecordType": "レコードタイプ", "Asset": "納入商品",
}
# どのオブジェクトにもあるシステム項目の既定の日本語ラベル
STD_FIELD_LABELS = {
    "OwnerId": "所有者", "CreatedById": "作成者", "CreatedDate": "作成日", "LastModifiedById": "最終更新者",
    "LastModifiedDate": "最終更新日", "SystemModstamp": "System Modstamp", "RecordTypeId": "レコードタイプ",
    "IsDeleted": "削除", "CurrencyIsoCode": "通貨", "LastActivityDate": "最終活動日", "LastViewedDate": "最終閲覧日",
    "LastReferencedDate": "最終参照日", "ParentId": "親", "ContentDocumentId": "ファイル",
}


def txt(el, tag):
    if el is None:
        return None
    x = el.find(NS + tag)
    return x.text.strip() if x is not None and x.text else None


def parse(path):
    try:
        return ET.parse(path).getroot()
    except (ET.ParseError, OSError):
        return None


class Exporter:
    def __init__(self, root: str, mapdir: str, repo: str, name_ja: str) -> None:
        self.root = root
        self.fa = os.path.join(root, *FA.split("/"))
        self.repo = repo
        self.db = repo
        self.name_ja = name_ja
        self.refs = [json.loads(l) for l in open(os.path.join(mapdir, "refs.jsonl"), encoding="utf-8")]
        self.fields = json.load(open(os.path.join(mapdir, "fields.json"), encoding="utf-8"))
        self.olabels = json.load(open(os.path.join(mapdir, "objects.json"), encoding="utf-8"))
        self.objects = set(self.olabels) | set(self.fields)
        for o, lab in STD_LABELS.items():   # 標準オブジェクトはメタデータに表示ラベルが無いので、既定の日本語ラベルを使う
            if o in self.objects and not self.olabels.get(o):
                self.olabels[o] = lab
        self.programs: dict[str, dict] = {}
        self.functions: dict[str, dict] = {}
        self.features: dict[str, dict] = {}
        self.stores: dict[str, dict] = {}
        self.items: dict[str, dict] = {}
        self.access: dict[tuple, dict] = {}
        self.calls: dict[tuple, dict] = {}
        self.ops: list[dict] = []
        self.unresolved: list[dict] = []
        self.op_seq: dict[tuple, int] = defaultdict(int)
        self.text_cache: dict[str, list[str]] = {}
        self.canon: dict[str, dict[str, str]] = {}

    # ---------- 共通 ----------
    def rel(self, fa_rel: str) -> str:
        return f"{FA}/{fa_rel}"

    def line_text(self, fa_rel: str, line: int) -> str:
        p = os.path.join(self.fa, *fa_rel.split("/"))
        if p not in self.text_cache:
            try:
                self.text_cache[p] = open(p, encoding="utf-8", errors="ignore").read().splitlines()
            except OSError:
                self.text_cache[p] = []
        lines = self.text_cache[p]
        return lines[line - 1].strip()[:300] if 0 < line <= len(lines) else ""

    def show_code(self, st: str, sn: str, fa_rel: str, line: int) -> str:
        """演算のルール説明に出す1行。項目自動更新は設定する値、フローは XML のタグを外した形。"""
        if st == "WorkflowFieldUpdate":
            root = parse(os.path.join(self.fa, *fa_rel.split("/")))
            name = sn.split(".", 1)[1]
            for fu in (root.iter(NS + "fieldUpdates") if root is not None else []):
                if txt(fu, "fullName") == name:
                    op = txt(fu, "operation") or ""
                    val = txt(fu, "formula") if op == "Formula" else txt(fu, "literalValue") if op == "Literal" else op
                    return f"{txt(fu, 'name') or name}: {' '.join((val or '').split())[:200]}"
        code = self.line_text(fa_rel, line)
        m = re.match(r"^<(\w+)>(.*)</\1>$", code)
        return f"{m.group(1)}: {m.group(2)}" if m else code

    def op_key(self, fa_rel: str, line: int) -> str:
        k = (fa_rel, line)
        self.op_seq[k] += 1
        return f"operation:{self.rel(fa_rel)}:L{max(line, 1)}-{self.op_seq[k]}"

    def known_obj(self, obj: str) -> bool:
        return obj in self.objects

    def table(self, obj: str) -> str:
        k = f"table:{self.db}.{obj}"
        if k not in self.stores:
            lab = self.olabels.get(obj)
            s = {"key": k, "kind": "Table", "dbId": self.db, "physicalName": obj, "storeType": "SOBJECT"}
            if lab:
                s["labels"] = [{"text": lab, "source": "DdlComment"}]
            if os.path.exists(os.path.join(self.fa, "objects", obj, f"{obj}.object-meta.xml")):
                s["sourceFile"] = self.rel(f"objects/{obj}/{obj}.object-meta.xml")
            self.stores[k] = s
        return k

    def is_relation(self, key: str) -> bool:
        """項目のキーが参照・主従の項目（標準の参照項目 AccountId・OwnerId 等を含む）か。"""
        obj, fld = key.split(".", 2)[1:]
        t = self.fields.get(obj, {}).get(fld, {}).get("type")
        return t in ("Lookup", "MasterDetail", "Hierarchy") or (t is None and fld.endswith("Id") and fld != "Id")

    def std_field_label(self, obj: str, fld: str) -> dict | None:
        """メタデータに表示ラベルが無い標準項目の和名。名前項目はオブジェクトの定義（nameField）から、
        システム項目と標準オブジェクトへの参照（AccountId 等）は Salesforce の既定のラベル（名前の変更を反映）から。"""
        olab = self.olabels.get(obj) or obj
        if fld == "Name":
            om = parse(os.path.join(self.fa, "objects", obj, f"{obj}.object-meta.xml"))
            nf = om.find(NS + "nameField") if om is not None else None
            if txt(nf, "label"):
                return {"text": txt(nf, "label"), "source": "DdlComment"}
            return {"text": f"{olab}名", "source": "DataDictionary"}
        if fld == "Id":
            return {"text": f"{olab} ID", "source": "DataDictionary"}
        if fld in STD_FIELD_LABELS:
            return {"text": STD_FIELD_LABELS[fld], "source": "DataDictionary"}
        if fld.endswith("Id") and fld[:-2] in STD_LABELS:   # AccountId → 取引先（名前を変えていれば、変えた名前）
            return {"text": self.olabels.get(fld[:-2]) or STD_LABELS[fld[:-2]], "source": "DataDictionary"}
        return None

    def column(self, target: str) -> str | None:
        """`Obj.Field` → 項目のキー。オブジェクトが地図に無い（管理パッケージ・不明）ものは None。"""
        if "." not in target or target.startswith("?"):
            return None
        obj, fld = target.split(".", 1)
        if not self.known_obj(obj) or "." in fld or "=" in fld:
            return None
        if re.match(r"^[A-Za-z0-9]+__\w+__c$", fld) and fld not in self.fields.get(obj, {}):
            return None   # 管理パッケージの項目（定義が無い）は扱わない
        if fld.endswith("__r") and fld[:-1] + "c" in self.fields.get(obj, {}):
            fld = fld[:-1] + "c"   # 参照の辿り（Product__r）は、参照項目（Product__c）として扱う
        # Apex は大文字・小文字を区別しないので、同じ項目の書き方の揺れ（id / Id）を1つにまとめる
        canon = self.canon.setdefault(obj, {f.lower(): f for f in self.fields.get(obj, {})})
        low = fld.lower()
        if low in canon:
            fld = canon[low]
        else:
            fld = fld[:1].upper() + fld[1:]
            canon[low] = fld
        k = f"column:{self.db}.{obj}.{fld}"
        if k not in self.items:
            info = self.fields.get(obj, {}).get(fld, {})
            it = {"key": k, "kind": "Column", "storeKey": self.table(obj), "physicalName": fld}
            if info.get("type"):
                it["dataType"] = info["type"]
            if info.get("label"):
                it["labels"] = [{"text": info["label"], "source": "DdlComment"}]
            else:
                lab = self.std_field_label(obj, fld)
                if lab:
                    it["labels"] = [lab]
            if os.path.exists(os.path.join(self.fa, "objects", obj, "fields", f"{fld}.field-meta.xml")):
                it["sourceFile"] = self.rel(f"objects/{obj}/fields/{fld}.field-meta.xml")
            self.items[k] = it
        return k

    def program(self, fa_rel: str, language: str, label: str | None = None) -> str:
        k = f"program:{self.rel(fa_rel)}"
        if k not in self.programs:
            p = {"key": k, "language": language, "sourceFile": self.rel(fa_rel)}
            if label:
                p["labels"] = [{"text": label, "source": "ScreenLabel"}]
            self.programs[k] = p
        return k

    def function(self, kind: str, name: str, fa_rel: str, language: str, label: str | None = None) -> str:
        k = f"function:{kind}:{name}"
        if k not in self.functions:
            pk = self.program(fa_rel, language, label)
            f = {"key": k, "programKey": pk, "name": name, "sourceFile": self.rel(fa_rel), "lineStart": 1}
            if label:
                f["labels"] = [{"text": label, "source": "ScreenLabel"}]
            self.functions[k] = f
        return k

    def feature(self, kind: str, fid: str, entry: list[str], label: str | None, src: str | None = None, schedule: str | None = None):
        k = f"feature:{kind}:{fid}"
        kmap = {"screen": "Screen", "batch": "Batch", "api": "ApiEndpoint", "other": "OtherFeature"}
        f = self.features.setdefault(k, {"key": k, "kind": kmap[kind], "featureId": fid, "entryFunctionKeys": []})
        for e in entry:
            if e not in f["entryFunctionKeys"]:
                f["entryFunctionKeys"].append(e)
        if label and "labels" not in f:
            f["labels"] = [{"text": label, "source": "ScreenLabel"}]
        if src and "sourceFile" not in f:
            f["sourceFile"] = src
        if schedule:
            f["schedule"] = schedule
        return k

    def screen_label(self, fk: str) -> str:
        """画面・ボタンの機能の表示名。例: 見積作成依頼（LWCの画面）、一括見積作成依頼（ボタン BusinessTravelerHeader__c）"""
        kind, name = fk.split(":", 2)[1:]
        lab = (self.functions.get(fk, {}).get("labels") or [{}])[0].get("text") or name
        if kind == "action":
            obj = name.split(".")[0] if "." in name else ""
            return f"{lab}（ボタン {self.olabels.get(obj) or obj}）" if obj else f"{lab}（ボタン）"
        return f"{lab}（{ {'lwc': 'LWC', 'aura': 'Aura', 'vf': 'Visualforce'}.get(kind, kind)}の画面）"

    # ---------- 部品 → メソッド ----------
    def meta_label(self, st: str, sn: str, file: str) -> str | None:
        """画面・ボタン・項目自動更新の表示ラベル（メタデータにあれば）。名前と同じなら None。"""
        fa = lambda *p: os.path.join(self.fa, *p)
        lab = None
        if st == "QuickAction":
            lab = txt(parse(fa(*file.split("/"))), "label")
        elif st == "Visualforce":
            lab = txt(parse(fa("pages", f"{sn}.page-meta.xml")), "label")
        elif st == "LWC":
            lab = txt(parse(fa("lwc", sn, f"{sn}.js-meta.xml")), "masterLabel")
        elif st == "WorkflowFieldUpdate":
            root = parse(fa(*file.split("/")))
            for fu in (root.iter(NS + "fieldUpdates") if root is not None else []):
                if txt(fu, "fullName") == sn.split(".", 1)[1]:
                    lab = txt(fu, "name")
        return lab if lab and lab != sn and lab != sn.split(".")[-1] else None

    def func_of(self, st: str, sn: str, file: str) -> str | None:
        if st in ("ApexClass", "ApexTest"):
            return self.function("apex", sn, file, "Apex")
        if st == "ApexTrigger":
            return self.function("trigger", sn, file, "Apex")
        if st == "Flow":
            return self.function("flow", sn, file, "Flow", self.flow_label.get(sn))
        if st == "LWC":
            return self.function("lwc", sn, file, "LWC", self.meta_label(st, sn, file))
        if st == "Aura":
            return self.function("aura", sn, file, "Aura")
        if st == "Visualforce":
            return self.function("vf", sn, file, "Visualforce", self.meta_label(st, sn, file))
        if st == "QuickAction":
            return self.function("action", sn, file, "QuickAction", self.meta_label(st, sn, file))
        if st == "ValidationRule":
            return self.function("vr", sn, file, "ValidationRule", f"入力規則 {sn}")
        if st == "WorkflowFieldUpdate":
            return self.function("wf", sn, file, "Workflow", self.meta_label(st, sn, file) or f"項目自動更新 {sn}")
        if st == "CustomField":
            info = self.fields.get(sn.split(".", 1)[0], {}).get(sn.split(".", 1)[1], {})
            if not (info.get("formula") or info.get("summaryOperation")):
                return None   # 選択リストの値などの参照だけで、値を作る処理ではない
            kind = "rollup" if info.get("summaryOperation") else "formula"
            lab = info.get("label")
            return self.function(kind, sn, file, "Formula", (lab + ("（積み上げ集計）" if kind == "rollup" else "（数式）")) if lab else None)
        return None

    def target_func(self, r: dict) -> str | None:
        """呼び出し先（target）→ メソッドのキー。"""
        t, tk = r["target"], r["tkind"]
        if tk == "class":
            return f"function:apex:{t}" if f"function:apex:{t}" in self.functions else None
        if tk == "flow":
            return f"function:flow:{t}" if f"function:flow:{t}" in self.functions else None
        if t.startswith("LWC:"):
            n = t[4:]
            for k in (f"function:lwc:{n}", f"function:aura:{n}"):
                if k in self.functions:
                    return k
        if t.startswith("QuickAction:"):
            k = f"function:action:{t[len('QuickAction:'):]}"
            return k if k in self.functions else None
        if t.startswith("VF:"):
            k = f"function:vf:{t[3:]}"
            return k if k in self.functions else None
        return None

    # ---------- 組み立て ----------
    def build(self):
        self.flow_label = {}
        self.flow_meta = {}
        fdir = os.path.join(self.fa, "flows")
        if os.path.isdir(fdir):
            for fn in os.listdir(fdir):
                if fn.endswith(".flow-meta.xml"):
                    r = parse(os.path.join(fdir, fn))
                    if r is None:
                        continue
                    name = fn[: -len(".flow-meta.xml")]
                    start = r.find(NS + "start")
                    self.flow_label[name] = txt(r, "label")
                    self.flow_meta[name] = {
                        "processType": txt(r, "processType"), "status": txt(r, "status"),
                        "triggerType": txt(start, "triggerType") if start is not None else None,
                        "object": txt(start, "object") if start is not None else None,
                        "schedule": (txt(start.find(NS + "schedule"), "frequency") if start is not None and start.find(NS + "schedule") is not None else None),
                    }
        # 1) 全参照から、部品ごとに集める
        per = defaultdict(lambda: {"file": None, "line": 1, "write": [], "copy": [], "cond": [], "read": [], "objs": [], "calls": [], "wide": []})
        for r in self.refs:
            st, sn = r["src_type"], r["src_name"]
            # テストクラスは本番の処理ではないので書き出さない（テストデータを作る代入が偽の連鎖になる）
            if st not in ("ApexClass", "ApexTrigger", "Flow", "LWC", "Aura", "Visualforce", "QuickAction",
                          "ValidationRule", "WorkflowFieldUpdate", "CustomField"):
                continue
            e = per[(st, sn)]
            e["file"] = e["file"] or r["file"]
            role, tk = r["role"], r["tkind"]
            if tk == "field":
                if role == "write":
                    e["write"].append(r)
                elif role == "copy_to" and r.get("via"):
                    e["copy"].append(r)
                elif role in ("condition", "filter", "summary"):
                    e["cond"].append(r)
                elif role in ("read", "formula", "display", "mention") and not (role == "mention" and r["conf"] == "low"):
                    e["read"].append(r)
            elif tk == "object":
                if role in ("read_all", "read_dynamic", "write_dynamic"):
                    e["wide"].append(r)
                if role in ("read", "write", "trigger_on", "read_all") or role.startswith("dml_") or role.endswith("_dynamic"):
                    e["objs"].append(r)
            elif role == "call":
                e["calls"].append(r)
        # 2) メソッドを先に全部作る（呼び出しの解決に使う）
        fkey = {}
        for (st, sn), e in per.items():
            if e["file"]:
                fk = self.func_of(st, sn, e["file"])
                if fk:
                    fkey[(st, sn)] = fk
        # 3) 中身
        save_entry = defaultdict(list)
        for (st, sn), e in per.items():
            fk = fkey.get((st, sn))
            if not fk:
                continue
            file = e["file"]
            conds = []
            for c in e["cond"]:
                ck = self.column(c["target"])
                if ck and ck not in conds and not ck.endswith(".Id"):   # Id での絞り込みは業務の条件ではないので外す
                    conds.append(ck)
            # Apex はクラス単位なので、クラスの中の WHERE 条件を全部の書き込みの条件にすると関係の薄い連鎖になる。
            # 書き込みの条件はフロー（開始条件・決定）・ワークフローだけに付ける。
            # 参照・主従の項目での絞り込み（親のレコードの子を取る等）は結合の条件で、値の判定ではないので外す
            write_conds = [] if st in ("ApexClass", "ApexTrigger", "LWC", "Aura", "Visualforce") else \
                [k for k in conds if not self.is_relation(k)]
            # 読み書き（表の単位）
            for o in e["objs"]:
                if not self.known_obj(o["target"]):
                    continue
                mode = "write" if (o["role"] == "write" or o["role"].startswith("dml_") or o["role"] == "write_dynamic") else "read"
                if o["role"] == "trigger_on":
                    save_entry[o["target"]].append(fk)
                    mode = "read"
                key = (fk, self.table(o["target"]), mode)
                self.access.setdefault(key, {"functionKey": fk, "storeKey": key[1], "mode": mode, "confidence": CONF.get(o["conf"], "Medium")})
            # 呼び出し
            for c in e["calls"]:
                tf = self.target_func(c)
                if tf and tf != fk:
                    self.calls.setdefault((fk, tf), {"from": fk, "to": tf, "confidence": CONF.get(c["conf"], "Medium"),
                                                    "sourceFile": self.rel(c["file"]), "line": max(c["line"], 1)})
            used_inputs = set(conds)
            if st == "CustomField":
                obj, fld = sn.split(".", 1)
                out = self.column(sn)
                info = self.fields.get(obj, {}).get(fld, {})
                ins = []
                for x in e["read"] + e["cond"]:
                    k = self.column(x["target"])
                    if k and k != out and k not in [i["key"] for i in ins]:
                        ins.append({"key": k, "role": "operand"})
                if not out:
                    continue
                if info.get("summaryOperation"):
                    agg = info["summaryOperation"].upper()
                    srcs = [i for i in ins]
                    self.ops.append({"key": self.op_key(file, 1), "kind": "Aggregation", "functionKey": fk, "inputs": srcs,
                                     "outputs": [out], "aggregateFunction": agg,
                                     "formula": f"{agg}({', '.join(i['key'].split('.', 2)[-1] for i in srcs) or '件数'})",
                                     "formulaAst": {"func": agg, "args": [{"ref": i["key"]} for i in srcs]},
                                     "confidence": "High", "sourceFile": self.rel(file), "lineStart": 1})
                    for i in srcs:   # 積み上げ集計は子の保存で計算し直される
                        child = i["key"].split(".")[1]
                        save_entry[child].append(fk)
                else:
                    formula = (info.get("formula") or "").strip()
                    self.ops.append({"key": self.op_key(file, 1), "kind": "Calculation", "functionKey": fk, "inputs": ins,
                                     "outputs": [out], "formula": formula[:2000] or "（数式）",
                                     # 数式は Salesforce の数式のまま見せる（共通基盤の関数に置き換えない）
                                     "formulaAst": {"const": " ".join(formula.split())[:300] or "（数式）"},
                                     "confidence": "High", "sourceFile": self.rel(file), "lineStart": 1, "snippet": formula[:300]})
                continue
            if st == "ValidationRule":
                obj, rule = sn.split(".", 1)
                vr = parse(os.path.join(self.fa, *file.split("/")))
                cond_text = txt(vr, "errorConditionFormula") or ""
                ins = [{"key": k, "role": "condition"} for k in conds]
                for x in e["read"]:
                    k = self.column(x["target"])
                    if k and k not in [i["key"] for i in ins]:
                        ins.append({"key": k, "role": "condition"})
                self.ops.append({"key": self.op_key(file, 1), "kind": "Validation", "functionKey": fk, "inputs": ins,
                                 "appliesWhen": cond_text[:2000] or "（条件）",
                                 "conditionAst": {"const": " ".join(cond_text.split())[:300] or "（条件）"},
                                 "message": {"id": rule, "text": (txt(vr, "errorMessage") or rule)[:500]},
                                 "confidence": "High", "sourceFile": self.rel(file), "lineStart": 1, "snippet": cond_text[:300]})
                if txt(vr, "active") != "false":
                    save_entry[obj].append(fk)
                continue
            if st == "WorkflowFieldUpdate":
                save_entry[sn.split(".", 1)[0]].append(fk)
            # 値を写す → 転記
            written_by_copy = set()
            for c in e["copy"]:
                out, src = self.column(c["target"]), self.column(c["via"])
                if not out or not src or out == src or out.endswith(".Id"):
                    continue
                ins = [{"key": src, "role": "source"}] + [{"key": k, "role": "condition"} for k in write_conds[:15] if k not in (src, out)]
                self.ops.append({"key": self.op_key(file, c["line"]), "kind": "Transfer", "functionKey": fk, "inputs": ins,
                                 "outputs": [out], "confidence": CONF.get(c["conf"], "Medium"), "sourceFile": self.rel(file),
                                 "lineStart": max(c["line"], 1), "snippet": self.line_text(file, c["line"])})
                written_by_copy.add(out)
                used_inputs.add(src)
            # 値を設定（写し元が分からない） → 計算
            done = set()
            for w in e["write"]:
                out = self.column(w["target"])
                # Id への代入は更新するレコードの指定で、値の設定ではない
                if not out or out in written_by_copy or out in done or out.endswith(".Id"):
                    continue
                done.add(out)
                ins = [{"key": k, "role": "condition"} for k in write_conds[:15] if k != out]
                code = self.show_code(st, sn, file, w["line"])
                self.ops.append({"key": self.op_key(file, w["line"]), "kind": "Calculation", "functionKey": fk, "inputs": ins,
                                 "outputs": [out], "formula": f"（{st} {sn} が設定）{code[:200]}",
                                 # 代入の行をそのまま見せる（条件は入力の「条件」に出る）
                                 "formulaAst": {"const": " ".join(code.split())[:200] or f"{st} {sn} が設定"},
                                 "confidence": CONF.get(w["conf"], "Medium"), "sourceFile": self.rel(file),
                                 "lineStart": max(w["line"], 1), "snippet": self.line_text(file, w["line"])})
            # 読むだけの項目 → この部品の画面項目・IF項目へ転記（どこで使われるかを項目単位で残す）
            reads = []
            for x in e["read"]:
                k = self.column(x["target"])
                if k and k not in used_inputs and k not in [y[0] for y in reads]:
                    reads.append((k, x))
            if reads:
                is_screen = st in ("LWC", "Aura", "Visualforce", "QuickAction")
                skind, ikind, pre = ("Screen", "ScreenField", "screen") if is_screen else ("ExternalInterface", "InterfaceField", "interface")
                # 画面（Screen）の置き場所は、共通基盤では同じ識別子の画面の機能（feature:screen:…）と同じものになるので、
                # 機能のキー（{種類}_{名前}）とそろえる
                ident = "_".join(fk.split(":", 2)[1:]) if is_screen else fk.split(":", 1)[1]
                skey = f"{pre}:{ident}"
                if skey not in self.stores:
                    self.stores[skey] = {"key": skey, "kind": skind, "physicalName": ident if is_screen else sn,
                                         # 画面は同じ識別子の機能と同じノードになるので、機能の表示名と同じにする
                                         "labels": [{"text": self.screen_label(fk) if is_screen else sn,
                                                     "source": "ScreenLabel" if is_screen else "SameName"}],
                                         "sourceFile": self.rel(file)}
                for k, x in reads:
                    phys = k.split(".", 1)[1]
                    ik = f"{'screenField' if is_screen else 'interfaceField'}:{ident}.{phys}"
                    if ik not in self.items:
                        lab = self.items.get(k, {}).get("labels")
                        it = {"key": ik, "kind": ikind, "storeKey": skey, "physicalName": phys}
                        if lab:
                            it["labels"] = lab
                        self.items[ik] = it
                    self.ops.append({"key": self.op_key(file, x["line"]), "kind": "Transfer", "functionKey": fk,
                                     "inputs": [{"key": k, "role": "source"}], "outputs": [ik],
                                     "confidence": CONF.get(x["conf"], "Medium"), "sourceFile": self.rel(file),
                                     "lineStart": max(x["line"], 1), "snippet": self.line_text(file, x["line"])})
            # 解析しきれなかった箇所
            for wref in e["wide"]:
                kind = "DynamicSql" if wref["role"] == "read_all" else "DynamicCall"
                reason = ("項目の一覧を実行時に組み立てる SOQL で、全項目を読む（複製など）" if kind == "DynamicSql"
                          else "項目名を変数で渡す put/get で、どの項目を読み書きするか静的には分からない")
                self.unresolved.append({"kind": kind, "functionKey": fk, "sourceFile": self.rel(file), "line": max(wref["line"], 1),
                                        "snippet": self.line_text(file, wref["line"]) or wref["target"], "reason": f"{reason}（{wref['target']}）",
                                        "confidence": "Low"})
        # 4) 機能
        for obj, entries in save_entry.items():
            if self.known_obj(obj):
                self.table(obj)
                lab = self.olabels.get(obj) or obj
                self.feature("other", f"save_{obj}", sorted(set(entries)), f"{lab}の保存（保存時に動く処理）",
                             self.stores.get(f"table:{self.db}.{obj}", {}).get("sourceFile"))
        for name, m in self.flow_meta.items():
            fk = f"function:flow:{name}"
            if fk not in self.functions:
                self.function("flow", name, f"flows/{name}.flow-meta.xml", "Flow", self.flow_label.get(name))
            src = self.rel(f"flows/{name}.flow-meta.xml")
            lab = self.flow_label.get(name)
            if m["processType"] == "Flow":
                self.feature("screen", f"flow_{name}", [fk], lab, src)
            elif m["triggerType"] == "Scheduled":
                self.feature("batch", f"flow_{name}", [fk], lab, src, m.get("schedule"))
        for fk, f in list(self.functions.items()):
            kind, name = fk.split(":", 2)[1], fk.split(":", 2)[2]
            if kind in ("lwc", "aura", "vf", "action"):   # action はクイックアクション（ボタンから開く画面）
                self.feature("screen", f"{kind}_{name}", [fk], self.screen_label(fk), f["sourceFile"])
            elif kind == "apex":
                p = os.path.join(self.root, *f["sourceFile"].split("/"))
                try:
                    t = open(p, encoding="utf-8", errors="ignore").read()
                except OSError:
                    t = ""
                if re.search(r"@RestResource", t):
                    self.feature("api", f"apex_{name}", [fk], None, f["sourceFile"])
                elif re.search(r"implements\s+[^{]*\b(Schedulable|Database\.Batchable)\b", t, re.I):
                    self.feature("batch", f"apex_{name}", [fk], None, f["sourceFile"])

    def screens_for_features(self):
        """共通基盤では画面の機能は同じ識別子の画面（Screen）と同じもので、物理名を画面から取る。
        項目を読まない画面（ボタン・画面フロー等）にも、空の画面を作っておく。"""
        for k, f in self.features.items():
            if f["kind"] != "Screen" or not f["entryFunctionKeys"]:
                continue
            fid = f["featureId"]
            sk = f"screen:{fid}"
            if sk not in self.stores:
                s = {"key": sk, "kind": "Screen", "physicalName": fid}
                if f.get("labels"):
                    s["labels"] = f["labels"]
                if f.get("sourceFile"):
                    s["sourceFile"] = f["sourceFile"]
                self.stores[sk] = s

    def to_json(self) -> dict:
        self.screens_for_features()
        return {
            "schemaVersion": "1.0",
            "system": {"repoId": self.repo, "systemNameJa": self.name_ja, "dbIds": [self.db],
                       "analyzedAt": time.strftime("%Y-%m-%dT%H:%M:%S+09:00"),
                       "adapterName": "salesforce-sf-lineage-adapter", "adapterVersion": "0.1.0"},
            "programs": list(self.programs.values()),
            "functions": list(self.functions.values()),
            "features": [f for f in self.features.values() if f["entryFunctionKeys"]],
            "dataStores": list(self.stores.values()),
            "dataItems": list(self.items.values()),
            "storeAccess": list(self.access.values()),
            "calls": list(self.calls.values()),
            "operations": self.ops,
            "unresolved": self.unresolved,
        }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", required=True, help="プロジェクトのルート（force-app のある場所）")
    ap.add_argument("--map", required=True, help="地図のフォルダ（lineage.py の .lineage）")
    ap.add_argument("--repo", required=True, help="システムの識別子（英数字・_・-。t_ で始めない）")
    ap.add_argument("--name-ja", required=True)
    ap.add_argument("--out", required=True, help="書き出す中間JSONのパス")
    a = ap.parse_args()
    if a.repo.startswith("t_") or not re.fullmatch(r"[A-Za-z0-9_-]+", a.repo):
        sys.exit("--repo は英数字・_・- だけで、t_ で始めない（t_ はテスト用）")
    ex = Exporter(a.root, a.map, a.repo, a.name_ja)
    ex.build()
    data = ex.to_json()
    os.makedirs(os.path.dirname(os.path.abspath(a.out)), exist_ok=True)
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
    kinds = defaultdict(int)
    for o in data["operations"]:
        kinds[o["kind"]] += 1
    print(f"中間JSON: プログラム {len(data['programs'])}・メソッド {len(data['functions'])}・機能 {len(data['features'])}・"
          f"置き場所 {len(data['dataStores'])}・項目 {len(data['dataItems'])}・読み書き {len(data['storeAccess'])}・"
          f"呼び出し {len(data['calls'])}・演算 {len(data['operations'])}（" + "・".join(f"{k} {v}" for k, v in sorted(kinds.items())) +
          f"）・未解決 {len(data['unresolved'])} → {a.out}")


if __name__ == "__main__":
    main()
