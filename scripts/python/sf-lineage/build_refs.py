"""Salesforce の force-app から「組織の地図」の参照（どの部品が、どの項目・選択肢・部品を使うか）を作る。

試作 v2（2026-11-11）。GF の過去課題での答え合わせで見つかった取りこぼしを直した版。
- 段階1: XML のメタデータ（項目・入力規則・画面・帳票・権限・設定・フロー・ワークフロー・メール）
- 段階2: Apex の項目の読み書き・DML（apex_refs.ApexAnalyzer。変数の型の宣言から追う）
出力: refs.jsonl（1行1参照）・fields.json（項目の一覧）・objects.json（オブジェクトの表示名）
使い方: python build_refs.py <force-app/main/default のパス> <出力フォルダ>
"""
from __future__ import annotations

import json
import os
import re
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, asdict, replace
from typing import Iterable

NS = "{http://soap.sforce.com/2006/04/metadata}"

STD_REL = {
    "Owner": "User", "CreatedBy": "User", "LastModifiedBy": "User", "Account": "Account",
    "Contact": "Contact", "Opportunity": "Opportunity", "Case": "Case", "Campaign": "Campaign",
    "Lead": "Lead", "RecordType": "RecordType", "Parent": None, "Pricebook2": "Pricebook2",
    "Product2": "Product2", "Contract": "Contract", "Order": "Order", "Quote": "Quote",
    "ConvertedAccount": "Account", "ConvertedContact": "Contact", "ConvertedOpportunity": "Opportunity",
    "ReportsTo": "Contact", "Manager": "User", "Who": None, "What": None, "Profile": "Profile", "UserRole": "UserRole",
}
FORMULA_FUNCS = {
    "AND", "OR", "NOT", "IF", "CASE", "ISBLANK", "ISNULL", "BLANKVALUE", "NULLVALUE", "ISPICKVAL", "TEXT",
    "VALUE", "LEN", "LEFT", "RIGHT", "MID", "FIND", "SUBSTITUTE", "TRIM", "UPPER", "LOWER", "CONTAINS",
    "BEGINS", "INCLUDES", "ISCHANGED", "PRIORVALUE", "ISNEW", "TODAY", "NOW", "DATE", "DATEVALUE", "DATETIMEVALUE",
    "YEAR", "MONTH", "DAY", "WEEKDAY", "ADDMONTHS", "ROUND", "FLOOR", "CEILING", "ABS", "MAX", "MIN", "MOD",
    "HYPERLINK", "IMAGE", "REGEX", "ISNUMBER", "TRUE", "FALSE", "NULL", "BR", "CURRENCYRATE", "VLOOKUP",
    "GETRECORDIDS", "LINKTO", "URLFOR", "ISCLONE", "TIMEVALUE", "HOUR", "MINUTE", "SECOND", "EXP", "LN", "LOG", "SQRT",
    "PARENTGROUPVAL", "PREVGROUPVAL", "INCLUDE", "JSENCODE", "HTMLENCODE", "URLENCODE", "CASESAFEID",
}


@dataclass
class Ref:
    src_type: str      # 参照元の種類（Flow・Layout・ApexClass など）
    src_name: str      # 参照元の名前
    file: str          # force-app/main/default からの相対パス
    line: int          # 行（おおよそ）
    role: str          # read / write / condition / display / permission / summary / formula / filter / trigger_on / call / value / mention / copy_to / label / dml_*
    tkind: str         # field / object / value / class / flow / component
    target: str        # 例: Account.Rank__c ／ Account ／ Account.Rank__c=A ／ MyClass ／ LWC:request ／ QuickAction:Obj.Name
    conf: str = "high" # high / mid / low
    via: str = ""      # copy_to のときの写し元の項目（例: Account.Rank__c）


