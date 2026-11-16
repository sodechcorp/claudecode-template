"""画面の部品が、Apex の取っていない項目を表示していないかの突き合わせ（ファイルを読むだけ。組織には触らない）。

  python scripts/python/sf-lineage/contract_check.py <メタデータのルート> [Apex クラス名 ...]

- <メタデータのルート>: classes/・aura/・lwc/・pages/・components/ を持つフォルダ（force-app/main/default、
  または retrieve した unpackaged のフォルダ）。リリースの確認では「デプロイする資材のとおりの組み合わせ」
  （資材の Apex・部品は資材の版、資材に入れない部品・controller は本番の版）を1つのフォルダに置いてから渡す
- クラス名は、画面の部品の controller になる Apex（@AuraEnabled・@RemoteAction・Visualforce の controller）を渡す。
  SOQL をサービスのクラスに分けている場合は、呼び出し元の controller のクラスを渡す。省くとルートの全クラス

判定の作り（手順と判定の決まり: .claude/templates/common/consumer-contract-check.md）:
- Apex 側（メソッドごと）: 変数の出どころを「= [SELECT …]」「.addAll(…)」「for (型 a : …) の中の .add(a)」「= 別の変数」ごとに持つ。
  SOQL 以外から入る経路（サービスの戻り値・ラッパー・Database.query 等）がある変数は「一部の経路を追えない」。
  画面に返すものは .put('キー', …)・new Map<…>{'キー' => …}・ラッパーの項目（r.opp = …）・Map で返さないメソッドの戻り値。
  子問い合わせは「リレーション名.項目」、集計・別名は別名、toLabel()・format()・convertCurrency() は中の項目、
  FIELDS(…) は項目を決められないものとして扱う
- Aura 側: controller="{クラス}" の .cmp・.app の中の式（{!…}・{#…}）を全部たどり、項目らしい参照
  （カスタムは __ を含み、標準は大文字で始まる名前）を、必ず「判定する」か「要目視に出す」かのどちらかにする。
  属性は同じ名前の Map のキーか、JS の component.set('v.属性', 結果.キー) で結ぶ。{!v.A.キー.項目} は途中のキー、
  繰り返しの変数・子コンポーネントに渡した値（行・一覧・参照先のレコード）は渡した元の出どころで判定する。
  datatable 等の data="{!…}" は列の fieldName（JS）を照らす。LWC の子は .html の {属性.項目} を照らす
- NG: どの経路の SOQL にも無い項目を表示している（Id は SOQL が必ず返すので除く。大文字・小文字は区別しない）
- 要目視（黙って OK にしない）: 出どころを追えない・一部の経路を追えない・属性と結ぶ Map のキーが無い・
  経路（SOQL）によって項目が違い一部に無い・子コンポーネントがルートに無い・LWC（Apex を直接 import）と Visualforce・
  使う部品がルートに1つも無いクラス
- 見ない: 項目らしくない名前（小文字で始まり __ を含まない。JS で足した値・length 等）、JS の中で組み立てる表示
終了コード: 0 = NG なし、1 = NG あり、2 = 指定したクラス・classes/ が無い、3 = 読めないファイル・処理の失敗
"""
from __future__ import annotations

import glob
import os
import re
import sys

STRIP_FUNCS = {"tolabel", "format", "convertcurrency"}
NOT_METHODS = {"if", "for", "while", "switch", "catch", "when", "do", "try", "else", "return", "new", "on"}
PRIMITIVE_TYPES = {"string", "boolean", "integer", "decimal", "double", "long", "date", "datetime", "id", "time"}
REF = r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*"
PATH = re.compile(r"(?<![\w.$])([A-Za-z_]\w*(?:\s*\[\s*\d+\s*\])?(?:\s*\.\s*[A-Za-z_]\w*(?:\s*\[\s*\d+\s*\])?)+)")
TOKEN = re.compile(r"<(/?)(\w+):(\w+)((?:[^>\"']|\"[^\"]*\"|'[^']*')*?)(/?)>|\{[!#]((?:[^{}'\"]|'[^']*'|\"[^\"]*\")*)\}", re.S)
ATTR = re.compile(r"(\w+)\s*=\s*(?:\"([^\"]*)\"|'([^']*)')")
WILD = "*"


