#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
build_detail_design_json.py

feature_groups.yml + 実コード → 詳細設計書JSONを自動生成する。

【自動抽出】
  - components[].api_name / type  : feature_ids.yml から
  - components[].callees          : LWC import文 / Apex外部クラス呼び出しから
  - object_access[]               : SOQL(R) / insert(INSERT) / update|upsert(W) / Flow XMLから
  - related_objects[]             : object_access + objectTranslations ラベルから
  - impact                        : 上記から導出

【人間が書く（既存JSONがあれば保持・なければプレースホルダー）】
  - summary / purpose / users / trigger_screen / trigger
  - business_flow[]  : 業務フローステップ
  - process_steps[]  : 処理概要ステップ
  - components[].role: 各コンポーネントの役割説明

Usage:
  python build_detail_design_json.py \\
    --group-id FG-001 \\
    --project-dir C:/workspace/16_グリーンフィールド/greenfield \\
    --groups-yml  C:/workspace/16_グリーンフィールド/greenfield/docs/.sf/feature_groups.yml \\
    --ids-yml     C:/workspace/16_グリーンフィールド/greenfield/docs/.sf/feature_ids.yml \\
    --output      C:/work/01_作業/グリーンフィールド/02_詳細設計/.tmp/FG-001_detail.json
"""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path
from datetime import date

try:
    import yaml
    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False


# ── 標準オブジェクト（SOQLのFROM句でよく出るもの） ─────────────────────────
_STANDARD_OBJECTS = {
    "Account", "Contact", "Lead", "Opportunity", "Case", "Task", "Event",
    "User", "Profile", "RecordType", "ContentDocument", "ContentDocumentLink",
    "ContentVersion", "EmailMessage", "Attachment", "Note", "Quote",
    "Product2", "Pricebook2", "PricebookEntry", "OrderItem", "Order",
}

# ── LWC callee 抽出 ───────────────────────────────────────────────────────────
_RE_LWC_IMPORT    = re.compile(r"""import\s+\w+\s+from\s+['"]c/(\w+)['"]""", re.I)
_RE_APEX_IMPORT   = re.compile(r"""import\s+\w+\s+from\s+['"]@salesforce/apex/(\w+)\.\w+['"]""", re.I)


def extract_lwc_callees(js_path: Path) -> list[str]:
    """LWC JSファイルからcallee一覧を抽出する（c/ インポート + @salesforce/apex インポート）。"""
    try:
        content = js_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []
    lwc   = _RE_LWC_IMPORT.findall(content)
    apex  = _RE_APEX_IMPORT.findall(content)
    seen: list[str] = []
    for name in lwc + apex:
        if name not in seen:
            seen.append(name)
    return seen


# ── Apex object_access 抽出 ───────────────────────────────────────────────────
_RE_SOQL_FROM  = re.compile(r"SELECT\s+.+?\s+FROM\s+([A-Za-z0-9_]+)", re.I | re.S)
_RE_VAR_TYPE   = re.compile(r"\b([A-Za-z][A-Za-z0-9_]*__c)\s+(\w+)\s*[=;(,\[]")
_RE_STD_VAR    = re.compile(r"\b(User|Contact|Lead|Account|Opportunity|Case)\s+(\w+)\s*[=;(,\[]")
_RE_LIST_TYPE  = re.compile(r"List<([A-Za-z][A-Za-z0-9_]*(?:__c)?|User|Contact|Lead|Account)>\s+(\w+)")
_RE_DML_INSERT = re.compile(r"\binsert\s+(\w+)", re.I)
_RE_DML_UPSERT = re.compile(r"\bupsert\s+(\w+)", re.I)
_RE_DML_UPDATE = re.compile(r"\bupdate\s+(\w+)", re.I)
_RE_NEW_OBJ    = re.compile(r"\bnew\s+([A-Za-z][A-Za-z0-9_]*(?:__c)?)\s*\(", re.I)
_RE_TRG_MAP    = re.compile(r"Map<Id,\s*([A-Za-z][A-Za-z0-9_]*__c)>")
_RE_TRG_LIST   = re.compile(r"List<([A-Za-z][A-Za-z0-9_]*__c)>")