class Index:
    def __init__(self, root: str) -> None:
        self.root = root
        self.refs: list[Ref] = []
        self.fields: dict[str, dict[str, dict]] = {}
        self.objects: set[str] = set()
        self.object_labels: dict[str, str | None] = {}
        self.field_owner: dict[str, set[str]] = {}
        self.child_rel: dict[tuple[str, str], str] = {}   # (親, 子リレーション名__r) -> 子オブジェクト
        self.classes: set[str] = set()
        self.flows: set[str] = set()
        self.quick_actions: set[str] = set()
        self.last_hops: list[tuple[str, str]] = []

    # ---------- 共通 ----------
    def rel(self, path: str) -> str:
        return os.path.relpath(path, self.root).replace("\\", "/")

    def add(self, src_type, src_name, path, text, needle, role, tkind, target, conf="high", via="") -> None:
        if not target:
            return
        line = find_line(text, needle) if needle else 1
        self.refs.append(Ref(src_type, src_name, self.rel(path), line, role, tkind, target, conf, via))

    def add_field(self, src_type, src_name, path, text, obj, field, role, conf="high", needle=None, via=""):
        if not obj or not field:
            return
        self.add(src_type, src_name, path, text, needle or field, role, "field", f"{obj}.{field}", conf, via)

    def add_hops(self, src_type, src_name, path, text):
        """直前の resolve_path で通った参照項目（X__r → X__c）を「読み」として記録する。"""
        for o, f in self.last_hops:
            self.add_field(src_type, src_name, path, text, o, f, "read", "mid")
        self.last_hops = []

    def resolve_path(self, obj: str | None, dotted: str) -> tuple[str | None, str | None, str]:
        """`Rel__r.Owner.Name` のような連鎖を、文脈のオブジェクトから辿って（オブジェクト, 項目, 確度）にする。
        親方向（参照項目）と子方向（子リレーション名）の両方を辿る。通った参照項目は self.last_hops に残す。"""
        self.last_hops = []
        parts = [p for p in dotted.split(".") if p]
        if not parts:
            return None, None, "low"
        conf = "high"
        cur = obj
        for p in parts[:-1]:
            if cur is None:
                return None, parts[-1], "low"
            nxt = None
            if p.endswith("__r"):
                lk_name = p[:-3] + "__c"
                lk = self.fields.get(cur, {}).get(lk_name)
                if lk and lk.get("referenceTo"):
                    nxt = lk["referenceTo"]
                    self.last_hops.append((cur, lk_name))
                elif (cur, p) in self.child_rel:
                    nxt = self.child_rel[(cur, p)]
            elif p in STD_REL:
                nxt = STD_REL[p] if STD_REL[p] is not None else (cur if p == "Parent" else None)
                if nxt is not None and p + "Id" in self.fields.get(cur, {}):
                    self.last_hops.append((cur, p + "Id"))
                if nxt is None:
                    conf = "low"
            elif p in self.objects:
                nxt = p
            elif (cur, p) in self.child_rel:   # 標準の子リレーション名（Contacts など）を表に持っている場合
                nxt = self.child_rel[(cur, p)]
            if nxt is None:
                return None, parts[-1], "low"
            cur = nxt
            conf = "mid" if conf == "high" else conf
        return cur, parts[-1], conf

    def owners(self, field: str) -> set[str]:
        return self.field_owner.get(field, set())

    # ---------- 項目の一覧（最初に作る） ----------
    def renamed_label(self, obj: str) -> str | None:
        """標準オブジェクトの名前の変更（「タブと表示ラベルの名前変更」）は、日本語の翻訳の caseValues に入る。"""
        root = parse(os.path.join(self.root, "objectTranslations", f"{obj}-ja", f"{obj}-ja.objectTranslation-meta.xml"))
        if root is None:
            return None
        for cv in root.iter(NS + "caseValues"):
            if txt(cv, "plural") != "true" and txt(cv, "value"):
                return txt(cv, "value")
        return None

    def load_objects(self) -> None:
        odir = os.path.join(self.root, "objects")
        if os.path.isdir(odir):
            for obj in os.listdir(odir):
                self.objects.add(obj)
                om = parse(os.path.join(odir, obj, f"{obj}.object-meta.xml"))
                self.object_labels[obj] = (txt(om, "label") if om is not None else None) or self.renamed_label(obj)
                fdir = os.path.join(odir, obj, "fields")
                self.fields.setdefault(obj, {})
                if not os.path.isdir(fdir):
                    continue
                for fn in os.listdir(fdir):
                    if not fn.endswith(".field-meta.xml"):
                        continue
                    name = fn[: -len(".field-meta.xml")]
                    root = parse(os.path.join(fdir, fn))
                    if root is None:
                        continue
                    info = {
                        "label": txt(root, "label"), "type": txt(root, "type"),
                        "referenceTo": txt(root, "referenceTo"), "formula": txt(root, "formula"),
                        "summaryOperation": txt(root, "summaryOperation"),
                        "relationshipName": txt(root, "relationshipName"),
                    }
                    self.fields[obj][name] = info
                    self.field_owner.setdefault(name, set()).add(obj)
                    if info["referenceTo"] and info["relationshipName"]:
                        self.child_rel[(info["referenceTo"], info["relationshipName"] + "__r")] = obj
        for d, ext, s in (("classes", ".cls", self.classes), ("flows", ".flow-meta.xml", self.flows),
                          ("quickActions", ".quickAction-meta.xml", self.quick_actions)):
            p = os.path.join(self.root, d)
            if os.path.isdir(p):
                s.update(f[: -len(ext)] for f in os.listdir(p) if f.endswith(ext))

    # ---------- 数式 ----------
    def formula_refs(self, src_type, src_name, path, text, obj, formula, role):
        if not formula:
            return
        for m in re.finditer(r'ISPICKVAL\s*\(\s*\{?!?\s*([\w.$]+)\s*\}?\s*,\s*["\']((?:[^"\'\\]|\\.)*)["\']', formula, re.I):
            tok = m.group(1).removeprefix("$Record.")
            o, fld, c = self.resolve_path(obj, tok) if "." in tok else (obj, tok, "high")
            if o and fld:
                self.add(src_type, src_name, path, text, m.group(2) or fld, "value", "value", f"{o}.{fld}={m.group(2)}", c)
        f = re.sub(r'"(?:[^"\\]|\\.)*"|\'(?:[^\'\\]|\\.)*\'', '""', formula)
        for m in re.finditer(r'(?<![\w$.])(\$?[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*)(\s*\()?', f):
            tok, call = m.group(1), m.group(2)
            if call or tok.upper() in FORMULA_FUNCS:
                continue
            if tok.startswith("$"):
                if tok.startswith("$Record."):
                    tok = tok[len("$Record."):]
                else:
                    continue
            o, fld, c = self.resolve_path(obj, tok) if "." in tok else (obj, tok, "high")
            if o and fld and (fld in self.fields.get(o, {}) or fld.endswith("__c") or o != obj):
                self.add_field(src_type, src_name, path, text, o, fld, role, c, needle=tok.split(".")[-1])
                self.add_hops(src_type, src_name, path, text)

    # ---------- オブジェクトの中 ----------
    def scan_objects(self) -> None:
        odir = os.path.join(self.root, "objects")
        if not os.path.isdir(odir):
            return
        for obj in os.listdir(odir):
            base = os.path.join(odir, obj)
            for sub, ext, handler in (
                ("fields", ".field-meta.xml", self._field),
                ("validationRules", ".validationRule-meta.xml", self._vr),
                ("listViews", ".listView-meta.xml", self._listview),
                ("recordTypes", ".recordType-meta.xml", self._recordtype),
                ("compactLayouts", ".compactLayout-meta.xml", self._compact),
                ("fieldSets", ".fieldSet-meta.xml", self._fieldset),
            ):
                d = os.path.join(base, sub)
                if not os.path.isdir(d):
                    continue
                for fn in os.listdir(d):
                    if fn.endswith(ext):
                        p = os.path.join(d, fn)
                        root, text = parse_with_text(p)
                        if root is not None:
                            handler(obj, fn[: -len(ext)], p, text, root)

    def _field(self, obj, name, p, text, root):
        st, sname = "CustomField", f"{obj}.{name}"
        if txt(root, "formula"):
            self.formula_refs(st, sname, p, text, obj, txt(root, "formula"), "formula")
        if txt(root, "summaryOperation"):
            for v in (txt(root, "summaryForeignKey"), txt(root, "summarizedField")):
                if v and "." in v:
                    o, f = v.split(".", 1)
                    self.add_field(st, sname, p, text, o, f, "summary", needle=f)
            for fi in root.iter(NS + "summaryFilterItems"):
                v = txt(fi, "field")
                if v and "." in v:
                    o, f = v.split(".", 1)
                    self.add_field(st, sname, p, text, o, f, "summary", needle=f)
        for lf in root.iter(NS + "lookupFilter"):
            for fi in lf.iter(NS + "filterItems"):
                v = txt(fi, "field")
                if v:
                    o, f, c = self.resolve_path(obj, v.replace("$Source.", ""))
                    self.add_field(st, sname, p, text, o or obj, f, "condition", c)
        vs = root.find(NS + "valueSet")
        if vs is not None:
            cf = txt(vs, "controllingField")
            if cf:
                self.add_field(st, sname, p, text, obj, cf, "condition", needle=cf)
            gvs = txt(vs, "valueSetName")
            if gvs:
                self.add(st, sname, p, text, gvs, "read", "component", f"GlobalValueSet:{gvs}")
            vd = vs.find(NS + "valueSetDefinition")
            if vd is not None:
                for v in vd.iter(NS + "value"):
                    fn = txt(v, "fullName")
                    if fn:
                        self.add(st, sname, p, text, fn, "value", "value", f"{obj}.{name}={unquote(fn)}")

    def _vr(self, obj, name, p, text, root):
        self.formula_refs("ValidationRule", f"{obj}.{name}", p, text, obj, txt(root, "errorConditionFormula"), "condition")
        edf = txt(root, "errorDisplayField")
        if edf:
            self.add_field("ValidationRule", f"{obj}.{name}", p, text, obj, edf, "display")

    def _listview(self, obj, name, p, text, root):
        for c in root.iter(NS + "columns"):
            self._loose_field("ListView", f"{obj}.{name}", p, text, obj, c.text, "display")
        for fi in root.iter(NS + "filters"):
            self._loose_field("ListView", f"{obj}.{name}", p, text, obj, txt(fi, "field"), "filter")

    def _recordtype(self, obj, name, p, text, root):
        for pv in root.iter(NS + "picklistValues"):
            pl = txt(pv, "picklist")
            if not pl:
                continue
            self.add_field("RecordType", f"{obj}.{name}", p, text, obj, pl, "condition")
            for v in pv.iter(NS + "values"):
                fn = txt(v, "fullName")
                if fn:
                    self.add("RecordType", f"{obj}.{name}", p, text, fn, "value", "value", f"{obj}.{pl}={unquote(fn)}")

    def _compact(self, obj, name, p, text, root):
        for f in root.iter(NS + "fields"):
            self._loose_field("CompactLayout", f"{obj}.{name}", p, text, obj, f.text, "display")

    def _fieldset(self, obj, name, p, text, root):
        for f in root.iter(NS + "field"):
            self._loose_field("FieldSet", f"{obj}.{name}", p, text, obj, f.text, "display")

    def _loose_field(self, st, sname, p, text, obj, v, role):
        if not v:
            return
        v = v.strip().replace("$", ".")
        if "." in v:
            head = v.split(".")[0]
            if head in self.objects:
                o, f, c = self.resolve_path(head, v.split(".", 1)[1]) if v.count(".") > 1 else (head, v.split(".")[-1], "high")
            else:
                o, f, c = self.resolve_path(obj, v)
            self.add_field(st, sname, p, text, o, f, role, c if o else "low", needle=v.split(".")[-1])
            self.add_hops(st, sname, p, text)
        elif obj and v in self.fields.get(obj, {}):
            self.add_field(st, sname, p, text, obj, v, role)
        elif v.endswith("__c"):
            if obj:
                self.add_field(st, sname, p, text, obj, v, role, "mid")
            else:
                for o in self.owners(v) or {"?"}:
                    self.add_field(st, sname, p, text, o, v, role, "low")

    # ---------- 画面・設定・帳票 ----------
    def scan_simple(self) -> None:
        handlers = {
            "layouts": (".layout-meta.xml", self._layout),
            "flexipages": (".flexipage-meta.xml", self._flexipage),
            "pathAssistants": (".pathAssistant-meta.xml", self._path),
            "reportTypes": (".reportType-meta.xml", self._reporttype),
            "quickActions": (".quickAction-meta.xml", self._quickaction),
            "workflows": (".workflow-meta.xml", self._workflow),
            "approvalProcesses": (".approvalProcess-meta.xml", self._approval),
            "assignmentRules": (".assignmentRules-meta.xml", self._criteria_rules),
            "autoResponseRules": (".autoResponseRules-meta.xml", self._criteria_rules),
            "escalationRules": (".escalationRules-meta.xml", self._criteria_rules),
            "duplicateRules": (".duplicateRule-meta.xml", self._duplicate),
            "matchingRules": (".matchingRule-meta.xml", self._matching),
            "permissionsets": (".permissionset-meta.xml", self._perm),
            "profiles": (".profile-meta.xml", self._perm),
            "flows": (".flow-meta.xml", self._flow),
            "customMetadata": (".md-meta.xml", self._custom_md),
        }
        for d, (ext, h) in handlers.items():
            dp = os.path.join(self.root, d)
            if not os.path.isdir(dp):
                continue
            for fn in os.listdir(dp):
                if fn.endswith(ext):
                    p = os.path.join(dp, fn)
                    root, text = parse_with_text(p)
                    if root is not None:
                        h(fn[: -len(ext)], p, text, root, d)
        p = os.path.join(self.root, "LeadConvertSettings", "LeadConvertSetting.LeadConvertSetting-meta.xml")
        if os.path.exists(p):
            root, text = parse_with_text(p)
            if root is not None:
                self._leadconvert("LeadConvertSetting", p, text, root, "")
        self._reports()
        self._email_templates()
        self._translations()

    def _actions_in(self, st, name, p, text, obj):
        """レイアウト・Lightning ページの中のアクション（クイックアクション）の配置。"""
        for qa in self.quick_actions:
            short = qa.split(".", 1)[1] if "." in qa else qa
            if f">{qa}<" in text or (obj and qa.startswith(obj + ".") and f">{short}<" in text):
                self.add(st, name, p, text, short, "display", "component", f"QuickAction:{qa}")

    def _layout(self, name, p, text, root, d):
        obj = name.split("-", 1)[0]
        for li in root.iter(NS + "layoutItems"):
            f = txt(li, "field")
            if f:
                self.add_field("Layout", name, p, text, obj, f, "display")
        for rl in root.iter(NS + "relatedLists"):
            rl_name = txt(rl, "relatedList") or ""
            child = rl_name.split(".", 1)[0] if "." in rl_name and rl_name.split(".", 1)[0] in self.objects else None
            for f in rl.iter(NS + "fields"):
                self._loose_field("Layout", name, p, text, child, f.text, "display")
        self._actions_in("Layout", name, p, text, obj)

    def _flexipage(self, name, p, text, root, d):
        obj = txt(root, "sobjectType")
        if obj:
            self.add("FlexiPage", name, p, text, obj, "display", "object", obj)
        for fi in root.iter(NS + "fieldItem"):
            v = (fi.text or "").replace("Record.", "", 1)
            if v:
                self.add_field("FlexiPage", name, p, text, obj, v.split(".")[-1], "display", "high" if obj else "low", needle=v.split(".")[-1])
        for m in re.finditer(r"\{!Record\.([\w.]+)\}", text):
            o, f, c = self.resolve_path(obj, m.group(1)) if "." in m.group(1) else (obj, m.group(1), "high")
            self.add_field("FlexiPage", name, p, text, o, f, "condition", c, needle=m.group(0))
        for m in re.finditer(r"<componentName>(?:c:|c__)([\w]+)</componentName>", text):
            self.add("FlexiPage", name, p, text, m.group(0), "display", "component", f"LWC:{m.group(1)}")
        if obj and ("force:detailPanel" in text or "force:recordDetailPanelMobile" in text):
            # ページレイアウトをそのまま表示する部品 → そのオブジェクトのレイアウトに置いた項目は、このページにも出る
            self.add("FlexiPage", name, p, text, "force:detailPanel", "display", "component", f"LayoutsOf:{obj}")
        self._actions_in("FlexiPage", name, p, text, obj)

    def _path(self, name, p, text, root, d):
        obj = txt(root, "sobjectType") or txt(root, "entityName")
        pl = txt(root, "fieldName")
        if pl:
            self.add_field("PathAssistant", name, p, text, obj, pl, "condition")
        for st in root.iter(NS + "pathAssistantSteps"):
            v = txt(st, "picklistValueName")
            if v and pl:
                self.add("PathAssistant", name, p, text, v, "value", "value", f"{obj}.{pl}={v}")
            for f in st.iter(NS + "fieldNames"):
                self.add_field("PathAssistant", name, p, text, obj, f.text, "display")

    def _reporttype(self, name, p, text, root, d):
        base = txt(root, "baseObject")
        self.add("ReportType", name, p, text, base, "read", "object", base or "")
        for c in root.iter(NS + "columns"):
            f, t = txt(c, "field"), txt(c, "table")
            if not f:
                continue
            o = base
            if t and "." in t:
                head, rest = t.split(".", 1)
                o = self.resolve_path(head if head in self.objects else base, rest + ".x")[0]
            elif t:
                o = t
            if o is None:
                for ow in self.owners(f.split(".")[-1]) or {"?"}:
                    self.add_field("ReportType", name, p, text, ow, f.split(".")[-1], "display", "low")
                continue
            self._loose_field("ReportType", name, p, text, o, f.split(".")[-1] if "." in f else f, "display")

    def _reports(self):
        dp = os.path.join(self.root, "reports")
        if not os.path.isdir(dp):
            return
        for dirpath, _, files in os.walk(dp):
            for fn in files:
                if not fn.endswith(".report-meta.xml"):
                    continue
                p = os.path.join(dirpath, fn)
                root, text = parse_with_text(p)
                if root is None:
                    continue
                name = self.rel(p)[len("reports/"):-len(".report-meta.xml")]
                for tag in ("field", "columns", "groupingsDown", "groupingsAcross", "column"):
                    for el in root.iter(NS + tag):
                        v = el.text if tag in ("field", "column") else txt(el, "field")
                        if v and ("__c" in v or "." in v):
                            self._loose_field("Report", name, p, text, None, v, "display")

    def _quickaction(self, name, p, text, root, d):
        obj = txt(root, "targetObject") or (name.split(".", 1)[0] if "." in name else None)
        for f in root.iter(NS + "field"):
            self._loose_field("QuickAction", name, p, text, obj, f.text, "display")
        for fo in root.iter(NS + "fieldOverrides"):
            self.add_field("QuickAction", name, p, text, obj, txt(fo, "field"), "write")
            self.formula_refs("QuickAction", name, p, text, name.split(".", 1)[0] if "." in name else obj, txt(fo, "formula"), "read")
        fd = txt(root, "flowDefinition")
        if fd:
            self.add("QuickAction", name, p, text, fd, "call", "flow", fd)
        lc = txt(root, "lightningComponent")
        if lc:
            self.add("QuickAction", name, p, text, lc, "call", "component", "LWC:" + lc.replace("c:", "").replace("c__", ""))
        pg = txt(root, "page")
        if pg:
            self.add("QuickAction", name, p, text, pg, "call", "component", f"VF:{pg}")

    def _workflow(self, name, p, text, root, d):
        obj = name
        for fu in root.iter(NS + "fieldUpdates"):
            fu_name = txt(fu, "fullName")
            target = txt(fu, "targetObject") or obj
            sname = f"{obj}.{fu_name}"
            self.add_field("WorkflowFieldUpdate", sname, p, text, target, txt(fu, "field"), "write", needle=fu_name)
            self.formula_refs("WorkflowFieldUpdate", sname, p, text, obj, txt(fu, "formula"), "read")
            lv = txt(fu, "literalValue")
            if lv and txt(fu, "field"):
                self.add("WorkflowFieldUpdate", sname, p, text, lv, "value", "value", f"{target}.{txt(fu, 'field')}={lv}")
        for al in root.iter(NS + "alerts"):
            an = f"{obj}.{txt(al, 'fullName')}"
            tp = txt(al, "template")
            if tp:
                self.add("WorkflowAlert", an, p, text, tp, "call", "component", f"EmailTemplate:{tp}")
            for rc in al.iter(NS + "recipients"):
                fld = txt(rc, "field")
                if fld:
                    self.add_field("WorkflowAlert", an, p, text, obj, fld, "read")
            for cc in al.iter(NS + "ccEmails"):
                pass
        for r in root.iter(NS + "rules"):
            rn = f"{obj}.{txt(r, 'fullName')}"
            for ci in r.iter(NS + "criteriaItems"):
                self._criteria_item("WorkflowRule", rn, p, text, ci)
            self.formula_refs("WorkflowRule", rn, p, text, obj, txt(r, "formula"), "condition")
            self.add("WorkflowRule", rn, p, text, txt(r, "fullName"), "trigger_on", "object", obj)
            for ac in list(r.iter(NS + "actions")):
                an, at = txt(ac, "name"), txt(ac, "type")
                if an and at == "Alert":
                    self.add("WorkflowRule", rn, p, text, an, "call", "component", f"EmailAlert:{obj}.{an}")
                elif an and at == "FieldUpdate":
                    self.add("WorkflowRule", rn, p, text, an, "call", "component", f"WorkflowFieldUpdate:{obj}.{an}")

    def _criteria_item(self, st, sname, p, text, ci):
        v = txt(ci, "field")
        if v and "." in v:
            o, f = v.split(".", 1)
            o2, f2, c = self.resolve_path(o, f) if "." in f else (o, f, "high")
            self.add_field(st, sname, p, text, o2, f2, "condition", c)
            val = txt(ci, "value")
            if val and o2 and f2:
                for one in val.split(","):
                    self.add(st, sname, p, text, one.strip(), "value", "value", f"{o2}.{f2}={one.strip()}", "mid")

    def _approval(self, name, p, text, root, d):
        obj = name.split(".", 1)[0]
        for ci in root.iter(NS + "criteriaItems"):
            self._criteria_item("ApprovalProcess", name, p, text, ci)
        for fe in root.iter(NS + "formula"):
            self.formula_refs("ApprovalProcess", name, p, text, obj, fe.text, "condition")
        self.add("ApprovalProcess", name, p, text, None, "trigger_on", "object", obj)
        for m in re.finditer(r"<name>([\w]+)</name>\s*<type>(Alert|FieldUpdate)</type>", text):
            kind = "EmailAlert" if m.group(2) == "Alert" else "WorkflowFieldUpdate"
            self.add("ApprovalProcess", name, p, text, m.group(1), "call", "component", f"{kind}:{obj}.{m.group(1)}")

    def _criteria_rules(self, name, p, text, root, d):
        st = {"assignmentRules": "AssignmentRule", "autoResponseRules": "AutoResponseRule", "escalationRules": "EscalationRule"}[d]
        for ci in root.iter(NS + "criteriaItems"):
            self._criteria_item(st, name, p, text, ci)
        for fe in root.iter(NS + "formula"):
            self.formula_refs(st, name, p, text, name, fe.text, "condition")
        tp = re.findall(r"<template>([^<]+)</template>", text)
        for t in tp:
            self.add(st, name, p, text, t, "call", "component", f"EmailTemplate:{t}")

    def _duplicate(self, name, p, text, root, d):
        obj = name.split(".", 1)[0]
        for fi in root.iter(NS + "duplicateRuleFilterItems"):
            self._loose_field("DuplicateRule", name, p, text, txt(fi, "table") or obj, txt(fi, "field"), "condition")
        for m in root.iter(NS + "matchingRule"):
            if m.text:
                self.add("DuplicateRule", name, p, text, m.text, "read", "component", f"MatchingRule:{obj}.{m.text}")

    def _matching(self, name, p, text, root, d):
        obj = name
        for mr in root.iter(NS + "matchingRules"):
            mn = f"{obj}.{txt(mr, 'fullName')}"
            for it in mr.iter(NS + "matchingRuleItems"):
                self.add_field("MatchingRule", mn, p, text, obj, txt(it, "fieldName"), "condition")

    def _perm(self, name, p, text, root, d):
        st = "PermissionSet" if d == "permissionsets" else "Profile"
        for fp in root.iter(NS + "fieldPermissions"):
            v = txt(fp, "field")
            if v and "." in v and (txt(fp, "readable") == "true" or txt(fp, "editable") == "true"):
                o, f = v.split(".", 1)
                self.add_field(st, name, p, text, o, f, "permission", needle=v)
        for ca in root.iter(NS + "classAccesses"):
            if txt(ca, "enabled") == "true":
                self.add(st, name, p, text, txt(ca, "apexClass"), "permission", "class", txt(ca, "apexClass") or "")
        for pa in root.iter(NS + "pageAccesses"):
            if txt(pa, "enabled") == "true":
                self.add(st, name, p, text, txt(pa, "apexPage"), "permission", "component", f"VF:{txt(pa, 'apexPage')}")

    def _leadconvert(self, name, p, text, root, d):
        for om in root.iter(NS + "objectMapping"):
            io, oo = txt(om, "inputObject"), txt(om, "outputObject")
            for mf in om.iter(NS + "mappingFields"):
                self.add_field("LeadConvertSetting", name, p, text, io, txt(mf, "inputField"), "read")
                self.add_field("LeadConvertSetting", name, p, text, oo, txt(mf, "outputField"), "write")

    def _custom_md(self, name, p, text, root, d):
        """カスタムメタデータのレコード: 値の中に書かれた項目名・オブジェクト名の出現（設定として使われるもの）。"""
        for m in re.finditer(r"<value[^>]*>([^<]+)</value>", text):
            v = m.group(1).strip()
            for tok in re.findall(r"\b(\w+__c)\b", v):
                if tok in self.objects:
                    self.add("CustomMetadata", name, p, text, tok, "mention", "object", tok, "low")
                else:
                    for o in self.owners(tok):
                        self.add_field("CustomMetadata", name, p, text, o, tok, "mention", "low")
            if "." in v and re.fullmatch(r"[A-Za-z]\w*\.\w+", v) and v.split(".")[0] in self.objects:
                self.add_field("CustomMetadata", name, p, text, v.split(".")[0], v.split(".")[1], "mention", "mid")

    def _email_templates(self):
        dp = os.path.join(self.root, "email")
        if not os.path.isdir(dp):
            return
        for dirpath, _, files in os.walk(dp):
            for fn in files:
                if not fn.endswith((".email", ".email-meta.xml")):
                    continue
                p = os.path.join(dirpath, fn)
                text = read(p)
                folder = os.path.basename(dirpath)
                tname = fn.replace(".email-meta.xml", "").replace(".email", "")
                name = f"{folder}/{tname}"
                rel_obj = None
                if fn.endswith(".email-meta.xml"):
                    m = re.search(r"<relatedEntityType>(\w+)</relatedEntityType>", text)
                    rel_obj = m.group(1) if m else None
                for m in re.finditer(r"\{!\s*([\w$]+)\.([\w.]+)\s*\}", text):
                    head, rest = m.group(1), m.group(2)
                    if head in self.objects:
                        o, f, c = self.resolve_path(head, rest) if "." in rest else (head, rest, "high")
                        self.add_field("EmailTemplate", name, p, text, o, f, "read", c, needle=m.group(0))
                    elif head.lower() == "relatedto" and rel_obj:
                        o, f, c = self.resolve_path(rel_obj, rest) if "." in rest else (rel_obj, rest, "high")
                        self.add_field("EmailTemplate", name, p, text, o, f, "read", c, needle=m.group(0))

    def _translations(self):
        dp = os.path.join(self.root, "objectTranslations")
        if not os.path.isdir(dp):
            return
        for od in os.listdir(dp):
            obj = od.rsplit("-", 1)[0]
            d = os.path.join(dp, od)
            if not os.path.isdir(d):
                continue
            for fn in os.listdir(d):
                if fn.endswith(".fieldTranslation-meta.xml"):
                    f = fn[: -len(".fieldTranslation-meta.xml")]
                    p = os.path.join(d, fn)
                    self.refs.append(Ref("FieldTranslation", f"{od}.{f}", self.rel(p), 1, "label", "field", f"{obj}.{f}", "high"))

    # ---------- フロー ----------
    def _flow(self, name, p, text, root, d):
        st = "Flow"
        start = root.find(NS + "start")
        sobj = txt(start, "object") if start is not None else None
        if sobj:
            ttype = txt(start, "triggerType") or ""
            role = "trigger_on" if ttype in ("RecordBeforeSave", "RecordAfterSave", "RecordBeforeDelete") else "read"
            order = txt(root, "triggerOrder") or ""
            self.add(st, name, p, text, sobj, role, "object", sobj,
                     via=f"{ttype}|{txt(start, 'recordTriggerType') or ''}|{order}" if role == "trigger_on" else "")
            for fi in start.iter(NS + "filters"):
                self.add_field(st, name, p, text, sobj, txt(fi, "field"), "condition")
            self.formula_refs(st, name, p, text, sobj, txt(start, "filterFormula"), "condition")
        var_obj: dict[str, str] = {}
        for v in root.iter(NS + "variables"):
            if txt(v, "objectType"):
                var_obj[txt(v, "name")] = txt(v, "objectType")
        for tag in ("recordLookups", "recordCreates", "recordUpdates", "recordDeletes", "dynamicChoiceSets"):
            for el in root.iter(NS + tag):
                if txt(el, "object"):
                    var_obj[txt(el, "name")] = txt(el, "object")
        for lp in root.iter(NS + "loops"):
            coll = txt(lp, "collectionReference")
            if coll and coll in var_obj:
                var_obj[txt(lp, "name")] = var_obj[coll]
        if sobj:
            var_obj["$Record"] = sobj
            var_obj["$Record__Prior"] = sobj

        def resolve_ref(ref: str | None):
            if not ref or "." not in ref:
                return None, None, "low"
            head, rest = ref.split(".", 1)
            o = var_obj.get(head)
            if not o:
                return None, None, "low"
            return self.resolve_path(o, rest) if "." in rest else (o, rest, "high")

        def ref_of(ref: str | None, role: str, via: str = ""):
            o2, f, c = resolve_ref(ref)
            if o2 and f:
                self.add_field(st, name, p, text, o2, f, role, c, needle=ref, via=via)
                self.add_hops(st, name, p, text)
                return f"{o2}.{f}"
            return None

        # 数式の変数・ふつうの変数を通した写し: 名前 → それが読んでいる項目
        res_src: dict[str, set[str]] = {}
        for fm in root.iter(NS + "formulas"):
            fn_ = txt(fm, "name")
            srcs = set()
            for mm in re.finditer(r"\{!([\w$]+)\.([\w.]+)\}", txt(fm, "expression") or ""):
                o2, f2, _ = resolve_ref(f"{mm.group(1)}.{mm.group(2)}")
                self.last_hops = []
                if o2 and f2:
                    srcs.add(f"{o2}.{f2}")
            if fn_ and srcs:
                res_src[fn_] = srcs
        for asg in root.iter(NS + "assignments"):
            for it in asg.iter(NS + "assignmentItems"):
                dst = txt(it, "assignToReference")
                v = first_elref(it)
                if dst and "." not in dst and v:
                    o2, f2, _ = resolve_ref(v)
                    self.last_hops = []
                    if o2 and f2:
                        res_src.setdefault(dst, set()).add(f"{o2}.{f2}")
                    elif v in res_src:
                        res_src.setdefault(dst, set()).update(res_src[v])

        def sources_of(v: str | None) -> set[str]:
            if not v:
                return set()
            if "." in v:
                o2, f2, _ = resolve_ref(v)
                self.last_hops = []
                return {f"{o2}.{f2}"} if o2 and f2 else set()
            return res_src.get(v, set())

        for tag in ("recordLookups", "recordUpdates", "recordCreates", "recordDeletes", "dynamicChoiceSets"):
            for el in root.iter(NS + tag):
                o = txt(el, "object")
                ir = txt(el, "inputReference")
                if not o and ir:
                    o = var_obj.get(ir)   # $Record などの変数ごと更新（object が無い）
                if o:
                    self.add(st, name, p, text, txt(el, "name"), "read" if tag in ("recordLookups", "dynamicChoiceSets") else "write", "object", o)
                for fi in el.iter(NS + "filters"):
                    self.add_field(st, name, p, text, o, txt(fi, "field"), "condition")
                    ref_of(first_elref(fi), "condition")
                for qf in el.iter(NS + "queriedFields"):
                    self.add_field(st, name, p, text, o, qf.text, "read")
                for tagf in ("displayField", "valueField", "sortField"):
                    v = txt(el, tagf)
                    if v and tag == "dynamicChoiceSets":
                        self.add_field(st, name, p, text, o, v, "read")
                for ia in el.iter(NS + "inputAssignments"):
                    fld = txt(ia, "field")
                    ev = first_elref(ia)
                    ref_of(ev, "read")
                    self.add_field(st, name, p, text, o, fld, "write")
                    for src in sources_of(ev):
                        if o and fld and src != f"{o}.{fld}":
                            self.add_field(st, name, p, text, o, fld, "copy_to", "mid", via=src)
                for oa in el.iter(NS + "outputAssignments"):
                    self.add_field(st, name, p, text, o, txt(oa, "field"), "read")
        for asg in root.iter(NS + "assignments"):
            for it in asg.iter(NS + "assignmentItems"):
                ev = first_elref(it)
                ref_of(ev, "read")
                dst = ref_of(txt(it, "assignToReference"), "write")
                if dst:
                    o, f = dst.split(".", 1)
                    for src in sources_of(ev):
                        if src != dst:
                            self.add_field(st, name, p, text, o, f, "copy_to", "mid", via=src)
                    sv = it.find(NS + "value")
                    lit = txt(sv, "stringValue") if sv is not None else None
                    if lit:   # 選択肢の値などを代入（保存前フローの起動条件と結ぶため）
                        self.add(st, name, p, text, lit, "value", "value", f"{dst}={lit}", "mid")
        for m in re.finditer(r"\$Label\.(\w+)", text):
            self.add(st, name, p, text, m.group(0), "read", "component", f"Label:{m.group(1)}")
        for dec in root.iter(NS + "decisions"):
            for cond in dec.iter(NS + "conditions"):
                lv = txt(cond, "leftValueReference")
                ref_of(lv, "condition")
                ref_of(first_elref(cond), "condition")
                sv = cond.find(NS + "rightValue")
                if lv and sv is not None and txt(sv, "stringValue"):
                    o2, f, c = resolve_ref(lv)
                    if o2 and f:
                        self.add(st, name, p, text, txt(sv, "stringValue"), "value", "value", f"{o2}.{f}={txt(sv, 'stringValue')}", "mid")
        for fm in root.iter(NS + "formulas"):
            expr = txt(fm, "expression") or ""
            for m in re.finditer(r"\{!([\w$]+)\.([\w.]+)\}", expr):
                ref_of(f"{m.group(1)}.{m.group(2)}", "read")
        for ac in root.iter(NS + "actionCalls"):
            at, an = txt(ac, "actionType"), txt(ac, "actionName")
            if at == "apex" and an:
                self.add(st, name, p, text, an, "call", "class", an)
            elif at == "emailAlert" and an:
                self.add(st, name, p, text, an, "call", "component", f"EmailAlert:{an}")
            elif at == "quickAction" and an:
                self.add(st, name, p, text, an, "call", "component", f"QuickAction:{an}")
            elif at == "flow" and an:
                self.add(st, name, p, text, an, "call", "flow", an)
        for sf in root.iter(NS + "subflows"):
            self.add(st, name, p, text, txt(sf, "flowName"), "call", "flow", txt(sf, "flowName") or "")
        for m in re.finditer(r"<extensionName>(?:c:|c__)(\w+)</extensionName>", text):
            self.add(st, name, p, text, m.group(0), "call", "component", f"LWC:{m.group(1)}")
        for m in re.finditer(r"\{!([\w$]+)\.([\w.]+)\}", text):
            ref_of(f"{m.group(1)}.{m.group(2)}", "read")

    # ---------- コード ----------
    def scan_code(self, parser) -> None:
        for d, ext, st0 in (("classes", ".cls", "ApexClass"), ("triggers", ".trigger", "ApexTrigger")):
            dp = os.path.join(self.root, d)
            if not os.path.isdir(dp):
                continue
            for fn in os.listdir(dp):
                if not fn.endswith(ext):
                    continue
                p = os.path.join(dp, fn)
                text = read(p)
                name = fn[: -len(ext)]
                st = "ApexTest" if st0 == "ApexClass" and is_test_class(text) else st0
                if st == "ApexTrigger":
                    m = re.search(r"\btrigger\s+\w+\s+on\s+(\w+)\s*\(", text, re.I)
                    if m:
                        self.add(st, name, p, text, m.group(0), "trigger_on", "object", m.group(1))
                if parser is not None:
                    self._soql(st, name, p, text, parser)
                self._dynamic_soql(st, name, p, text)
                self._code_mentions(st, name, p, text)
        for d, st in (("lwc", "LWC"), ("aura", "Aura")):
            dp = os.path.join(self.root, d)
            if not os.path.isdir(dp):
                continue
            for comp in os.listdir(dp):
                cdir = os.path.join(dp, comp)
                if not os.path.isdir(cdir):
                    continue
                for fn in os.listdir(cdir):
                    if fn.endswith((".js", ".html", ".cmp", ".app", ".evt")):
                        p = os.path.join(cdir, fn)
                        text = read(p)
                        for m in re.finditer(r"@salesforce/schema/(\w+)\.([\w.]+)", text):
                            o, f, c = self.resolve_path(m.group(1), m.group(2)) if "." in m.group(2) else (m.group(1), m.group(2), "high")
                            self.add_field(st, comp, p, text, o, f, "read", c, needle=m.group(0))
                            self.add_hops(st, comp, p, text)
                        for m in re.finditer(r"@salesforce/label/c\.(\w+)", text):
                            self.add(st, comp, p, text, m.group(0), "read", "component", f"Label:{m.group(1)}")
                        for m in re.finditer(r"@salesforce/apex/(\w+)\.\w+", text):
                            self.add(st, comp, p, text, m.group(0), "call", "class", m.group(1))
                        for m in re.finditer(r'controller\s*=\s*"(?:\w+\.)?(\w+)"', text):
                            self.add(st, comp, p, text, m.group(0), "call", "class", m.group(1))
                        for m in re.finditer(r"<c-([\w-]+)", text):
                            self.add(st, comp, p, text, m.group(0), "call", "component", "LWC:" + kebab_to_camel(m.group(1)))
                        for m in re.finditer(r"""from\s+['"]c/(\w+)['"]""", text):
                            self.add(st, comp, p, text, m.group(0), "call", "component", "LWC:" + m.group(1))
                        for m in re.finditer(r"<c:(\w+)", text):
                            self.add(st, comp, p, text, m.group(0), "call", "component", "LWC:" + m.group(1))
                        self._code_mentions(st, comp, p, text)
        dp = os.path.join(self.root, "pages")
        if os.path.isdir(dp):
            for fn in os.listdir(dp):
                if fn.endswith(".page"):
                    p = os.path.join(dp, fn)
                    text = read(p)
                    name = fn[:-5]
                    for m in re.finditer(r'(?:controller|extensions)\s*=\s*"([\w,\s.]+)"', text):
                        for c in m.group(1).split(","):
                            self.add("Visualforce", name, p, text, c.strip(), "call", "class", c.strip())
                    self._code_mentions("Visualforce", name, p, text)

    def _soql_body(self, st, name, p, src, body, parent_obj, line) -> None:
        fc = body.child_by_field_name("from_clause")
        if fc is None:
            return
        frm = src[fc.start_byte:fc.end_byte].decode("utf-8", "ignore")
        m = re.search(r"\bFROM\s+(\w+)", frm, re.I)
        if not m:
            return
        name_from = m.group(1)
        if parent_obj:
            obj = self.child_rel.get((parent_obj, name_from))
            if obj is None:
                return
        else:
            obj = name_from
        self.refs.append(Ref(st, name, self.rel(p), line, "read", "object", obj, "high"))
        where = body.child_by_field_name("where_clause")
        stack = list(body.children)
        while stack:
            n = stack.pop()
            if n.type == "subquery":
                for b in n.children:
                    if b.type == "soql_query_body":
                        self._soql_body(st, name, p, src, b, obj, line)
                continue
            if n.type == "field_identifier":
                tok = src[n.start_byte:n.end_byte].decode("utf-8", "ignore")
                o, f, c = self.resolve_path(obj, tok) if "." in tok else (obj, tok, "high")
                role = "condition" if where is not None and where.start_byte <= n.start_byte < where.end_byte else "read"
                if o and f:
                    self.refs.append(Ref(st, name, self.rel(p), line, role, "field", f"{o}.{f}", c))
                    for ho, hf in self.last_hops:
                        self.refs.append(Ref(st, name, self.rel(p), line, "read", "field", f"{ho}.{hf}", "mid"))
                    self.last_hops = []
                continue
            stack.extend(n.children)

    def _soql(self, st, name, p, text, parser) -> None:
        src = text.encode("utf-8")
        try:
            tree = parser.parse(src)
        except Exception:
            return
        for q in iter_type(tree.root_node, "query_expression"):
            for body in q.children:
                if body.type == "soql_query_body":
                    self._soql_body(st, name, p, src, body, None, q.start_point[0] + 1)

    def _dynamic_soql(self, st, name, p, text) -> None:
        """文字列で組み立てる SOQL（`'SELECT … FROM X …'`）。FROM と、SELECT・WHERE に書かれた項目を確度「中」で記録する。
        `'SELECT ' + 項目の一覧を作る関数 + ' FROM X'` のように項目を関数で組み立てるもの（全項目の複製など）は「全項目を読む」とする。"""
        objs_ci = {o.lower(): o for o in self.objects}
        for m in re.finditer(r"'((?:[^'\\]|\\.)*\bFROM\s+(\w+)(?:[^'\\]|\\.)*)'", text, re.I):
            obj = objs_ci.get(m.group(2).lower())
            if not obj:
                continue
            stmt_start = max(text.rfind(";", 0, m.start()), text.rfind("{", 0, m.start())) + 1
            stmt = text[stmt_start:m.end() + 200]
            if not re.search(r"SELECT", text[stmt_start:m.end()], re.I) or re.match(r"\s*SELECT\b", m.group(1), re.I):
                continue   # SELECT と同じ文字列の中なら下の通常の処理で扱う
            line = text.count("\n", 0, m.start()) + 1
            sel = text[stmt_start:m.start()]
            if re.search(r"\+\s*\w+\s*\(", sel) or re.search(r"getGlobalDescribe|fields\.getMap|FieldSet|buildSafeFieldList", text):
                self.refs.append(Ref(st, name, self.rel(p), line, "read_all", "object", obj, "low"))
            else:
                self.refs.append(Ref(st, name, self.rel(p), line, "read", "object", obj, "mid"))
        for m in re.finditer(r"System\.Label\.(\w+)|Label\.(\w+)", text):
            lab = m.group(1) or m.group(2)
            self.add(st, name, p, text, m.group(0), "read", "component", f"Label:{lab}")
        for m in re.finditer(r"'(\s*SELECT\b(?:[^'\\]|\\.)*)'", text, re.I):
            s = m.group(1)
            fm = re.search(r"\bFROM\s+(\w+)", s, re.I)
            line = text.count("\n", 0, m.start()) + 1
            if not fm:
                continue
            obj = fm.group(1)
            if obj not in self.objects and obj.lower() not in {o.lower() for o in self.objects}:
                continue
            self.refs.append(Ref(st, name, self.rel(p), line, "read", "object", obj, "mid"))
            sel = s[: fm.start()]
            rest = s[fm.end():]
            for tok in re.findall(r"\b([A-Za-z]\w*(?:\.\w+)*)\b", re.sub(r"^\s*SELECT", "", sel, flags=re.I)):
                if tok.upper() in ("COUNT", "SUM", "MAX", "MIN", "AVG", "TOLABEL", "FORMAT", "CONVERTCURRENCY"):
                    continue
                o, f, c = self.resolve_path(obj, tok) if "." in tok else (obj, tok, "mid")
                if o and f and (f in self.fields.get(o, {}) or f.endswith("__c") or f in ("Id", "Name")):
                    self.refs.append(Ref(st, name, self.rel(p), line, "read", "field", f"{o}.{f}", "mid"))
            for tok in re.findall(r"\b(\w+__c)\b", rest):
                if tok in self.fields.get(obj, {}):
                    self.refs.append(Ref(st, name, self.rel(p), line, "condition", "field", f"{obj}.{tok}", "mid"))

    def _code_mentions(self, st, name, p, text) -> None:
        """項目名・オブジェクト名・参照名・クラス名・フロー名の出現。項目名は持っているオブジェクトそれぞれに結びつける。"""
        seen: set[str] = set()
        for m in re.finditer(r"\b(\w+__(?:c|r))\b", text):
            tok = m.group(1)
            if tok in seen:
                continue
            seen.add(tok)
            if tok in self.objects:
                self.add(st, name, p, text, tok, "mention", "object", tok, "mid")
                continue
            fld = tok[:-3] + "__c" if tok.endswith("__r") else tok
            owners = self.owners(fld)
            if not owners:
                continue
            conf = "mid" if len(owners) == 1 else "low"
            for o in owners:
                self.add(st, name, p, text, tok, "mention", "field", f"{o}.{fld}", conf)
        for cls in self.classes:
            if cls != name and re.search(r"\b%s\b" % re.escape(cls), text):
                self.add(st, name, p, text, cls, "call", "class", cls, "mid")
        for fl in self.flows:
            if re.search(r"['\"]%s['\"]" % re.escape(fl), text):
                self.add(st, name, p, text, fl, "call", "flow", fl, "mid")