class ReadError(Exception):
    pass


def read(path: str) -> str:
    with open(path, "rb") as f:
        b = f.read()
    if b.startswith((b"\xff\xfe", b"\xfe\xff")) or b"\x00" in b[:4096]:
        raise ReadError(f"UTF-16 などで読めないファイル: {path}")
    return b.decode("utf-8-sig", errors="replace")


# ---------------------------------------------------------------- Apex
def strip_comments(text: str) -> str:
    """// と /* */ を空白にする（文字列リテラルの中は残す。行番号と長さを保つ）。"""
    def repl(m: re.Match) -> str:
        return m.group(1) if m.group(1) else re.sub(r"[^\n]", " ", m.group(0))
    return re.sub(r"('(?:\\.|[^'\\\n])*')|//[^\n]*|/\*.*?\*/", repl, text, flags=re.S)


def blank_strings(text: str) -> str:
    """文字列リテラルの中身を空白にする（長さは保つ）。"""
    return re.sub(r"'(?:\\.|[^'\\\n])*'", lambda m: "'" + " " * (len(m.group(0)) - 2) + "'", text)


def soql_spans(text: str) -> dict[int, tuple[int, str]]:
    """[SELECT ...] の開始位置 → (終了位置, 中身)。"""
    spans = {}
    for m in re.finditer(r"\[\s*SELECT\b", text, re.I):
        depth, i = 0, m.start()
        while i < len(text):
            if text[i] == "[":
                depth += 1
            elif text[i] == "]":
                depth -= 1
                if depth == 0:
                    break
            i += 1
        spans[m.start()] = (i + 1, text[m.start() + 1:i])
    return spans


def split_top(s: str) -> list[str]:
    out, depth, cur = [], 0, []
    for ch in s:
        depth += {"(": 1, ")": -1}.get(ch, 0)
        if ch == "," and depth == 0:
            out.append("".join(cur))
            cur = []
        else:
            cur.append(ch)
    out.append("".join(cur))
    return out


def select_fields(soql: str) -> frozenset[str]:
    """SELECT の項目（小文字の項目パス）。WILD を含むものは項目を決められない（FIELDS()）。"""
    m = re.match(r"\s*SELECT\s+", soql, re.I)
    if not m:
        return frozenset()
    body, depth, end = soql[m.end():], 0, None
    for i, ch in enumerate(body):
        depth += {"(": 1, ")": -1}.get(ch, 0)
        if depth == 0 and re.match(r"\sFROM\s", body[i:i + 6], re.I):
            end = i
            break
    fields: set[str] = set()
    for item in split_top(body[:end] if end is not None else body):
        item = item.strip()
        if not item:
            continue
        if item.startswith("("):   # 子問い合わせ
            sub = item.strip("() \n\t")
            rel = re.search(r"\sFROM\s+(\w+)", " " + sub, re.I)
            if rel:
                r = rel.group(1).lower()
                fields.add(r)
                fields.update(f"{r}.{f}" for f in select_fields(sub))
            continue
        tm = re.match(r"TYPEOF\s+(\w+)", item, re.I)
        if tm:   # 多態の参照: 中の項目は種類ごとに違うので、参照先の下は全部あるものと見なす
            fields.update({tm.group(1).lower(), tm.group(1).lower() + "." + WILD})
            continue
        fm = re.match(r"(\w+)\s*\(\s*([\w.]+)\s*\)\s*(\w+)?$", item)
        if fm:
            fn = fm.group(1).lower()
            if fn == "fields":
                fields.add(WILD)
            elif fn in STRIP_FUNCS:
                fields.add(fm.group(2).lower())
            if fm.group(3):
                fields.add(fm.group(3).lower())
            continue
        toks = item.split()
        fields.add(toks[0].lower())
        if len(toks) == 2:   # 別名（GROUP BY の項目）
            fields.add(toks[1].lower())
    return frozenset(fields)


def body_end(text: str, open_brace: int) -> int:
    depth, i = 1, open_brace + 1
    while depth and i < len(text):
        depth += {"{": 1, "}": -1}.get(text[i], 0)
        i += 1
    return i