def _is_sf_object(name: str) -> bool:
    return name.endswith("__c") or name in _STANDARD_OBJECTS


def extract_apex_object_access(cls_path: Path, comp_api: str) -> list[dict]:
    """Apexクラスから object_access エントリを抽出する。"""
    try:
        content = cls_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []

    # 変数名 → オブジェクト型のマッピング（__c カスタム + 主要標準オブジェクト）
    var_types: dict[str, str] = {}
    for m in _RE_VAR_TYPE.finditer(content):
        var_types[m.group(2)] = m.group(1)
    for m in _RE_STD_VAR.finditer(content):
        var_types[m.group(2)] = m.group(1)
    for m in _RE_LIST_TYPE.finditer(content):
        var_types[m.group(2)] = m.group(1)

    # トリガーハンドラー: Map/List 型からプライマリオブジェクトを特定
    trigger_obj: str | None = None
    for pat in (_RE_TRG_MAP, _RE_TRG_LIST):
        m = pat.search(content)
        if m:
            trigger_obj = m.group(1)
            break

    access: dict[str, str] = {}  # {obj_api: operation}

    # SOQL → R
    for m in _RE_SOQL_FROM.finditer(content):
        obj = m.group(1)
        if _is_sf_object(obj) and obj not in access:
            access[obj] = "R"

    # new ObjName__c(...) → INSERT 候補
    insert_candidate: set[str] = set()
    for m in _RE_NEW_OBJ.finditer(content):
        insert_candidate.add(m.group(1))

    # insert var → INSERT
    for m in _RE_DML_INSERT.finditer(content):
        var = m.group(1)
        # 直接型: insert new ObjName__c(...)
        if var in var_types:
            access[var_types[var]] = "INSERT"
        # トリガー context: insert trigger.new は INSERT
        elif trigger_obj and var.lower() in ("trigger", "newlist", "new"):
            access[trigger_obj] = "INSERT"

    # new ObjName__c かつ insert がある → INSERT
    for obj in insert_candidate:
        # Apexファイル内に insert キーワードがあれば INSERT
        if re.search(r"\binsert\b", content, re.I):
            if obj not in access or access[obj] == "R":
                access[obj] = "INSERT"

    # update / upsert var → W（既に INSERT 判定されていれば上書きしない）
    for pat in (_RE_DML_UPDATE, _RE_DML_UPSERT):
        for m in pat.finditer(content):
            var = m.group(1)
            obj = var_types.get(var)
            if obj and access.get(obj) not in ("INSERT",):
                access[obj] = "W"

    # トリガーハンドラー: プロパティアクセスフィールドを持つ場合 Trigger.new → INSERT
    if trigger_obj and trigger_obj not in access:
        if re.search(r"trigger\.new|trigger\.newList|newList", content, re.I):
            access[trigger_obj] = "INSERT"

    return [
        {"component": comp_api, "object": obj, "operation": op}
        for obj, op in access.items()
        if _is_sf_object(obj)
    ]


# ── Flow XML object_access 抽出 ────────────────────────────────────────────────
def extract_flow_apex_callees(flow_path: Path) -> list[str]:
    """Flow XMLから @InvocableMethod 呼び出し先 Apex クラスを抽出する。"""
    try:
        content = flow_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []
    # <actionCalls>/<apexClass> または <actionType>Apex の <actionName>
    callees: list[str] = []
    for block in re.findall(r"<actionCalls>(.*?)</actionCalls>", content, re.DOTALL):
        m = re.search(r"<apexClass>([A-Za-z0-9_]+)</apexClass>", block)
        if not m:
            m = re.search(r"<actionName>([A-Za-z0-9_]+)</actionName>", block)
        if m and m.group(1) not in callees:
            callees.append(m.group(1))
    return callees


