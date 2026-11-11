"""使われていない部品の候補（棚卸し・削除の影響確認の入口）。地図の中で、どこからも参照されていない部品を出す。

  python unused.py <地図のフォルダ> <force-app/main/default> [--type field|apex|flow|lwc|vf] [--all]

- 項目: どこからも参照されていない項目と、ページレイアウト・権限・翻訳にだけ出る（処理・帳票・リストビューで使われていない）項目
- Apex: 呼ばれていないクラス（テストクラス・トリガーのハンドラから呼ばれるもの・画面やフロー・外部から直接呼ばれる入口
  〔@AuraEnabled・@InvocableMethod・@RestResource・webservice・Schedulable・Batchable・Queueable・global・VF のコントローラ〕は除く）
- フロー: 起動のきっかけ（保存・スケジュール・プラットフォームイベント）が無く、どこからも呼ばれていない自動起動フロー・画面フロー
- LWC・VF: どこにも置かれていない・呼ばれていない画面部品
地図は force-app から作るので、組織の外（外部システム・URL 直打ち・データ）からの使われ方は分からない。あくまで候補で、
削除・整理の前に、組織での利用状況（レポートの実行・画面の利用・データの件数）と担当者に確かめる。
"""
from __future__ import annotations

import json
import os
import re
import sys
import xml.etree.ElementTree as ET

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from modified import load_all  # noqa: E402

NS = "{http://soap.sforce.com/2006/04/metadata}"
WEAK = {"Layout", "PermissionSet", "Profile", "FieldTranslation", "CompactLayout"}   # 置いてある・権限があるだけ
ENTRY = re.compile(r"@AuraEnabled|@InvocableMethod|@InvocableVariable|@RestResource|\bwebservice\b|\bglobal\b|"
                   r"implements\s+[^{]*\b(Schedulable|Database\.Batchable|Queueable|Messaging\.InboundEmailHandler|"
                   r"Auth\.RegistrationHandler|Process\.Plugin|Metadata\.DeployCallback|System\.Finalizer)\b", re.I)


def last_mod(mods: list[dict], key: str) -> str:
    for d in mods:   # 本番を先に
        x = d["items"].get(key)
        if x and x.get("lastModifiedDate"):
            return f"〔最終更新 {'本番' if not d.get('isSandbox') else d['org']} {x['lastModifiedDate'][:10]} {x.get('lastModifiedByName') or ''}〕"
    return ""


def show(title: str, rows: list[str], show_all: bool) -> None:
    print(f"## {title}（{len(rows)}）")
    for r in rows[: None if show_all else 30]:
        print(f"- {r}")
    if not show_all and len(rows) > 30:
        print(f"- … ほか {len(rows) - 30}（--all で全部）")