def methods(text: str) -> list[tuple[str, int, int]]:
    """メソッド（コンストラクタを含む）の (名前, 本体の開始, 本体の終了)。入れ子のものは除く。"""
    found = []
    for m in re.finditer(r"\b(\w+)\s*\(([^()]*(?:\([^()]*\)[^()]*)*)\)\s*(?:throws\s+[\w.,\s]+)?\{", text):
        name = m.group(1)
        if name.lower() in NOT_METHODS:
            continue
        pre = text[max(0, m.start() - 200):m.start()].rstrip()
        prev = re.search(r"(\w+)\s*$", pre)
        if not re.search(r"[\w>\]]$", pre) or (prev and prev.group(1).lower() in NOT_METHODS):
            continue
        found.append((m.start(), m.end(), body_end(text, m.end() - 1), name))
    out, last_end = [], -1
    for start, b_start, end, name in sorted(found):
        if start >= last_end:
            out.append((name, b_start, end))
            last_end = end
    return out


def rhs_until(text: str, pos: int, stops: str = ";") -> str:
    depth, i = 0, pos
    while i < len(text):
        ch = text[i]
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            if depth == 0:
                break
            depth -= 1
        elif ch in stops and depth == 0:
            break
        i += 1
    return text[pos:i].strip()


class Src:
    """変数・キーの出どころ: SOQL ごとの項目の集合と、追えない経路があるか。"""
    def __init__(self):
        self.sets: set[frozenset[str]] = set()
        self.partial = False


def classify(text: str, pos: int, spans) -> tuple[str, object]:
    """pos から始まる式の出どころ: ('sets', fs) / ('var', 名前) / ('empty', None) / ('other', None)。"""
    if text[pos:pos + 1] == "[" and pos in spans:
        return "sets", select_fields(spans[pos][1])
    rhs = rhs_until(text, pos, ";,")
    if not rhs or re.fullmatch(r"null|new\s+[\w.<>,\s\[\]]+\(\s*\)|new\s+[\w.<>,\s\[\]]+\{\s*\}", rhs, re.I):
        return "empty", None
    vm = re.fullmatch(r"(\w+)(?:\s*\[\s*\w+\s*\])?", rhs)
    if vm:
        return "var", vm.group(1).lower()
    return "other", None


