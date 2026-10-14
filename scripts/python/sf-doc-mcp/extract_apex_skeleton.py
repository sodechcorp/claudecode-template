#!/usr/bin/env python3
"""
extract_apex_skeleton.py

Apex ソース (.cls) を静的解析し、generate_feature_design.py 互換の
スケルトン JSON を生成する。

structural フィールド（node_type / calls / object_ref / sub_steps / branch）を
機械的に確定し、エージェントは title / detail / overview のみ補完する。

制限事項:
  - ネストされた制御構造は深さに関係なく認識するが、内側ブロックは統合される
  - 動的 SOQL（文字列結合）の FROM 句は検出精度が下がる場合がある
  - ジェネリクスを含む複雑な型は一部不完全に解析される

Usage:
  python extract_apex_skeleton.py --input MyClass.cls [--output skeleton.json]
  python extract_apex_skeleton.py --input MyClass.cls  # stdout
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path


# ─── 正規表現 ────────────────────────────────────────────────────────────────

_RE_CLASS = re.compile(
    r'(?:public|global)\s+(?:with\s+sharing\s+|without\s+sharing\s+)?'
    r'(?:virtual\s+|abstract\s+)?class\s+(\w+)',
    re.I,
)
_RE_CLASS_DECL = re.compile(r'\bclass\b([^{]*)\{', re.I)
_RE_IMPLEMENTS = re.compile(r'\bimplements\b(.*)', re.I | re.S)
_RE_STRING = re.compile(r"'(?:\\.|[^'\\\n])*'")
_RE_SOQL_INLINE = re.compile(r'\[(\s*SELECT\b.+?)\]', re.I | re.S)
_RE_FROM = re.compile(r'\bFROM\s+(\w+)\b', re.I)
_RE_SOQL_DB = re.compile(
    r'Database\.(?:query|getQueryLocator)\s*\(([^;]+)\)', re.I
)
_RE_DML_STMT = re.compile(
    r'\b(insert|update|delete|upsert|undelete)\s+(\w[\w.]*)\s*;', re.I
)
_RE_DML_DB = re.compile(
    r'Database\.(insert|update|delete|upsert|undelete)\s*\(\s*(\w+)', re.I
)
_RE_EXT_CALL = re.compile(
    r'\b([A-Z]\w*)\.((?!query|getQueryLocator)\w+)\s*\('
)

_SYSTEM_CLASSES = {
    'System', 'Database', 'Test', 'Schema', 'Math', 'String', 'Integer', 'Long',
    'Double', 'Decimal', 'Boolean', 'Date', 'DateTime', 'Time', 'List', 'Map', 'Set',
    'Blob', 'Id', 'SObject', 'Type', 'JSON', 'UserInfo', 'ApexPages', 'PageReference',
    'Trigger', 'Logger', 'LoggingLevel', 'Messaging', 'Object', 'Limits', 'Label',
    'URL', 'EncodingUtil', 'Crypto', 'Pattern', 'Matcher', 'Application',
    'DmlException', 'QueryException', 'NullPointerException', 'CalloutException',
    'AsyncException', 'Exception', 'FlowExecutionErrorException',
}

# コレクション / 文字列変数のメソッド名 — これらを呼び出しているなら外部クラス呼び出しではない
# (例: PLC.size() は List 変数の .size() であり CommonUtil.size() ではない)
_COLLECTION_METHODS = {
    'size', 'isEmpty', 'get', 'add', 'remove', 'contains', 'put',
    'keySet', 'values', 'clear', 'clone', 'getSObject', 'addAll',
    'removeAll', 'entrySet', 'containsKey', 'compareTo', 'equals',
    'hashCode', 'toString', 'format', 'indexOf', 'split', 'substring',
    'toLowerCase', 'toUpperCase', 'trim', 'length', 'replace',
    'startsWith', 'endsWith', 'join', 'sort', 'iterator', 'next',
    'hasNext', 'subList', 'set', 'append', 'replaceAll', 'toList',
}

_ENTRY_METHODS = [
    'execute', 'invoke', 'start', 'finish', 'run', 'process',
    'handleAfterInsert', 'handleAfterUpdate', 'handleBeforeInsert', 'handleBeforeUpdate',
    'handleAfterDelete', 'handleBeforeDelete', 'handleAfterUndelete',
]

_RE_AURA_ENABLED_METHOD = re.compile(
    r'@AuraEnabled(?:\s*\(\s*cacheable\s*=\s*\w+\s*\))?\s+'
    r'(?:(?:public|global|private|protected|override|static|virtual|testMethod)\s+)+'
    r'[\w<>.\[\],\s]+?\s+(\w+)\s*\([^)]*\)\s*\{',
    re.I,
)


# ─── コメント除去 ─────────────────────────────────────────────────────────────

def strip_comments(code: str) -> str:
    out, i = [], 0
    in_str, sc = False, ''
    while i < len(code):
        c = code[i]
        if in_str:
            out.append(c)
            if c == '\\' and i + 1 < len(code):
                i += 1
                out.append(code[i])
            elif c == sc:
                in_str = False
        elif c in ('"', "'"):
            in_str, sc = True, c
            out.append(c)
        elif code[i:i + 2] == '//':
            while i < len(code) and code[i] != '\n':
                i += 1
            continue
        elif code[i:i + 2] == '/*':
            i += 2
            while i < len(code) and code[i:i + 2] != '*/':
                if code[i] == '\n':
                    out.append('\n')
                i += 1
            i += 2
            continue
        else:
            out.append(c)
        i += 1
    return ''.join(out)


# ─── ブロック抽出ユーティリティ ───────────────────────────────────────────────

def balanced_end(code: str, pos: int) -> int:
    """pos 位置の '{' に対応する '}' のインデックスを返す。"""
    depth = 0
    in_str, sc = False, ''
    i = pos
    while i < len(code):
        c = code[i]
        if in_str:
            if c == '\\':
                i += 1
            elif c == sc:
                in_str = False
        elif c in ('"', "'"):
            in_str, sc = True, c
        elif c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return len(code) - 1


def find_brace(code: str, start: int) -> int:
    for k in range(start, len(code)):
        if code[k] == '{':
            return k
    return len(code)


def extract_method(code: str, names: list[str]) -> tuple[str, str]:
    """優先順位順でメソッド本体 (method_name, body) を返す。"""
    for name in names:
        pat = re.compile(
            r'(?:(?:public|private|global|protected|override|static|virtual|testMethod)\s+)+'
            r'[\w<>.\[\],\s]+?\b' + re.escape(name) + r'\s*\([^)]*\)\s*\{',
            re.I,
        )
        m = pat.search(code)
        if not m:
            continue
        bp = m.end() - 1
        ep = balanced_end(code, bp)
        return name, code[bp + 1:ep]
    return '', ''


# ─── セグメントクラス ─────────────────────────────────────────────────────────

class Seg:
    """メソッド本体内の論理ブロック。"""

    def __init__(self, kind: str, code: str):
        self.kind = kind  # if|for|while|try|catch|finally|switch|return|throw|stmts
        self.code = code

    def soqls(self) -> list[tuple[str, str]]:
        res = []
        for m in _RE_SOQL_INLINE.finditer(self.code):
            q = re.sub(r'\s+', ' ', m.group(0)).strip()
            fm = _RE_FROM.search(m.group(1))
            res.append((fm.group(1) if fm else '?', q))
        for m in _RE_SOQL_DB.finditer(self.code):
            fm = _RE_FROM.search(m.group(1))
            if fm:
                res.append((fm.group(1), re.sub(r'\s+', ' ', m.group(0)).strip()))
        return res

    def dmls(self) -> list[tuple[str, str]]:
        res = []
        for m in _RE_DML_STMT.finditer(self.code):
            res.append((m.group(1).upper(), m.group(2)))
        for m in _RE_DML_DB.finditer(self.code):
            res.append((m.group(1).upper(), m.group(2)))
        return res

    def ext_calls(self) -> list[str]:
        seen, res = set(), []
        _sys_upper = {s.upper() for s in _SYSTEM_CLASSES}
        _coll_upper = {m.upper() for m in _COLLECTION_METHODS}
        for m in _RE_EXT_CALL.finditer(self.code):
            cls = m.group(1)
            method = m.group(2)
            # システムクラスおよびコレクション/文字列メソッドは除外
            if cls.upper() in _sys_upper:
                continue
            if method.upper() in _coll_upper:
                continue
            k = f"{cls}.{method}"
            if k not in seen:
                seen.add(k)
                res.append(k)
        return res


# ─── メソッド本体の分割 ───────────────────────────────────────────────────────

def split_body(body: str) -> list[Seg]:
    """メソッド本体をトップレベルの制御構造単位で Seg リストに分割する。"""
    segs: list[Seg] = []
    pos, n = 0, len(body)
    stmts: list[str] = []

    def flush():
        text = '\n'.join(stmts).strip()
        if text:
            segs.append(Seg('stmts', text))
        stmts.clear()

    while pos < n:
        while pos < n and body[pos] in ' \t\n\r':
            pos += 1
        if pos >= n:
            break
        rest = body[pos:]

        # ── try / catch / finally ──────────────────────────────────────────
        if re.match(r'try\s*\{', rest, re.I):
            flush()
            bp = find_brace(body, pos)
            ep = balanced_end(body, bp)
            segs.append(Seg('try', body[bp + 1:ep]))
            pos = ep + 1
            # 続く catch / finally を読む
            while pos < n:
                while pos < n and body[pos].isspace():
                    pos += 1
                r2 = body[pos:]
                if re.match(r'\}?\s*catch\s*\(', r2, re.I):
                    bp2 = find_brace(body, pos)
                    ep2 = balanced_end(body, bp2)
                    segs.append(Seg('catch', body[bp2 + 1:ep2]))
                    pos = ep2 + 1
                elif re.match(r'\}?\s*finally\s*\{', r2, re.I):
                    bp2 = find_brace(body, pos)
                    ep2 = balanced_end(body, bp2)
                    segs.append(Seg('finally', body[bp2 + 1:ep2]))
                    pos = ep2 + 1
                    break
                else:
                    break
            continue

        # ── if / else if / else ────────────────────────────────────────────
        if re.match(r'if\s*\(', rest, re.I):
            flush()
            bp = find_brace(body, pos)
            ep = balanced_end(body, bp)
            if_code = body[pos:ep + 1]
            pos = ep + 1
            while pos < n:
                while pos < n and body[pos].isspace():
                    pos += 1
                r2 = body[pos:]
                if re.match(r'\}?\s*else\s+if\s*\(', r2, re.I):
                    bp2 = find_brace(body, pos)
                    ep2 = balanced_end(body, bp2)
                    if_code += '\n' + body[pos:ep2 + 1]
                    pos = ep2 + 1
                elif re.match(r'\}?\s*else\s*\{', r2, re.I):
                    bp2 = find_brace(body, pos)
                    ep2 = balanced_end(body, bp2)
                    if_code += '\n' + body[pos:ep2 + 1]
                    pos = ep2 + 1
                    break
                else:
                    break
            segs.append(Seg('if', if_code))
            continue

        # ── for / while ────────────────────────────────────────────────────
        m_loop = re.match(r'(for|while)\s*\(', rest, re.I)
        if m_loop:
            flush()
            bp = find_brace(body, pos)
            ep = balanced_end(body, bp)
            segs.append(Seg(m_loop.group(1).lower(), body[pos:ep + 1]))
            pos = ep + 1
            continue

        # ── switch on ──────────────────────────────────────────────────────
        if re.match(r'switch\s+on\s+', rest, re.I):
            flush()
            bp = find_brace(body, pos)
            ep = balanced_end(body, bp)
            segs.append(Seg('switch', body[pos:ep + 1]))
            pos = ep + 1
            continue

        # ── return / throw ─────────────────────────────────────────────────
        m_rt = re.match(r'(return|throw)\b', rest, re.I)
        if m_rt:
            flush()
            semi = body.find(';', pos)
            end = (semi + 1) if semi >= 0 else n
            segs.append(Seg(m_rt.group(1).lower(), body[pos:end]))
            pos = end
            continue

        # ── その他のステートメント ─────────────────────────────────────────
        next_semi = body.find(';', pos)
        next_brace = body.find('{', pos)

        if next_semi < 0:
            stmts.append(rest.strip())
            pos = n
        elif next_brace >= 0 and next_brace < next_semi:
            ep = balanced_end(body, next_brace)
            stmts.append(body[pos:ep + 1].strip())
            pos = ep + 1
        else:
            stmts.append(body[pos:next_semi + 1].strip())
            pos = next_semi + 1

    flush()
    return segs


# ─── セグメント → ステップ変換 ───────────────────────────────────────────────

def seg_to_step(seg: Seg, no: int) -> dict:
    step: dict = {
        'no': no,
        'title': '',
        'detail': '',
        'node_type': 'process',
        'calls': None,
        'object_ref': None,
        'branch': None,
        'sub_steps': [],
    }

    soqls = seg.soqls()
    dmls = seg.dmls()
    calls = seg.ext_calls()

    for obj, q in soqls:
        step['sub_steps'].append({'title': 'SOQL', 'detail': q})
    for op, var in dmls:
        step['sub_steps'].append({'title': 'DML', 'detail': f'{op} {var}'})

    if soqls:
        step['object_ref'] = {'text': soqls[0][0]}
    elif dmls:
        step['object_ref'] = {'text': dmls[0][1].split('.')[0]}

    # calls は SOQL/DML がない場合のみ設定（DB操作の方が重要度が高い）
    if calls and not soqls and not dmls:
        txt = calls[0]
        step['calls'] = {'text': txt if len(txt) <= 20 else txt[:17] + '...'}

    # node_type の決定
    if seg.kind == 'if':
        step['node_type'] = 'decision'
        has_error_else = bool(re.search(
            r'\}\s*else\s*\{.*?(throw\b|Exception\b|rollback)', seg.code, re.I | re.S
        ))
        step['branch'] = {
            'text': '',
            'node_type': 'error' if has_error_else else 'process',
            'label': 'False',
        }
    elif seg.kind == 'switch':
        step['node_type'] = 'decision'
        step['branch'] = {'text': '', 'node_type': 'process', 'label': 'default'}
    elif seg.kind in ('catch', 'throw'):
        step['node_type'] = 'error'
    elif seg.kind == 'return':
        step['node_type'] = 'success' if re.search(
            r'return\s+(true|result|response|wrapper|res|output)\b', seg.code, re.I
        ) else 'process'
    # try / for / while / finally / stmts → process (デフォルト)

    return step


def build_steps(segs: list[Seg]) -> list[dict]:
    steps: list[dict] = []
    no = 1
    i = 0

    while i < len(segs):
        seg = segs[i]

        # 連続する stmts をまとめる
        if seg.kind == 'stmts':
            merged_code = seg.code
            j = i + 1
            while j < len(segs) and segs[j].kind == 'stmts':
                merged_code += '\n' + segs[j].code
                j += 1
            merged = Seg('stmts', merged_code)
            # 意味のある処理を含む場合のみステップ化
            has_content = (
                merged.soqls()
                or merged.dmls()
                or merged.ext_calls()
                or bool(re.search(r'\w+\s*[\+\-\*\/]?=\s*\w+', merged.code))
                or bool(re.search(r'\.\w+\s*\(', merged.code))
            )
            if has_content:
                steps.append(seg_to_step(merged, no))
                no += 1
            i = j

        # try → 直後の catch/finally と統合
        elif seg.kind == 'try':
            step = seg_to_step(seg, no)
            no += 1
            j = i + 1
            catch_segs = []
            while j < len(segs) and segs[j].kind in ('catch', 'finally'):
                catch_segs.append(segs[j])
                j += 1
            if catch_segs:
                step['branch'] = {'text': '', 'node_type': 'error', 'label': 'catch'}
            steps.append(step)
            # catch/finally の内容は try ステップの branch で表現済みのため
            # メインフローへの追加は省略する（node_type:"error" の単独ステップが
            # check_design_json.py のエラーチェックに引っかかるデッドロックを回避）
            i = j

        else:
            steps.append(seg_to_step(seg, no))
            no += 1
            i += 1

    if not steps:
        steps = [{
            'no': 1, 'title': '', 'detail': '', 'node_type': 'process',
            'calls': None, 'object_ref': None, 'branch': None, 'sub_steps': [],
        }]
    return steps


# ─── @AuraEnabled メソッド → ステップ変換 ───────────────────────────────────

def method_to_step(method_name: str, segs: list[Seg], no: int) -> dict:
    """@AuraEnabled メソッド全体を1ステップに集約する。"""
    all_soqls: list[tuple[str, str]] = []
    all_dmls: list[tuple[str, str]] = []
    all_calls: list[str] = []
    seen_calls: set[str] = set()

    for seg in segs:
        all_soqls.extend(seg.soqls())
        all_dmls.extend(seg.dmls())
        for c in seg.ext_calls():
            if c not in seen_calls:
                seen_calls.add(c)
                all_calls.append(c)

    sub_steps: list[dict] = []
    for obj, q in all_soqls:
        sub_steps.append({'title': 'SOQL', 'detail': q})
    for op, var in all_dmls:
        sub_steps.append({'title': 'DML', 'detail': f'{op} {var}'})

    object_ref = None
    if all_soqls:
        object_ref = {'text': all_soqls[0][0]}
    elif all_dmls:
        object_ref = {'text': all_dmls[0][1].split('.')[0]}

    calls = None
    if all_calls:
        txt = all_calls[0]
        calls = {'text': txt if len(txt) <= 20 else txt[:17] + '...'}

    has_error = any(s.kind in ('catch', 'throw') for s in segs)
    branch = {'text': '', 'node_type': 'error', 'label': 'catch'} if has_error else None

    return {
        'no': no,
        'title': method_name,  # エージェントが意味のある名称に上書き
        'detail': '',
        'node_type': 'process',
        'calls': calls,
        'object_ref': object_ref,
        'branch': branch,
        'sub_steps': sub_steps,
    }


# ─── クラス種別検出 ───────────────────────────────────────────────────────────

def detect_type(code: str) -> str:
    # 文字列の URL・クラス名では判定しない。implements は最初のクラス宣言のもの（内部クラスのものは見ない）
    code = _RE_STRING.sub("''", code)
    decl = _RE_CLASS_DECL.search(code)
    m = _RE_IMPLEMENTS.search(decl.group(1)) if decl else None
    if m:
        s = m.group(1)
        if re.search(r'Database\.Batchable', s, re.I):
            return 'Apex_Batch'
        if re.search(r'Queueable', s, re.I):
            return 'Apex_Queueable'
        if re.search(r'Schedulable', s, re.I):
            return 'Apex_Schedulable'
    if re.search(r'@InvocableMethod', code, re.I):
        return 'Apex_Invocable'
    if re.search(r'TriggerHandler', code, re.I):
        return 'Apex_TriggerHandler'
    if re.search(r'\bHttp\b|\bHttpRequest\b|\bHttpResponse\b|\bWebServiceCallout\b', code, re.I):
        return 'Apex_Integration'
    return 'Apex'


# ─── メイン解析 ───────────────────────────────────────────────────────────────

def parse_apex(code: str) -> dict:
    clean = strip_comments(code)

    m_cls = _RE_CLASS.search(clean)
    api_name = m_cls.group(1) if m_cls else 'UnknownClass'
    cls_type = detect_type(clean)

    # ── @AuraEnabled コントローラ検出（2メソッド以上で確定）───────────────
    aura_matches = list(_RE_AURA_ENABLED_METHOD.finditer(clean))
    if len(aura_matches) >= 2:
        cls_type = 'Apex_AuraEnabled'
        steps: list[dict] = []
        total_segs = 0
        for idx, am in enumerate(aura_matches):
            mname = am.group(1)
            bp = am.end() - 1  # '{' の位置
            ep = balanced_end(clean, bp)
            body = clean[bp + 1: ep]
            segs = split_body(body)
            total_segs += len(segs)
            steps.append(method_to_step(mname, segs, idx + 1))

        return {
            'type': cls_type,
            'api_name': api_name,
            'name': '',
            'overview': {
                'purpose': '',
                'trigger': '',
                'preconditions': '',
                'summary': '',
            },
            'steps': steps,
            'params': {'input': [], 'output': []},
            'revision_history': [],
            '_parser_meta': {
                'entry_method': f'@AuraEnabled×{len(aura_matches)}',
                'segment_count': total_segs,
                'step_count': len(steps),
            },
        }

    # ── 通常クラス: エントリーポイント候補（優先順位順）───────────────────
    all_public = [
        m.group(1)
        for m in re.finditer(
            r'(?:public|global|override)\s+[\w<>.\[\]]+\s+(\w+)\s*\(', clean, re.I
        )
    ]
    priority = _ENTRY_METHODS + [x for x in all_public if x not in _ENTRY_METHODS]

    method_name, body = extract_method(clean, priority)

    # フォールバック: クラス本体全体
    if not body and m_cls:
        bp = find_brace(clean, m_cls.end())
        if bp < len(clean):
            body = clean[bp + 1: balanced_end(clean, bp)]

    segs = split_body(body) if body else []
    steps = build_steps(segs)

    return {
        'type': cls_type,
        'api_name': api_name,
        'name': '',
        'overview': {
            'purpose': '',
            'trigger': '',
            'preconditions': '',
            'summary': '',
        },
        'steps': steps,
        'params': {'input': [], 'output': []},
        'revision_history': [],
        '_parser_meta': {
            'entry_method': method_name or '(not found)',
            'segment_count': len(segs),
            'step_count': len(steps),
        },
    }


# ─── CLI ─────────────────────────────────────────────────────────────────────

def main() -> None:
    ap = argparse.ArgumentParser(description='Apex ソース → スケルトンJSON')
    ap.add_argument('--input',  '-i', required=True, help='入力 .cls ファイル')
    ap.add_argument('--output', '-o', help='出力 JSON ファイル（省略時 stdout）')
    args = ap.parse_args()

    input_path = Path(args.input)
    try:
        code = input_path.read_text(encoding='utf-8')
    except FileNotFoundError:
        print(f"[ERROR] ファイルが見つかりません: {input_path}", file=sys.stderr)
        sys.exit(1)
    except PermissionError:
        print(f"[ERROR] ファイルへのアクセス権がありません: {input_path}", file=sys.stderr)
        sys.exit(1)
    result = parse_apex(code)
    out = json.dumps(result, ensure_ascii=False, indent=2)

    if args.output:
        Path(args.output).write_text(out, encoding='utf-8')
        meta = result['_parser_meta']
        print(
            f"[OK] {args.output}  "
            f"entry={meta['entry_method']}  "
            f"steps={meta['step_count']}",
            file=sys.stderr,
        )
    else:
        print(out)


if __name__ == '__main__':
    main()