# ---------- 小さな道具 ----------
def is_test_class(text: str) -> bool:
    return re.search(r"@isTest\b|\btestMethod\b", text, re.I) is not None


def mark_test_helpers(refs: list[Ref]) -> list[Ref]:
    """テストからしか呼ばれず、名前に Test を含むクラス（@isTest の付かないテストデータ作成用の部品）もテストとして扱う。
    名前で絞るのは、スケジュール・バッチ等は画面の設定から動かすのでメタデータ上はテストからしか呼ばれないため。
    権限での参照は数えない。どこからも呼ばれないクラスは本番の部品のまま。"""
    tests = {r.src_name for r in refs if r.src_type == "ApexTest"}
    while True:
        callers: dict[str, set[tuple[str, str]]] = {}
        for r in refs:
            if r.tkind == "class" and r.role == "call" and r.target != r.src_name:
                callers.setdefault(r.target, set()).add((r.src_type, r.src_name))
        new = {c for c, s in callers.items()
               if c not in tests and "test" in c.lower() and s and all(t == "ApexTest" for t, _ in s)}
        new &= {r.src_name for r in refs if r.src_type == "ApexClass"}
        if not new:
            return refs
        tests |= new
        refs = [replace(r, src_type="ApexTest") if r.src_type == "ApexClass" and r.src_name in new else r for r in refs]