def analyze(body: str, orig: str):
    """1つのメソッドを読み、(キー → Src, ラッパーの項目 → Src, Map で返さない戻り値の Src) を返す。"""
    spans = soql_spans(body)
    srcs: dict[str, list] = {}
    wrap_srcs: dict[str, list] = {}
    for m in re.finditer(r"(?<![\w.])(\w+)(?:\.(\w+))?\s*=(?![=>])\s*", body):
        if m.group(1).lower() in ("if", "while", "return"):
            continue
        kind = classify(body, m.end(), spans)
        if kind[0] == "empty":
            continue
        if m.group(2):   # obj.field = …（ラッパーの項目。SOQL か変数から入るものだけ）
            if kind[0] in ("sets", "var"):
                wrap_srcs.setdefault(m.group(2).lower(), []).append(kind)
        else:
            srcs.setdefault(m.group(1).lower(), []).append(kind)
    loop_adds = set()
    for m in re.finditer(r"for\s*\(\s*[\w.<>, ]+?\s+(\w+)\s*:\s*", body):
        rest = m.end()
        if body[rest:rest + 1] == "[" and rest in spans:
            src, after = ("sets", select_fields(spans[rest][1])), spans[rest][0]
        else:
            im = re.match(r"(\w+)\s*", body[rest:])
            if not im:
                continue
            src, after = ("var", im.group(1).lower()), rest + im.end()
        cm = re.match(r"\s*\)\s*\{", body[after:])
        if not cm:
            continue
        b0 = after + cm.end()
        b1 = body_end(body, b0 - 1)
        for a in re.finditer(r"(\w+)\.add\(\s*" + re.escape(m.group(1)) + r"\s*\)", body[b0:b1]):
            srcs.setdefault(a.group(1).lower(), []).append(src)
            loop_adds.add(b0 + a.start())
    for m in re.finditer(r"(\w+)\.(addAll|add)\(\s*", body):
        if m.group(2) == "add" and m.start() in loop_adds:
            continue
        srcs.setdefault(m.group(1).lower(), []).append(classify(body, m.end(), spans))

    resolved: dict[str, Src] = {}

    def resolve_var(name: str, seen=()) -> Src:
        if name in resolved:
            return resolved[name]
        s = Src()
        if name in seen:
            return s
        if name not in srcs:
            s.partial = True   # 引数・外から来る変数
        for kind, val in srcs.get(name, []):
            if kind == "sets":
                s.sets.add(val)
            elif kind == "var":
                o = resolve_var(val, seen + (name,))
                s.sets |= o.sets
                s.partial |= o.partial or not o.sets
            elif kind == "other":
                s.partial = True
        resolved[name] = s
        return s

    def src_at(pos: int) -> Src:
        kind = classify(body, pos, spans)
        if kind[0] == "sets":
            s = Src()
            s.sets.add(kind[1])
            return s
        if kind[0] == "var":
            return resolve_var(kind[1])
        s = Src()
        s.partial = True
        return s

    keys: dict[str, Src] = {}
    for m in list(re.finditer(r"\.put\(\s*'(\w+)'\s*,\s*", orig)) + list(re.finditer(r"'(\w+)'\s*=>\s*", orig)):
        s = src_at(m.end())
        k = keys.setdefault(m.group(1).lower(), Src())
        k.sets |= s.sets
        k.partial |= s.partial or not s.sets
    wraps: dict[str, Src] = {}
    for f, kinds in wrap_srcs.items():
        w = wraps.setdefault(f, Src())
        for kind, val in kinds:
            if kind == "sets":
                w.sets.add(val)
            else:
                o = resolve_var(val)
                w.sets |= o.sets
                w.partial |= o.partial
    direct = None
    rm = re.search(r"\breturn\s+(?=\S)", body)
    if rm and not keys:
        s = src_at(rm.end())
        if s.sets:
            direct = s
    return keys, wraps, direct


class ClassInfo:
    def __init__(self, cls_text: str):
        orig = strip_comments(cls_text)
        text = blank_strings(orig)
        self.keys: dict[str, Src] = {}
        self.wraps: dict[str, Src] = {}
        self.direct: dict[str, Src] = {}
        for name, start, end in methods(text) or [("(class)", 0, len(text))]:
            keys, wraps, direct = analyze(text[start:end], orig[start:end])
            for d, src in ((self.keys, keys), (self.wraps, wraps)):
                for k, s in src.items():
                    t = d.setdefault(k, Src())
                    t.sets |= s.sets
                    t.partial |= s.partial
            if direct:
                self.direct[name] = direct

    def direct_note(self) -> str:
        return "".join(f"。Map で返さないメソッド {m} の取得項目: {', '.join(sorted(f for s in d.sets for f in s))}"
                       for m, d in self.direct.items())


# ---------------------------------------------------------------- 判定
def field_like(seg: str) -> bool:
    """Salesforce の項目らしいか（カスタムは __ を含み、標準は大文字で始まる）。"""
    return "__" in seg or seg[:1].isupper()


def has(ref: str, fields: frozenset[str]) -> bool:
    r = ref.lower()
    if r == "id" or any(f.endswith("." + WILD) and r.startswith(f[:-1]) for f in fields):
        return True
    if r.endswith(".id") and has(r[:-3], fields):
        return True
    return any(f == r or f.startswith(r + ".") for f in fields)


class Binding:
    """部品の中の名前（属性・繰り返しの変数・子の属性）が指す出どころ。"""
    def __init__(self, label: str, src: Src | None = None, prefix: tuple = (), why: str | None = None, map_like=False):
        self.label, self.src, self.prefix, self.why, self.map_like = label, src, prefix, why, map_like


