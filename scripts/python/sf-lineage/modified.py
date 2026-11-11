"""部品の最終更新日・更新者を組織から読み取りで取る（Metadata API の一覧取得 = sf org list metadata。組織は変えない）。

  python modified.py <地図のフォルダ> <force-app/main/default> --target-org <別名> [--target-org <別名2> ...]

- 保存先: <地図のフォルダ>/modified-<別名>.json（{"org", "isSandbox", "fetched_at", "items": {"<地図の種類>:<名前>": {...}}}）
- 表示: 手元の force-app より組織のほうが新しい部品（取り直しが要る）・組織にあって手元に無い部品・
  2つ以上の組織を取ったときは、本番より Sandbox のほうが新しい部品（本番に未リリースの変更の候補）
- 管理パッケージの部品（namespacePrefix の付く installed）は扱わない
"""
from __future__ import annotations

import datetime as dt
import glob
import json
import os
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor

# Metadata API の種類 → 地図の種類（refs.jsonl の src_type）と、手元のファイル（source 形式）
TYPES = {
    "ApexClass": ("ApexClass", "classes/{n}.cls"),
    "ApexTrigger": ("ApexTrigger", "triggers/{n}.trigger"),
    "ApexPage": ("Visualforce", "pages/{n}.page"),
    "LightningComponentBundle": ("LWC", "lwc/{n}"),
    "AuraDefinitionBundle": ("Aura", "aura/{n}"),
    "Flow": ("Flow", "flows/{n}.flow-meta.xml"),
    "ValidationRule": ("ValidationRule", "objects/{o}/validationRules/{m}.validationRule-meta.xml"),
    "CustomField": ("CustomField", "objects/{o}/fields/{m}.field-meta.xml"),
    "CustomObject": ("CustomObject", "objects/{n}/{n}.object-meta.xml"),
    "WorkflowRule": ("WorkflowRule", "workflows/{o}.workflow-meta.xml"),
    "WorkflowFieldUpdate": ("WorkflowFieldUpdate", "workflows/{o}.workflow-meta.xml"),
    "WorkflowAlert": ("WorkflowAlert", "workflows/{o}.workflow-meta.xml"),
    "ApprovalProcess": ("ApprovalProcess", "approvalProcesses/{n}.approvalProcess-meta.xml"),
    "QuickAction": ("QuickAction", "quickActions/{n}.quickAction-meta.xml"),
    "Layout": ("Layout", "layouts/{n}.layout-meta.xml"),
    "FlexiPage": ("FlexiPage", "flexipages/{n}.flexipage-meta.xml"),
    "ReportType": ("ReportType", "reportTypes/{n}.reportType-meta.xml"),
    "ListView": ("ListView", "objects/{o}/listViews/{m}.listView-meta.xml"),
    "RecordType": ("RecordType", "objects/{o}/recordTypes/{m}.recordType-meta.xml"),
    "CompactLayout": ("CompactLayout", "objects/{o}/compactLayouts/{m}.compactLayout-meta.xml"),
    "FieldSet": ("FieldSet", "objects/{o}/fieldSets/{m}.fieldSet-meta.xml"),
    "PathAssistant": ("PathAssistant", "pathAssistants/{n}.pathAssistant-meta.xml"),
    "DuplicateRule": ("DuplicateRule", "duplicateRules/{n}.duplicateRule-meta.xml"),
    "PermissionSet": ("PermissionSet", "permissionsets/{n}.permissionset-meta.xml"),
    "CustomLabel": ("Label", "labels/CustomLabels.labels-meta.xml"),
}


def sf_json(args: list[str], timeout: int = 300):
    exe = shutil.which("sf") or shutil.which("sf.cmd")
    if not exe:
        raise SystemExit("sf コマンドが見つかりません")
    env = dict(os.environ, SF_DISABLE_AUTOUPDATE="true", SF_USE_PROGRESS_BAR="false", MSYS_NO_PATHCONV="1")
    r = subprocess.run([exe] + args + ["--json"], capture_output=True, text=True, encoding="utf-8", errors="replace",
                       timeout=timeout, env=env)
    try:
        return json.loads(r.stdout)
    except json.JSONDecodeError:
        return {"status": 1, "message": (r.stdout + r.stderr)[-300:]}


