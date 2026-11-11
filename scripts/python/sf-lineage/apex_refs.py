"""Apex（クラス・トリガー）の「項目の読み・書き・DML」を、変数の型の宣言から追って作る（試作の段階2）。

Apex は変数の型を宣言する言語なので、ローカル変数・引数・クラスのメンバー・for の変数の宣言を表にして、
`o.Probability = 80` の `o` がどのオブジェクトかを決める。汎用の SObject と動的 SOQL は追わない（未解決として数える）。
使い方: python apex_refs.py <force-app/main/default のパス> <出力フォルダ>
"""
from __future__ import annotations

import json
import os
import re
import sys
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from build_refs import Index, Ref, iter_type, read  # noqa: E402

COLLECTIONS = {"list", "set"}
# どのオブジェクトにもある標準項目（取得したメタデータの項目の一覧には入っていないことが多い）
UNIVERSAL = {"id", "name", "ownerid", "createddate", "createdbyid", "lastmodifieddate", "lastmodifiedbyid",
             "recordtypeid", "isdeleted", "systemmodstamp", "currencyisocode", "lastactivitydate"}


class ApexAnalyzer:
    def __init__(self, ix: Index, parser) -> None:
        self.ix = ix
        self.parser = parser
        self.obj_ci = {o.lower(): o for o in ix.objects}
        self.field_ci = {o: {f.lower(): f for f in fs} for o, fs in ix.fields.items()}
        self.stats = Counter()

    # ---------- 型 ----------
    def obj_name(self, name: str | None) -> str | None:
        return self.obj_ci.get(name.lower()) if name else None

    def type_info(self, node, src) -> tuple[str | None, bool]:
        """型のノード → (オブジェクト名, コレクションか)。"""
        if node is None:
            return None, False
        t = node.type
        if t == "type_identifier":
            return self.obj_name(text(node, src)), False
        if t == "array_type":
            el = node.child_by_field_name("element") or (node.named_children[0] if node.named_children else None)
            o, _ = self.type_info(el, src)
            return o, True
        if t == "generic_type":
            kids = node.named_children
            base = text(kids[0], src).lower() if kids else ""
            args = [c for c in (kids[1].named_children if len(kids) > 1 else [])]
            if base in COLLECTIONS and args:
                o, _ = self.type_info(args[0], src)
                return o, True
            if base == "map" and args:
                o, _ = self.type_info(args[-1], src)
                return o, True
        if t == "scoped_type_identifier":
            return self.obj_name(text(node, src).split(".")[-1]), False
        return None, False

    def canon_field(self, obj: str, field: str) -> str | None:
        return self.field_ci.get(obj, {}).get(field.lower())

    # ---------- 1ファイル ----------
    def analyze(self, st: str, name: str, path: str) -> list[Ref]:
        textv = read(path)
        src = textv.encode("utf-8")
        tree = self.parser.parse(src)
        root = tree.root_node
        rel = self.ix.rel(path)
        refs: list[Ref] = []
        trig_obj = None
        if st == "ApexTrigger":
            m = re.search(r"\btrigger\s+\w+\s+on\s+(\w+)\s*\(", textv, re.I)
            trig_obj = self.obj_name(m.group(1)) if m else None
        # 変数の表（ファイル全体で1つ。同じ名前を別の型で使い回すと後の宣言が勝つので確度は mid）
        sym: dict[str, tuple[str, bool]] = {}
        for decl_type, name_field in (("field_declaration", None), ("local_variable_declaration", None)):
            for d in iter_type(root, decl_type):
                o, coll = self.type_info(d.child_by_field_name("type"), src)
                if not o:
                    continue
                for vd in d.named_children:
                    if vd.type == "variable_declarator":
                        n = vd.child_by_field_name("name")
                        if n is not None:
                            sym[text(n, src).lower()] = (o, coll)
        for fp in iter_type(root, "formal_parameter"):
            o, coll = self.type_info(fp.child_by_field_name("type"), src)
            n = fp.child_by_field_name("name")
            if o and n is not None:
                sym[text(n, src).lower()] = (o, coll)
        for ef in iter_type(root, "enhanced_for_statement"):
            o, coll = self.type_info(ef.child_by_field_name("type"), src)
            n = ef.child_by_field_name("name")
            if o and n is not None:
                sym[text(n, src).lower()] = (o, False)

        def expr_obj(node) -> tuple[str | None, bool]:
            """式 → (オブジェクト, コレクションか)。"""
            if node is None:
                return None, False
            t = node.type
            if t == "identifier":
                return sym.get(text(node, src).lower(), (None, False))
            if t == "this":
                return None, False
            if t == "array_access":
                o, _ = expr_obj(node.child_by_field_name("array"))
                return o, False
            if t == "parenthesized_expression":
                return expr_obj(node.named_children[0]) if node.named_children else (None, False)
            if t == "cast_expression":
                return self.type_info(node.child_by_field_name("type"), src)
            if t == "object_creation_expression":
                return self.type_info(node.child_by_field_name("type"), src)
            if t == "query_expression":
                m = re.search(r"\bFROM\s+(\w+)", text(node, src), re.I)
                return (self.obj_name(m.group(1)) if m else None), True
            if t == "field_access":
                ob = node.child_by_field_name("object")
                fld = text(node.child_by_field_name("field"), src)
                if ob is not None and ob.type == "identifier" and text(ob, src).lower() == "trigger" and fld.lower() in ("new", "old", "newmap", "oldmap"):
                    return trig_obj, True
                o, coll = expr_obj(ob)
                if o and not coll:
                    o2, _, _ = self.ix.resolve_path(o, fld + ".x")
                    return o2, False
                return None, False
            if t == "method_invocation":
                ob = node.child_by_field_name("object")
                mname = text(node.child_by_field_name("name"), src).lower()
                o, coll = expr_obj(ob)
                if o and coll and mname in ("get", "values", "clone", "deepclone"):
                    return o, mname == "values"
                if o and not coll and mname == "clone":
                    return o, False
                return None, False
            return None, False

        def field_of(node) -> str | None:
            """式が単純な項目の読み（b.Y・b.Rel__r.Y）なら `Obj.Field` を返す。"""
            if node is None or node.type != "field_access":
                return None
            chain = []
            cur = node
            while cur is not None and cur.type == "field_access":
                chain.append(text(cur.child_by_field_name("field"), src))
                cur = cur.child_by_field_name("object")
            chain.reverse()
            bo, coll = expr_obj(cur)
            if not bo or coll:
                return None
            o, f, _ = self.ix.resolve_path(bo, ".".join(chain)) if len(chain) > 1 else (bo, chain[0], "high")
            self.ix.last_hops = []
            if not o or not f:
                return None
            cf = self.canon_field(o, f)
            return f"{o}.{cf or f}"

        def add(node, role: str, obj: str, field: str | None, conf: str = "mid", tkind: str = "field"):
            line = node.start_point[0] + 1
            if tkind == "field":
                cf = self.canon_field(obj, field) if field else None
                target = f"{obj}.{cf or field}"
                if cf is None and not (field and (field.lower() in UNIVERSAL or field.lower().endswith("__r") or not self.ix.fields.get(obj))):
                    conf = "low"  # 項目の一覧に無いカスタム項目（変数の取り違えの疑い）
            else:
                target = obj
            refs.append(Ref(st, name, rel, line, role, tkind, target, conf))

        # 項目への代入・読み
        for fa in iter_type(root, "field_access"):
            parent = fa.parent
            if parent is not None and parent.type == "field_access" and parent.child_by_field_name("object") == fa:
                continue  # 連鎖の内側は、外側でまとめて扱う
            chain = []
            cur = fa
            while cur is not None and cur.type == "field_access":
                chain.append(text(cur.child_by_field_name("field"), src))
                cur = cur.child_by_field_name("object")
            chain.reverse()
            base_obj, coll = expr_obj(cur)
            if cur is not None and cur.type == "identifier" and text(cur, src).lower() == "trigger" and chain and chain[0].lower() in ("new", "old", "newmap", "oldmap"):
                continue
            if not base_obj or coll:
                self.stats["unresolved_field_access"] += 1 if (chain and chain[-1].lower().endswith("__c")) else 0
                continue
            o, f, c = self.ix.resolve_path(base_obj, ".".join(chain)) if len(chain) > 1 else (base_obj, chain[0], "high")
            hops = list(self.ix.last_hops)
            self.ix.last_hops = []
            if not o or not f:
                continue
            is_left = parent is not None and parent.type == "assignment_expression" and parent.child_by_field_name("left") == fa
            add(fa, "write" if is_left else "read", o, f, "mid" if c == "high" else c)
            for ho, hf in hops:
                add(fa, "read", ho, hf, "mid")
            if is_left:   # 写す連鎖: a.X = b.Y なら、Y から X へ写した
                right = parent.child_by_field_name("right")
                if right is not None and right.type == "string_literal":   # 選択肢の値などの代入
                    lit = text(right, src).strip("'")
                    cf = self.canon_field(o, f) or f
                    refs.append(Ref(st, name, rel, fa.start_point[0] + 1, "value", "value", f"{o}.{cf}={lit}", "mid"))
                src_field = field_of(right)
                if src_field and src_field != f"{o}.{f}":
                    add(fa, "copy_to", o, f, "mid")
                    refs[-1].via = src_field
            self.stats["field_access"] += 1
        # new Obj(Field = 値)
        for oc in iter_type(root, "object_creation_expression"):
            o, _ = self.type_info(oc.child_by_field_name("type"), src)
            if not o:
                continue
            args = oc.child_by_field_name("arguments")
            for a in (args.named_children if args is not None else []):
                if a.type == "assignment_expression":
                    left = a.child_by_field_name("left")
                    if left is not None and left.type == "identifier":
                        add(a, "write", o, text(left, src), "high")
        # put('Field', v) / get('Field')
        for mi in iter_type(root, "method_invocation"):
            mname = text(mi.child_by_field_name("name"), src).lower()
            if mname not in ("put", "get"):
                continue
            o, coll = expr_obj(mi.child_by_field_name("object"))
            args = mi.child_by_field_name("arguments")
            first = args.named_children[0] if args is not None and args.named_children else None
            if o and not coll and first is not None and first.type == "string_literal":
                add(mi, "write" if mname == "put" else "read", o, text(first, src).strip("'"), "mid")
            elif o and not coll and first is not None:   # 項目名を変数で渡す（どの項目かは不明）
                add(mi, "write_dynamic" if mname == "put" else "read_dynamic", o, None, "low", tkind="object")
            elif first is not None and first.type == "string_literal" and not o:
                self.stats["unresolved_put_get"] += 1
        # DML
        for dml in iter_type(root, "dml_expression"):
            kind = next((text(c, src).lower() for c in dml.children if c.type == "dml_type"), "dml")
            tgt = dml.child_by_field_name("target")
            o, _ = expr_obj(tgt)
            if o:
                add(dml, "write", o, None, "mid", tkind="object")
                refs[-1].role = f"dml_{kind}"
            else:
                self.stats["unresolved_dml"] += 1
        # 動的 SOQL（数えるだけ）
        self.stats["dynamic_soql"] += len(re.findall(r"Database\.query(?:WithBinds)?\s*\(", textv))
        return refs


