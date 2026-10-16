# -*- coding: utf-8 -*-
"""カスタム項目の利用箇所取得（MetadataComponentDependency）"""

import urllib.parse
from collections import defaultdict

# 表示するコンポーネントタイプ（不要なノイズを除外）
_INCLUDE_TYPES = {
    "Layout",
    "Flow",
    "FlowDefinition",
    "ApexClass",
    "ApexTrigger",
    "ValidationRule",
    "WorkflowRule",
    "CustomReport",
    "ReportType",
    "EmailTemplate",
    "QuickAction",
    "CompactLayout",
    "FieldSet",
    "LightningComponentBundle",
    "AuraDefinitionBundle",
    "FlexiPage",
}

# 表示名の整形マップ
_TYPE_LABEL = {
    "Layout":                   "レイアウト",
    "Flow":                     "フロー",
    "FlowDefinition":           "フロー",
    "ApexClass":                "Apex",
    "ApexTrigger":              "Apexトリガー",
    "ValidationRule":           "入力規則",
    "WorkflowRule":             "ワークフロー",
    "CustomReport":             "レポート",
    "ReportType":               "レポートタイプ",
    "EmailTemplate":            "メールテンプレート",
    "QuickAction":              "クイックアクション",
    "CompactLayout":            "コンパクトレイアウト",
    "FieldSet":                 "項目セット",
    "LightningComponentBundle": "LWC",
    "AuraDefinitionBundle":     "Aura",
    "FlexiPage":                "Lightningページ",
}


def fetch_field_usage(sf, obj_api_name: str) -> dict[str, str]:
    """
    指定オブジェクトのカスタム項目利用箇所を一括取得する。

    Returns:
        {field_api_name: "利用箇所の文字列"} の辞書
        例: {"CustomerPriority__c": "レイアウト: 取引先, フロー: 顧客ランク判定"}
    """
    # Step1: カスタム項目 Id → API名 マッピング
    q1 = (f"SELECT Id, DeveloperName FROM CustomField "
          f"WHERE EntityDefinition.QualifiedApiName = '{obj_api_name}'")
    r1 = sf.restful(f"tooling/query?q={urllib.parse.quote(q1, safe='')}")

    id_to_api: dict[str, str] = {
        r["Id"]: f"{r['DeveloperName']}__c"
        for r in r1.get("records", [])
    }
    if not id_to_api:
        return {}

    # Step2: MetadataComponentDependency 一括取得（200件チャンクで URL 長超過を回避）
    _CHUNK = 200
    ids = list(id_to_api.keys())
    all_records: list[dict] = []
    for i in range(0, len(ids), _CHUNK):
        id_list = "','".join(ids[i:i + _CHUNK])
        q2 = (f"SELECT MetadataComponentName, MetadataComponentType, RefMetadataComponentId "
              f"FROM MetadataComponentDependency "
              f"WHERE RefMetadataComponentId IN ('{id_list}')")
        r2 = sf.restful(f"tooling/query?q={urllib.parse.quote(q2, safe='')}")
        all_records.extend(r2.get("records", []))

    # Step3: api_name → 利用箇所リスト にまとめる
    usage_map: dict[str, list[str]] = defaultdict(list)
    for r in all_records:
        comp_type = r.get("MetadataComponentType", "")
        if comp_type not in _INCLUDE_TYPES:
            continue
        api_name = id_to_api.get(r["RefMetadataComponentId"])
        if not api_name:
            continue
        label = _TYPE_LABEL.get(comp_type, comp_type)
        name  = r.get("MetadataComponentName", "")
        entry = f"{label}: {name}"
        if entry not in usage_map[api_name]:
            usage_map[api_name].append(entry)

    # Step4: リストを改行区切りの文字列に変換
    return {
        api: "\n".join(sorted(items))
        for api, items in usage_map.items()
    }