def main() -> None:
    args = sys.argv[1:]
    if len(args) < 2:
        print(__doc__)
        sys.exit(1)
    mapdir, fa = args[0], args[1]
    kind = args[args.index("--type") + 1] if "--type" in args else None
    show_all = "--all" in args
    refs = [json.loads(l) for l in open(os.path.join(mapdir, "refs.jsonl"), encoding="utf-8")]
    fields = json.load(open(os.path.join(mapdir, "fields.json"), encoding="utf-8"))
    mods = load_all(mapdir)
    by_target: dict[str, set[str]] = {}
    for r in refs:
        if r["src_type"] == "ApexTest":
            continue
        by_target.setdefault(r["target"].lower(), set()).add(r["src_type"])
    print("使われていない部品の候補（地図の中で参照が無いもの。組織の外・データからの使われ方は分からないので、整理・削除の前に組織と担当者で確かめる）")

    if kind in (None, "field"):
        none, weak = [], []
        for o, fs in sorted(fields.items()):
            for f in sorted(fs):
                if not f.endswith("__c") or re.match(r"^[A-Za-z0-9]+__\w+__c$", f):
                    continue   # 標準項目・管理パッケージの項目
                users = by_target.get(f"{o}.{f}".lower(), set())
                lab = fs[f].get("label") or ""
                row = f"{o}.{f}（{lab}）{last_mod(mods, f'CustomField:{o}.{f}')}"
                if not users:
                    none.append(row)
                elif users <= WEAK:
                    weak.append(row + f" ← {'・'.join(sorted(users))}だけ")
        show("項目: どこからも参照されていない", none, show_all)
        show("項目: レイアウト・権限・翻訳にだけ出る（処理・帳票・リストビューで使われていない）", weak, show_all)

    if kind in (None, "apex"):
        rows = []
        cdir = os.path.join(fa, "classes")
        trig_text = ""
        tdir = os.path.join(fa, "triggers")
        for fn in (os.listdir(tdir) if os.path.isdir(tdir) else []):
            if fn.endswith(".trigger"):
                trig_text += open(os.path.join(tdir, fn), encoding="utf-8", errors="ignore").read()
        vf_ctrl = set()
        pdir = os.path.join(fa, "pages")
        for fn in (os.listdir(pdir) if os.path.isdir(pdir) else []):
            if fn.endswith(".page"):
                t = open(os.path.join(pdir, fn), encoding="utf-8", errors="ignore").read()
                for m in re.finditer(r'(?:controller|extensions)\s*=\s*"([^"]+)"', t, re.I):
                    vf_ctrl |= {c.strip() for c in m.group(1).split(",")}
        for fn in sorted(os.listdir(cdir) if os.path.isdir(cdir) else []):
            if not fn.endswith(".cls"):
                continue
            name = fn[:-4]
            src = open(os.path.join(cdir, fn), encoding="utf-8", errors="ignore").read()
            if re.search(r"@isTest|\btestMethod\b", src, re.I) or "test" in name.lower():
                continue
            if by_target.get(name.lower()) or ENTRY.search(src) or name in vf_ctrl or re.search(rf"\b{re.escape(name)}\b", trig_text):
                continue
            rows.append(f"{name}{last_mod(mods, f'ApexClass:{name}')}")
        show("Apex クラス: どこからも呼ばれていない（画面・フロー・外部・スケジュールの入口でもない）", rows, show_all)

    if kind in (None, "flow"):
        rows = []
        fdir = os.path.join(fa, "flows")
        for fn in sorted(os.listdir(fdir) if os.path.isdir(fdir) else []):
            if not fn.endswith(".flow-meta.xml"):
                continue
            name = fn[: -len(".flow-meta.xml")]
            try:
                root = ET.parse(os.path.join(fdir, fn)).getroot()
            except ET.ParseError:
                continue
            st = root.find(NS + "start")
            tt = st.find(NS + "triggerType") if st is not None else None
            status = root.find(NS + "status")
            if tt is not None and tt.text:
                continue   # 保存・スケジュール・プラットフォームイベントで動く
            if by_target.get(name.lower()):
                continue
            pt = root.find(NS + "processType")
            label = root.find(NS + "label")
            rows.append(f"{name}（{label.text if label is not None else ''}・{pt.text if pt is not None else ''}・"
                        f"{status.text if status is not None else ''}）{last_mod(mods, f'Flow:{name}')}")
        show("フロー: 起動のきっかけが無く、どこからも呼ばれていない（ボタン・ページ・ほかのフロー・Apex・URL から呼ぶ想定のものは確かめる）", rows, show_all)

    if kind in (None, "lwc", "vf"):
        rows = []
        for d, key, st in (("lwc", "LWC:{}", "LWC"), ("aura", "LWC:{}", "Aura")):
            dp = os.path.join(fa, d)
            if kind == "vf":
                break
            for name in sorted(os.listdir(dp) if os.path.isdir(dp) else []):
                if not os.path.isdir(os.path.join(dp, name)) or by_target.get(key.format(name).lower()):
                    continue
                meta = os.path.join(dp, name, f"{name}.js-meta.xml")
                exposed = os.path.exists(meta) and "<isExposed>true</isExposed>" in open(meta, encoding="utf-8", errors="ignore").read()
                rows.append(f"{st}:{name}" + ("（公開しているが、取得したページ・タブ・フロー・アクションに置かれていない。Experience Cloud のサイトのページは取得していなければ分からない）" if exposed else "")
                            + last_mod(mods, f"{st}:{name}"))
        pdir = os.path.join(fa, "pages")
        if kind in (None, "vf"):
            for fn in sorted(os.listdir(pdir) if os.path.isdir(pdir) else []):
                if fn.endswith(".page") and not by_target.get(f"VF:{fn[:-5]}".lower()):
                    rows.append(f"VF:{fn[:-5]}（ボタン・タブ・URL から開く想定のものは確かめる）{last_mod(mods, 'Visualforce:' + fn[:-5])}")
        show("画面部品: どこにも置かれていない・呼ばれていない", rows, show_all)


if __name__ == "__main__":
    main()