def extract_flow_object_access(flow_path: Path, comp_api: str) -> list[dict]:
    """Flow XMLから object_access エントリを抽出する。"""
    try:
        content = flow_path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return []

    _OP_MAP = {
        "recordLookups":  "R",
        "recordCreates":  "INSERT",
        "recordUpdates":  "W",
        "recordDeletes":  "W",
    }
    access: dict[str, str] = {}
    for tag, op in _OP_MAP.items():
        for block in re.findall(rf"<{tag}>(.*?)</{tag}>", content, re.DOTALL):
            m = re.search(r"<object>([A-Za-z0-9_]+)</object>", block)
            if m:
                obj = m.group(1)
                if _is_sf_object(obj):
                    # 優先順位: INSERT > W > R
                    prev = access.get(obj)
                    if prev is None:
                        access[obj] = op
                    elif op == "INSERT" and prev != "INSERT":
                        access[obj] = "INSERT"
                    elif op == "W" and prev == "R":
                        access[obj] = "W"

    return [
        {"component": comp_api, "object": obj, "operation": op}
        for obj, op in access.items()
    ]


# ── objectTranslations ラベル ──────────────────────────────────────────────────
def load_obj_labels(project_dir: Path) -> tuple[dict[str, str], dict[str, str]]:
    """objectTranslations から {obj_api: label} と {obj_api: {field_api: label}} を返す。"""
    obj_labels: dict[str, str] = {}
    field_labels: dict[str, dict[str, str]] = {}
    trans_dir = project_dir / "force-app/main/default/objectTranslations"
    if not trans_dir.exists():
        return obj_labels, {}
    for obj_dir in trans_dir.iterdir():
        if not obj_dir.name.endswith("-ja"):
            continue
        obj_api = obj_dir.name[:-3]
        obj_trans = obj_dir / f"{obj_dir.name}.objectTranslation-meta.xml"
        if obj_trans.exists():
            c = obj_trans.read_text(encoding="utf-8", errors="ignore")
            m = re.search(r"<value>([^<]+)</value>", c)
            if m:
                obj_labels[obj_api] = m.group(1).strip()
        for fxml in obj_dir.glob("*.fieldTranslation-meta.xml"):
            field_api = fxml.name.replace(".fieldTranslation-meta.xml", "")
            c = fxml.read_text(encoding="utf-8", errors="ignore")
            m = re.search(r"<label><!--\s*(.*?)\s*--></label>", c)
            if m and m.group(1):
                field_labels.setdefault(obj_api, {})[field_api] = m.group(1).strip()
    return obj_labels, field_labels


# ── ソースファイル検索 ──────────────────────────────────────────────────────────
_FLOW_TYPES  = {"flow", "画面フロー", "screenflow", "autolaunched", "autolaunchedflow"}
_APEX_TYPES  = {"apex", "batch", "trigger_handler", "apex_test"}
_LWC_TYPES   = {"lwc", "aura"}

def find_source_file(api_name: str, ftype: str, project_dir: Path) -> Path | None:
    base = project_dir / "force-app/main/default"
    candidates = []
    ft = ftype.lower().replace(" ", "")
    if ft in _LWC_TYPES:
        candidates = [
            base / ft / api_name / f"{api_name}.js",
            base / "lwc" / api_name / f"{api_name}.js",
        ]
    elif ft in _APEX_TYPES:
        candidates = [base / "classes" / f"{api_name}.cls"]
    elif ft == "trigger":
        candidates = [base / "triggers" / f"{api_name}.trigger-meta.xml",
                      base / "triggers" / f"{api_name}.trigger"]
    elif ft in _FLOW_TYPES or ft.startswith("flow") or ft.endswith("フロー"):
        candidates = [base / "flows" / f"{api_name}.flow-meta.xml"]
    for p in candidates:
        if p.exists():
            return p
    return None


# ── YAML ロード ─────────────────────────────────────────────────────────────────
def _load_yaml(path: Path) -> dict | list:
    if not _HAS_YAML:
        raise RuntimeError("PyYAML が必要です: pip install pyyaml")
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