class Report:
    def __init__(self):
        self.ng: dict[tuple, set] = {}
        self.manual: dict[tuple, set] = {}
        self.lines: list[str] = []

    def judge(self, where: str, b: Binding, path: str, cname: str):
        if b.src is None or not b.src.sets:
            self.manual.setdefault((where, cname, b.why or "出どころを追えない"), set()).add(path)
            return
        sets = b.src.sets
        hit = [has(path, s) for s in sets]
        wild = any(WILD in s for s in sets)
        if not any(hit):
            if wild:
                self.manual.setdefault((where, cname, f"{b.label}: FIELDS() の SOQL があり項目を決められない"), set()).add(path)
            else:
                self.ng.setdefault((where, cname, b.label), set()).add(path)
        elif not all(hit):
            self.manual.setdefault((where, cname, f"{b.label}: SOQL ごとに項目が違い、一部の SOQL に無い（どの場合に表示するかを目視）"), set()).add(path)
        if b.src.partial:
            self.manual.setdefault((where, cname, f"{b.label}: 一部の経路では出どころを追えない（サービスの戻り値・ラッパー等）"), set()).add(path)


def paths_in(expr: str) -> list[list[str]]:
    expr = re.sub(r"'[^']*'|\"[^\"]*\"", " ", expr)
    out = []
    for m in PATH.finditer(expr):
        p = re.sub(r"\s+|\[\s*\d+\s*\]", "", m.group(1))
        out.append(p.split("."))
    return out


def single_path(expr: str) -> list[str] | None:
    m = re.fullmatch(r"\s*\{[!#]\s*([A-Za-z_]\w*(?:\s*\[\s*\d+\s*\])?(?:\s*\.\s*[A-Za-z_]\w*(?:\s*\[\s*\d+\s*\])?)*)\s*\}\s*", expr)
    return re.sub(r"\s+|\[\s*\d+\s*\]", "", m.group(1)).split(".") if m else None