def drop_ambiguous_mentions(refs: list[Ref]) -> list[Ref]:
    """同じ部品に、同じ項目名への型の分かる参照（出現以外）があれば、その項目名の確度「低」の出現（他のオブジェクトに付けたもの）を捨てる。"""
    typed: dict[tuple[str, str, str], set[str]] = {}
    for r in refs:
        if r.tkind == "field" and r.role != "mention" and "." in r.target:
            o, f = r.target.split(".", 1)
            typed.setdefault((r.src_type, r.src_name, f.lower()), set()).add(o)
    out = []
    for r in refs:
        if r.tkind == "field" and r.role == "mention" and r.conf == "low" and "." in r.target:
            o, f = r.target.split(".", 1)
            objs = typed.get((r.src_type, r.src_name, f.lower()))
            if objs and o not in objs:
                continue
        out.append(r)
    return out


def parse(path: str):
    try:
        return ET.parse(path).getroot()
    except (ET.ParseError, OSError):
        return None


def parse_with_text(path: str):
    text = read(path)
    try:
        return ET.fromstring(text.encode("utf-8")), text
    except ET.ParseError:
        return None, text


def read(path: str) -> str:
    with open(path, encoding="utf-8", errors="ignore") as f:
        return f.read()


def txt(el, tag: str) -> str | None:
    if el is None:
        return None
    x = el.find(NS + tag)
    return x.text.strip() if x is not None and x.text else None