def fetch(alias: str) -> dict:
    org = sf_json(["data", "query", "--query", "SELECT IsSandbox, Name FROM Organization", "--target-org", alias])
    recs = (org.get("result") or {}).get("records") or []
    if not recs:
        raise SystemExit(f"組織 {alias} につながりません: {org.get('message', '')[:200]}")
    items, errors = {}, []

    def one(mt):
        d = sf_json(["org", "list", "metadata", "--metadata-type", mt, "--target-org", alias])
        if d.get("status") not in (0, None):
            errors.append(f"{mt}: {str(d.get('message'))[:120]}")
            return []
        r = d.get("result") or []
        return [(mt, x) for x in (r if isinstance(r, list) else [r])]

    with ThreadPoolExecutor(max_workers=6) as ex:
        for rows in ex.map(one, TYPES):
            for mt, x in rows:
                if x.get("namespacePrefix") and x.get("manageableState") == "installed":
                    continue   # 管理パッケージ
                st = TYPES[mt][0]
                items[f"{st}:{x['fullName']}"] = {
                    "type": mt, "lastModifiedDate": x.get("lastModifiedDate"), "lastModifiedByName": x.get("lastModifiedByName"),
                    "createdDate": x.get("createdDate"), "createdByName": x.get("createdByName")}
    return {"org": alias, "orgName": recs[0].get("Name"), "isSandbox": bool(recs[0].get("IsSandbox")),
            "fetched_at": dt.datetime.now().isoformat(timespec="seconds"), "items": items, "errors": errors}


def load_all(mapdir: str) -> list[dict]:
    """保存済みの組織ごとの最終更新（本番を先に）。"""
    out = []
    for p in sorted(glob.glob(os.path.join(mapdir, "modified-*.json"))):
        try:
            out.append(json.load(open(p, encoding="utf-8")))
        except (OSError, json.JSONDecodeError):
            pass
    return sorted(out, key=lambda d: d.get("isSandbox", True))


def org_label(d: dict) -> str:
    return "本番" if not d.get("isSandbox") else d["org"]


def stamp(mods: list[dict], st: str, sn: str) -> str:
    """地図の部品に付ける「最終更新」の短い文字列。例: 〔最終更新 本番 2026-10-01 山田 太郎／uat 2026-11-10 佐藤 花子（本番より新しい）〕"""
    if st == "ApexTest":
        st = "ApexClass"
    parts, prod = [], None
    for d in mods:
        x = d["items"].get(f"{st}:{sn}")
        if not x or not x.get("lastModifiedDate"):
            continue
        day = x["lastModifiedDate"][:10]
        newer = ""
        if not d.get("isSandbox"):
            prod = x["lastModifiedDate"]
        elif prod and x["lastModifiedDate"] > prod:
            newer = "（本番より新しい）"
        parts.append(f"{org_label(d)} {day} {x.get('lastModifiedByName') or ''}{newer}".strip())
    return f" 〔最終更新 {'／'.join(parts)}〕" if parts else ""


def local_path(fa: str, mt: str, full: str) -> str | None:
    pat = TYPES[mt][1]
    o, m = (full.split(".", 1) + [""])[:2] if "." in full else (full, "")
    if mt == "Layout":
        return os.path.join(fa, pat.format(n=full))
    return os.path.join(fa, *pat.format(n=full, o=o, m=m).split("/"))


def mtime(p: str) -> float | None:
    if os.path.isdir(p):
        ts = [os.path.getmtime(os.path.join(dp, f)) for dp, _, fs in os.walk(p) for f in fs]
        return max(ts) if ts else None
    return os.path.getmtime(p) if os.path.exists(p) else None


