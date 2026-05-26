# -*- coding: utf-8 -*-
"""Salesforce メタデータ取得"""

import sys
from typing import Any
from connector import SalesforceConnector
from dependency import fetch_field_usage


class MetadataFetcher:
    """Salesforce から各種メタデータを取得するクラス"""

    def __init__(self, connector: SalesforceConnector):
        self._conn = connector

    @property
    def _sf(self):
        return self._conn.sf

    # ------------------------------------------------------------------ #
    # 公開メソッド
    # ------------------------------------------------------------------ #

    def fetch_all(self, object_api_name: str, sections: dict,
                  verbose: bool = False) -> dict[str, Any]:
        """指定オブジェクトの全メタデータをまとめて返す"""
        result: dict[str, Any] = {"object_api_name": object_api_name}

        describe = self._describe_object(object_api_name)
        result["describe"] = describe

        fetches = [
            ("fields",           lambda: self._fetch_fields(describe)),
            ("object_info",      lambda: self._fetch_object_info(describe)),
            ("record_types",     lambda: self._fetch_record_types(object_api_name)),
            ("page_layouts",     lambda: self._fetch_page_layouts(object_api_name)),
            ("lightning_pages",  lambda: self._fetch_lightning_pages(object_api_name)),
            ("compact_layouts",  lambda: self._fetch_compact_layouts(object_api_name)),
            ("search_layouts",   lambda: self._fetch_search_layouts(object_api_name)),
            ("field_sets",       lambda: self._fetch_field_sets(object_api_name)),
            ("validation_rules", lambda: self._fetch_validation_rules(object_api_name)),
            ("lookup_filters",   lambda: self._fetch_lookup_filters(describe)),
        ]

        for section_key, fetch_fn in fetches:
            if sections.get(section_key, True):
                data = fetch_fn()
                result[section_key] = data
                if verbose:
                    count = len(data) if isinstance(data, list) else "—"
                    print(f"    {section_key}: {count} 件")

        # EntityDefinition からオブジェクト設定フラグを object_info にマージ
        if "object_info" in result:
            extra = self._fetch_entity_definition(object_api_name)
            for k, v in extra.items():
                if v is not None:
                    result["object_info"][k] = v

        # カスタム項目の利用箇所取得（sections で field_usage が true の場合）
        if sections.get("field_usage", True):
            result["field_usage"] = fetch_field_usage(self._sf, object_api_name)
            if verbose:
                print(f"    field_usage: {len(result['field_usage'])} 件")

        return result

    # ------------------------------------------------------------------ #
    # 内部ヘルパー
    # ------------------------------------------------------------------ #

    def _describe_object(self, api_name: str) -> dict:
        obj = getattr(self._sf, api_name)
        return obj.describe()

    def _tooling_query(self, soql: str) -> list:
        """Tooling API 経由で SOQL を実行する（ページネーション対応）"""
        try:
            result  = self._sf.restful("tooling/query/", params={"q": soql})
            records = result.get("records", [])
            while result.get("nextRecordsUrl"):
                path   = result["nextRecordsUrl"].split("/services/data/", 1)[-1]
                result = self._sf.restful(path)
                records.extend(result.get("records", []))
            return records
        except Exception as e:
            print(f"  [WARN Tooling API] {e} | SQL: {soql[:80]}")
            return []

    # ------------------------------------------------------------------ #
    # 各セクション取得
    # ------------------------------------------------------------------ #

    def _fetch_fields(self, describe: dict) -> list[dict]:
        rows = []
        for f in describe.get("fields", []):
            rows.append({
                "api_name":       f.get("name", ""),
                "label":          f.get("label", ""),
                "custom":         f.get("custom", False),
                "data_type":      f.get("type", ""),
                "length":         f.get("length") or f.get("precision") or "",
                "scale":          f.get("scale", ""),
                "required":       not f.get("nillable", True),
                "unique":         f.get("unique", False),
                "external_id":    f.get("externalId", False),
                "formula":        f.get("calculatedFormula", ""),
                "default_value":  f.get("defaultValue", ""),
                "picklist_values": [v["value"] for v in f.get("picklistValues", [])
                                    if v.get("active")],
                "reference_to":   f.get("referenceTo", []),
                "help_text":      f.get("inlineHelpText", ""),
                "description":    f.get("description", ""),
                "creatable":      f.get("createable", False),
                "updatable":      f.get("updateable", False),
            })
        return rows

    def _fetch_object_info(self, describe: dict) -> dict:
        return {
            # 基本情報
            "label":         describe.get("label", ""),
            "label_plural":  describe.get("labelPlural", ""),
            "api_name":      describe.get("name", ""),
            "key_prefix":    describe.get("keyPrefix", ""),
            "custom":        describe.get("custom", False),
            # describe から確実に取得できる機能フラグ
            "feed_enabled":  describe.get("feedEnabled", False),   # Chatterフィード
            "searchable":    describe.get("searchable", False),    # 検索を許可
            "bulk_api":      describe.get("replicateable", False), # BulkAPIアクセスを許可
            # EntityDefinition で補完（カスタムオブジェクトのみ）
            "track_history":     None,
            "sharing_model":     None,
            "deployment_status": None,
        }

    def _fetch_record_types(self, api_name: str) -> list[dict]:
        try:
            result = self._sf.query(
                f"SELECT Id, Name, DeveloperName, Description, IsActive "
                f"FROM RecordType WHERE SobjectType = '{api_name}'"
            )
            rows = []
            for r in result.get("records", []):
                rows.append({
                    "id":             r.get("Id", ""),
                    "name":           r.get("Name", ""),
                    "developer_name": r.get("DeveloperName", ""),
                    "description":    r.get("Description", ""),
                    "is_active":      r.get("IsActive", False),
                })
            return rows
        except Exception as e:
            print(f"[WARN] _fetch_record_types({api_name}): {e}", file=sys.stderr)
            return []

    def _fetch_page_layouts(self, api_name: str) -> list[dict]:
        # レイアウト一覧
        layouts = self._tooling_query(
            f"SELECT Id, Name FROM Layout "
            f"WHERE EntityDefinition.QualifiedApiName = '{api_name}'"
        )
        # 承認ページレイアウトを除外（名前に承認プロセスID "04a" が含まれる）
        layout_map = {r["Id"]: r["Name"] for r in layouts
                      if " 04a" not in r.get("Name", "")}

        # プロファイル割り当て（LayoutId IN (...) でフィルター）
        if layout_map:
            ids_str = ", ".join(f"'{lid}'" for lid in layout_map.keys())
            assignments = self._tooling_query(
                f"SELECT Layout.Id, Layout.Name, Profile.Name, RecordType.Name "
                f"FROM ProfileLayout "
                f"WHERE LayoutId IN ({ids_str})"
            )
        else:
            assignments = []

        # レイアウト名 → {profile, record_type} リスト
        assign_map: dict[str, list] = {}
        for a in assignments:
            layout_name = (a.get("Layout") or {}).get("Name", "")
            profile     = (a.get("Profile") or {}).get("Name", "")
            rt          = (a.get("RecordType") or {}).get("Name", "（共通）")
            if layout_name not in assign_map:
                assign_map[layout_name] = []
            assign_map[layout_name].append({"profile": profile, "record_type": rt})

        result = []
        for layout_id, layout_name in layout_map.items():
            assigns = assign_map.get(layout_name, [])
            profiles = list(dict.fromkeys(a["profile"] for a in assigns))
            rts      = list(dict.fromkeys(a["record_type"] for a in assigns))
            result.append({
                "id":           layout_id,
                "name":         layout_name,
                "profiles":     "\n".join(profiles),
                "record_types": "\n".join(rts),
            })

        # 割り当て情報が取れなかった場合は基本情報だけ（フィルタ済み layout_map を使用）
        if not result:
            return [{"id": lid, "name": lname, "profiles": "", "record_types": ""}
                    for lid, lname in layout_map.items()]

        return result

    def _fetch_lightning_pages(self, api_name: str) -> list[dict]:
        records = self._tooling_query(
            f"SELECT Id, MasterLabel, DeveloperName, Type FROM FlexiPage "
            f"WHERE EntityDefinitionId = '{api_name}'"
        )
        return [
            {
                "id":             r["Id"],
                "label":          r.get("MasterLabel", ""),
                "developer_name": r.get("DeveloperName", ""),
                "type":           r.get("Type", ""),
            }
            for r in records
        ]

    def _fetch_compact_layouts(self, api_name: str) -> list[dict]:
        try:
            resp = self._sf.restful(f"sobjects/{api_name}/describe/compactLayouts")
            layouts = resp.get("compactLayouts", [])
            return [
                {
                    "id":     cl.get("id", ""),
                    "name":   cl.get("name", ""),
                    "label":  cl.get("label", ""),
                    "fields": [f.get("label", "") for f in cl.get("fields", [])],
                }
                for cl in layouts
            ]
        except Exception as e:
            print(f"[WARN] _fetch_compact_layouts({api_name}): {e}", file=sys.stderr)
            return []

    def _fetch_search_layouts(self, api_name: str) -> list[dict]:
        try:
            resp = self._sf.restful(f"sobjects/{api_name}/describe/searchLayouts")
            if isinstance(resp, list):
                return resp
            return [resp] if resp else []
        except Exception:
            return []

    def _fetch_field_sets(self, api_name: str) -> list[dict]:
        records = self._tooling_query(
            f"SELECT Id, DeveloperName, MasterLabel, Description FROM FieldSet "
            f"WHERE EntityDefinition.QualifiedApiName = '{api_name}'"
        )
        return [
            {
                "id":             r["Id"],
                "developer_name": r.get("DeveloperName", ""),
                "label":          r.get("MasterLabel", ""),
                "description":    r.get("Description", ""),
            }
            for r in records
        ]

    def _fetch_validation_rules(self, api_name: str) -> list[dict]:
        id_records = self._tooling_query(
            f"SELECT Id FROM ValidationRule "
            f"WHERE EntityDefinition.QualifiedApiName = '{api_name}'"
        )
        records = []
        for r in id_records:
            detail = self._tooling_query(
                f"SELECT Id, ValidationName, Active, Description, "
                f"ErrorMessage, ErrorDisplayField, Metadata "
                f"FROM ValidationRule WHERE Id = '{r['Id']}'"
            )
            if detail:
                records.append(detail[0])
        return [
            {
                "id":                 r["Id"],
                "name":               r.get("ValidationName", ""),
                "active":             r.get("Active", False),
                "description":        r.get("Description", ""),
                "condition_formula":  (r.get("Metadata") or {}).get("errorConditionFormula", ""),
                "error_message":      r.get("ErrorMessage", ""),
                "error_display_field": r.get("ErrorDisplayField", ""),
            }
            for r in records
        ]

    def _fetch_entity_definition(self, api_name: str) -> dict:
        """EntityDefinition からオブジェクト設定を取得"""
        records = self._tooling_query(
            f"SELECT IsFieldHistoryTracked, InternalSharingModel, DeploymentStatus "
            f"FROM EntityDefinition WHERE QualifiedApiName = '{api_name}'"
        )
        if not records:
            return {}
        r = records[0]
        return {
            "track_history":     r.get("IsFieldHistoryTracked"),
            "sharing_model":     r.get("InternalSharingModel") or "",
            "deployment_status": r.get("DeploymentStatus") or "",
        }

    def _fetch_lookup_filters(self, describe: dict) -> list[dict]:
        filters = []
        for f in describe.get("fields", []):
            lf = f.get("filteredLookupInfo")
            if lf:
                filters.append({
                    "field_api_name":    f.get("name", ""),
                    "field_label":       f.get("label", ""),
                    "controlling_fields": lf.get("controllingFields", []),
                    "dependent":         lf.get("dependent", False),
                    "optional_filter":   lf.get("optionalFilter", False),
                })
        return filters