def first_elref(el) -> str | None:
    v = el.find(NS + "value")
    if v is None:
        v = el.find(NS + "rightValue")
    return txt(v, "elementReference") if v is not None else None


def find_line(text: str, needle: str | None) -> int:
    if not needle:
        return 1
    i = text.find(needle)
    return text.count("\n", 0, i) + 1 if i >= 0 else 1


def unquote(s: str) -> str:
    from urllib.parse import unquote as u
    return u(s)


def kebab_to_camel(s: str) -> str:
    parts = s.split("-")
    return parts[0] + "".join(x[:1].upper() + x[1:] for x in parts[1:])


def iter_type(node, t: str) -> Iterable:
    stack = [node]
    while stack:
        n = stack.pop()
        if n.type == t:
            yield n
        stack.extend(reversed(n.children))


def main() -> None:
    root, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    try:
        from tree_sitter_language_pack import get_parser
        parser = get_parser("apex")
    except Exception as e:
        print("Apex の解析部品が使えないので、SOQL は名前の出現だけで扱います:", e)
        parser = None
    ix = Index(root)
    ix.load_objects()
    ix.scan_objects()
    ix.scan_simple()
    ix.scan_code(parser)
    apex_n = 0
    if parser is not None:   # 段階2: Apex の項目の読み書き・DML・写す連鎖
        sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
        from apex_refs import ApexAnalyzer
        an = ApexAnalyzer(ix, parser)
        for d, ext, st0 in (("classes", ".cls", "ApexClass"), ("triggers", ".trigger", "ApexTrigger")):
            dp = os.path.join(root, d)
            if os.path.isdir(dp):
                for fn in os.listdir(dp):
                    if fn.endswith(ext):
                        fp = os.path.join(dp, fn)
                        st = "ApexTest" if st0 == "ApexClass" and is_test_class(read(fp)) else st0
                        rs = an.analyze(st, fn[: -len(ext)], fp)
                        apex_n += len(rs)
                        ix.refs += rs
    ix.refs = drop_ambiguous_mentions(mark_test_helpers(ix.refs))
    uniq = {}
    for r in ix.refs:
        k = (r.src_type, r.src_name, r.role, r.tkind, r.target, r.via)
        if k not in uniq:
            uniq[k] = r
    with open(os.path.join(out, "refs.jsonl"), "w", encoding="utf-8") as f:
        for r in uniq.values():
            f.write(json.dumps(asdict(r), ensure_ascii=False) + "\n")
    with open(os.path.join(out, "fields.json"), "w", encoding="utf-8") as f:
        json.dump(ix.fields, f, ensure_ascii=False)
    with open(os.path.join(out, "objects.json"), "w", encoding="utf-8") as f:
        json.dump(ix.object_labels, f, ensure_ascii=False)
    from collections import Counter
    c = Counter(r.src_type for r in uniq.values())
    print(f"参照 {len(uniq)} 件（重複を除く。うち Apex の読み書き {apex_n}）／オブジェクト {len(ix.objects)}・項目 {sum(len(v) for v in ix.fields.values())}")
    print("  " + ", ".join(f"{k} {v}" for k, v in c.most_common()))


if __name__ == "__main__":
    main()