# ── メイン処理 ─────────────────────────────────────────────────────────────────
def build_json(
    group_id: str,
    project_dir: Path,
    groups_yml: Path,
    ids_yml: Path,
    existing_json: dict | None = None,
    project_name: str = "",
) -> dict:
    # 1. feature_groups.yml からグループ定義を取得
    groups_data = _load_yaml(groups_yml)
    groups = groups_data.get("groups", []) if isinstance(groups_data, dict) else groups_data
    group = next((g for g in groups if g.get("group_id") == group_id), None)
    if not group:
        raise ValueError(f"group_id '{group_id}' が feature_groups.yml に見つかりません")

    # 2. feature_ids.yml から feature_id → {type, api_name} のマップ
    ids_data = _load_yaml(ids_yml)
    features_raw = ids_data.get("features", []) if isinstance(ids_data, dict) else []
    id_map: dict[str, dict] = {f["id"]: f for f in features_raw if "id" in f}

    # 3. このグループのfeature一覧を解決
    fids = group.get("feature_ids", [])
    group_features = []
    for fid in fids:
        clean_fid = fid.strip().split("#")[0].strip()  # コメント除去
        if clean_fid in id_map:
            entry = id_map[clean_fid]
            if not entry.get("deprecated", False):
                group_features.append(entry)

    # 4. objectTranslations ラベル
    obj_labels, _ = load_obj_labels(project_dir)

    # 5. 各コンポーネントの callees + object_access を抽出
    components: list[dict] = []
    all_object_access: list[dict] = []
    existing_comp_map: dict[str, dict] = {}
    if existing_json:
        for c in existing_json.get("components", []):
            existing_comp_map[c.get("api_name", "")] = c

    for feat in group_features:
        api_name = feat.get("api_name", "")
        ftype    = feat.get("type", "Apex")
        if not api_name:
            continue

        src = find_source_file(api_name, ftype, project_dir)

        # callees 抽出
        callees: list[str] = []
        obj_access: list[dict] = []

        ft = ftype.lower().replace(" ", "")
        if ft in _LWC_TYPES and src:
            callees = extract_lwc_callees(src)
        elif ft in _APEX_TYPES and src:
            obj_access = extract_apex_object_access(src, api_name)
        elif ft == "trigger" and src:
            obj_access = extract_apex_object_access(src, api_name)
        elif (ft in _FLOW_TYPES or ft.startswith("flow") or ft.endswith("フロー")) and src:
            obj_access = extract_flow_object_access(src, api_name)
            callees    = extract_flow_apex_callees(src)

        all_object_access.extend(obj_access)

        # role は既存JSONから保持、なければプレースホルダー
        prev = existing_comp_map.get(api_name, {})
        role = prev.get("role") or f"（{ftype}: 役割を記入してください）"

        components.append({
            "api_name": api_name,
            "type":     ftype,
            "role":     role,
            "callees":  callees,
        })

    # 6. object_access の重複整理（同コンポーネント×同オブジェクトは優先度: INSERT>W>R）
    _prio = {"INSERT": 3, "W": 2, "RW": 2, "R": 1}
    merged_access: dict[tuple[str, str], str] = {}
    for entry in all_object_access:
        key = (entry["component"], entry["object"])
        cur = merged_access.get(key)
        new_op = entry["operation"]
        if cur is None or _prio.get(new_op, 0) > _prio.get(cur, 0):
            merged_access[key] = new_op
    object_access = [
        {"component": comp, "object": obj, "operation": op}
        for (comp, obj), op in sorted(merged_access.items())
    ]

    # 7. related_objects: object_access 登場オブジェクトをユニーク収集
    seen_objs: list[str] = []
    for entry in object_access:
        if entry["object"] not in seen_objs:
            seen_objs.append(entry["object"])
    related_objects = []
    for obj_api in seen_objs:
        label = obj_labels.get(obj_api, obj_api)
        # 既存JSONのfields/relationsを保持
        prev_obj = {}
        if existing_json:
            prev_obj = next(
                (o for o in existing_json.get("related_objects", [])
                 if o.get("api_name") == obj_api), {}
            )
        related_objects.append({
            "api_name":  obj_api,
            "label":     label,
            "fields":    prev_obj.get("fields", []),
            "relations": prev_obj.get("relations", []),
        })

    # 8. impact
    lwc_comps  = [c["api_name"] for c in components if c["type"] in ("LWC", "Aura")]
    apex_comps = [c["api_name"] for c in components if c["type"] in ("Apex", "Batch")]
    flow_comps = [c["api_name"] for c in components if c["type"] == "Flow"]
    insert_objs = [e["object"] for e in object_access if e["operation"] == "INSERT"]
    write_objs  = [e["object"] for e in object_access if e["operation"] in ("W", "RW")]
    read_objs   = [e["object"] for e in object_access if e["operation"] == "R"]
    update_objs = list(dict.fromkeys(insert_objs + write_objs))

    # 9. 業務記述は既存JSONから保持（なければプレースホルダー）
    ex = existing_json or {}
    result = {
        "feature_id":   group_id,
        "name_ja":      group.get("name_ja", ""),
        "project_name": project_name or ex.get("project_name", ""),
        "author":       ex.get("author", ""),
        "date":         ex.get("date", str(date.today())),

        "summary":        ex.get("summary", "（機能の概要を記入してください）"),
        "purpose":        ex.get("purpose", "（目的を記入してください）"),
        "users":          ex.get("users", "（利用者・利用部門を記入してください）"),
        "trigger_screen": ex.get("trigger_screen", "（起点画面を記入してください）"),
        "trigger":        ex.get("trigger", "（操作トリガーを記入してください）"),

        "business_flow":  ex.get("business_flow", []),
        "related_objects": related_objects,
        "process_steps":  ex.get("process_steps", []),
        "components":     components,

        "impact": {
            "update_objects":       update_objs,
            "reference_objects":    list(dict.fromkeys(read_objs)),
            "related_apex":         apex_comps,
            "related_flow":         flow_comps,
            "related_lwc":          lwc_comps,
            "external_integrations": ex.get("impact", {}).get("external_integrations", []),
            "feature_dependencies":  ex.get("impact", {}).get("feature_dependencies", []),
        },
        "object_access": object_access,
    }
    return result