def report(fa: str, mods: list[dict], brief: bool = False) -> None:
    """brief=True は件数だけ（lineage.py status 用。保存済みの一覧から出すので組織にはつながない）。"""
    for d in mods:
        stale, missing = [], []
        for key, x in d["items"].items():
            mt = x["type"]
            st, full = key.split(":", 1)
            if mt in ("WorkflowRule", "WorkflowFieldUpdate", "WorkflowAlert", "CustomObject", "PermissionSet", "CustomLabel") or not x.get("lastModifiedDate"):
                continue   # 1ファイルにまとまる種類・手元に取らないことの多い種類は、取り直しの判定に使わない
            top = os.path.join(fa, TYPES[mt][1].split("/")[0])
            if not os.path.isdir(top):
                continue   # この種類をそもそも取っていない
            p = local_path(fa, mt, full)
            t = mtime(p) if p else None
            org_t = dt.datetime.fromisoformat(x["lastModifiedDate"].replace("Z", "+00:00")).timestamp()
            if t is None:
                missing.append((x["lastModifiedDate"][:10], key, x.get("lastModifiedByName")))
            elif org_t > t + 60:
                stale.append((x["lastModifiedDate"][:10], key, x.get("lastModifiedByName")))
        if brief:
            print(f"組織 {org_label(d)}（{d['org']}）の最終更新: {d['fetched_at'][:16]} に取得／手元より組織のほうが新しい部品 {len(stale)} 件・"
                  f"組織にあって手元に無い部品 {len(missing)} 件" + ("（/sf-retrieve で取り直すと地図も新しくなる）" if stale else ""))
            continue
        print(f"■ {org_label(d)}（{d['org']}・{d['orgName']}）: 部品 {len(d['items'])} 件の最終更新を取った（{d['fetched_at']}）"
              + (f"。取れなかった種類: {'、'.join(d['errors'])}" if d.get("errors") else ""))
        if stale:
            print(f"  手元の force-app より組織のほうが新しい部品 {len(stale)} 件（取り直しが要る。ファイルの更新日時との比較なので推定）:")
            for day, key, who in sorted(stale, reverse=True)[:15]:
                print(f"    {day} {key}（{who}）")
            if len(stale) > 15:
                print(f"    … ほか {len(stale) - 15}")
        if missing:
            print(f"  組織にあって手元に無い部品 {len(missing)} 件（取っていない・新しく作られた）:")
            for day, key, who in sorted(missing, reverse=True)[:10]:
                print(f"    {day} {key}（{who}）")
            if len(missing) > 10:
                print(f"    … ほか {len(missing) - 10}")
    prod = next((d for d in mods if not d.get("isSandbox")), None)
    for d in mods:
        if prod is None or d is prod:
            continue
        newer = [(x["lastModifiedDate"][:10], k, x.get("lastModifiedByName")) for k, x in d["items"].items()
                 if k in prod["items"] and x.get("lastModifiedDate") and prod["items"][k].get("lastModifiedDate")
                 and x["lastModifiedDate"] > prod["items"][k]["lastModifiedDate"]]
        only = [k for k in d["items"] if k not in prod["items"]]
        if brief:
            print(f"{d['org']} のほうが本番より新しい部品 {len(newer)} 件・{d['org']} にだけある部品 {len(only)} 件（取得時点）")
            continue
        print(f"■ {d['org']} のほうが本番より新しい部品 {len(newer)} 件・{d['org']} にだけある部品 {len(only)} 件（本番に未リリースの変更の候補。リリース・作業の重なりの確認に使う）")
        for day, key, who in sorted(newer, reverse=True)[:15]:
            print(f"    {day} {key}（{who}）")
        if len(newer) > 15:
            print(f"    … ほか {len(newer) - 15}")


def main() -> None:
    args = sys.argv[1:]
    if len(args) < 2 or "--target-org" not in args:
        print(__doc__)
        sys.exit(1)
    mapdir, fa = args[0], args[1]
    aliases = [args[i + 1] for i, a in enumerate(args) if a == "--target-org" and i + 1 < len(args)]
    os.makedirs(mapdir, exist_ok=True)
    for a in aliases:
        d = fetch(a)
        with open(os.path.join(mapdir, f"modified-{a}.json"), "w", encoding="utf-8") as f:
            json.dump(d, f, ensure_ascii=False)
    report(fa, [d for d in load_all(mapdir) if d["org"] in aliases])


if __name__ == "__main__":
    main()