class Checker:
    def __init__(self, root: str, cname: str, info: ClassInfo, rep: Report):
        self.root, self.cname, self.info, self.rep = root, cname, info, rep
        self.aura_dirs = {os.path.basename(d).lower(): d for d in glob.glob(os.path.join(root, "aura", "*")) if os.path.isdir(d)}
        self.lwc_dirs = {os.path.basename(d).lower(): d for d in glob.glob(os.path.join(root, "lwc", "*")) if os.path.isdir(d)}
        self.stack: list[str] = []   # 今たどっている子の並び（同じ部品の入れ子の繰り返しだけを止める）

    def key_binding(self, k: str, note: str = "") -> Binding:
        return Binding(f"Map のキー {k}{note}", self.info.keys[k.lower()])

    def resolve(self, segs: list[str], scope, attrs: dict, top: bool):
        """(Binding, 残りのパス) か None（この Apex と関係ない）。"""
        if segs[0] == "v":
            if len(segs) < 2:
                return None
            attr, rest = segs[1].lower(), segs[2:]
            ab = attrs.get(attr)
            if ab is not None and not ab.map_like:
                return ab, rest
            if top and attr in self.ignored:
                return None
            if top and ab is None and attr in self.info.keys:
                return self.key_binding(attr), rest
            if top or ab is not None:
                for i, s in enumerate(rest):
                    if s.lower() in self.info.keys:
                        return self.key_binding(s), rest[i + 1:]
                    if s.lower() in self.info.wraps:
                        return Binding(f"ラッパーの項目 {s}", self.info.wraps[s.lower()]), rest[i + 1:]
            if ab is not None:
                return ab, rest
            if top:
                return Binding(f"属性 {segs[1]}", None, why=f"属性 {segs[1]} と結ぶ Map のキーが無い{self.info.direct_note()}", map_like=True), rest
            return None
        for var, b in reversed(scope):
            if var == segs[0]:
                return (b, segs[1:]) if b is not None else None
        return None

    def ref(self, where: str, segs: list[str], scope, attrs, top):
        r = self.resolve(segs, scope, attrs, top)
        if r is None:
            return
        b, rest = r
        while rest and not field_like(rest[-1]):
            rest = rest[:-1]
        if not rest or not all(field_like(s) for s in rest):
            return
        self.rep.judge(where, b, ".".join(list(b.prefix) + rest), self.cname)

    def derive(self, b: Binding, rest: list[str], top: bool, what: str) -> Binding | None:
        """値（一覧・1件・参照先）を渡したときの、受け取る側の出どころ。"""
        path = list(b.prefix) + rest
        if b.src is None or not b.src.sets or not rest:
            return Binding(b.label, b.src, tuple(path), b.why, b.map_like)
        return Binding(b.label, b.src, tuple(path), b.why)

    def items_binding(self, items_val: str, scope, attrs, top) -> Binding | None:
        segs = single_path(items_val)
        r = self.resolve(segs, scope, attrs, top) if segs else None
        if r is None:
            return Binding("items", None, why=f"繰り返しの items（{items_val}）を追えない") if top else None
        b, rest = r
        if b.src is None or not b.src.sets:
            return Binding(b.label, b.src, (), b.why or "出どころを追えない")
        path = ".".join(list(b.prefix) + rest).lower()
        if not path:
            return Binding(b.label, b.src, (), b.why)
        child = Src()
        child.partial = b.src.partial
        for s in b.src.sets:
            child.sets.add(frozenset(f[len(path) + 1:] for f in s if f.startswith(path + ".")))
        if not any(child.sets):
            return Binding(f"{b.label} の {path}", None, why=f"子リレーション {path} の項目を SOQL から追えない")
        return Binding(f"{b.label} の子リレーション {path}", child)

    def check(self, path: str, attrs: dict, top: bool, depth: int = 0, where: str = ""):
        key = path.lower()
        name = os.path.basename(path)
        if key in self.stack or depth > 3:
            why = "子コンポーネントが自分を入れ子にしている" if key in self.stack else "子コンポーネントの入れ子が4段より深く、ここから先を追っていない"
            self.rep.manual.setdefault((where or name, self.cname, f"{name}: {why}"), set()).update(attrs)
            return
        self.stack.append(key)
        try:
            self._check(path, name, attrs, top, depth)
        finally:
            self.stack.pop()

    def _check(self, path: str, name: str, attrs: dict, top: bool, depth: int):
        t = re.sub(r"<!--.*?-->", lambda m: re.sub(r"[^\n]", " ", m.group(0)), read(path), flags=re.S)
        bundle = os.path.dirname(path)
        js = " ".join(read(p) for p in glob.glob(os.path.join(bundle, "*.js")) if os.path.isfile(p))
        if top:
            self.ignored = set()
            for m in re.finditer(r"<aura:attribute\b((?:[^>\"']|\"[^\"]*\"|'[^']*')*)>", t):
                a = {x[0].lower(): (x[1] or x[2]) for x in ATTR.findall(m.group(1))}
                if a.get("type", "").lower() in PRIMITIVE_TYPES and a.get("name"):
                    self.ignored.add(a["name"].lower())
            for m in re.finditer(r"target(?:Fields|Record)\s*=\s*[\"']\{[!#]\s*v\.(\w+)", t):
                self.ignored.add(m.group(1).lower())
            attrs = dict(attrs)
            for m in re.finditer(r"\.set\(\s*['\"]v\.(\w+)['\"]\s*,\s*([^;]+?)\)\s*;", js):
                attr, rhs = m.group(1).lower(), m.group(2).strip()
                km = re.search(r"(?:\.|\[\s*['\"])(\w+)['\"]?\s*\]?\s*$", rhs)
                if km and km.group(1).lower() in self.info.keys and km.group(1).lower() != attr:
                    attrs[attr] = self.key_binding(km.group(1), f"（JS で v.{m.group(1)} に入れる）")
                elif rhs.endswith("getReturnValue()") and self.info.direct and not self.info.keys:
                    if len(self.info.direct) == 1:
                        mname, src = next(iter(self.info.direct.items()))
                        attrs[attr] = Binding(f"{mname} の戻り値（JS で v.{m.group(1)} に入れる）", src)
                    else:
                        attrs[attr] = Binding(f"属性 {m.group(1)}", None, why="Map で返さないメソッドが複数あり、どれを入れるか追えない")
        scope: list[tuple[str, Binding]] = []
        for m in TOKEN.finditer(t):
            line = t.count("\n", 0, m.start()) + 1
            where = f"{name}:{line}"
            if m.group(6) is not None:   # 式
                for segs in paths_in(m.group(6)):
                    self.ref(where, segs, scope, attrs, top)
                continue
            closing, ns, tag, attr_text, selfclose = m.group(1), m.group(2).lower(), m.group(3), m.group(4), m.group(5)
            if closing:
                if ns == "aura" and tag.lower() == "iteration" and scope:
                    scope.pop()
                continue
            values = {a[0]: (a[1] or a[2]) for a in ATTR.findall(attr_text)}   # findall は使わなかった側を空文字で返す
            is_iter = ns == "aura" and tag.lower() == "iteration"
            for an, av in values.items():
                if is_iter and an.lower() in ("items", "var"):
                    continue
                for em in re.finditer(r"\{[!#]((?:[^{}'\"]|'[^']*'|\"[^\"]*\")*)\}", av):
                    for segs in paths_in(em.group(1)):
                        self.ref(where, segs, scope, attrs, top)
            if is_iter:
                var = values.get("var")
                items = values.get("items", "")
                b = self.items_binding(items, scope, attrs, top) if var else None
                if not selfclose:
                    scope.append((var or "", b))   # b が None の変数（この Apex と結ばない繰り返し）は判定しない
                continue
            if "data" in values and ns != "c":   # datatable 等
                self.datatable(where, ns, tag, values["data"], js, scope, attrs, top)
            if ns == "c":
                self.child(where, tag, values, scope, attrs, top, depth)

    def datatable(self, where, ns, tag, val, js, scope, attrs, top):
        segs = single_path(val)
        r = self.resolve(segs, scope, attrs, top) if segs else None
        if r is None:
            if top:
                self.rep.manual.setdefault((where, self.cname, f"{ns}:{tag} の data（{val}）を追えない"), set()).add("列")
            return
        b, rest = r
        cols = sorted(set(re.findall(r"fieldName\s*:\s*['\"](" + REF + ")['\"]", js)))
        if not cols:
            self.rep.manual.setdefault((where, self.cname, f"{ns}:{tag} の列の fieldName が JS に見つからない"), set()).add("列")
            return
        rb = self.derive(b, rest, top, "data")
        for c in cols:
            if all(field_like(s) for s in c.split(".")):
                self.rep.judge(where + f"（{ns}:{tag} の列）", rb, ".".join(list(rb.prefix) + c.split(".")), self.cname)

    def child(self, where, tag, values, scope, attrs, top, depth):
        passed = {}
        for an, av in values.items():
            segs = single_path(av)
            if not segs:
                continue
            r = self.resolve(segs, scope, attrs, top)
            if r is None:
                continue
            b, rest = r
            passed[an.lower()] = self.derive(b, rest, top, an)
        if not passed:
            return
        low = tag.lower()
        if low in self.aura_dirs:
            p = os.path.join(self.aura_dirs[low], os.path.basename(self.aura_dirs[low]) + ".cmp")
            if os.path.isfile(p):
                self.check(p, passed, False, depth + 1, where)
                return
        if low in self.lwc_dirs:
            d = self.lwc_dirs[low]
            for h in glob.glob(os.path.join(d, "*.html")):
                ht = read(h)
                for an, b in passed.items():
                    for pm in re.finditer(r"\{\s*" + re.escape(an) + r"\.(" + REF + r")\s*\}", ht, re.I):
                        rest = pm.group(1).split(".")
                        if all(field_like(s) for s in rest):
                            ln = ht.count("\n", 0, pm.start()) + 1
                            self.rep.judge(f"{where} → LWC {os.path.basename(h)}:{ln}", b, ".".join(list(b.prefix) + rest), self.cname)
            jst = " ".join(read(p) for p in glob.glob(os.path.join(d, "*.js")) if os.path.isfile(p))
            for an in passed:
                if re.search(r"this\." + re.escape(an) + r"\b", jst, re.I):
                    self.rep.manual.setdefault((where, self.cname, f"LWC {os.path.basename(d)} の JS でも {an} を使う（JS の中の項目を目視）"), set()).add(an)
            return
        self.rep.manual.setdefault((where, self.cname, f"子コンポーネント c:{tag} がルートに無い（渡している属性の表示項目を目視）"), set()).update(passed)