def main():
    parser = argparse.ArgumentParser(description="feature_groups.yml + 実コード → 詳細設計JSON")
    parser.add_argument("--group-id",    required=True,  help="FG-001 など")
    parser.add_argument("--project-dir", required=True,  help="SF プロジェクトルート")
    parser.add_argument("--groups-yml",  required=True,  help="feature_groups.yml のパス")
    parser.add_argument("--ids-yml",     required=True,  help="feature_ids.yml のパス")
    parser.add_argument("--output",       required=True,  help="出力JSONパス")
    parser.add_argument("--project-name", default="",     help="プロジェクト名（省略時は既存JSONの値を保持）")
    args = parser.parse_args()

    project_dir = Path(args.project_dir)
    out_path    = Path(args.output)

    # 既存JSONがあれば読み込み（業務記述を保持するため）
    existing_json = None
    if out_path.exists():
        try:
            existing_json = json.loads(out_path.read_text(encoding="utf-8"))
            print(f"既存JSON読み込み: {out_path.name}（業務記述を保持）")
        except Exception as e:
            print(f"警告: 既存JSON読み込み失敗 ({e})", file=sys.stderr)

    result = build_json(
        group_id      = args.group_id,
        project_dir   = project_dir,
        groups_yml    = Path(args.groups_yml),
        ids_yml       = Path(args.ids_yml),
        existing_json = existing_json,
        project_name  = args.project_name,
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[OK] {args.group_id} → {out_path}")
    print(f"  components: {len(result['components'])}件")
    print(f"  object_access: {len(result['object_access'])}件")
    print(f"  related_objects: {len(result['related_objects'])}件")


if __name__ == "__main__":
    main()