def text(node, src: bytes) -> str:
    return src[node.start_byte:node.end_byte].decode("utf-8", "ignore") if node is not None else ""


def main() -> None:
    root, out = sys.argv[1], sys.argv[2]
    os.makedirs(out, exist_ok=True)
    from tree_sitter_language_pack import get_parser
    ix = Index(root)
    ix.load_objects()
    an = ApexAnalyzer(ix, get_parser("apex"))
    refs: list[Ref] = []
    for d, ext, st in (("classes", ".cls", "ApexClass"), ("triggers", ".trigger", "ApexTrigger")):
        dp = os.path.join(root, d)
        if not os.path.isdir(dp):
            continue
        for fn in os.listdir(dp):
            if fn.endswith(ext):
                refs += an.analyze(st, fn[: -len(ext)], os.path.join(dp, fn))
    uniq = {}
    for r in refs:
        uniq.setdefault((r.src_type, r.src_name, r.role, r.tkind, r.target, r.line), r)
    from dataclasses import asdict
    with open(os.path.join(out, "refs_apex.jsonl"), "w", encoding="utf-8") as f:
        for r in uniq.values():
            f.write(json.dumps(asdict(r), ensure_ascii=False) + "\n")
    roles = Counter(r.role for r in uniq.values())
    confs = Counter(r.conf for r in uniq.values())
    print(f"Apex の参照 {len(uniq)} 件: " + ", ".join(f"{k} {v}" for k, v in roles.most_common()))
    print("確度: " + ", ".join(f"{k} {v}" for k, v in confs.most_common()))
    print("追えなかったもの: " + ", ".join(f"{k} {v}" for k, v in an.stats.items() if k.startswith(("unresolved", "dynamic"))))


if __name__ == "__main__":
    main()