def main() -> int:
    if len(sys.argv) < 2 or sys.argv[1] in ("-h", "--help"):
        print(__doc__)
        return 0
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except (AttributeError, ValueError):
        pass
    root = sys.argv[1]
    if not os.path.isdir(os.path.join(root, "classes")):
        print(f"[ERROR] {root} に classes/ が無い（ルートの指定を確かめる）")
        return 2
    wanted = {c.lower() for c in sys.argv[2:]}
    classes = {os.path.basename(p)[:-4]: p for p in glob.glob(os.path.join(root, "classes", "*.cls")) if os.path.isfile(p)}
    missing = sorted(c for c in wanted if c not in {n.lower() for n in classes})
    if missing:
        print(f"[ERROR] {root}/classes に無いクラス: {', '.join(missing)}（資材に無い controller は本番から取って置く）")
        return 2
    try:
        comps = [p for pat in ("aura/*/*.cmp", "aura/*/*.app") for p in glob.glob(os.path.join(root, pat)) if os.path.isfile(p)]
        comp_text = {p: read(p) for p in comps}
        lwc_js = {p: read(p) for p in glob.glob(os.path.join(root, "lwc", "*", "*.js")) if os.path.isfile(p)}
        vf = {p: read(p) for pat in ("pages/*.page", "components/*.component") for p in glob.glob(os.path.join(root, pat)) if os.path.isfile(p)}
        rep, checked = Report(), []
        for cname, cpath in sorted(classes.items()):
            if wanted and cname.lower() not in wanted:
                continue
            info = ClassInfo(read(cpath))
            users = [0, 0, 0]
            ck = Checker(root, cname, info, rep)
            for path, t in comp_text.items():
                if re.search(r"controller\s*=\s*[\"'](?:\w+\.)?" + re.escape(cname) + r"[\"']", t, re.I):
                    users[0] += 1
                    ck.check(path, {}, True)
            for path, t in lwc_js.items():
                if f"@salesforce/apex/{cname}." in t:
                    users[1] += 1
                    rep.lines.append(f"LWC {os.path.basename(os.path.dirname(path))}: {cname} を import（.html の項目・.js の record.項目・getFieldValue を目視で照合）")
            for path, t in vf.items():
                if re.search(r"(?:controller|extensions)\s*=\s*[\"'][^\"']*\b" + re.escape(cname) + r"\b", t, re.I):
                    users[2] += 1
                    rep.lines.append(f"Visualforce {os.path.basename(path)}: {cname} を使う（{{!…}} の項目を目視で照合）")
            partial = sum(1 for s in info.keys.values() if s.partial)
            checked.append(f"{cname}（画面に返すキー {len(info.keys)} 件・うち追えない経路あり {partial} 件／使う部品 Aura {users[0]}・LWC {users[1]}・VF {users[2]}）")
            if wanted and not any(users):
                rep.lines.append(f"{cname}: このクラスを使う部品がルートに1つも無い（使う部品の置き忘れか、サービスのクラスなら呼び出し元の controller のクラスを渡す）")
    except ReadError as e:
        print(f"[ERROR] {e}")
        return 3
    except Exception as e:   # noqa: BLE001  落ちたことを NG と区別する
        print(f"[ERROR] 処理に失敗した: {type(e).__name__}: {e}")
        return 3

    print("== 対象の Apex: " + ("、".join(checked) if checked else "なし"))
    print("== NG（取っていない項目を表示）")
    ng = [f"{w} ← {c}（{label}）: 取っていない項目を表示 {', '.join(sorted(p))}" for (w, c, label), p in rep.ng.items()]
    print("\n".join("  " + x for x in ng) if ng else "  なし")
    print("== 要目視")
    manual = [f"{w} ← {c}: {why}（{', '.join(sorted(p))}）" for (w, c, why), p in rep.manual.items()] + rep.lines
    print("\n".join("  " + x for x in manual) if manual else "  なし")
    return 1 if ng else 0


if __name__ == "__main__":
    sys.exit(main())
